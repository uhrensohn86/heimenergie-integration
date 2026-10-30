"""One UI flow selects devices and tariff, no YAML or helper configuration."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    DOMAIN, CONF_DEVICES, CONF_POWER_ENTITIES, CONF_PRICE_ENTITY,
    CONF_PRICE_FIXED, CONF_BASE_MONTHLY,
)
from .discovery import device_selection


def schema(data: dict | None = None):
    data = data or {}
    entity_price = {}
    if data.get(CONF_PRICE_ENTITY):
        entity_price[vol.Optional(CONF_PRICE_ENTITY, default=data[CONF_PRICE_ENTITY])] = selector.EntitySelector(selector.EntitySelectorConfig(domain=["sensor", "input_number"]))
    else:
        entity_price[vol.Optional(CONF_PRICE_ENTITY)] = selector.EntitySelector(selector.EntitySelectorConfig(domain=["sensor", "input_number"]))
    return vol.Schema({
        vol.Optional(CONF_DEVICES, default=data.get(CONF_DEVICES, [])):
            selector.DeviceSelector(selector.DeviceSelectorConfig(multiple=True)),
        vol.Optional(CONF_POWER_ENTITIES, default=data.get(CONF_POWER_ENTITIES, [])):
            selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor", multiple=True)),
        **entity_price,
        vol.Required(CONF_PRICE_FIXED, default=data.get(CONF_PRICE_FIXED, 0.0)):
            selector.NumberSelector(selector.NumberSelectorConfig(min=0, max=10, step=0.0001, mode=selector.NumberSelectorMode.BOX)),
        vol.Required(CONF_BASE_MONTHLY, default=data.get(CONF_BASE_MONTHLY, 0.0)):
            selector.NumberSelector(selector.NumberSelectorConfig(min=0, max=1000, step=0.01, mode=selector.NumberSelectorMode.BOX)),
    })


def resolve(hass, supplied):
    return device_selection(hass, supplied.get(CONF_DEVICES, []), supplied.get(CONF_POWER_ENTITIES, []))


class HeimEnergyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            resolved = resolve(self.hass, user_input)
            if resolved:
                await self.async_set_unique_id("heimenergie_main")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="HeimEnergie", data={**user_input, "resolved": resolved})
            return self.async_show_form(step_id="user", data_schema=schema(user_input), errors={"base": "no_power_sensor"})
        return self.async_show_form(step_id="user", data_schema=schema())

    @staticmethod
    def async_get_options_flow(config_entry):
        return HeimEnergyOptionsFlow()


class HeimEnergyOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        previous = {**self.config_entry.data, **self.config_entry.options}
        if user_input is not None:
            resolved = resolve(self.hass, user_input)
            if resolved:
                return self.async_create_entry(title="", data={**user_input, "resolved": resolved})
            return self.async_show_form(step_id="init", data_schema=schema(user_input), errors={"base": "no_power_sensor"})
        return self.async_show_form(step_id="init", data_schema=schema(previous))
