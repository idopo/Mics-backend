"""FDA view-key/detector-ref scanner + per-pilot resolver (Plan 25-03, DVK-02/06/11).

Split out of `api/detector_keys.py` to respect that file's 300-line budget (plan constraint) —
`detector_keys.py` re-exports both public functions here, so `from detector_keys import
scan_fda_view_keys, resolve_view_key_issues` keeps working for every consumer.

`scan_fda_view_keys` is pilot-agnostic (a pure scan of the FDA JSON). `resolve_view_key_issues`
is pilot-specific — it classifies the scan against ONE pilot's declared hardware config and
produces `preflight_validate` issues. Do not move pilot-specific resolution into
`fda_validation.py` — save-time validation stays pilot-agnostic (see that module's docstring).
"""
import re

from fda_utils import scan_fda_condition_operands

_TOKEN_RE = re.compile(r"\{(\w+)\}")

# `_key_sort` is imported lazily (inside the two functions below that need it), not at module
# level: `detector_keys.py` re-exports this module's public functions via a bottom-of-file
# import, so a module-level `from detector_keys import _key_sort` here would deadlock whichever
# of the two modules imports first. Both modules are fully loaded by the time either function
# is actually called, so the lazy import is not fragile — only the module-level one would be.


def _walk_view_actions(location: str, actions) -> list[dict]:
    """Sibling of `fda_utils._scan_actions`: walks the SAME action lists (entry_actions,
    trigger_assignments[*].actions, `if`-action then/else) but extracts `type: "view"`
    key_templates instead of hardware/flag/timer/method refs. There are now two action
    walkers over one shape, for two different targets — `_scan_actions` returns hardware
    refs, this returns key templates.
    """
    if not isinstance(actions, list):
        return []
    results: list[dict] = []
    for i, action in enumerate(actions):
        if not isinstance(action, dict):
            continue
        action_type = action.get("type")
        if action_type == "view":
            key_template = action.get("key_template")
            if isinstance(key_template, str) and key_template:
                results.append({
                    "location": f"{location}[{i}].key_template",
                    "kind": "key_template",
                    "value": key_template,
                    "ref": action.get("source_ref"),
                    "channel": None,
                })
        elif action_type == "if":
            results.extend(_walk_view_actions(f"{location}[{i}].then", action.get("then")))
            results.extend(_walk_view_actions(f"{location}[{i}].else", action.get("else")))
    return results


def scan_fda_view_keys(fda_json: dict) -> list[dict]:
    """Every place a view key or detector channel is named across the FDA. Never raises.

    A COMPOSITION, not a walker: the condition half is entirely delegated to
    `fda_utils.scan_fda_condition_operands` (plan 01 task 3) — the ONE condition walker,
    shared with the save-time gate — classified here into `operand`/`detector` results. The
    action half (`key_template`) is this function's own, via `_walk_view_actions` above.

    `{"tracker": ...}` is NOT a Pi view operand (`mics_task.py` maps both `tracker` and `flag`
    to `self.flags[key].value`, never `self.view`) but is scanned here as one anyway, for
    preflight purposes only: the resolver's valid-key set already includes every toolkit flag,
    so a legitimate `{"tracker": "some_flag"}` resolves clean and a flag-shaped key that is not
    a real view key produces, at worst, a false negative. Do not "fix" the UI/Pi naming
    mismatch here — see the plan's <interfaces> note.

    -> [{"location": "transitions[0].condition_tree.left",
         "kind": "operand" | "detector" | "key_template",
         "value": "LICKER0" | None,       # literal key, or raw template; None for a detector
         "ref": "MPR121" | None,          # detector ref, or a view action's source_ref
         "channel": 2 | None},            # detector channel only
        ...]
    """
    if not isinstance(fda_json, dict):
        return []
    results: list[dict] = []

    for entry in scan_fda_condition_operands(fda_json):
        operand = entry["operand"]
        if not isinstance(operand, dict):
            continue
        location = entry["location"]
        if "view" in operand or "tracker" in operand:
            value = operand.get("view") if "view" in operand else operand.get("tracker")
            if isinstance(value, str):
                results.append({"location": location, "kind": "operand", "value": value, "ref": None, "channel": None})
        elif "view_detector" in operand:
            vd = operand["view_detector"]
            if isinstance(vd, dict):
                ref, channel = vd.get("ref"), vd.get("channel")
                if isinstance(ref, str) and ref and isinstance(channel, int) and not isinstance(channel, bool) and channel >= 0:
                    results.append({"location": location, "kind": "detector", "value": None, "ref": ref, "channel": channel})

    states = fda_json.get("states")
    if isinstance(states, dict):
        items = list(states.items())
    elif isinstance(states, list):
        items = [
            (s.get("name") or f"[{i}]", s) if isinstance(s, dict) else (f"[{i}]", None)
            for i, s in enumerate(states)
        ]
    else:
        items = []
    for state_name, state_body in items:
        if not isinstance(state_body, dict):
            continue
        results.extend(_walk_view_actions(f"states.{state_name}.entry_actions", state_body.get("entry_actions")))

    trigger_assignments = fda_json.get("trigger_assignments")
    if isinstance(trigger_assignments, list):
        for i, ta in enumerate(trigger_assignments):
            if not isinstance(ta, dict):
                continue
            results.extend(_walk_view_actions(f"trigger_assignments[{i}].actions", ta.get("actions")))

    return results


def _detector_issue(location: str, ref: str, channel: int, channels: list[int], device_name: str | None) -> dict:
    """R1/R2: one `view_key_unresolved` issue carrying the `detector`/`available_channels`
    fields and the resolved key name, even though the stored FDA never carries that name."""
    from detector_keys import _key_sort

    resolved_device_name = device_name or ref
    resolved_key = f"{resolved_device_name}{channel}"
    sorted_channels = sorted(channels)
    module_keys = sorted((f"{resolved_device_name}{c}" for c in sorted_channels), key=_key_sort)
    return {
        "module_id": None,
        "module_name": ref,
        "issue": "view_key_unresolved",
        "detail": (
            f"{location}: references {ref} channel {channel}, which would be '{resolved_key}' on "
            f"this pilot. This pilot's {ref} has channels {', '.join(str(c) for c in sorted_channels)} "
            f"({', '.join(module_keys)})."
        ),
        "location": location,
        "key": resolved_key,
        "available_keys": module_keys,
        "detector": {"ref": ref, "channel": channel},
        "available_channels": sorted_channels,
    }


def _literal_issue(location: str, module_name: str, key: str, available_keys: list[str]) -> dict:
    """R1: the same issue kind as `_detector_issue`, but without the `detector`/
    `available_channels` fields — a renderer that ignores those fields still renders
    something correct."""
    return {
        "module_id": None,
        "module_name": module_name,
        "issue": "view_key_unresolved",
        "detail": (
            f"{location}: names view key '{key}', which this pilot does not have. "
            f"This pilot's detector channels: {', '.join(available_keys) if available_keys else '(none)'}."
        ),
        "location": location,
        "key": key,
        "available_keys": available_keys,
    }


def resolve_view_key_issues(
    fda_json: dict,
    valid_keys: set[str],
    device_names: dict[str, str],
    module_channels: dict[str, list[int]],
    detector_keys: list[str],
    skip_modules: set[str] | None = None,
) -> list[dict]:
    """`scan_fda_view_keys` classified against ONE pilot's actual wiring -> preflight issues,
    in the shape `preflight_validate` already returns. Never raises on a malformed scan entry.

    `module_channels` is `{module_name: derive_channels(cfg)}` for this pilot — the DVK-11
    range check. `device_names` is `{module_name: cfg["device_name"]}` — used for both
    `{device_name}` template resolution and the resolved-name diagnostic (R2). `detector_keys`
    is the flat, pilot-wide list of derived keys shown as `available_keys` on a literal-key
    issue (a mistyped key has no module context to scope the suggestion to). `skip_modules` is
    `preflight_validate` step 7's `already_flagged` (R3) — only the `detector` branch consults
    it; a module already reported `missing` in step 6 is not reported again for an
    out-of-range channel either.

    Precision over coverage (module docstring of the plan): every branch below that "reports
    nothing" is deliberate — see the plan's <interfaces> resolution-rules table.
    """
    from detector_keys import _key_sort

    skip_modules = skip_modules or set()
    global_available_keys = sorted(detector_keys, key=_key_sort)
    issues: list[dict] = []

    for entry in scan_fda_view_keys(fda_json):
        kind = entry["kind"]
        location = entry["location"]

        if kind == "detector":
            ref, channel = entry["ref"], entry["channel"]
            if ref in skip_modules or ref not in module_channels:
                continue
            channels = module_channels[ref]
            if channel in channels:
                continue
            issues.append(_detector_issue(location, ref, channel, channels, device_names.get(ref)))
            continue

        if kind == "operand":
            key = entry["value"]
            if key not in valid_keys:
                issues.append(_literal_issue(location, "", key, global_available_keys))
            continue

        # kind == "key_template"
        template, ref = entry["value"], entry["ref"]
        tokens = set(_TOKEN_RE.findall(template or ""))
        if "device_name" not in tokens:
            if not tokens and template not in valid_keys:
                issues.append(_literal_issue(location, ref or "", template, global_available_keys))
            continue  # tokens present but no {device_name} -> unresolvable statically (report nothing)

        device_name = device_names.get(ref) if ref else None
        if not device_name:
            issues.append(_literal_issue(location, ref or "", template, global_available_keys))
            continue

        resolved = template.replace("{device_name}", device_name)
        if _TOKEN_RE.search(resolved):
            continue  # e.g. "{device_name}{pin_number}" — varies per interrupt, never guessed
        if resolved not in valid_keys:
            issues.append(_literal_issue(location, ref or "", resolved, global_available_keys))

    return issues
