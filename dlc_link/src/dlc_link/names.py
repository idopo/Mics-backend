"""The ONE bodypart-string to signal-name transform (D-12).

DLC bodypart names are arbitrary researcher-authored strings (`"left ear"`,
`"tail-base"`, `"Nose"`). This module is the single declaration site for turning one of
those strings into a Python identifier; no other module in this package, and no
generated artefact, may re-derive it. `dlc-link-generate` emits the resulting map as
data and `dlc_link`'s adapter/live modules IMPORT that map — they never recompute it.
An undeclared name is dropped Pi-side as `unknown_name`, invisibly from the sender's
point of view, so a divergence here is a silent total failure (D-12).

**Threat T-35-01 (this plan's threat model): this regex gate is the security boundary
of the whole phase, not a cosmetic check.** The identifier `to_identifier` returns is
interpolated verbatim into Python source that is stored in
`hardware_lib_versions.source_code` and later `exec`'d on the Pi. `to_identifier` is
total: every input either yields a value matching `^[a-z][a-z0-9_]*$`, or raises
`InvalidBodypartName`. Nothing may catch that exception and substitute a mangled
default — a mangled default is exactly the unpredictable-name failure D-12 exists to
prevent.
"""
import keyword
import re

_STRIP_RUN = re.compile(r"[^a-z0-9]+")
_VALID_IDENT = re.compile(r"^[a-z][a-z0-9_]*$")

# `alive` is reserved because `api/extlink_keys.py`'s `derive_extlink_keys`
# unconditionally adds `f"{source_id}.alive"` to every module's key set — a bodypart
# named `alive` would collide with the liveness key. The rest guard against shadowing
# names this package's own generated classes and call sites depend on.
_RESERVED_NAMES = frozenset(
    {"alive", "self", "release", "bind", "source_id", "role", "stale_ms"}
)


class InvalidBodypartName(ValueError):
    """Raised when a DLC bodypart string cannot produce a safe Python identifier.

    Never swallow this and never fall back to a mangled default — see the module
    docstring's T-35-01 note.
    """


def to_identifier(bodypart: str) -> str:
    """Convert one DLC bodypart string into a safe Python identifier, or raise.

    Lowercases the string, collapses every maximal run of characters outside
    `[a-z0-9]` into a single `_`, and strips leading/trailing `_`. The result must then
    be non-empty, match `^[a-z][a-z0-9_]*$` (a leading digit is REJECTED rather than
    silently prefixed — silent prefixing would produce a name the researcher cannot
    predict, exactly the failure D-12 exists to prevent), not be a Python keyword or
    soft keyword, and not collide with this package's reserved names.
    """
    lowered = bodypart.lower()
    collapsed = _STRIP_RUN.sub("_", lowered).strip("_")

    if not collapsed:
        raise InvalidBodypartName(
            "bodypart {!r} produces an empty identifier after normalisation".format(bodypart)
        )
    if not _VALID_IDENT.match(collapsed):
        raise InvalidBodypartName(
            "bodypart {!r} normalises to {!r}, which does not match ^[a-z][a-z0-9_]*$ "
            "(a leading digit is rejected rather than silently prefixed)".format(
                bodypart, collapsed
            )
        )
    if keyword.iskeyword(collapsed) or keyword.issoftkeyword(collapsed):
        raise InvalidBodypartName(
            "bodypart {!r} normalises to {!r}, which is a Python keyword".format(
                bodypart, collapsed
            )
        )
    if collapsed in _RESERVED_NAMES:
        raise InvalidBodypartName(
            "bodypart {!r} normalises to {!r}, which is reserved by dlc_link "
            "(collides with a signal or field name every module already uses)".format(
                bodypart, collapsed
            )
        )
    return collapsed


def signal_names_for(ident: str, coords: bool) -> list:
    """Signal names for one identifier. Likelihood is always present, even when
    `coords` is False — per D-17, likelihood is the guard that makes a coordinate
    usable at all, not merely the cheap signal.
    """
    names = ["{}_likelihood".format(ident)]
    if coords:
        names.append("{}_x".format(ident))
        names.append("{}_y".format(ident))
    return names


def build_name_map(pose_order: list, wanted: list, coords_for: set) -> dict:
    """Build the bodypart -> signal-name map the generator emits and the adapter imports.

    `pose_order` is the AUTHORITATIVE row order of the model runner's pose array —
    the list of bodypart strings such that `pose[i]` is `pose_order[i]`. It is NOT the
    config's declared order: D-42 records that DLC-Live's documentation states only
    that `single_animal=True` yields `(num_bodyparts, 3)`, and says nothing about
    whether that is the 10 multianimal parts or all 32, nor about row order. A caller
    passing the config's declared order here is passing an unverified guess.

    `wanted` is the ordered selection of bodypart strings to emit signals for.
    `coords_for` is the subset of `wanted` that additionally gets x and y.

    Returns an ordered mapping:
        {original_bodypart: {"ident": ..., "index": <position in pose_order>,
                              "coords": bool, "signals": {"likelihood": ..., "x": ..., "y": ...}}}

    `index` is the position in `pose_order`, NEVER in the filtered `wanted` list — the
    adapter indexes the pose array by it, and an off-by-one here sends the wrong
    keypoint's numbers under the right name (T-35-02b), the worst failure mode
    available.

    Collision detection runs over the WHOLE of `pose_order`, not just `wanted` — the
    model's full keypoint space must be unambiguous before any subset of it is
    selected, so a later expansion of `wanted` can never introduce a silent merge that
    an earlier, narrower selection let through (T-35-02).
    """
    if not set(coords_for) <= set(wanted):
        extra = sorted(set(coords_for) - set(wanted))
        raise InvalidBodypartName(
            "coords_for entries {!r} are not present in wanted {!r}".format(extra, wanted)
        )

    pose_index_by_bodypart = {}
    ident_by_bodypart = {}
    original_by_ident = {}
    for index, bodypart in enumerate(pose_order):
        pose_index_by_bodypart[bodypart] = index
        ident = to_identifier(bodypart)
        if ident in original_by_ident and original_by_ident[ident] != bodypart:
            raise InvalidBodypartName(
                "bodyparts {!r} and {!r} both normalise to identifier {!r} — refusing "
                "to silently merge them".format(original_by_ident[ident], bodypart, ident)
            )
        original_by_ident[ident] = bodypart
        ident_by_bodypart[bodypart] = ident

    name_map = {}
    for bodypart in wanted:
        if bodypart not in pose_index_by_bodypart:
            raise InvalidBodypartName(
                "wanted bodypart {!r} is absent from pose_order; pose_order contains "
                "{!r}".format(bodypart, pose_order)
            )
        ident = ident_by_bodypart[bodypart]
        coords = bodypart in coords_for
        names = signal_names_for(ident, coords)
        signals = {"likelihood": names[0]}
        if coords:
            signals["x"] = names[1]
            signals["y"] = names[2]
        name_map[bodypart] = {
            "ident": ident,
            "index": pose_index_by_bodypart[bodypart],
            "coords": coords,
            "signals": signals,
        }
    return name_map


def flat_signal_names(name_map: dict) -> list:
    """Every emitted signal name across `name_map`, sorted and de-duplicated — the
    generator, the converter and the tests all need the same canonical list.
    """
    names = set()
    for entry in name_map.values():
        names.update(entry["signals"].values())
    return sorted(names)
