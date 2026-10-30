"""Dependency-free checks for the period and base tariff math."""
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
import importlib.util
from pathlib import Path

path = Path(__file__).resolve().parents[1]/"custom_components"/"heimenergie"/"maths.py"
spec = importlib.util.spec_from_file_location("heimenergie_maths", path)
maths = importlib.util.module_from_spec(spec)
spec.loader.exec_module(maths)


def close(a,b): assert abs(a-b)<1e-8, (a,b)


def test_fixed_charge():
    close(maths.monthly_fixed_share(date(2026,2,2),"today",28),1)
    close(maths.monthly_fixed_share(date(2026,10,30),"month",12),12)
    close(maths.monthly_fixed_share(date(2026,10,30),"year",12),144)
    close(maths.monthly_fixed_share(date(2026,10,30),"week",31),
          (6*31/31)+(1*31/30))


def test_period_rollover():
    state={}
    maths.credit(state,date(2026,10,30),1.25)
    close(state["periods"]["month"]["kwh"],1.25)
    maths.credit(state,date(2026,11,1),0.25)
    close(state["periods"]["today"]["kwh"],0.25)
    close(state["periods"]["month"]["kwh"],0.25)
    close(state["periods"]["year"]["kwh"],1.5)
    assert maths.period_key(date(2027,1,1),"week")=="2026-W53"


def test_power_midnight_split():
    berlin=ZoneInfo("Europe/Berlin")
    state={}
    beginning=datetime(2026,10,30,23,59,30,tzinfo=berlin)
    end=datetime(2026,10,31,0,0,30,tzinfo=berlin)
    amount=maths.accumulate_power(state, beginning,end,1000)
    close(amount,1/60)
    close(state["periods"]["today"]["kwh"],1/120)
    assert state["periods"]["today"]["key"]=="2026-10-31"
    close(state["periods"]["month"]["kwh"],1/60)


def test_invalid_gap_and_reset():
    berlin=ZoneInfo("Europe/Berlin")
    state={}
    begin=datetime(2026,10,30,11,0,tzinfo=berlin)
    assert maths.accumulate_power(state,begin,begin+timedelta(minutes=10),200)==0
    assert maths.cumulative_delta(None,120.1)==0
    close(maths.cumulative_delta(120.1,120.3),0.2)
    close(maths.cumulative_delta(120.3,0.5),0.5)
    close(maths.cumulative_delta(1000.0,999.9),0.0)


def test_dst_fall_back():
    berlin=ZoneInfo("Europe/Berlin")
    state={}
    before=datetime(2026,10,25,2,58,tzinfo=berlin,fold=0)
    after=datetime(2026,10,25,2,2,tzinfo=berlin,fold=1)
    # Clock moved backwards but 4 real minutes elapsed.
    close(maths.accumulate_power(state,before,after,1000),4/60)
