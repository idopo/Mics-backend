# Phase 25: Detector-derived view keys visible in the FDA editor — Context

**Gathered:** 2026-07-29
**Status:** Ready for re-planning (supersedes the first plan set at `c38ee36`/`c697089`/`553ecff`)
**Source:** Direct decision with the user, mid-review of the first plan set

---

<domain>
## Phase Boundary

Phase 24 made a hardware trigger **write** into a detector's per-electrode view keys
(`LICKER1…LICKER4`), rig-proven with no Python callback. Phase 25 makes those channels **usable
from the editor** — as transition-condition and state-body operands — and resolves them per pilot
before START.

What changed on 2026-07-29: the first plan set stored the *literal* key (`LICKER2`) in the task
definition. The user identified that this puts a per-pilot name inside a pilot-agnostic artifact.
The phase now stores a **detector reference + channel index** and resolves the name at runtime.
</domain>

---

<decisions>
## Implementation Decisions (LOCKED)

### D1 — Condition operands reference the detector and channel, never the resolved key

A transition or if-action operand stores:

```json
{"view_detector": {"ref": "MPR121", "channel": 2}}
```

The editor shows *"MPR121 — channel 2"*. The Pi resolves it to `f"{device_name}{channel}"` at
build time from the referenced hardware object, exactly as the Phase 24 `view` **action** already
resolves `{device_name}` from its `source_ref` (`mics_task.py:689-716`). The literal key
(`LICKER2`, `TONGUE2`, …) never enters the stored JSON.

**Why this and not the alternatives:**
- Renaming `device_name` on a pilot leaves every task definition untouched and correct. Under the
  literal-key design a rename silently orphaned stored definitions, and the only signals were an
  "(unknown)" tag if you happened to reopen the definition, or a preflight issue if you tried to
  start. It would **not** raise the red `!` badge — that is driven by `validation_status`, computed
  against the *toolkit*'s flags and hardware-module refs (`api/routers/toolkits.py:684`,
  `api/routers/hardware_libs.py:320`), and `device_name` lives in a *pilot* row that nothing
  re-validates against.
- It reuses a pattern already shipped and rig-proven in Phase 24 rather than inventing one.

**Single resolution site on the Pi — verified:** `_build_transition_lambda` delegates both operands
to `_build_condition_operand` (`mics_task.py:1206-1207`) for the unified `{left, op, right}` format
the GUI emits. The `view` branch is `mics_task.py:539-542`. Legacy `{view, op, rhs}` conditions
(`mics_task.py:1214-1223`) are hand-authored v1/v2 JSON only and are **out of scope** — the GUI
never emits them.

### D2 — No hardware fact moves into the task definition

`device_name`, `num_detectors`, `first_channel` and `address` all stay in
`pilot_hardware_config.config`. Two candidate designs were rejected:

- **`device_name` into the task definition** — creates a second store. The Pi still receives its
  copy from `pilot_hardware_config` via `get_dispatch_spec` (`toolkit_dispatch.py:96-104`) →
  `_merge_prefs_hardware` (`mics_task.py:193-212`), so the two could disagree. That is precisely
  the failure DVK-01 exists to prevent.
- **`device_name` + `num_detectors` into the task definition** — `num_detectors` is a physical fact
  the definition cannot see. The Pi raises when `len(read()) < num_detectors`
  (`mics_task.py:286-291`), and two cages with different spout counts could no longer share one
  task definition. `first_channel` is literally which pins were soldered.

The dividing line: **the pilot owns what is true about the cage; the task definition owns what the
experiment means.** A channel index is experiment vocabulary. A device name is a per-rig label.

### D3 — Migration cost is zero (verified, not assumed)

All 149 rows of `task_definitions` were walked for `{"view": <str>}` operands on 2026-07-29. Six
definitions use view operands: 124 (`Mixer_AUDIO1`, `Timers_TIMER_TO_NEW_TRIAL`), 128 (`cue_led2`),
179 (`counter`), 185 (`boolean_flag`, Gili's — do not touch), 186 and 187 (`TIMER`). **Not one
references a detector channel.** Expected: the editor could never express a licker transition
(`ConditionBuilder.tsx` renders a `<select>` whose options never included `LICKER*`).

Consequence: **no migration, no dual-read, no back-compat shim for detector keys.** A stored
literal `LICKER2` is not a case that exists. DVK-05's unknown-key degrade path narrows to its real
purpose — keys the backend cannot model — and must NOT be justified by legacy detector keys.

### D4 — The DVK-02 cross-pilot union survives, demoted to advisory

The union across `pilot_hardware_config` rows is still built and still reports `conflict` with
`by_pilot` provenance — but it now only decides **what the picker offers** (which channel indices
exist, and what the resolved names would look like as a preview). Nothing pilot-specific is stored.

This makes the conflict case benign rather than dangerous: pilots disagreeing on `num_detectors`
changes which channels are *offered*, not whether a saved definition is correct.

### D5 — The trigger `view` action is untouched

`key_template: "{device_name}{pin_number}"` with `source_ref` stays exactly as Phase 24 shipped and
rig-proved (runs 478/480/481). D1 gives condition operands the same property the trigger path
already had. DVK-04's contribution is unchanged: offer the token and completions rather than free
typing.

### D6 — Channel-group labels come from `device_name`, never from the module name or a regex

The editor labels a channel group `"LICKER channels"` (from a backend-supplied `device_names`),
falling back to the module name only when absent. It must **never** recover the prefix by stripping
digits off a key — that re-implements the key format in TypeScript and breaks for any `device_name`
ending in a digit (`SPOUT2` × 4 → `SPOUT20…SPOUT23`).

A hardcoded `LICKER` in any user-facing string is the exact defect fixed twice in Phase 24
(`386e7bf`, `121c971`). Tests must assert a `TONGUE`-named device renders as `"TONGUE channels"`.

### Claude's Discretion

- The wire name of the operand key (`view_detector` is a proposal, not a mandate) — but it must be
  distinguishable from `{"view": "..."}` without ambiguity, and rejected by the validator when the
  referenced module is not a detector.
- Whether preflight (DVK-06) reports an out-of-range channel as its own issue kind or reuses
  `view_key_unresolved`.
- How the picker presents the resolved-name preview (e.g. `MPR121 — channel 2 (→ LICKER2)`).
</decisions>

---

<specifics>
## Specific Facts Verified This Session

- `scan_fda_for_refs` (`api/fda_utils.py:5-30`) walks **only** `states[*].entry_actions` and
  `trigger_assignments[*].actions`, recursing into `if` branches. It **never sees transition
  conditions**, so the new operand needs its own scanner — which plan 03 was already building for
  DVK-06. `fda_validation.py` has no view-operand validation at all today (`"view"` appears only in
  `VALID_ACTION_TYPES` at line 35 and the `key_template` check at 294).
- `validation_status` / the red `!` badge: set at `api/routers/toolkits.py:409`, the `_revalidate`
  helper at `:684`, and `api/routers/hardware_libs.py:320` (lib version removes a referenced
  method). Rendered at `TaskDefinitions.tsx:329-341`. Nothing re-validates on a
  `pilot_hardware_config` change — under D1 this no longer matters for detector keys.
- `hardware_modules` columns: `id, name, display_name, hardware_lib_id, class_name, description,
  created_at` — **no config column**. Confirmed via `\d hardware_modules`. `device_name` and
  `num_detectors` exist only in `pilot_hardware_config.config`.
- Backend test suite: 86 passing in-container (`docker exec mics_api python3 -m pytest /app/tests/ -q`).

**Carry forward unchanged from the superseded plan set** (all independently verified by the
plan-checker; do not re-derive):
- DVK-09 = scalar `first_channel` (default `0`), `range(first, first + num_detectors)`, byte-identical
  to today when absent; `curr_vals` must be indexed by absolute channel, and the length guard becomes
  `len(curr_vals) < first + num_detectors`.
- `first_channel` cannot be an instance attribute — `Touch_Detector.__init__` (`i2c.py:957-963`)
  assigns only `num_detectors`/`device_name`, and `Hardware.__init__` discards other kwargs. It must
  be read from `prefs.HARDWARE[group][name]`. `i2c.py` stays byte-identical.
- DVK-10 = narrow `execute_trigger`'s `except KeyError` (`task.py:285-298`) to the
  `self.triggers[pin]` lookup, with the error-report body itself wrapped so a raising
  `dispatch_event` cannot escape into `process_queue` (which stays untouched).
- `_build_toolkit_row` has six call sites (`toolkits.py` 121, 166, 196, 248, 361, 506); the editor
  reads **166** (`get_toolkits_by_name`). `module_detector_channels` must run at the call site and
  arrive via a new kwarg — `db` is not in scope inside the function.
- React unit tests: Node's built-in runner over `.mts` under `tests/` (outside `tsconfig` `include`),
  `node --test "tests/**/*.test.mts"`, zero new dependencies. Type-only imports must use
  `import type`.
</specifics>

---

<deferred>
## Deferred

- **Re-validating task definitions when a pilot hardware config changes** (would raise the red `!`
  on `device_name` drift). D1 removes the need for detector keys specifically; a general
  pilot-config-triggered revalidation remains unbuilt and unscoped.
- **Non-contiguous detector channels** — `first_channel` + count only, no channel list. User
  decision 2026-07-29: the extra editor UI is unjustified by contiguous 1–4 wiring.
- **`process_queue` has no exception handler** (`task.py:258-266`) — a non-`KeyError` callback
  exception permanently disables all trigger processing. User deferred; STATE.md Outstanding item 4
  must remain open.
- **Legacy hand-authored `{view, op, rhs}` transition conditions** — not GUI-emitted, out of scope.
</deferred>

---

*Phase: 25-detector-derived-view-keys-visible-in-the-fda-editor*
*Context captured 2026-07-29 — supersedes the literal-key design in the first plan set*
