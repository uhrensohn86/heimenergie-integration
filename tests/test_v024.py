"""v0.2.4: verified technical-meter fallback with safe counter pairing.

Pure-Python fakes. All names/IDs below are invented test fixtures.
"""
from __future__ import annotations
import importlib.util
import json
import sys
import types
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / 'custom_components' / 'heimenergie'
for name in ('homeassistant','homeassistant.helpers',
             'homeassistant.helpers.device_registry',
             'homeassistant.helpers.entity_registry',
             'custom_components','custom_components.heimenergie'):
    module = sys.modules.setdefault(name, types.ModuleType(name))
    module.__path__ = []

def load(name, file):
    spec = importlib.util.spec_from_file_location(name, BASE / file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

load('custom_components.heimenergie.const', 'const.py')
disc = load('custom_components.heimenergie.discovery','discovery.py')

class State:
    def __init__(self, name, unit, kind='energy', sc='total_increasing', **extra):
        self.entity_id=name
        self.name=name
        self.attributes={'unit_of_measurement':unit,'device_class':kind,'state_class':sc, **extra}

class States:
    def __init__(self, *items):
        self.data={item.entity_id:item for item in items}
    def async_all(self, domain):
        return [s for s in self.data.values() if s.entity_id.startswith(domain+'.')]
    def get(self, key):
        return self.data.get(key)

class Registry:
    pass

sys.modules['homeassistant.helpers.entity_registry'].async_get = lambda ha: Registry()
sys.modules['homeassistant.helpers.entity_registry'].async_entries_for_device = lambda reg, dev: [
    types.SimpleNamespace(entity_id='sensor.media_plug_today_energy',disabled_by=None)
]

POWER='sensor.media_plug_current_power'
METER={'name':'Media Plug','power':POWER,'device_id':'meter-1'}


def hass(*extra):
    return types.SimpleNamespace(states=States(
        State(POWER,'W','power','measurement'),
        State('sensor.media_plug_today_energy','kWh'),
        State('sensor.media_plug_verbrauch_heute','kWh',last_period='2'),
        State('sensor.media_plug_kosten_heute','€','monetary',None),
        State('sensor.media_plug_verbrauch_monat','kWh',last_period='15'),
        State('sensor.media_plug_kosten_monat','€','monetary',None),
        State('sensor.media_plug_verbrauch_jahr','kWh',last_period='40'),
        State('sensor.media_plug_kosten_jahr','€','monetary',None),
        *extra,
    ))


def test_technical_meter_name_resolves_periods_even_after_consumer_rename():
    selected=disc.rebind_consumer(hass(), METER, 'Media Console 7')
    assert selected['name']=='Media Console 7'
    assert selected['power']==POWER
    for period, label in [('today','heute'),('month','monat'),('year','jahr')]:
        assert selected['reuse']['energy_'+period]=='sensor.media_plug_verbrauch_'+label
        assert selected['reuse']['cost_'+period]=='sensor.media_plug_kosten_'+label
    assert selected['reuse']['energy_week'] is None
    assert selected['reuse']['cost_week'] is None


def test_consumer_specific_counter_wins_over_technical_meter():
    ha=hass(
        State('sensor.media_console_7_verbrauch_heute','kWh',last_period='2'),
        State('sensor.media_console_7_kosten_heute','€','monetary',None),
    )
    selected=disc.rebind_consumer(ha,METER,'Media Console 7')
    assert selected['reuse']['energy_today']=='sensor.media_console_7_verbrauch_heute'
    assert selected['reuse']['cost_today']=='sensor.media_console_7_kosten_heute'


def test_mismatched_or_generic_alias_must_not_match_unrelated_counters():
    ha=hass(State('sensor.generic_plug_verbrauch_woche','kWh',last_period='3'),
            State('sensor.generic_plug_kosten_woche','€','monetary',None))
    altered={**METER,'name':'Generic Plug'}  # does not identify POWER
    selected=disc.rebind_consumer(ha,altered,'Media Console 7')
    assert selected['reuse']['energy_week'] is None
    assert selected['reuse']['cost_week'] is None


def test_cost_is_not_paired_without_matching_energy():
    selected=disc.rebind_consumer(hass(
        State('sensor.media_plug_kosten_woche','€','monetary',None)),METER,'Media Console 7')
    assert selected['reuse']['energy_week'] is None
    assert selected['reuse']['cost_week'] is None


def test_isolated_new_session_never_reuses_old_meter_counters():
    selected=disc.rebind_consumer(hass(),METER,'New Console',fresh_session=True)
    assert all(v is None for v in selected['reuse'].values())


def test_ambiguous_candidates_do_not_get_guessed():
    ha=hass(State('sensor.media_plug_energie_woche','kWh'),
            State('sensor.media_plug_verbrauch_woche','kWh'))
    selected=disc.rebind_consumer(ha,METER,'Media Console 7')
    assert selected['reuse']['energy_week'] is None


def test_manifest():
    assert tuple(map(int, json.loads((BASE/'manifest.json').read_text())['version'].split('.'))) >= (0, 2, 4)

if __name__=='__main__':
    for key,value in sorted(globals().copy().items()):
        if key.startswith('test_') and callable(value):
            value()
    print('HeimEnergie v0.2.4: Messgerät-Alias, Kosten-Kopplung, Sitzungs-Trennung OK')
