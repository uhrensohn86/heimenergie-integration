"""Check matching with fake Home Assistant registries, no installation needed."""
import importlib.util
from pathlib import Path
import sys
import types

BASE=Path(__file__).resolve().parents[1]/"custom_components"/"heimenergie"

# Provide minimal module namespace so discovery can be tested without HA.
for name in ("homeassistant","homeassistant.helpers","homeassistant.helpers.device_registry",
             "homeassistant.helpers.entity_registry", "custom_components",
             "custom_components.heimenergie"):
    if name not in sys.modules:
        mod=types.ModuleType(name); mod.__path__=[]
        sys.modules[name]=mod


def load(name, file):
    spec=importlib.util.spec_from_file_location(name,BASE/file)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module

load("custom_components.heimenergie.const","const.py")
d=load("custom_components.heimenergie.discovery","discovery.py")


class S:
    def __init__(self, eid, unit, cls=None, state_class=None, name=None):
        self.entity_id=eid
        self.attributes={"unit_of_measurement":unit,"device_class":cls,"state_class":state_class}
        self.name=name or eid


class States:
    def __init__(self, states):self._states=states
    def get(self, id):return self._states.get(id)
    def async_all(self, domain):return [s for id,s in self._states.items() if id.startswith(domain+'.')]


def test_auto_discovery_reuses_existing_meters():
    from homeassistant.helpers import device_registry as dr, entity_registry as er
    states={
        "sensor.sample_power":S("sensor.sample_power","W","power",name="Example plug"),
        "sensor.sample_total_energy":S("sensor.sample_total_energy","kWh","energy","total_increasing"),
        "sensor.example_plug_verbrauch_heute":S("sensor.example_plug_verbrauch_heute","kWh","energy"),
        "sensor.example_plug_kosten_heute":S("sensor.example_plug_kosten_heute","€","monetary"),
        "sensor.example_plug_month_energy":S("sensor.example_plug_month_energy","kWh","energy"),
    }
    device=types.SimpleNamespace(name="Example Plug",name_by_user=None)
    dr.async_get=lambda hass:types.SimpleNamespace(async_get=lambda id:device)
    er.async_get=lambda hass:object()
    er.async_entries_for_device=lambda reg, dev: [types.SimpleNamespace(entity_id=x,disabled_by=None) for x in states]
    hass=types.SimpleNamespace(states=States(states))
    result=d.device_selection(hass,["some-device"],[])
    assert len(result)==1
    assert result[0]["power"]=="sensor.sample_power"
    assert result[0]["source_energy"]=="sensor.sample_total_energy"
    assert result[0]["reuse"]["energy_today"]=="sensor.example_plug_verbrauch_heute"
    assert result[0]["reuse"]["cost_today"]=="sensor.example_plug_kosten_heute"
    assert result[0]["reuse"]["energy_month"]=="sensor.example_plug_month_energy"


def test_slugs():
    assert d.slug("Müßig") == "mussig"
    assert d.slug("Küche") == "kuche"
    assert d.slug("Messpunkt / Büro") == "messpunkt_buro"
