"""v0.2.3 tests: consumer/meter separation, naming, safe session isolation.

No private HA configuration and no installed HA or third-party library needed.
"""
from __future__ import annotations
import importlib.util
import json
import sys
import types
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / 'custom_components' / 'heimenergie'

for name in ('homeassistant', 'homeassistant.helpers',
             'homeassistant.helpers.device_registry',
             'homeassistant.helpers.entity_registry',
             'homeassistant.helpers.selector',
             'homeassistant.config_entries', 'custom_components',
             'custom_components.heimenergie', 'voluptuous'):
    module = sys.modules.setdefault(name, types.ModuleType(name))
    if name in ('homeassistant', 'homeassistant.helpers', 'custom_components',
                'custom_components.heimenergie'):
        module.__path__ = []


class MockFlow:
    def __init_subclass__(cls, **kwargs):
        return super().__init_subclass__()


sys.modules['homeassistant.config_entries'].ConfigFlow = MockFlow
sys.modules['homeassistant.config_entries'].OptionsFlow = MockFlow


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, BASE / filename)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


load('custom_components.heimenergie.const', 'const.py')
disc = load('custom_components.heimenergie.discovery', 'discovery.py')
flow = load('custom_components.heimenergie.config_flow', 'config_flow.py')


class FakeState:
    def __init__(self, eid, unit, kind, state_class='total_increasing', **attrs):
        self.entity_id = eid
        self.name = eid
        self.attributes = dict(unit_of_measurement=unit, device_class=kind,
                               state_class=state_class, **attrs)


class FakeStates:
    def __init__(self, states):
        self.data = {st.entity_id: st for st in states}

    def get(self, eid):
        return self.data.get(eid)

    def async_all(self, domain):
        return [st for st in self.data.values() if st.entity_id.startswith(domain + '.')]


class FakeRegistry:
    def __init__(self, devices):
        self.devices = devices

    def async_get(self, dev_id):
        return self.devices.get(dev_id)


class FakeDevice:
    def __init__(self, name):
        self.name = name
        self.name_by_user = None


METER = FakeState('sensor.example_plug_power', 'W', 'power')
NATIVE = FakeState('sensor.example_plug_today_energy', 'kWh', 'energy')
ENERGY = FakeState('sensor.refrigerator_verbrauch_heute', 'kWh', 'energy', last_period='2.5')
COST = FakeState('sensor.refrigerator_kosten_heute', '€', 'monetary', state_class=None)
METER_SOURCE = FakeState('sensor.example_plug_total_energy', 'kWh', 'energy')
hass = types.SimpleNamespace(states=FakeStates([METER, NATIVE, ENERGY, COST, METER_SOURCE]))


def fake_er(hass):
    return types.SimpleNamespace()


def fake_entries(reg, device_id):
    return [types.SimpleNamespace(entity_id=x, disabled_by=None) for x in
            [METER.entity_id, NATIVE.entity_id, METER_SOURCE.entity_id]] if device_id == 'meter-id' else []


sys.modules['homeassistant.helpers.entity_registry'].async_get = fake_er
sys.modules['homeassistant.helpers.entity_registry'].async_entries_for_device = fake_entries
sys.modules['homeassistant.helpers.device_registry'].async_get = lambda hass: FakeRegistry({'fridge-id': FakeDevice('Refrigerator')})


def meter():
    return {'name': 'Example Plug', 'power': METER.entity_id, 'device_id': 'meter-id',
            'source_energy': METER_SOURCE.entity_id, 'reuse': {}}


def test_new_consumer_custom_name_reuses_logical_meters():
    value = flow.assigned_consumer(hass, meter(), None,
                                   {'consumer_name': 'Refrigerator', 'consumer_type': 'fridge'})
    assert value['name'] == 'Refrigerator'
    assert value['meter_name'] == 'Example Plug'
    assert value['power'] == METER.entity_id
    assert value['tracker_key'].startswith('consumer_')
    assert value['reuse']['energy_today'] == ENERGY.entity_id
    assert value['reuse']['cost_today'] == COST.entity_id


def test_existing_ha_consumer_selection():
    value = flow.assigned_consumer(hass, meter(), None, {'consumer_device': 'fridge-id'})
    assert value['name'] == 'Refrigerator'
    assert value['consumer_device_id'] == 'fridge-id'
    assert value['reuse']['energy_today'] == ENERGY.entity_id


def test_legacy_rename_preserves_existing_tracker_key():
    original = {'name': 'Example Plug', 'power': METER.entity_id}
    edited = flow.assigned_consumer(hass, meter(), original, {'consumer_name': 'Refrigerator'})
    assert edited['tracker_key'] == METER.entity_id
    assert edited['reuse']['energy_today'] == ENERGY.entity_id


def test_replug_begins_new_identity_without_reusing_period_meters():
    original = {'name': 'Refrigerator', 'power': METER.entity_id,
                'tracker_key': 'consumer_old', 'consumer_device_id': ''}
    changed = flow.assigned_consumer(hass, meter(), original,
                                     {'consumer_name': 'Other Appliance', 'new_session': True})
    assert changed['tracker_key'] != original['tracker_key']
    assert changed['tracker_key'].startswith('consumer_')
    assert all(value is None for value in changed['reuse'].values())
    assert changed['source_energy'] == METER_SOURCE.entity_id
    assert changed['isolation_mode'] is True
    # Reconfiguring a tariff cannot silently re-use pre-switch period totals.
    again = flow.assigned_consumer(hass, meter(), changed,
                                   {'consumer_name': 'Other Appliance'})
    assert again['tracker_key'] == changed['tracker_key']
    assert again['isolation_mode'] is True
    assert all(v is None for v in again['reuse'].values())
    # The old readings are still keyed under consumer_old, not the plug.
    store = {'consumer_old': {'periods': {'today': {'kwh': 20}}}}
    assert changed['tracker_key'] not in store


def test_switching_ha_consumer_also_starts_new_session():
    original = {'name': 'Old Consumer', 'power': METER.entity_id,
                'tracker_key': 'old', 'consumer_device_id': 'different-device'}
    changed = flow.assigned_consumer(hass, meter(), original,
                                     {'consumer_device': 'fridge-id'})
    assert changed['tracker_key'] != 'old'
    assert changed['name'] == 'Refrigerator'
    assert changed['reuse']['energy_today'] is None


def test_blank_initial_consumer_is_rejected():
    try:
        flow.assigned_consumer(hass, meter(), None, {})
    except ValueError as exc:
        assert str(exc) == 'missing_consumer'
    else:
        raise AssertionError('New loads must have a name or selected HA device')


def test_runtime_uses_consumer_specific_storage():
    co = (BASE / 'coordinator.py').read_text()
    sensor = (BASE / 'sensor.py').read_text()
    assert 'dev.get("tracker_key", dev["power"])' in co
    assert 'archived_prefixes' in sensor
    assert 'consumer_device_id' in sensor
    assert 'registry.async_remove(previous.entity_id)' in sensor



def test_options_flow_skips_existing_and_prompts_new_meter():
    import asyncio
    older = {**meter(), "name": "Refrigerator", "tracker_key": "old-id",
             "consumer_configured": True, "consumer_type": "fridge",
             "consumer_device_id": ""}
    extra = {"name": "Second Plug", "power": "sensor.another_plug_power",
             "device_id": "", "source_energy": "", "reuse": {}}
    original_resolve, original_schema = flow.resolve, flow.consumer_schema
    hass_reference = hass
    class FakeFlow(flow._ConsumerSteps):
        _entry_title = ""
        hass = hass_reference

        def async_show_form(self, **kwargs):
            return {"kind": "form", **kwargs}

        def async_create_entry(self, **kwargs):
            return {"kind": "entry", **kwargs}
    try:
        flow.resolve = lambda h, payload: [meter(), extra]
        flow.consumer_schema = lambda prior: {"prior": prior}
        ff = FakeFlow()
        ff._begin({"devices": ["dummy"]}, [older])
        frm = asyncio.run(ff._next_consumer())
        assert frm["kind"] == "form" and ff._next_index == 1
        assert ff._bound[0]["tracker_key"] == "old-id"
        done = asyncio.run(ff.async_step_consumer({"consumer_name": "New Device"}))
        assert done["kind"] == "entry"
        assigned = done["data"]["resolved"]
        assert len(assigned) == 2
        assert assigned[0]["name"] == "Refrigerator"
        assert assigned[1]["name"] == "New Device"
    finally:
        flow.resolve, flow.consumer_schema = original_resolve, original_schema


def test_consumer_checkpoint_metadata_is_saved_locally():
    script = (BASE / 'coordinator.py').read_text()
    assert 'self.consumer_history[tracker_key]' in script
    assert '"consumer_history": self.consumer_history' in script
    assert 'self.store.async_delay_save(self._store_payload, 5)' in script
    assert 'await self.store.async_save(self._store_payload())' in script


def test_manifest_and_localization():
    assert json.loads((BASE / 'manifest.json').read_text())['version'] == '0.2.3'
    for name in ('strings.json', 'translations/de.json'):
        obj = json.loads((BASE / name).read_text())
        assert 'consumer' in obj['config']['step']
        assert 'consumer' in obj['options']['step']
        assert 'new_session' in obj['options']['step']['consumer']['data']


if __name__ == '__main__':
    test_new_consumer_custom_name_reuses_logical_meters()
    test_existing_ha_consumer_selection()
    test_legacy_rename_preserves_existing_tracker_key()
    test_replug_begins_new_identity_without_reusing_period_meters()
    test_switching_ha_consumer_also_starts_new_session()
    test_blank_initial_consumer_is_rejected()
    test_options_flow_skips_existing_and_prompts_new_meter()
    test_consumer_checkpoint_metadata_is_saved_locally()
    test_runtime_uses_consumer_specific_storage()
    test_manifest_and_localization()
    print('HeimEnergie v0.2.3: Verbraucherzuordnung, Historientrennung, Katalog OK')
