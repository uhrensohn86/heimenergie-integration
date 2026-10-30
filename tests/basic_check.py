"""Run without pytest or Home Assistant: python tests/basic_check.py."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
import importlib.util
import json

root=Path(__file__).resolve().parents[1]
module=root/"custom_components/heimenergie/maths.py"
spec=importlib.util.spec_from_file_location("hm_math",module)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

assert abs(m.monthly_fixed_share(date(2026,10,30),"year",12)-144)<1e-9
assert abs(m.monthly_fixed_share(date(2026,10,30),"month",12)-12)<1e-9
assert abs(m.monthly_fixed_share(date(2026,10,30),"week",31)-(6+31/30))<1e-9
state={}
m.credit(state,date(2026,10,30),2.0)
m.credit(state,date(2026,11,1),1.0)
assert state["periods"]["month"]["kwh"]==1.0
assert state["periods"]["year"]["kwh"]==3.0
state={}
berlin=ZoneInfo("Europe/Berlin")
s=datetime(2026,10,30,23,59,30,tzinfo=berlin)
assert abs(m.accumulate_power(state,s,s+timedelta(minutes=1),1000)-(1/60))<1e-8
assert abs(m.cumulative_delta(1000,999.9))<1e-8
manifest=json.loads((root/"custom_components/heimenergie/manifest.json").read_text())
assert manifest["domain"]=="heimenergie" and manifest["config_flow"]
print("HeimEnergie: Grundpreis, Zählerwechsel, Leistung und Manifest OK")
