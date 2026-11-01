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


# Only complete words match: "day" must never match "weekday", for example.
def _period_words(period: str) -> set[str]:
    return set(PERIOD_TOKENS[period])


def _period_present(identifier: str, period: str) -> bool:
    words = identifier.lower().split("_")
    return any(word in _period_words(period) for word in words)


def _device_stems(device_name: str, power_id: str) -> set[str]:
    names = {slug(device_name), slug(power_id.split(".", 1)[-1])}
    # Keep stripping common power suffixes to reach the device root.
    for suffix in ("_current_power", "_current_leistung", "_power", "_leistung"):
        names.update({name.removesuffix(suffix) for name in tuple(names)})
    return {name for name in names if name}


def _kind_valid(entity_id: str, state: Any, kind: str, period: str) -> bool:
    identifier = entity_id.split(".", 1)[-1]
    if not _period_present(identifier, period):
        return False
    words = set(identifier.split("_"))
    unit = str(state.attributes.get("unit_of_measurement", "")).lower()
    if kind == "energy":
        return unit in ("wh", "kwh", "mwh") and bool(words & {"energy", "energie", "verbrauch", "consumption"})
    return (unit in ("€", "eur") or state.attributes.get("device_class") == "monetary") and bool(words & {"cost", "costs", "kosten"})


def _paired_cost_ids(energy_id: str) -> set[str]:
    """Only trust a cost counter sharing the full naming pattern of its energy counter.

    E.g. sensor.foo_verbrauch_heute -> sensor.foo_kosten_heute.
    Other cost entities can still be shown by HA, but are not silently paired.
    """
    domain, identifier = energy_id.split(".", 1)
    candidates = set()
    for energy_token in ("verbrauch", "energy", "energie", "consumption"):
        for cost_token in ("kosten", "cost", "costs"):
            words = identifier.split("_")
            candidates.update(domain + "." + "_".join(cost_token if word == energy_token else word for word in words)
                              for _ in (0,) if energy_token in words)
    return candidates


def period_match(hass: Any, device_name: str, power_id: str,
                 registered_ids: set[str], kind: str, period: str,
                 energy_id: str | None = None) -> str | None:
    """Select a period value only when its source and period are sufficiently clear.

    Prefer an existing *_verbrauch_heute utility meter over a parallel
    *_today_energy sensor. If there are equally ranked candidates, do not guess.
    Costs must correspond to the chosen energy naming scheme, otherwise
    HeimEnergie computes costs from precisely that energy and the tariff.
    """
    if kind == "cost" and not energy_id:
        return None
    paired_costs = _paired_cost_ids(energy_id) if kind == "cost" else None
    stems = _device_stems(device_name, power_id)
    scores: list[tuple[int, str]] = []
    for state in hass.states.async_all("sensor"):
        entity_id = state.entity_id
        if entity_id.startswith("sensor.heimenergie_"):
            continue  # Never accidentally reuse sensors from our own integration.
        ident = entity_id.split(".", 1)[-1]
        on_device = entity_id in registered_ids
        same_prefix = any(ident.startswith(stem + "_") for stem in stems)
        if not (on_device or same_prefix):
            continue
        if not _kind_valid(entity_id, state, kind, period):
            continue
        if kind == "cost" and entity_id not in paired_costs:
            continue
        words = ident.split("_")
        score = 20 if on_device else 10
        if same_prefix:
            score += 10
        if kind == "cost":
            score += 80  # Strict naming correspondence already established.
        else:
            # Existing HA utility meters often follow *_verbrauch_heute.
            # Smart plugs often follow *_today_energy and can coexist.
            if any(words.index(t) > 0 and words[words.index(t) - 1] in ("verbrauch", "energie", "energy", "consumption")
                   for t in _period_words(period) if t in words):
                score += 60
            if str(state.attributes.get("state_class", "")) in ("total", "total_increasing"):
                score += 10
            if "last_period" in state.attributes:
                score += 15  # HA utility_meter exposes the prior period reading.
            if state.attributes.get("device_class") == "energy":
                score += 5
        scores.append((score, entity_id))
    scores.sort(reverse=True)
    if not scores or (len(scores) > 1 and scores[0][0] == scores[1][0]):
        return None
    return scores[0][1]


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
        reuse = {}
        for period in PERIODS:
            energy = period_match(hass, result["name"], result["power"], registered,
                                  "energy", period)
            reuse[f"energy_{period}"] = energy
            reuse[f"cost_{period}"] = period_match(
                hass, result["name"], result["power"], registered,
                "cost", period, energy_id=energy
            )
        result["reuse"] = reuse
    return results
