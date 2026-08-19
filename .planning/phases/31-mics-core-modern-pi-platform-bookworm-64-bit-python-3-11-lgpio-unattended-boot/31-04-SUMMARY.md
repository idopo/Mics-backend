---
phase: 31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot
plan: 04
subsystem: platform
tags: [provisioning, prefs, boot-partition, bash, shellcheck, json-render]

# Dependency graph
requires:
  - phase: 31-03
    provides: "Python 3.11/numpy 1.26-importable tree, requirements.txt from a measured import closure"
provides:
  - "pilot/prefs.template.json -- the tracked, never-runtime-written prefs source (pilot/prefs.json is now gitignored)"
  - "deploy/render-prefs.sh -- idempotent every-boot render of prefs.json from template + /boot/firmware/mics.conf, atomic write, real JSON via python3, shellcheck clean"
  - "deploy/mics.conf.example -- the two-line boot-partition config a researcher edits from any laptop"
  - "tools/tree_integrity/final_checks.py f2_prefs re-pointed at the template, with all four assertions intact"
  - "tests/test_prefs_render.py (8 tests) and 8 new f2_prefs unit tests in tests/test_tree_integrity.py -- permanent gates"
affects: [31-05, 31-C1, 31-C2, 31-09]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Runtime-rendered config split: tracked template + gitignored runtime output, rendered fresh from the template on every invocation so stale runtime-written keys (e.g. SUBJECT) are dropped by construction rather than needing an explicit prune step"
    - "Atomic script writes: mktemp next to the target + mv, with an EXIT trap cleaning up the temp file on any failure, so a failed render can never leave a half-written prefs.json"
    - "BACKEND_HOST comma-separated fallback list: first entry used live, full list preserved in a sibling *_FALLBACKS key for a later self-heal, decided and documented rather than left half-implemented"

key-files:
  created:
    - /home/ido/mics_core/deploy/render-prefs.sh
    - /home/ido/mics_core/deploy/mics.conf.example
    - /home/ido/mics_core/tests/test_prefs_render.py
    - /home/ido/mics_core/pilot/prefs.template.json (renamed from pilot/prefs.json)
  modified:
    - /home/ido/mics_core/.gitignore
    - /home/ido/mics_core/tools/tree_integrity/final_checks.py
    - /home/ido/mics_core/tools/tree_protect_list.json
    - /home/ido/mics_core/tests/test_tree_integrity.py
    - /home/ido/mics_core/tests/test_shed_absences.py

key-decisions:
  - "The tree_protect_list.json edit was the single deliberate key named by the plan: runtime_generated[0].referenced_from, from 'pilot/prefs.json (PLUGIN_DB)' to 'pilot/prefs.template.json (PLUGIN_DB)'. Verified the exemption's actual behavioural key is 'path' (pilot/plugin_db.json), not referenced_from -- so this edit is documentation hygiene, not a behaviour change, exactly as the plan's <action> step 5 required. No --rebaseline run."
  - "f2_prefs now reports 'pilot/prefs.template.json is missing' rather than demanding pilot/prefs.json, satisfying the plan's own stated requirement that a fresh clone (which has no gitignored runtime file) must not fail the guard."
  - "TERMINALIP_FALLBACKS: implemented rather than dropped. BACKEND_HOST is split on commas, the first entry becomes TERMINALIP, and the full list is always written to TERMINALIP_FALLBACKS (even for a single-entry BACKEND_HOST) so the key's presence/shape never depends on how many backends are configured -- a later backend move can self-heal without a second FAT-partition edit. Documented in mics.conf.example."
  - "The render script never merges with a prior output -- it rebuilds prefs.json from the template on every invocation before applying the two substitutions. This satisfies the plan's 'drop stale runtime keys (SUBJECT) on re-render' requirement by construction, with no explicit prune/diff step needed."
  - "Atomic write via mktemp+mv, not a direct overwrite, so a render that fails partway (e.g. the CHANGE_ME safety check tripping) can never leave a corrupt or half-substituted prefs.json for the pilot to load on next boot."
  - "python3 -c (a real JSON library) chosen over sed for the substitution, per the plan's explicit preference -- makes the 'value contains / or &' shellcheck/sed-survival test moot rather than needing to write and pass one."

requirements-completed: [PLAT-08]

# Metrics
duration: ~15min
completed: 2026-08-19
---

# Phase 31 Plan 04: Prefs Template/Runtime Split and the Boot-Partition Renderer Summary

**Split `pilot/prefs.json` into a tracked `prefs.template.json` (never runtime-written) and a gitignored runtime instance, rendered idempotently every boot by a new shellcheck-clean `deploy/render-prefs.sh` from `/boot/firmware/mics.conf` — so a field unit's `git pull` never conflicts and a `mics.conf` edit takes effect on the next boot, not never.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-08-19T07:44Z
- **Completed:** 2026-08-19T07:52Z
- **Tasks:** 2 completed
- **Files modified:** 9 (1 renamed, 4 new, 5 modified)

## Accomplishments

- **Task 1:** `git mv pilot/prefs.json pilot/prefs.template.json`; added the file to `.gitignore` with a comment explaining why (`prefs.py:505-525` saves the whole file on every `set()`, `pilot.py:595` sets `SUBJECT` on every run start). Re-pointed `tools/tree_integrity/final_checks.py`'s `f2_prefs` at the template — all four assertions (parses, no `132.77.*`, no top-level `SUBJECT`/`PORT_CALIBRATION`, no `HARDWARE.UNREAL`) kept, and the MISSING message now names the template rather than demanding a runtime file a fresh clone will never have. Made the plan's one deliberate manifest edit: `tools/tree_protect_list.json`'s `runtime_generated[0].referenced_from` now reads `pilot/prefs.template.json (PLUGIN_DB)`, verified (per the plan's own guidance) to be a human breadcrumb, not the key the exemption actually resolves on (`path`, unchanged). 8 new synthetic-tree unit tests added to `tests/test_tree_integrity.py`, confirmed RED against the pre-rename `f2_prefs`, then GREEN. `tests/test_shed_absences.py`'s pre-existing `f2_prefs`/`PORT_CALIBRATION` test (from plan 02) updated to write `prefs.template.json` to match.
- **Task 2:** Wrote `deploy/render-prefs.sh` (bash, `set -euo pipefail`, shellcheck 0.9.0 clean) honouring the plan-05 contract byte-for-byte: defaults `/opt/mics/pilot/prefs.template.json` + `/boot/firmware/mics.conf` → `/opt/mics/pilot/prefs.json`, overridable via `--template`/`--conf`/`--out`. Substitutes `TERMINALIP`/`NAME` via `python3 -c` (real JSON, no `sed`), writes atomically (`mktemp` + `mv`, EXIT trap), and refuses non-zero on: missing `mics.conf`, missing template, a required key absent from `mics.conf`, or any output that would still contain `CHANGE_ME` — in every refusal case leaving an existing `prefs.json` untouched. `BACKEND_HOST` accepts a comma-separated fallback list; the first entry becomes `TERMINALIP` and the full list is preserved in `TERMINALIP_FALLBACKS`. `deploy/mics.conf.example` documents the two keys plus the fallback-list behaviour and the hostname-independence note. `tests/test_prefs_render.py` (8 subprocess-driven tests in `tmp_path`) confirmed RED against the not-yet-existing script, then GREEN on first run against the real implementation.

## Task Commits

Each task committed as TDD pairs:

1. **Task 1: rename + re-point the guard** — TDD: `01d9e6d` (test, RED verified against the pre-rename tree) → `3ce4d63` (feat, GREEN)
2. **Task 2: renderer + mics.conf.example** — TDD: `03cc450` (test, RED verified against the not-yet-existing script) → `0c5e1c1` (feat, GREEN)

All four commits are in `~/mics_core` on `phase-31-modern-pi-platform`.

## Files Created/Modified

- `/home/ido/mics_core/pilot/prefs.template.json` — renamed from `pilot/prefs.json` via `git mv`; content unchanged
- `/home/ido/mics_core/.gitignore` — added `pilot/prefs.json` with a WHY comment
- `/home/ido/mics_core/tools/tree_integrity/final_checks.py` — `f2_prefs` reads `pilot/prefs.template.json`; MISSING message names the template
- `/home/ido/mics_core/tools/tree_protect_list.json` — the plan's one deliberate manifest edit: `runtime_generated[0].referenced_from` renamed
- `/home/ido/mics_core/tests/test_tree_integrity.py` — 8 new `f2_prefs` unit tests (clean pass, missing-template message, unparseable JSON, `132.77.*`, `SUBJECT`, `PORT_CALIBRATION`, `HARDWARE.UNREAL`, a rendered `prefs.json` alongside a missing template)
- `/home/ido/mics_core/tests/test_shed_absences.py` — updated its pre-existing `f2_prefs` test to write `prefs.template.json`
- `/home/ido/mics_core/deploy/render-prefs.sh` — new, the every-boot renderer (139 lines incl. comments)
- `/home/ido/mics_core/deploy/mics.conf.example` — new, the two-key boot-partition config
- `/home/ido/mics_core/tests/test_prefs_render.py` — new, 8 subprocess-driven tests

## Decisions Made

See `key-decisions` in the frontmatter. In short: kept the manifest edit to exactly the one key the plan named; re-verified that key is documentation, not the exemption's behavioural anchor, before touching it; implemented the `TERMINALIP_FALLBACKS` option (not dropped) since it cost nothing extra to render correctly; and let "rebuild from template every run" do the stale-key-dropping work implicitly rather than writing a separate prune step.

## Deviations from Plan

None — plan executed exactly as written. Both tasks' TDD cycles went RED-for-the-expected-reason (pre-rename `f2_prefs` reading the old path; `render-prefs.sh` not existing yet) then GREEN on the first implementation attempt, with no bugs found requiring auto-fix.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required. `deploy/mics.conf.example` is a template for the researcher-facing boot-partition file; nothing here writes to a real `/boot/firmware/` or deploys to a Pi.

## Next Phase Readiness

- Plan 05 (`mics-prefs.service`) can `ExecStart=/opt/mics/deploy/render-prefs.sh` against the fixed contract this plan established (paths, exit codes) with zero renegotiation.
- `pilot/prefs.json` is now genuinely never tracked, closing the `git pull`-conflicts-on-every-experiment problem this plan existed to fix — verified live: rendering into the real repo's `pilot/prefs.json` leaves `git status --porcelain` showing nothing for that path.
- `tools/check_tree_integrity.py --strict` unchanged at 35 closure members / 30 protected files / 1 known-dangling exemption / 0 violations; `tools/pytest_delta.py` reports 0 new failures against the 187-failed/253-passed baseline.
- `requirements mark-complete PLAT-08` found no checkbox/traceability row in `REQUIREMENTS.md` (same structural gap as every prior Phase 31 plan) — completion tracked here and via `gsd-tools roadmap update-plan-progress 31` instead.

---
*Phase: 31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot*
*Completed: 2026-08-19*

## Self-Check: PASSED

All 9 created/renamed/modified file paths verified present on disk in `~/mics_core`
(`pilot/prefs.template.json`, `deploy/render-prefs.sh`, `deploy/mics.conf.example`,
`tests/test_prefs_render.py`, `.gitignore`, `tools/tree_integrity/final_checks.py`,
`tools/tree_protect_list.json`, `tests/test_tree_integrity.py`,
`tests/test_shed_absences.py`). All 4 commit hashes verified present via
`git log --oneline --all` in `~/mics_core` (`01d9e6d`, `3ce4d63`, `03cc450`,
`0c5e1c1`). This SUMMARY.md itself confirmed present in `mics-backend`.
