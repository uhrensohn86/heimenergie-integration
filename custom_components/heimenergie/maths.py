"""Pure, testable calendar and energy calculation helpers. No HA dependency."""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta, timezone
from typing import Any

PERIODS = ("today", "week", "month", "year")


def period_key(day: date, period: str) -> str:
    if period == "today":
        return day.isoformat()
    if period == "week":
        y, w, _ = day.isocalendar()
        return f"{y}-W{w:02d}"
    if period == "month":
        return day.strftime("%Y-%m")
    if period == "year":
        return str(day.year)
    raise ValueError(f"Unknown period: {period}")


def monthly_fixed_share(day: date, period: str, monthly_price: float) -> float:
    """Full-period fixed charge; weekly/daily prorated by calendar days."""
    if period == "month":
        return monthly_price
    if period == "year":
        return monthly_price * 12
    if period == "today":
        return monthly_price / calendar.monthrange(day.year, day.month)[1]
    if period == "week":
        monday = day - timedelta(days=day.weekday())
        return sum(
            monthly_price / calendar.monthrange((monday + timedelta(days=i)).year,
                                                (monday + timedelta(days=i)).month)[1]
            for i in range(7)
        )
    raise ValueError(f"Unknown period: {period}")


def normalize_tracker(data: dict[str, Any] | None, today: date) -> dict[str, Any]:
    """Keep stable 4 buckets; period keys automatically reset at rollover."""
    if not isinstance(data, dict):
        data = {}
    buckets = data.setdefault("periods", {})
    for period in PERIODS:
        expected = period_key(today, period)
        previous = buckets.get(period)
        if not isinstance(previous, dict) or previous.get("key") != expected:
            buckets[period] = {"key": expected, "kwh": 0.0}
    return data


def credit(data: dict[str, Any], when: date, delta_kwh: float) -> None:
    if delta_kwh <= 0:
        return
    normalize_tracker(data, when)
    for period in PERIODS:
        data["periods"][period]["kwh"] += delta_kwh


def accumulate_power(data: dict[str, Any], start: datetime, end: datetime,
                     watts: float, max_gap_seconds: float = 300) -> float:
    """Split a short held-power interval at local-date boundaries.

    The caller supplies timezone-aware datetimes (same UTC offset handling rules),
    and must not pass a span across an application restart. Longer spans are
    discarded, rather than silently inventing hours of unmeasured consumption.
    """
    if start.tzinfo is None or end.tzinfo is None or watts < 0:
        return 0.0
    elapsed = (end.astimezone(timezone.utc) - start.astimezone(timezone.utc)).total_seconds()
    if elapsed <= 0 or elapsed > max_gap_seconds:
        return 0.0
    delta = 0.0
    cursor = start.astimezone(timezone.utc)
    end_utc = end.astimezone(timezone.utc)
    local_tz = end.tzinfo
    while cursor < end_utc:
        following = min(end_utc, cursor + timedelta(seconds=60))
        # Subdivide one minute again at UTC instant of a local date rollover,
        # if one exists (including DST transitions).
        cursor_local = cursor.astimezone(local_tz)
        following_local = following.astimezone(local_tz)
        if cursor_local.date() != following_local.date():
            lo, hi = cursor, following
            while (hi - lo).total_seconds() > 0.25:
                mid = lo + (hi - lo) / 2
                if mid.astimezone(local_tz).date() == cursor_local.date():
                    lo = mid
                else:
                    hi = mid
            following = hi
        kwh = watts * (following - cursor).total_seconds() / 3_600_000
        credit(data, cursor.astimezone(local_tz).date(), kwh)
        delta += kwh
        cursor = following
    return delta


def cumulative_delta(previous: float | None, current: float) -> float:
    """An increasing counter can reset to zero; do not subtract past usage."""
    if current < 0:
        return 0.0
    if previous is None:
        return 0.0
    if current >= previous:
        return current - previous
    # A tiny downward correction is NOT a meter reset; otherwise a
    # 1000 -> 999.99 glitch would fabricate nearly 1000 kWh.
    return current if current <= max(1.0, previous * 0.1) else 0.0
