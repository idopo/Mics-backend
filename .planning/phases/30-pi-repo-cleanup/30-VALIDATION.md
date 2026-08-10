---
phase: 30
slug: pi-repo-cleanup
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-08-10
verified: 2026-08-10
---

# Phase 30 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

**What makes this phase's validation unusual:** it is removal-only, so the classic
"write a failing test, then implement" loop does not apply — there is no new behaviour to
assert. The property under test is a **negative**: that nothing which is still reachable was
removed, and that nothing removed is still referenced. Two further constraints shape everything
below:

1. **`autopilot` cannot be imported on this host** (`npyscreen` absent), so `py_compile` /
   `compileall` is the ceiling for agent-run verification of the Pi tree. No agent-run test can
   instantiate a `Task`, a `Hardware`, or the registry.
2. **The Pi's dominant failure mode is silence.** There is no `TASK_ERROR` emitter anywhere on
   the Pi (`pilot.py:609` catches a failed START, sets state IDLE, reports nothing), so a
   removal that breaks dispatch presents as a run stuck `running` forever, not as an error. An
   import check therefore cannot be the acceptance gate — HYG-02's live session is.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend, in-container) + `compileall` for the Pi tree |
| **Config file** | backend: none at repo root (in-container `tests/`); Pi tree: **none — Wave 0 adds one** (HYG-09 removes `autopilot/pytest.ini`, the tree's only pytest config) |
| **Quick run command** | `python3 -m compileall -q /home/ido/pi-mirror/autopilot /home/ido/pi-mirror/tools /home/ido/pi-mirror/tests` |
| **Full suite command** | `python3 /home/ido/pi-mirror/tools/check_tree_integrity.py --strict && docker compose exec -T api python -m pytest -q tests/` |
| **Estimated runtime** | quick ~4 s · full ~12 s (integrity guard ~10 s, backend suite ~1.2 s / 352 tests) |

**Note on the backend suite:** it is in scope only because HYG-05 edits `hardware_libs`
version 26 (the `exec()`'d `i2c.py` copy). No other requirement touches backend code.

---

## Sampling Rate

- **After every task commit:** `compileall` over the surviving tree (~4 s).
- **After every removal task specifically:** `check_tree_integrity.py` (~10 s) — a removal is
  exactly the operation that can silently orphan an import, so the guard runs on the same
  cadence as the deletions, not per wave.
- **After every plan wave:** full suite.
- **Before `/gsd:verify-work`:** full suite green **and** the HYG-02 rig session recorded in
  `30-HARDWARE-VALIDATION.md`.
- **Max feedback latency:** 12 s for anything agent-run. The rig proof is inherently
  human-latency and is scheduled once, at the end, not sampled.

---

## Wave 0 Requirements

This phase's Wave 0 is unusually load-bearing: it builds the instrument that makes every later
removal checkable. **Without it, HYG-07 and HYG-13 have no automated verification at all** and
the sweep degrades to eyeballing.

- [ ] `/home/ido/pi-mirror/tools/check_tree_integrity.py` — the reachability guard. Three
      assertions, all derived from the audit and all runnable on this host without importing
      `autopilot`:
      1. **Closure completeness** — recompute the static import closure from
         `autopilot/autopilot/core/pilot.py` by AST, following in-function imports (this
         codebase lazily imports a lot), and assert every file in the closure exists.
      2. **No dangling references** — for every removed path, assert no surviving `.py`, `.sh`,
         `.json` or `prefs` entry still names it. This is the check that would have caught
         `cameras.py` (`i2c.py:8`) and `unreal.py` (15 plugin importers).
      3. **Survival manifest** — assert the HYG-13 protect-list is present verbatim: the five
         `external_hardware*` files, all 23 root test modules, `fda_vocabulary.py`, and the
         Phase 26 reserved names are absent-but-not-flagged.
- [ ] `/home/ido/pi-mirror/tests/test_tree_integrity.py` — unit tests for the guard itself,
      covering: a synthetic tree with a dangling import fails assertion 2; a tree missing a
      closure member fails assertion 1; a clean tree passes all three.
- [ ] `/home/ido/pi-mirror/pyproject.toml` (or `pytest.ini`) + `conftest.py` — the root pytest
      config HYG-09 requires, replacing `autopilot/pytest.ini`. Must set `pythonpath` so the 21
      existing test modules stop relying on per-file `sys.path` hacks, **and must
      `collect_ignore` `test_compute_ops.py` and `test_log_action_values.py`**, which import
      `autopilot` at top level and therefore cannot be collected on this host (npyscreen). Mark
      them Pi-only with a comment naming the gap. **Landing this before any deletion means the
      suite is runnable throughout the sweep rather than only at the end.**
- [ ] **A recorded failure-count baseline.** The root suite has pre-existing failures, so no gate
      may chain a bare `python3 -m pytest -q` with `&&`. Gates assert a *delta* against the Wave 0
      baseline, or deselect known-failing node IDs explicitly.
- [ ] **A `known_dangling` exemption in the guard's protect-list.** `mics_task.py:1589` imports
      `autopilot.autopilot.core.pilot`, which does not resolve — the guard flags it on its first
      run against the *untouched* tree. 30-CONTEXT.md defers that defect, so the guard must assert
      it is **still** dangling (so it cannot be silently repaired inside this phase) rather than
      fail on it. Wave 0's baseline is "1 known violation, exempted", not zero.

**Deliberate scope note:** the guard is a permanent artifact, not scaffolding. It ships in the
new repo and re-runs on any future tree change, which is what makes HYG-07's "reproducible from
criteria, not from a hand-list" claim true rather than aspirational.

---

## Per-Requirement Verification Map

Task IDs are assigned by the planner; this maps requirements to their verification so the
planner can attach the right `<verify><automated>` block to each task it creates.

| Requirement | Test Type | Automated Command | File | Status |
|---|---|---|---|---|
| HYG-01 credential absent from history | integration | `git -C <new-repo> log -p \| grep -c -F -f /home/ido/.hyg01-probe.txt` → expect 0 | new repo | ⬜ pending |
| HYG-02 pilot starts + session runs | **manual (rig)** | — see Manual-Only | — | ⬜ pending |
| HYG-03 plugin cluster removed, ordering held | unit | `check_tree_integrity.py --strict` (assertions 1+2) | `tools/check_tree_integrity.py` | ❌ W0 |
| HYG-04 empty HANDSHAKE is a no-op | integration | `curl -s -XPOST $API/pilots/{id}/tasks -d '{"tasks":[]}'` → assert `tasks_received: 0`, row count unchanged before/after | live API | ⬜ pending |
| HYG-05 `cameras.py` + both import copies | unit + integration | `check_tree_integrity.py` (assertion 2) **and** `docker compose exec -T api python -m pytest -q tests/` | guard + backend suite | ❌ W0 |
| HYG-06 sweep collateral removed, `tasks/` compiles | unit | `python3 -m compileall -q ~/pi-mirror/autopilot/autopilot/tasks` → exit 0 | — | ⬜ pending |
| HYG-07 Terminal tree removed | unit | `check_tree_integrity.py` (assertion 2) | guard | ❌ W0 |
| HYG-08 vendored/generated bulk removed | unit | `du -s` assertion in guard: tree ≤ **8 MB** excluding `.git` **and excluding `pilot/sounds/`** | guard | ❌ W0 |
| HYG-09 root pytest config replaces `pytest.ini` | unit | `cd ~/pi-mirror && python3 -m pytest --collect-only -q tests/` → **exactly 19** distinct `tests/*.py` module paths (21 present − 2 `collect_ignore`d Pi-only modules), no collection error | root config | ❌ W0 |
| HYG-10 no rig-specific config | unit | guard assertion: `prefs.json` contains no `132.77.*`, no `SUBJECT`, no `PORT_CALIBRATION`, no `UNREAL` key | guard | ❌ W0 |
| HYG-11 244 dead lines removed | unit | `python3 -m compileall -q` + guard assertion 1 (closure intact after edits) | — | ⬜ pending |
| HYG-12 `Event_Dispatcher.py` fixes survive | unit | grep assertion in guard: `_dropped_no_clock` and `_dropped_on_send` both present | guard | ❌ W0 |
| HYG-13 survival manifest intact | unit | `check_tree_integrity.py` (assertion 3) | guard | ❌ W0 |
| HYG-14 restorations applied, holds resolved | unit | grep assertions: `enable_ntp_and_wait()` / `disable_ntp()` still present **and still commented** at `pilot.py:~1137` (restoration **deferred by the user 2026-08-10**; the gate guards against the sweep deleting them, not against them being commented); `logger.warning` restored at `station.py:~1333`; `open_file` absent. **Toggle removal asserts the commented *toggle forms*, never bare tokens** — absence of `set_cdc_manual(0x3f)`, of `self.triggers['IR1']`, and of `pulse_and_notify(...OG_TRIGGER...)` | guard | ❌ W0 |

*Status: ⬜ pending · ✅ green · ❌ W0 (blocked on Wave 0 artifact) · ⚠️ flaky*

**Sampling continuity check:** no three consecutive removal tasks can run without the guard,
because the guard is the only thing that detects an orphaned import. The planner must attach
`check_tree_integrity.py --strict` to **every** task whose `files_modified` includes a deletion.

> **Never assert a bare identifier tree-wide.** `IR1` and `OG_TRIGGER` are **live hardware
> declarations** in `pilot/prefs.json` (`HARDWARE.GPIO.IR1`, `HARDWARE.GPIO.OG_TRIGGER`) and
> survive this phase by design — HYG-10 deliberately leaves the `GPIO`, `I2C`, `Mixer`, `Timers`
> and `Modules` groups alone. What HYG-14 retires is the *commented-out toggle*, not the pin
> declaration. A tree-wide `! grep -q 'OG_TRIGGER'` therefore fails at the exit gate and, because
> the plans forbid weakening an assertion to make it pass, the only compliant response would be
> stripping live GPIO entries from `prefs.json` after every destructive plan has landed and
> before any rig proof. Assert the toggle's call form, never the token.
>
> The same trap applies to docstrings: an assertion that a deleted module's name appears nowhere
> must exclude docstring string constants, or 23 surviving plugin files and a `run_task`
> docstring fail gates that describe no real breakage.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|---|---|---|---|
| Pilot starts and completes a real session from the cleaned tree | HYG-02 | `autopilot` cannot be imported on this host; the rig is the only environment that can run it, and the Pi's silent-failure mode means only a real session proves dispatch. **USER-RUN** — the agent never starts or stops the pilot. | 1. Clear the `ExtlinkDemo` fixture off pilot 1 first (see Blockers). 2. Deploy the cleaned tree to `.28` via the branch. 3. Start the pilot. 4. Confirm HANDSHAKE reaches the backend. 5. Start a `source_less_toolkit` protocol. 6. Confirm CONTINUOUS events land in ES and the run reaches `completed`, not a stuck `running`. 7. Record run number + md5 manifest in `30-HARDWARE-VALIDATION.md`. |
| The Pi test modules pass on the Pi | HYG-13 | The suite has **never been run anywhere** — the project's largest standing verification debt, predating this phase. Requires the Pi's Python 3.7 + `npyscreen`. **USER-RUN**, from `~/Apps/mice_interactive_home_cage` on the device. | `python3 -m pytest -q tests/` on the Pi. **Count reconciliation:** `tests/` holds **21** modules, not 23 — the 23 in earlier notes counted the 2 Phase 26 reserved-but-absent names (`test_openephys_client.py`, `test_openephys_markers.py`). **`test_compute_ops.py` and `test_log_action_values.py` cannot even be *collected* on the dev host** — they do top-level `autopilot` imports, which pull `setup_autopilot` → `npyscreen`, so collection exits 2. They must be `collect_ignore`d in the root config as Pi-only, not treated as failures. On the Pi all 21 are expected to collect and pass; anything else is a finding about the pre-existing debt, not about this phase. |
| Gmail app password revoked | HYG-01 | Action in a third-party account, outside any repo. | Revoke at Google account → app passwords. Record date in `30-HARDWARE-VALIDATION.md`. Must be done **before** publication, not after. |
| New repo created and branch cut | HYG-01 | The standing rule forbids the agent running git in `pi-mirror` or on the Pi. The branch lives on the user's machine. | User creates the new repo from the pruned tree with a fresh `git init`, and cuts the `.28` branch on the old repo. Agent hands over a verified-clean tree, nothing more. |

---

## Blockers to schedule before the rig proof

- **`ExtlinkDemo` on pilot 1.** Module 62, `role: router_bind`, `required: true`, still assigned
  to toolkit 100 and configured on pilot 1 — every real session there preflight-fails or hangs
  the full 30 s `wait_timeout_s`. A second standing dependency: a TCP echo listener on the dev
  host at `132.77.73.125:5597`, without which `demo.alive` drops false ~3 s into every run.
  Teardown in `18-HARDWARE-VALIDATION.md` §3; DB rows to remove: module 62, lib 177, pilot
  config 21, task def 434. **HYG-02 cannot pass until this is cleared**, and it would fail for
  reasons unrelated to the cleanup — which is exactly the kind of false signal that discredits a
  destructive phase.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or a Wave 0 dependency
- [x] Sampling continuity: every deletion task carries `check_tree_integrity.py --strict`
- [x] Wave 0 covers all ❌ W0 references above (guard, guard tests, root pytest config)
- [x] No watch-mode flags
- [x] Feedback latency < 12 s for agent-run checks — every agent-run gate is an AST/text scan
      plus `compileall`; the equivalent scans measured 1–2 s over the whole tree
- [ ] `ExtlinkDemo` cleared off pilot 1 before the rig checkpoint — **USER ACTION, still open.**
      Blocks plan 09's live-session proof only; Waves 0–5 are unaffected
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-08-10, after plan check 3 and a targeted re-verification of the
remediation commit `655a457`.

Verification trail — three independent checker passes, each re-measuring the previous round's
self-reported claims against the real tree rather than trusting them:

| Pass | Outcome |
|---|---|
| Check 1 | 8 blockers, 6 warnings → revision 1 addressed all 14 |
| Check 2 | all 8 prior blockers confirmed genuinely fixed; 4 new blockers → revision 2 (`4db4c37`) |
| Check 3 | 4 blockers — 3 confirmed against the tree, 1 a false positive (the checker ran `pytest -qq`; the plan runs `-q`) → remediation `655a457` |
| Targeted re-verify | **PASS.** Alias rule reproduced independently (43 alias targets, 103 re-export occurrences suppressed, 0 false positives); guard run cumulatively after every deletion task → 0 violations at each checkpoint bar one that its own task removes; plans 02/03 tried in both Wave-1 orders → 0 either way. 3 documentation nits, all fixed |

The one substantive blocker check 3 found — the guard resolving only `ImportFrom.node.module`,
leaving it blind to `from autopilot.hardware import unreal` and so to the phase's own acceptance
case 2 — is closed by `<from_package_import_submodule_must_resolve>` in plan 01.
