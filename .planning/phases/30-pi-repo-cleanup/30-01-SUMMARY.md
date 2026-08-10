---
phase: 30-pi-repo-cleanup
plan: 01
subsystem: testing
tags: [ast, static-analysis, pytest, pi-mirror, reachability-guard, tree-integrity]

# Dependency graph
requires: []
provides:
  - "tools/check_tree_integrity.py — stdlib-only reachability guard with --strict / --final / --rebaseline"
  - "tools/tree_protect_list.json — 30 protected paths + sha256 baseline + 3 reserved-absent + 1 known-dangling + 4 scan-skip + 1 runtime-generated"
  - "tests/test_tree_integrity.py — 21 synthetic-tree unit tests for the guard itself"
  - "Root pytest.ini + conftest.py replacing autopilot/pytest.ini (HYG-09)"
  - "30-PYTEST-BASELINE.json — 179 failing node IDs + reusable delta_command"
  - "30-HARDWARE-VALIDATION.md — pre-sweep baseline, md5 manifest, removal ledger"
  - "/home/ido/.hyg01-probe.txt — credential probe captured outside every repository"
affects: [30-02, 30-03, 30-04, 30-05, 30-06, 30-07, 30-08, 30-09]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Invocation-context module scanning: only `-m|import|from <mod>` counts as a module reference"
    - "Docstring-node-identity exclusion so Sphinx prose is never a dangling reference"
    - "ImportFrom alias rule gated on `__init__.py` bindings, so re-exports are not false positives"
    - "Inverted assertions: a deferred defect must stay broken, deferred code must stay commented"
    - "SELF_PATHS: a scanner must exclude its own assertion literals from every tree-wide scan"

key-files:
  created:
    - /home/ido/pi-mirror/tools/check_tree_integrity.py
    - /home/ido/pi-mirror/tools/tree_integrity/resolver.py
    - /home/ido/pi-mirror/tools/tree_integrity/scan.py
    - /home/ido/pi-mirror/tools/tree_integrity/manifest.py
    - /home/ido/pi-mirror/tools/tree_integrity/final_checks.py
    - /home/ido/pi-mirror/tools/tree_protect_list.json
    - /home/ido/pi-mirror/tests/test_tree_integrity.py
    - /home/ido/pi-mirror/pytest.ini
    - /home/ido/pi-mirror/conftest.py
    - .planning/phases/30-pi-repo-cleanup/30-PYTEST-BASELINE.json
    - .planning/phases/30-pi-repo-cleanup/30-HARDWARE-VALIDATION.md
  modified: []
  deleted:
    - /home/ido/pi-mirror/autopilot/pytest.ini
    - /home/ido/pi-mirror/autopilot/.coveragerc

key-decisions:
  - "Guard split into tools/tree_integrity/{resolver,scan,manifest,final_checks}.py to hold the CLI at 255 lines, inside the 180-300 band the plan requires"
  - "The guard's own tests live in tests/ but are deliberately NOT protect-listed — later plans may need to extend them"
  - "delta_command hardened to treat pytest exit code 2 as a collection break, not only the 'during collection' string"
  - "F3's NTP assertion inverted mid-execution per user amendment: the clock block stays commented, and its two anchor comments are asserted to survive plan 06's comment sweep"

patterns-established:
  - "Every later deletion task runs `python3 tools/check_tree_integrity.py --strict`; a wave gate never chains a bare pytest with &&"
  - "Guard calibration is proven by simulated removals (resolver patched), never by deleting from the tree"

requirements-completed: [HYG-09, HYG-12, HYG-13, HYG-01]

# Metrics
duration: 18min
completed: 2026-08-10
---

# Phase 30 Plan 01: Wave 0 Instrument Summary

**A stdlib-only AST reachability guard that is silent on the whole untouched Pi tree and loud the instant a survivor names a removed module — plus the pre-sweep baselines (pytest failure set, protected-file manifest, credential probe) every later plan measures its deltas against.**

## Performance

- **Duration:** 18 min
- **Started:** 2026-08-10T12:44:13Z
- **Completed:** 2026-08-10T13:02:20Z
- **Tasks:** 3
- **Files created/modified:** 13 (11 created, 2 deleted)

## Accomplishments

- **`check_tree_integrity.py --strict` exits 0 on the untouched tree with no assertion weakened.** The one real defect — `mics_task.py:1589` importing `autopilot.autopilot.core.pilot` — is held as **1 known violation, exempted**, under an *inverted* assertion: the reference must still be present and must still fail to resolve, so this phase cannot silently repair it.
- **Calibration reproduced the plan's independently measured numbers exactly**, in both directions:

  | Scenario | Measured | Plan predicted |
  |---|---|---|
  | Untouched tree, exemption removed | 1 raw violation (`mics_task.py:1589`) | 1 |
  | Simulated `rm hardware/unreal.py` | 13 | 13 |
  | Simulated `rm hardware/cameras.py` | 5 | 5 |
  | Simulated `rm core/subject.py` | 4 | 4 |
  | Simulated `rm core/terminal.py` + `setup/request_helpers.py` | 3 (incl. `setup_autopilot.py:198` string and `install_pyspin.sh:64/65`) | — |
  | Unparseable `.json` under 2(d) | 3, exactly the 3 named | 3 |

  Nothing was deleted to obtain these: removals were simulated by patching the resolver.
- **All four acceptance cases from `<dangling_reference_cases_the_guard_must_catch>` are caught**: the `i2c.py:8` camera import, the plugin `unreal` importers, the `.write()` string literal in `setup_autopilot.py:198`, and the shell `python -c` in `install_pyspin.sh`.
- **21 guard unit tests pass**, including both load-bearing discrimination pairs asserted as single tests (docstring vs `.write()` argument; submodule alias vs re-exported class), the bare-token regression test, the `.sh`-is-never-path-scanned test, and the F3 self-exclusion test.
- **HYG-09 landed**: root `pytest.ini` + `conftest.py` with `collect_ignore` for the 2 Pi-only modules; `autopilot/pytest.ini` and `autopilot/.coveragerc` removed. Collection produces **no error** (was exit 2).
- **Pytest failure baseline recorded**: 179 failed / 202 passed over 381 collected, with the complete 179-entry `failing_node_ids` list. The pre-existing failure set is bit-for-bit identical to the plan's pre-Wave-0 measurement — the deltas are only the 21 new guard tests.
- **HYG-01 credential probe captured** outside every repository at `/home/ido/.hyg01-probe.txt`, mode 600, 2 literal lines, verified to contain no blank line anywhere including the end.

## The reusable delta command (plans 02–09 copy this verbatim)

Never chain a bare `python3 -m pytest -q` with `&&` — the suite has 179 pre-existing failures.

```bash
cd /home/ido/pi-mirror && python3 - <<'PY'
import json,subprocess,sys
b=json.load(open('/home/ido/mics-backend/.planning/phases/30-pi-repo-cleanup/30-PYTEST-BASELINE.json'))
r=subprocess.run([sys.executable,'-m','pytest','-q','tests/'],capture_output=True,text=True)
if r.returncode == 2 or ('error' in r.stdout.lower() and 'during collection' in r.stdout):
    print('COLLECTION ERROR - not a delta, a break'); print(r.stdout[-2000:]); sys.exit(1)
now={l.split()[1] for l in r.stdout.splitlines() if l.startswith('FAILED')}
new=sorted(now-set(b['failing_node_ids']))
print('new failures:',len(new));  [print(' ',n) for n in new]
sys.exit(1 if new else 0)
PY
```

Exits 0 when the failure set is unchanged or has shrunk, 1 on any **new** failing node ID, and 1 loudly on a collection error. Smoke-tested: exits 0, `new failures: 0`.

## Task Commits

Task 1's deliverables live **entirely inside `/home/ido/pi-mirror`**, which is not agent-managed version control — the standing Pi rule forbids running any git command there, including `status`. It therefore has no commit; its evidence is the recorded verification output below and §1 of `30-HARDWARE-VALIDATION.md`.

1. **Task 1: Build check_tree_integrity.py and its tests** — no commit (pi-mirror is not a git-managed tree); verified by `pytest tests/test_tree_integrity.py` (21 passed) + `--strict` exit 0 + protect-list shape assertions
2. **Task 2: Root pytest config + recorded failure baseline** — `1f97097` (chore)
3. **Task 3: Pre-sweep baseline + HYG-01 credential probe** — `7db97ac` (docs)

## Files Created/Modified

**In `/home/ido/pi-mirror` (not version-controlled by the agent):**
- `tools/check_tree_integrity.py` (255 lines) — CLI + closure and dangling-reference checks
- `tools/tree_integrity/resolver.py` (157) — dotted-name resolution, the ImportFrom alias rule, docstring node identity
- `tools/tree_integrity/scan.py` (66) — `INVOCATION` regex, `SELF_PATHS`, skip lists, config loading
- `tools/tree_integrity/manifest.py` (89) — protected-set sha256, HYG-12 counters, inverted known-dangling assertion
- `tools/tree_integrity/final_checks.py` (207) — F1–F6 exit gate
- `tools/tree_protect_list.json` — 30 protected + 30-entry `baseline_sha256` + exemptions
- `tests/test_tree_integrity.py` (447) — 21 synthetic-tree tests
- `pytest.ini`, `conftest.py` — root config, `sys.path` bootstrap, `collect_ignore`
- **Deleted:** `autopilot/pytest.ini`, `autopilot/.coveragerc`

**In `mics-backend` (committed):**
- `.planning/phases/30-pi-repo-cleanup/30-PYTEST-BASELINE.json`
- `.planning/phases/30-pi-repo-cleanup/30-HARDWARE-VALIDATION.md`

## Decisions Made

- **Split the guard into a thin CLI plus a `tools/tree_integrity/` package.** A single file came out at 336 lines — over the project's 300-line ceiling — while the plan also required `check_tree_integrity.py` to be ≥180 lines. Splitting the manifest checks and the exit gate lands the CLI at 255, inside the band, with every module well under 300.
- **`tests/test_tree_integrity.py` is deliberately not protect-listed.** It is this phase's own instrument; later plans may legitimately extend it, and freezing its sha256 would make that a manifest violation. The protect-list holds exactly the 21 pre-existing test modules plus 9 non-test files = 30.
- **Hardened the `delta_command`** to treat pytest exit code 2 as a collection break in addition to the `'during collection'` string match. Root `addopts = -q` means `pytest -q` runs at `-qq`; the FAILED node-id lines survive that but the counts line does not, so relying on stdout text alone was thinner than it looked. A strengthening, not a weakening.
- **Suppressed `SyntaxWarning` inside the guard's AST parse.** Eleven legacy plugins carry invalid escape sequences; their warnings flooded the guard's output, and the spec requires silence on success apart from the `OK:` line. The warnings are a real (pre-existing) code-quality issue but belong to the plugin files plans 04/05 delete.

## Deviations from Plan

### Findings (recorded, not silently patched)

**Finding 1. [Rule 1 — planning arithmetic error] Task 2's "exactly 19 collectable modules" is unreachable by construction; the correct number is 20.**
- **Found during:** Task 2 (root pytest config)
- **Issue:** The plan's `<done>` computes `19 = 21 present − 2 collect_ignored`. But plan 01 Task 1 *itself* creates `tests/test_tree_integrity.py`, so by the time Task 2 runs there are 22 present, not 21. The assertion could never pass without either deleting the guard's own tests or moving them out of `tests/` — and the plan's `files_modified` and `artifacts` both place them at `/home/ido/pi-mirror/tests/test_tree_integrity.py`.
- **Fix:** Asserted **20** and recorded the full three-number chain in `30-HARDWARE-VALIDATION.md` §2 (`23 = 21 pre-existing + 2 reserved-absent`; `22 present = 21 + the guard's own tests`; `20 collectable = 22 − 2 Pi-only`). No assertion was weakened — the premise changed because this plan added a file. HYG-13's protect-list is untouched at 30 entries.
- **Verification:** `pytest --collect-only -q tests/` → 20 distinct module paths, no collection error, both Pi-only modules absent, `tests/test_tree_integrity.py` present.
- **Committed in:** `1f97097` (baseline JSON records `collectable_modules: 20` and the reconciliation text)

**Finding 2. [Coordinator amendment — user decision] F3's NTP assertion inverted mid-execution.**
- **Found during:** Task 3, before F3 had run in anger
- **Issue:** The user deferred the NTP restoration. `pilot.py:1137-1148` stays commented out and plan 06 no longer uncomments it. The original F3 asserted the calls are *live*, which would have failed `--final` at plan 08 — after every destructive plan had landed and before any rig proof — over a change the phase deliberately no longer makes.
- **Fix:** F3 now asserts `self.enable_ntp_and_wait()` and `self.disable_ntp()` appear **only** in commented form (`^\s*#\s*self\.…`) and **never** uncommented (`^\s*self\.…`), plus that both anchor comments survive (`# ---- CLOCK SETUP ----`, `# Freeze wall clock so it never jumps during the task`). The second half is the one that matters: plan 06's 244-line dead-comment sweep targets exactly this shape and would otherwise eat the deferred block invisibly.
- **Files modified:** `tools/tree_integrity/final_checks.py`, `tests/test_tree_integrity.py`
- **Verification:** New three-part test (`deferred` → 0 violations; `uncommented` → 2; `swept` → 4 incl. both comment losses). Against the real tree, F3 reports 26 violations, **none NTP-related** — all 26 belong to plans 04/05/06.
- **Committed in:** `7db97ac` (recorded as §6.7 of the validation log; the guard itself lives in pi-mirror)

### Bookkeeping

- Tree size measured 202,630,324 bytes excluding `.git` vs the plan's recorded 202,275,257. The 355 KB difference is this plan's own artifacts plus `__pycache__` from `compileall`. Recorded in §1, not a finding.

---

**Total deviations:** 2 findings recorded (1 planning arithmetic error, 1 user amendment), 0 assertions weakened.
**Impact on plan:** None on scope. Both are recorded in the validation log so plans 02–09 inherit the corrected numbers rather than rediscovering them.

## Issues Encountered

- **`autopilot/.coveragerc` removal needed a real reference check.** Filtered `grep` on this host can render a matching line blank, so the check ran as an unfiltered Python scan over the whole tree. Result: `.coveragerc` is named only by `autopilot/pytest.ini` (removed in the same change) and `autopilot/.travis.yml` (upstream CI, itself removed by plan 02). Safe.
- **The guard initially read its own assertion literals as tree content.** Resolved by a single `SELF_PATHS` set excluded from 2(b), 2(c), **2(d)** and F3/F5. Including 2(d) is not defensive symmetry: `tree_protect_list.json`'s `scan_skip` values are repo-relative glob-free paths, so the moment plans 02/03 delete those trees the guard's own protect-list would become four self-inflicted violations.

## User Setup Required

**Two human actions are still open and both are outside every repository:**

1. **Revoke the Gmail app password at Google** (account → app passwords). Must happen **before** publication. Deleting `AssociationLearning.py` is not sufficient — the credential is in `.git`, which is why publication is a fresh `git init`. The literals needed to *prove* the history is clean are captured at `/home/ido/.hyg01-probe.txt` (sha256 `63a70fd9…92f4`); do not move or edit that file.
2. **Clear `ExtlinkDemo` off pilot 1** before the HYG-02 rig session (module 62, lib 177, pilot config 21, task def 434; teardown in `18-HARDWARE-VALIDATION.md` §3). Blocks plan 09 only; Waves 0–5 are unaffected.

## Next Phase Readiness

**Wave 1 (plans 02 and 03, parallel) is unblocked.** The gate every later plan runs:

```bash
python3 /home/ido/pi-mirror/tools/check_tree_integrity.py --strict
```

Expected today: `OK: 40 closure members, 30 protected files, 1 known-dangling exemptions held, 0 violations` (plus one `note:` about `.vscode/launch.json`, which plan 03 removes).

Notes for plans 02–09:
- **Never run `--rebaseline` again.** A rebaseline after a sweep erases the evidence the manifest exists to provide.
- `--final` is expected to FAIL until Wave 5. It currently reports 45 violations across F1–F6, all owned by later plans. Do not attempt to make it pass early.
- The four `scan_skip` prefixes (`autopilot/tests/`, `autopilot/examples/`, `autopilot/docs/`, `terminal/`) are a Wave-1 convenience only; `--final` F1 asserts all four are gone.
- `mics_task.py:1589` must still read `from autopilot.autopilot.core.pilot import _write_hardware_libs`. **This phase does not repair it.**
- No git command was run in `/home/ido/pi-mirror` at any point.

## Self-Check: PASSED

All 13 claimed artifacts exist on disk; both deleted files confirmed gone; both task commits
(`1f97097`, `7db97ac`) present in git. Re-verified at summary time:
`check_tree_integrity.py --strict` exit 0, `pytest tests/test_tree_integrity.py` 21 passed.

---
*Phase: 30-pi-repo-cleanup*
*Completed: 2026-08-10*
