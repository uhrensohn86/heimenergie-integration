"""Track device energy and periods; keep all data inside the HA instance."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from collections.abc import Callable

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .maths import accumulate_power, cumulative_delta, normalize_tracker, credit
from .const import DOMAIN, PERIODS, CONF_BASE_MONTHLY, CONF_PRICE_ENTITY, CONF_PRICE_FIXED

_LOGGER = logging.getLogger(__name__)


def _numeric(hass: HomeAssistant, entity_id: str) -> float | None:
    state = hass.states.get(entity_id) if entity_id else None
    if not state or state.state in ("unavailable", "unknown", "none"):
        return None
    try:
        return float(state.state)
    except (ValueError, TypeError):
        return None


def _watts(hass: HomeAssistant, entity_id: str) -> float | None:
    value = _numeric(hass, entity_id)
    if value is None:
        return None
    unit = str(hass.states.get(entity_id).attributes.get("unit_of_measurement", "W")).lower()
    return value * 1000 if unit == "kw" else value / 1000 if unit == "mw" else value


def _kwh(hass: HomeAssistant, entity_id: str) -> float | None:
    value = _numeric(hass, entity_id)
    if value is None:
        return None
    unit = str(hass.states.get(entity_id).attributes.get("unit_of_measurement", "kWh")).lower()
    return value / 1000 if unit == "wh" else value * 1000 if unit == "mwh" else value


class HeimCoordinator:
    def __init__(self, hass: HomeAssistant, entry):
        self.hass, self.entry = hass, entry
        self.devices = list(entry.options.get("resolved", entry.data.get("resolved", [])))
        self.store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        self.trackers = {}
        self.mapping = {}
        self._listeners: set[Callable] = set()
        self._unsub = []
        self._started = False
        self._next_save_at = 0.0

    async def async_start(self) -> None:
        stored = await self.store.async_load()
        self.trackers = stored.get("trackers", {}) if isinstance(stored, dict) else {}
        now = dt_util.now()
        for dev in self.devices:
            item = normalize_tracker(self.trackers.setdefault(dev["power"], {}), now.date())
            # An HA restart never implies the previous W measurement remained
            # valid while Home Assistant was down.
            item["last_at"] = None
            item["last_power"] = None
            # Replacing the source invalidates its old cumulative baseline.
            source = dev.get("source_energy", "")
            if item.get("source_energy_id") != source:
                item["last_energy"] = None
            item["source_energy_id"] = source
        watched = {d["power"] for d in self.devices}
        watched |= {d["source_energy"] for d in self.devices if d.get("source_energy")}
        price_ent = self.options.get(CONF_PRICE_ENTITY, "")
        if price_ent:
            watched.add(price_ent)
        for dev in self.devices:
            watched |= {e for e in dev.get("reuse", {}).values() if e}
        self._unsub.append(async_track_state_change_event(self.hass, sorted(watched), self._changed))
        self._unsub.append(async_track_time_interval(self.hass, self._tick, timedelta(seconds=60)))
        self._unsub.append(self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self._on_stop))
        self._started = True
        self._sample(now)

    @property
    def options(self) -> dict:
        return {**self.entry.data, **self.entry.options}

    @callback
    def _changed(self, event) -> None:
        self._sample(dt_util.now())

    @callback
    def _tick(self, when: datetime) -> None:
        self._sample(dt_util.as_local(when))

    @callback
    def _on_stop(self, event) -> None:
        self.hass.async_create_task(self.store.async_save({"trackers": self.trackers}))

    @callback
    def _sample(self, when: datetime) -> None:
        modified = False
        for dev in self.devices:
            power_id = dev["power"]
            tracked = normalize_tracker(self.trackers.setdefault(power_id, {}), when.date())
            source = dev.get("source_energy", "")
            if source:
                current = _kwh(self.hass, source)
                if current is not None:
                    if not tracked.get("has_sample"):
                        tracked["has_sample"] = True
                        modified = True
                    previous = tracked.get("last_energy")
                    diff = cumulative_delta(previous, current)
                    credit(tracked, when.date(), diff)
                    tracked["last_energy"] = current
                    modified |= diff > 0
            else:
                power = _watts(self.hass, power_id)
                if power is not None and not tracked.get("has_sample"):
                    tracked["has_sample"] = True
                    modified = True
                previous_iso = tracked.get("last_at")
                previous_watts = tracked.get("last_power")
                if previous_iso and previous_watts is not None:
                    try:
                        start = datetime.fromisoformat(previous_iso)
                        delta = accumulate_power(tracked, start, when, previous_watts)
                        modified |= delta > 0
                    except (TypeError, ValueError, OverflowError):
                        _LOGGER.warning("Invalid stored meter timestamp for %s", power_id)
                tracked["last_at"] = when.isoformat()
                tracked["last_power"] = power
            # Date rollover can change all period sensors even without energy.
        # Schedule a small delayed write no more than once every 120s.
        # Calling Store.async_delay_save for every frequent sensor update
        # continuously postpones its write in recent HA versions.
        if modified and self.hass.loop.time() >= self._next_save_at:
            self.store.async_delay_save(lambda: {"trackers": self.trackers}, 5)
            self._next_save_at = self.hass.loop.time() + 120
        for callback_fn in tuple(self._listeners):
            callback_fn()

    @callback
    def notify(self) -> None:
        for callback_fn in tuple(self._listeners):
            callback_fn()

    def listen(self, update: Callable) -> Callable:
        self._listeners.add(update)
        return lambda: self._listeners.discard(update)

    def derived_energy(self, dev: dict, period: str) -> float:
        self.trackers.setdefault(dev["power"], {})
        tracked = normalize_tracker(self.trackers[dev["power"]], dt_util.now().date())
        return float(tracked["periods"][period]["kwh"]) if tracked.get("has_sample") else None

    def energy(self, dev: dict, period: str) -> float | None:
        existing = dev.get("reuse", {}).get("energy_" + period)
        return _kwh(self.hass, existing) if existing else self.derived_energy(dev, period)

    def price(self) -> float | None:
        price_entity = self.options.get(CONF_PRICE_ENTITY, "")
        price = _numeric(self.hass, price_entity) if price_entity else None
        if price is not None and price >= 0:
            return price
        try:
            fixed = float(self.options.get(CONF_PRICE_FIXED, 0))
            return fixed if fixed >= 0 else None
        except (TypeError, ValueError):
            return None

    def base_monthly(self) -> float:
        try:
            return max(0.0, float(self.options.get(CONF_BASE_MONTHLY, 0)))
        except (TypeError, ValueError):
            return 0.0

    def cost(self, dev: dict, period: str) -> float | None:
        existing = dev.get("reuse", {}).get("cost_" + period)
        if existing:
            return _numeric(self.hass, existing)
        energy, price = self.energy(dev, period), self.price()
        return energy * price if energy is not None and price is not None else None

    async def async_close(self) -> None:
        for unsub in self._unsub:
            unsub()
        self._unsub.clear()
        await self.store.async_save({"trackers": self.trackers})
