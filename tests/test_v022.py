"""v0.2.2 discovery regression tests; pure-python mocks, no HA installation."""
from __future__ import annotations

from pathlib import Path
import importlib.util
import asyncio
import json
import sys
import types

BASE = Path(__file__).resolve().parents[1] / 'custom_components' / 'heimenergie'
for name in ('homeassistant', 'homeassistant.helpers', 'homeassistant.helpers.device_registry',
             'homeassistant.helpers.entity_registry', 'custom_components',
             'custom_components.heimenergie'):
    mod = sys.modules.setdefault(name, types.ModuleType(name))
    mod.__path__ = []


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, BASE / path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

load('custom_components.heimenergie.const', 'const.py')
discovery = load('custom_components.heimenergie.discovery', 'discovery.py')


class FakeState:
    def __init__(self, eid, unit, kind, state_class='total_increasing', **attrs):
        self.entity_id = eid
        self.name = eid
        self.attributes = {'unit_of_measurement': unit, 'device_class': kind,
                           'state_class': state_class, **attrs}


class FakeStates:
    def __init__(self, state_list):
        self.data = {s.entity_id: s for s in state_list}

    def get(self, eid):
        return self.data.get(eid)

    def async_all(self, domain):
        return [s for s in self.data.values() if s.entity_id.startswith(domain + '.')]


POWER = FakeState('sensor.example_current_power', 'W', 'power')
TOTAL = FakeState('sensor.example_total_energy', 'kWh', 'energy')
UTILITY_TODAY = FakeState('sensor.example_verbrauch_heute', 'kWh', 'energy', last_period='1.2')
NATIVE_TODAY = FakeState('sensor.example_today_energy', 'kWh', 'energy')
UTILITY_COST = FakeState('sensor.example_kosten_heute', '€', 'monetary', state_class=None)
MONTHLY_NATIVE = FakeState('sensor.example_month_energy', 'kWh', 'energy')
MONTHLY_COST = FakeState('sensor.example_kosten_monat', '€', 'monetary', state_class=None)


def test_reuse_preference():
    hass = types.SimpleNamespace(states=FakeStates([
        POWER, TOTAL, UTILITY_TODAY, NATIVE_TODAY, UTILITY_COST,
        MONTHLY_NATIVE, MONTHLY_COST,
    ]))
    registered = {POWER.entity_id, TOTAL.entity_id, NATIVE_TODAY.entity_id, MONTHLY_NATIVE.entity_id}
    energy = discovery.period_match(hass, 'Example', POWER.entity_id, registered, 'energy', 'today')
    assert energy == UTILITY_TODAY.entity_id, energy
    assert discovery.period_match(hass, 'Example', POWER.entity_id, registered, 'cost', 'today', energy) == UTILITY_COST.entity_id
    assert discovery.period_match(hass, 'Example', POWER.entity_id, registered, 'cost', 'today', None) is None
    month = discovery.period_match(hass, 'Example', POWER.entity_id, registered, 'energy', 'month')
    assert month == MONTHLY_NATIVE.entity_id
    # Don't reuse a cost whose energy basis is not demonstrated.
    assert discovery.period_match(hass, 'Example', POWER.entity_id, registered, 'cost', 'month', month) is None
    # Don't confuse unrelated current-period identities or own integration sensors.
    hass.states.data['sensor.heimenergie_example_verbrauch_heute'] = FakeState('sensor.heimenergie_example_verbrauch_heute', 'kWh', 'energy')
    assert discovery.period_match(hass, 'Example', POWER.entity_id, registered, 'energy', 'today') == energy


def test_ambiguity():
    hass = types.SimpleNamespace(states=FakeStates([
        POWER,
        FakeState('sensor.example_verbrauch_heute', 'kWh', 'energy'),
        FakeState('sensor.example_consumption_heute', 'kWh', 'energy'),
    ]))
    assert discovery.period_match(hass, 'Example', POWER.entity_id, set(), 'energy', 'today') is None


def test_no_stale_cost_when_new_period_created():
    hass = types.SimpleNamespace(states=FakeStates([POWER, UTILITY_COST]))
    assert discovery.period_match(hass, 'Example', POWER.entity_id, set(), 'energy', 'today') is None
    assert discovery.period_match(hass, 'Example', POWER.entity_id, set(), 'cost', 'today', None) is None


def test_cleanup_hook_present():
    # Validate public HA callback name and correct storage key without importing HA.
    import ast
    script = (BASE / '__init__.py').read_text(encoding='utf-8')
    parsed = ast.parse(script)
    nodes = {fn.name: fn for fn in parsed.body if isinstance(fn, ast.AsyncFunctionDef)}
    assert 'async_remove_entry' in nodes
    func = ast.get_source_segment(script, nodes['async_remove_entry'])
    assert 'Store(hass, 1, f"{DOMAIN}.{entry.entry_id}").async_remove()' in func
    assert 'async_unload_entry' in nodes
    # Removal is not invoked during a normal unload (which happens on options changes).
    unload = ast.get_source_segment(script, nodes['async_unload_entry'])
    assert '.async_remove(' not in unload


def test_owned_registry_cleanup_is_narrow():
    import ast
    script = (BASE / 'sensor.py').read_text()
    assert 'er.async_entries_for_config_entry(registry, entry.entry_id)' in script
    assert 'previous.unique_id.startswith(own_prefix)' in script
    assert 'previous.unique_id not in desired_ids' in script
    assert 'registry.async_remove(previous.entity_id)' in script
    ast.parse(script)


def test_manifest():
    manifest = json.loads((BASE / 'manifest.json').read_text())
    assert manifest['version'] in ('0.2.2', '0.2.3')
    assert manifest['domain'] == 'heimenergie'


if __name__ == '__main__':
    test_reuse_preference()
    test_ambiguity()
    test_no_stale_cost_when_new_period_created()
    test_cleanup_hook_present()
    test_owned_registry_cleanup_is_narrow()
    test_manifest()
    print('HeimEnergie v0.2.2: Sensor-Auswahl, Kosten-Kopplung und Deinstallation OK')
