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
