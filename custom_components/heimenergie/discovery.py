"""Conservative sensor matching: prefer same HA device, reuse only high-confidence periods."""
from __future__ import annotations

import re
import unicodedata
from typing import Any

from homeassistant.helpers import device_registry as dr, entity_registry as er
from .const import PERIODS

PERIOD_TOKENS = {
    "today": ("heute", "today", "daily", "day"),
    "week": ("woche", "week", "weekly"),
    "month": ("monat", "month", "monthly"),
    "year": ("jahr", "year", "yearly"),
}


def slug(value: str) -> str:
    replacements = {"ä": "a", "ö": "o", "ü": "u", "ß": "ss"}
    for a, b in replacements.items():
        value = value.lower().replace(a, b)
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "_", value).strip("_")


def power_score(entity_id: str, state: Any) -> int:
    attr = state.attributes
    unit = str(attr.get("unit_of_measurement", "")).lower()
    if unit not in ("w", "kw", "mw"):
        return -1
    name = entity_id.lower()
    score = 100 if attr.get("device_class") == "power" else 20
    if any(s in name for s in ("_power", "leistung", "current_power")):
        score += 15
    if "total" in name or "peak" in name or "maximum" in name:
        score -= 25
    return score


def energy_score(entity_id: str, state: Any) -> int:
    attr = state.attributes
    unit = str(attr.get("unit_of_measurement", "")).lower()
    if unit not in ("wh", "kwh", "mwh"):
        return -1
    id_text = entity_id.lower()
    if any(token in id_text for toks in PERIOD_TOKENS.values() for token in toks):
        return -1  # Daily/monthly counters are NOT cumulative source energy.
    if attr.get("state_class") not in ("total", "total_increasing"):
        return -1  # Do not mistake arbitrary consumption measurements for a lifetime counter.
    score = 100 if attr.get("device_class") == "energy" else 15
    score += 20 if attr.get("state_class") == "total_increasing" else 0
    if "total" in id_text or "gesamt" in id_text:
        score += 15
    if "power" in id_text or "leistung" in id_text:
        score -= 30
    return score


def period_match(hass: Any, device_name: str, power_id: str,
                 registered_ids: set[str], kind: str, period: str) -> str | None:
    """Reuse an existing period entity only if identity + unit + period are clear."""
    tokens = PERIOD_TOKENS[period]
    stems = {slug(device_name), slug(power_id.split(".", 1)[1])}
    for suffix in ("_current_power", "_power", "_leistung"):
        stems.update({stem.removesuffix(suffix) for stem in tuple(stems)})
    stems.discard("")
    valid = []
    for entity_id, state in ((s.entity_id, s) for s in hass.states.async_all("sensor")):
        ident = entity_id.split(".", 1)[1]
        same_physical_device = entity_id in registered_ids
        same_prefix = any(ident.startswith(stem + "_") for stem in stems)
        if not same_physical_device and not same_prefix:
            continue
        if not any(t in ident for t in tokens):
            continue
        attrs = state.attributes
        unit = str(attrs.get("unit_of_measurement", "")).lower()
        if kind == "energy":
            if unit not in ("wh", "kwh", "mwh"):
                continue
            if not any(t in ident for t in ("energie", "energy", "verbrauch", "consumption")):
                continue
        else:
            if unit not in ("€", "eur") and attrs.get("device_class") != "monetary":
                continue
            if not any(t in ident for t in ("kosten", "cost")):
                continue
        valid.append(entity_id)
    return valid[0] if len(valid) == 1 else None


def device_selection(hass: Any, selected_devices: list[str],
                     selected_powers: list[str]) -> list[dict[str, Any]]:
    reg = er.async_get(hass)
    devreg = dr.async_get(hass)
    results: list[dict[str, Any]] = []
    seen_power: set[str] = set()
    for device_id in selected_devices:
        device = devreg.async_get(device_id)
        if not device:
            continue
        entries = er.async_entries_for_device(reg, device_id)
        ids = {e.entity_id for e in entries if not e.disabled_by}
        candidates = [(power_score(eid, hass.states.get(eid)), eid)
                      for eid in ids if hass.states.get(eid)]
        candidates = sorted(((score, eid) for score, eid in candidates if score >= 0), reverse=True)
        if not candidates:
            continue
        power = candidates[0][1]
        if power in seen_power:
            continue
        seen_power.add(power)
        energies = sorted(((energy_score(eid, hass.states.get(eid)), eid)
                           for eid in ids if hass.states.get(eid)), reverse=True)
        energies = [eid for score, eid in energies if score >= 0]
        friendly = device.name_by_user or device.name or hass.states[power].name
        results.append({"name": friendly, "device_id": device_id, "power": power,
                        "source_energy": energies[0] if energies else "",
                        "registered_ids": sorted(ids)})
    for power in selected_powers:
        if power in seen_power or not (state := hass.states.get(power)) or power_score(power, state) < 0:
            continue
        seen_power.add(power)
        results.append({"name": state.name, "device_id": "", "power": power,
                        "source_energy": "", "registered_ids": []})
    for result in results:
        registered = set(result.pop("registered_ids"))
        result["reuse"] = {
            f"{kind}_{period}": period_match(hass, result["name"], result["power"], registered, kind, period)
            for kind in ("energy", "cost") for period in PERIODS
        }
    return results
