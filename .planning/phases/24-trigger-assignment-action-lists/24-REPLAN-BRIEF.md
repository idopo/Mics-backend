# Phase 24 — Re-plan Brief for Plans 06 / 07 / 08

**Date:** 2026-07-27
**Trigger for re-plan:** user decision — *"we are only working with sourceless toolkits from
now on... no need to run legacy learning_cage backed toolkit"*, with the clarification that
`check_for_detectors` / `detect_change` functionality **must still exist**, just via the
sourceless (backend-authored) path rather than the `learning_cage` Python class.

**Recommended entry point:** `/gsd:discuss-phase 24` — **not** `/gsd:plan-phase 24 --gaps`.
`--gaps` reads VERIFICATION.md and writes fix plans against requirements it assumes still
hold. Here two requirements need rewording and one needs a different home. That is
requirement-level drift.

**Plans 01–05 are unaffected** and already executed. They contain no `learning_cage`
dependency. See `24-HARDWARE-VALIDATION.md` for what is proven on hardware.

---

## 1. Requirement-by-requirement

### Plan 24-06

| Req | Disposition | Rationale |
|---|---|---|
| **TRIGA-11** | **DROP** | *"No Python callback registered for `TOUCH_INT`"* is vacuous on a sourceless toolkit: it dispatches to `mics_task` and never had a Python callback. The grep-based proof tests a property that cannot exist. Its rig-proof half is superseded by run 475 (already achieved) — see the validation log. |
| **TRIGA-12** | **KEEP — now load-bearing** | Was a robustness fix for a hypothetical registry-declared detector. `MPR121` is now registered as hardware module 7, so it is the actual path. `check_for_detectors` (`mics_task.py:261`) filters with `isinstance(v, Touch_Detector)` against the class imported at line 17, while `_resolve_hardware_classes` `exec`s the registry copy into a fresh namespace → **different class object** → zero matches → no `LICKER0..3` trackers → a `view` action writes a missing key with **no exception and no data**. This single change is what stands between the current state and working lick detection. |
| **TRIGA-05** | **KEEP, retarget** | The `detectedLick` *pattern* (choose the target tracker from a returned value) is still the goal; only the reference implementation changes from `learning_cage.detectedLick` to a UI-built list on a sourceless toolkit. |

**Note:** `learning_cage.py` edits from plan 24-01 (`SEMANTIC_HARDWARE`) are deployed and
harmless, but irrelevant to the sourceless path — see §2.

### Plan 24-07 (rig proof)

Checkpoint 3 is written entirely around unregistering `self.triggers['TOUCH_INT']` and
grepping to prove it. **Rewrite required**, not re-scoping.

- **Checkpoint 1 (UI round-trip)** — survives, and should run **first**, not last. Five of the
  seven defects in the validation log were in the UI↔API seam and only surfaced by using the
  editor. Doing this checkpoint early is now evidence-backed, not a preference.
- **Checkpoint 2 (422 negative cases)** — survives; already partly executed (8 live cases pass).
- **Checkpoint 3** — replace with: build the lick action list on toolkit 100, run, touch each
  of the four electrodes, confirm `LICKER0..3` update with `pi_timestamp`. Depends on TRIGA-12.

Two stale mechanics to fix while rewriting:
1. It specifies `git -C /home/ido/pi-mirror status --porcelain …/i2c.py`. The project's
   `pi-deploy` skill **forbids all git operations in `pi-mirror`**. Use instead:
   `diff <(ssh -i ~/.ssh/pi_mics pi@132.77.72.28 'cat ~/Apps/.../i2c.py') /home/ido/pi-mirror/.../i2c.py`
2. It says `cd ~/pi-mirror && python3 -m pytest` — that is the **dev host**, where `autopilot`
   cannot import (`npyscreen`). The correct path is
   `cd ~/Apps/mice_interactive_home_cage` **on the Pi**, user-run.

### Plan 24-08

| Req | Disposition | Rationale |
|---|---|---|
| **TRIGA-13** | **REWORD — design gap** | Derives detector view keys at HANDSHAKE from `prefs.HARDWARE` (`device_name` × `num_detectors`). A registry-declared detector **is not in `prefs.HARDWARE`** — it arrives per-run via `PREFS_HARDWARE` in the START payload. The Pi structurally cannot derive these keys for the sourceless path. The **backend** can, from `pilot_hardware_config` — which is essentially Phase 25 DVK-01/02/06. Decide: move to Phase 25, or re-scope TRIGA-13 as a backend derivation. |
| **TRIGA-14** | Partly delivered | The `ArgInput` half (flag options = toolkit flags ∪ variables) landed in plan 24-03. The `ConditionBuilder` operand half remains. |
| **TRIGA-15** | **KEEP, adjust** | `trigger_name` is still a free-text box; a typo saves cleanly and silently never fires. Needs the `trigger_sources` column. **Adjustment:** `Digital_Out.is_trigger = True` (gpio.py:343), not only `Digital_In` — so the naive predicate lists every LED as a trigger source. Decide whether that is acceptable or the predicate needs narrowing. |

---

## 2. Constraints discovered this session (not in any existing plan)

1. **A sourceless task receives ONLY the `Modules` group.** `mics_task.py:94` does
   `self.HARDWARE = self._resolve_hardware_classes(kwargs["HARDWARE"])` — a **wholesale
   replace** — and `get_dispatch_spec` only ever emits `hardware["Modules"]`. So a
   backend-authored task has no `GPIO`, `I2C`, `Timers` or `UNREAL` groups at all.
   **Everything a sourceless task touches must be a registered hardware module.** This also
   makes `SEMANTIC_HARDWARE` on Pi classes irrelevant for this path, including the entry
   plan 24-01 added to `learning_cage`. This constraint should be written down explicitly —
   consider whether replace-vs-merge is the right semantic.

2. **Registry prerequisites are now satisfied** (were blockers when the re-plan was first
   scoped): modules 7 (`MPR121`/`Touch_Detector`) and 8 (`TOUCH_INT`/`Digital_In`) exist with
   pilot-1 configs and are attached to toolkit 100.

3. **Hardware action `method` is unvalidated by the backend.** `fda_validation` checks
   `CALLABLE_METHODS` only for `type:"method"`. `{type:"hardware", ref:"MPR121", method:""}`
   returns 200 and is a silent no-op on the Pi — the exact failure class TRIGA-07 exists to
   prevent. AST metadata for hardware libs already exists, so this is implementable.
   **Add as a new requirement.**

4. **The editor's save/refetch model was never exercised by withheld saves.** Autosave
   replaces the whole `trigger_assignments` array, and (until `4ac5a18`) any React Query
   refetch overwrote in-progress local state. Both surfaced only once incomplete
   assignments legitimately stopped saving. Any future plan that adds validation gates to
   editor-driven data should account for this interaction explicitly.

5. **ES cannot verify action arguments.** `@log_action` records kwargs only, so
   `hardware.set(x)` never logs `x`, and the envelope `level` on a `set` event is the
   post-call hardware state. Any acceptance criterion of the form "confirm the action
   passed value N" is **unverifiable from ES today** and must either use `Tracker.set`
   (which does log `value`) or add argument logging.

6. **TRIGA-06's DB claim is wrong.** It states task def 185 is the only row with non-empty
   `trigger_assignments` (live check, 2026-07-26). Task def **181** has one too and caused
   three defects. Any cleanup step must re-run the query, not trust the recorded finding.

---

## 3. Suggested phase shape after re-plan

- **06′** — TRIGA-12 capability matching in `check_for_detectors` (+ TRIGA-05 retargeted).
  Small, high-value, unblocks everything downstream.
- **07′** — rewritten rig proof: checkpoint 1 moved to the front; checkpoint 3 = four
  electrodes → `LICKER0..3` on a sourceless toolkit.
- **08′** — TRIGA-15 (`trigger_sources` + dropdown) and the new hardware-`method` validation
  requirement. TRIGA-13 decision: keep here as a backend derivation, or hand to Phase 25.
