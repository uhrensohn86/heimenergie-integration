"""Period and cost sensors, plus an authenticated local dashboard catalog."""
from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util import dt as dt_util

from .const import DOMAIN, PERIODS, PERIOD_LABELS
from .maths import monthly_fixed_share
from .discovery import slug
from .coordinator import _watts


class HeimSensor(SensorEntity):
    _attr_should_poll = False
    _attr_has_entity_name = False

    def __init__(self, coordinator, key: str, name: str, unit: str | None,
                 calculate: Callable, device=None, kind: str = "other"):
        self.coordinator = coordinator
        self.key = key
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_{key}"
        self._attr_native_unit_of_measurement = unit
        self._calculate = calculate
        self.kind = kind
        self.device = device
        self._last_signature = None
        if kind == "energy":
            self._attr_device_class = SensorDeviceClass.ENERGY
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        elif kind == "power":
            self._attr_device_class = SensorDeviceClass.POWER
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif kind == "cost":
            self._attr_device_class = SensorDeviceClass.MONETARY
        if device is not None:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"{coordinator.entry.entry_id}_{slug(device['power'])}")},
                name=f"HeimEnergie {device['name']}",
                manufacturer="HeimEnergie",
            )

    @property
    def native_value(self):
        result = self._calculate()
        return round(result, 5) if isinstance(result, (float, int)) else result

    @property
    def extra_state_attributes(self):
        if self.kind == "catalog":
            return {
                "heimenergie_catalog_version": 1,
                "devices": self.coordinator.mapping.get("devices", []),
                "fixed": self.coordinator.mapping.get("fixed", {}),
                "price_entity": self.coordinator.options.get("price_entity", ""),
                "price_fixed": self.coordinator.options.get("price_fixed", 0),
                "base_monthly": self.coordinator.base_monthly(),
                "only_monitored_devices": True,
            }
        if self.kind == "summary":
            known = sum(self.coordinator.cost(d, self.key.rsplit("_",1)[-1]) is not None
                        for d in self.coordinator.devices) if self.key.startswith("sum_cost_") else None
            return {"device_count": len(self.coordinator.devices),
                    "known_devices": known, "only_monitored_devices": True}
        if self.kind in ("energy", "cost") and self.device:
            return {"source_power": self.device["power"],
                    "source_energy": self.device.get("source_energy") or None}
        return None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.coordinator.listen(self._updated))
        if self.key in self.coordinator.mapping.get("entity_keys", {}):
            entries = self.coordinator.mapping["entity_keys"][self.key]
            for entry in entries:
                entry[0][entry[1]] = self.entity_id
        self.coordinator.notify()

    @callback
    def _updated(self):
        # Avoid an unnecessary recorder write for every sensor on each HA
        # update; keep the dashboard catalog current when mapping changes.
        signature = (self.native_value, repr(self.extra_state_attributes))
        if signature != self._last_signature:
            self._last_signature = signature
            self.async_write_ha_state()


def _sum_known(items):
    values = [v for v in items if v is not None]
    return sum(values) if values else None


async def async_setup_entry(hass, entry, async_add_entities):
    co = hass.data[DOMAIN][entry.entry_id]
    entities = []
    catalog = HeimSensor(co, "catalog", "HeimEnergie Katalog", None,
                         lambda: len(co.devices), kind="catalog")
    entities.append(catalog)
    co.mapping = {"devices": [], "fixed": {}, "entity_keys": {}}

    def register(key, target, field):
        co.mapping["entity_keys"].setdefault(key, []).append((target, field))

    for d in co.devices:
        row = {"name": d["name"], "power": d["power"]}
        co.mapping["devices"].append(row)
        for period in PERIODS:
            for kind in ("energy", "cost"):
                field = f"{kind}_{period}"
                existing = d.get("reuse", {}).get(field)
                if existing:
                    row[field] = existing
                    continue
                key = f"device_{slug(d['power'])}_{field}"
                name = f"HeimEnergie {d['name']} {PERIOD_LABELS[period]} {'Energie' if kind=='energy' else 'Kosten'}"
                if kind == "energy":
                    calculate = (lambda device=d, period=period: co.derived_energy(device, period))
                    unit = "kWh"
                else:
                    calculate = (lambda device=d, period=period: co.cost(device, period))
                    unit = "€"
                entities.append(HeimSensor(co, key, name, unit, calculate, device=d, kind=kind))
                register(key, row, field)

    entities.append(HeimSensor(
        co, "total_power", "HeimEnergie Gesamtleistung überwachte Geräte", "W",
        lambda: _sum_known([_watts(hass, d["power"]) for d in co.devices]), kind="power"))

    for period in PERIODS:
        short = PERIOD_LABELS[period]
        energy_key = f"sum_energy_{period}"
        cost_key = f"sum_cost_{period}"
        base_key = f"base_{period}"
        billed_key = f"monitored_plus_base_{period}"
        def base(p=period):
            return monthly_fixed_share(dt_util.now().date(), p, co.base_monthly())
        entities.append(HeimSensor(co, energy_key, f"HeimEnergie erfasste Energie {short}", "kWh",
                lambda p=period: _sum_known([co.energy(d, p) for d in co.devices]), kind="summary"))
        entities.append(HeimSensor(co, cost_key, f"HeimEnergie erfasste Verbrauchskosten {short}", "€",
                lambda p=period: _sum_known([co.cost(d, p) for d in co.devices]), kind="summary"))
        entities.append(HeimSensor(co, base_key, f"HeimEnergie Grundpreis {short}", "€", base, kind="cost"))
        entities.append(HeimSensor(co, billed_key, f"HeimEnergie erfasste Kosten inkl Grundpreis {short}", "€",
                lambda p=period: (lambda s: s + monthly_fixed_share(dt_util.now().date(), p, co.base_monthly())
                      if s is not None else None)(_sum_known([co.cost(d, p) for d in co.devices])),
                kind="cost"))
        register(base_key, co.mapping["fixed"], f"base_{period}")
        register(billed_key, co.mapping["fixed"], f"cost_incl_base_{period}")
        register(energy_key, co.mapping["fixed"], f"total_energy_{period}")
        register(cost_key, co.mapping["fixed"], f"total_cost_{period}")
    async_add_entities(entities)
