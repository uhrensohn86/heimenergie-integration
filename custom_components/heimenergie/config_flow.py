"""UI-only configuration: select a physical meter, then assign its measured load.

A rename keeps the consumer's history. A *confirmed* plug/load switch creates
an independent meter session. No personal names or entity IDs are in the code.
"""
from __future__ import annotations

from uuid import uuid4

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import selector

from .const import (
    DOMAIN, CONF_DEVICES, CONF_POWER_ENTITIES, CONF_PRICE_ENTITY,
    CONF_PRICE_FIXED, CONF_BASE_MONTHLY, CONF_EDIT_CONSUMERS,
    CONF_CONSUMER_DEVICE, CONF_CONSUMER_NAME, CONF_CONSUMER_TYPE,
    CONF_NEW_SESSION,
)
from .discovery import device_selection, rebind_consumer

CONSUMER_TYPES = (
    {"value": "other", "label": "Sonstiges"},
    {"value": "fridge", "label": "Kühlschrank"},
    {"value": "washing_machine", "label": "Waschmaschine"},
    {"value": "dishwasher", "label": "Geschirrspüler"},
    {"value": "server", "label": "Server / Netzwerk"},
    {"value": "vacuum", "label": "Staubsauger"},
    {"value": "printer", "label": "Drucker / 3D-Drucker"},
    {"value": "television", "label": "TV / Unterhaltung"},
)


def schema(data: dict | None = None):
    """First select measuring hardware and tariff – no helper or YAML setup."""
    data = data or {}
    entity_price = {}
    if data.get(CONF_PRICE_ENTITY):
        entity_price[vol.Optional(CONF_PRICE_ENTITY, default=data[CONF_PRICE_ENTITY])] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["sensor", "input_number"]))
    else:
        entity_price[vol.Optional(CONF_PRICE_ENTITY)] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["sensor", "input_number"]))
    return vol.Schema({
        vol.Optional(CONF_DEVICES, default=data.get(CONF_DEVICES, [])):
            selector.DeviceSelector(selector.DeviceSelectorConfig(multiple=True)),
        vol.Optional(CONF_POWER_ENTITIES, default=data.get(CONF_POWER_ENTITIES, [])):
            selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor", multiple=True)),
        **entity_price,
        vol.Required(CONF_PRICE_FIXED, default=data.get(CONF_PRICE_FIXED, 0.0)):
            selector.NumberSelector(selector.NumberSelectorConfig(
                min=0, max=10, step="any", mode=selector.NumberSelectorMode.BOX)),
        vol.Required(CONF_BASE_MONTHLY, default=data.get(CONF_BASE_MONTHLY, 0.0)):
            selector.NumberSelector(selector.NumberSelectorConfig(
                min=0, max=1000, step=0.01, mode=selector.NumberSelectorMode.BOX)),
        vol.Optional(CONF_EDIT_CONSUMERS, default=False):
            selector.BooleanSelector(),
    })


def consumer_schema(previous: dict | None = None):
    """Only shown for newly selected meters or on explicit reassignment."""
    previous = previous or {}
    fields = {
        vol.Optional(CONF_CONSUMER_NAME, default=previous.get("name", "")):
            selector.TextSelector(selector.TextSelectorConfig()),
        vol.Optional(CONF_CONSUMER_TYPE, default=previous.get("consumer_type", "other")):
            selector.SelectSelector(selector.SelectSelectorConfig(
                options=list(CONSUMER_TYPES), mode=selector.SelectSelectorMode.DROPDOWN)),
        vol.Required(CONF_NEW_SESSION, default=False): selector.BooleanSelector(),
    }
    if previous.get("consumer_device_id"):
        fields[vol.Optional(CONF_CONSUMER_DEVICE, default=previous["consumer_device_id"])] = (
            selector.DeviceSelector(selector.DeviceSelectorConfig()))
    else:
        fields[vol.Optional(CONF_CONSUMER_DEVICE)] = (
            selector.DeviceSelector(selector.DeviceSelectorConfig()))
    return vol.Schema(fields)


def resolve(hass, supplied):
    return device_selection(hass, supplied.get(CONF_DEVICES, []),
                            supplied.get(CONF_POWER_ENTITIES, []))


def assigned_consumer(hass, meter: dict, previous: dict | None, supplied: dict):
    """Bind consumer identity to the measurement, never to its display name.

    Legacy integrations used the power entity ID as tracker storage key. That
    key MUST survive a simple rename/migration or old counters will disappear.
    Starting a new measurement session explicitly creates a new key, prevents
    reusing full-day/month counters from the old load and retains old snapshots.
    """
    previous = previous or {}
    name_input = str(supplied.get(CONF_CONSUMER_NAME, "") or "").strip()
    consumer_device = str(supplied.get(CONF_CONSUMER_DEVICE, "") or "")
    old_device = str(previous.get("consumer_device_id", "") or "")
    devreg = dr.async_get(hass)
    chosen = devreg.async_get(consumer_device) if consumer_device else None
    if consumer_device and not chosen:
        raise ValueError("unknown_consumer_device")
    # If user just selected an HA consumer device, do not accidentally keep
    # the prefilled technical meter name from a legacy record.
    unchanged_legacy_name = bool(previous) and name_input == previous.get("name", "")
    if chosen and (not name_input or (consumer_device != old_device and unchanged_legacy_name)):
        chosen_name = chosen.name_by_user or chosen.name or meter["name"]
    else:
        chosen_name = name_input or previous.get("name") or meter["name"]
    fresh = bool(supplied.get(CONF_NEW_SESSION, False))
    if previous and old_device and consumer_device != old_device:
        # Switching which HA device is measured is a new load by definition.
        fresh = True
    if (fresh or not previous) and not (name_input or chosen):
        raise ValueError("missing_consumer")
    tracker_key = (f"consumer_{uuid4().hex}" if fresh else
                   previous.get("tracker_key", previous.get("power", "")) or
                   f"consumer_{uuid4().hex}")
    # A replacement load must never inherit old full-period meter values even
    # after a later options edit (tariff change, another device added, etc.).
    isolated = fresh or bool(previous.get("isolation_mode", False))
    bound = rebind_consumer(hass, meter, chosen_name, fresh_session=isolated)
    bound.update({
        "meter_name": meter["name"],
        "consumer_device_id": consumer_device,
        "consumer_type": supplied.get(CONF_CONSUMER_TYPE, previous.get("consumer_type", "other")),
        "tracker_key": tracker_key,
        "consumer_configured": True,
        "isolation_mode": isolated,
    })
    return bound


class _ConsumerSteps:
    """Shared follow-up steps for initial config and options reconfiguration."""

    def _begin(self, supplied: dict, previous: list[dict] | None = None):
        self._supplied = {k: v for k, v in supplied.items() if k != CONF_EDIT_CONSUMERS}
        self._meters = resolve(self.hass, supplied)
        self._previous = {d["power"]: d for d in (previous or [])}
        self._edit_all = bool(supplied.get(CONF_EDIT_CONSUMERS))
        self._next_index = 0
        self._bound = []

    async def _next_consumer(self):
        while self._next_index < len(self._meters):
            meter = self._meters[self._next_index]
            old = self._previous.get(meter["power"])
            if old and old.get("consumer_configured") and not self._edit_all:
                # Re-evaluate matching using the chosen consumer name, but
                # preserve existing lifetime identity and readings.
                bound = rebind_consumer(self.hass, meter, old["name"],
                                         fresh_session=bool(old.get("isolation_mode", False)))
                for k in ("meter_name", "consumer_device_id", "consumer_type",
                          "tracker_key", "consumer_configured", "isolation_mode"):
                    if k in old:
                        bound[k] = old[k]
                self._bound.append(bound)
                self._next_index += 1
                continue
            return await self.async_step_consumer()
        return self._finish()

    async def async_step_consumer(self, user_input=None):
        meter = self._meters[self._next_index]
        old = self._previous.get(meter["power"])
        if user_input is not None:
            try:
                assigned = assigned_consumer(self.hass, meter, old, user_input)
            except ValueError as exc:
                error = str(exc)
                if error not in ("missing_consumer", "unknown_consumer_device"):
                    error = "unknown_consumer_device"
                return self.async_show_form(
                    step_id="consumer", data_schema=consumer_schema(old or {}),
                    errors={"base": error},
                    description_placeholders={"meter": meter["name"]},
                )
            self._bound.append(assigned)
            self._next_index += 1
            return await self._next_consumer()
        return self.async_show_form(
            step_id="consumer", data_schema=consumer_schema(old or {}),
            description_placeholders={"meter": meter["name"]},
        )

    def _finish(self):
        return self.async_create_entry(title=self._entry_title, data={
            **self._supplied, "resolved": self._bound,
        })


class HeimEnergyConfigFlow(_ConsumerSteps, config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    _entry_title = "HeimEnergie"

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            self._begin(user_input)
            if self._meters:
                await self.async_set_unique_id("heimenergie_main")
                self._abort_if_unique_id_configured()
                return await self._next_consumer()
            return self.async_show_form(
                step_id="user", data_schema=schema(user_input),
                errors={"base": "no_power_sensor"},
            )
        return self.async_show_form(step_id="user", data_schema=schema())

    @staticmethod
    def async_get_options_flow(config_entry):
        return HeimEnergyOptionsFlow()


class HeimEnergyOptionsFlow(_ConsumerSteps, config_entries.OptionsFlow):
    _entry_title = ""

    async def async_step_init(self, user_input=None):
        previous = {**self.config_entry.data, **self.config_entry.options}
        if user_input is not None:
            self._begin(user_input, previous.get("resolved", []))
            if self._meters:
                return await self._next_consumer()
            return self.async_show_form(
                step_id="init", data_schema=schema(user_input),
                errors={"base": "no_power_sensor"},
            )
        return self.async_show_form(step_id="init", data_schema=schema(previous))
