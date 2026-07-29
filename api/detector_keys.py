"""Detector-derived view keys (Plan 25-01, DVK-01/DVK-02).

P1: this is the SINGLE derivation helper for LICKER0...LICKER3-style view keys. No consumer
ever re-implements f"{device_name}{i}" — `grep -rn "device_name}{" api/` outside this file must
stay empty.

P2: `channels` (the raw index set) is a first-class return alongside `keys` (the resolved-name
preview). A condition operand stores {"view_detector": {"ref": ..., "channel": <index>}} — the
editor needs indices, not just names, and must never recover an index by stripping digits off a
key (breaks for any device_name ending in a digit, e.g. SPOUT2 x 4 -> SPOUT20..SPOUT23).

P3: this derivation is deliberately duplicated once per language runtime — the Pi twin lives at
~/pi-mirror/autopilot/tasks/fda_vocabulary.py (plan 02), since the two runtimes cannot import
each other. Both sides pin the identical GOLDEN_CASES table in their test suites; change one,
change both.

P4: a malformed `first_channel` yields NO keys here (an API read must never 500 on a bad config
row) but RAISES ValueError on the Pi (loud where it matters, safe where it is only a render).

Boundary note (DVK-07): `api/fda_validation.py` deliberately does NOT import this module. The
detector-key format never widens the flag namespace; that boundary is pinned behaviourally by
`fda_validation._valid_flag_names`' equality test, not by import structure alone.
"""
from sqlalchemy import text as sa_text


def _as_int(value) -> int | None:
    """Coerce int or numeric str to int; reject bool explicitly (bool is a subclass of int)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def derive_channels(config: dict | None) -> list[int]:
    """The declared channel indices: range(first_channel, first_channel + num_detectors).

    Never raises. Requires device_name to be present (even though the value itself is unused
    here) so this function stays in lockstep with derive_view_keys — a caller can never get
    channels it has no key for.
    """
    if not isinstance(config, dict):
        return []
    device_name = config.get("device_name")
    if not isinstance(device_name, str) or not device_name:
        return []

    num_detectors = _as_int(config.get("num_detectors"))
    if num_detectors is None or num_detectors <= 0:
        return []

    raw_first = config.get("first_channel")
    if raw_first is None:
        first_channel = 0
    else:
        first_channel = _as_int(raw_first)
        if first_channel is None or first_channel < 0:
            return []

    return list(range(first_channel, first_channel + num_detectors))


def derive_view_keys(config: dict | None) -> list[str]:
    """The ONE key format. f"{device_name}{i}" for i in derive_channels(config). Never raises."""
    channels = derive_channels(config)
    if not channels:
        return []
    device_name = config["device_name"]
    return [f"{device_name}{i}" for i in channels]


def _key_sort(key: str) -> tuple[str, int]:
    """(prefix, index) so LICKER2 sorts before LICKER11 — plain sorted() is lexicographic and
    would read wrong in the editor dropdown."""
    i = len(key)
    while i > 0 and key[i - 1].isdigit():
        i -= 1
    prefix, digits = key[:i], key[i:]
    return (prefix, int(digits) if digits else -1)


def module_detector_channels(db, module_names: list[str]) -> list[dict]:
    """Per module, the union of derived channels/keys across every pilot that has a
    pilot_hardware_config row named for that module — ADVISORY ONLY (CONTEXT D4).

    This result decides what the picker OFFERS; nothing pilot-specific is ever stored by it, so
    a `conflict` changes which channels are offered, not whether a saved definition is correct.
    Per-pilot resolution (is THIS channel valid on THIS pilot) is preflight's job (plan 03),
    scoped to one pilot_id against the same table.

    A pilot whose config derives no channels is dropped from `by_pilot` entirely. A module whose
    configured rows all derive nothing is omitted from the result entirely.
    """
    if not module_names:
        return []

    rows = db.execute(
        sa_text(
            "SELECT phc.name AS module_name, phc.pilot_id, p.name AS pilot_name, phc.config "
            "FROM pilot_hardware_config phc "
            "JOIN pilots p ON p.id = phc.pilot_id "
            "WHERE phc.name = ANY(:names) "
            "ORDER BY phc.name, p.name"
        ),
        {"names": list(module_names)},
    ).fetchall()

    groups: dict[str, list[dict]] = {}
    for row in rows:
        channels = derive_channels(row.config)
        if not channels:
            continue
        keys = derive_view_keys(row.config)
        groups.setdefault(row.module_name, []).append({
            "pilot_id": row.pilot_id,
            "pilot_name": row.pilot_name,
            "device_name": (row.config or {}).get("device_name"),
            "channels": channels,
            "keys": keys,
        })

    result = []
    for module_name in sorted(groups):
        by_pilot = sorted(groups[module_name], key=lambda p: p["pilot_name"])
        device_names = sorted({p["device_name"] for p in by_pilot})
        all_channels = sorted({c for p in by_pilot for c in p["channels"]})
        all_keys = sorted({k for p in by_pilot for k in p["keys"]}, key=_key_sort)
        conflict = len({frozenset(p["keys"]) for p in by_pilot}) > 1
        result.append({
            "module_name": module_name,
            "device_names": device_names,
            "channels": all_channels,
            "keys": all_keys,
            "conflict": conflict,
            "by_pilot": by_pilot,
        })
    return result
