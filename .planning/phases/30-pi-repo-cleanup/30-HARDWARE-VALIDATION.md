# Phase 30 — Hardware Validation Log

**Opened:** 2026-08-10 (plan 30-01, Wave 0)
**Closed at the exit gate:** 2026-08-10 (plan 30-08, Wave 5)
**Tree under test:** `/home/ido/pi-mirror`
**Undo:** `~/pi-mirror.bak-2026-08-10` (plain copy; `pi-mirror` has no agent-managed git).
Second, independent copy of the rescued behavioural data: `/home/ido/pi-data-preserved/`.
**Status:** sweep complete. `check_tree_integrity.py --final` exits 0. 12 of 14 requirements
PROVEN; HYG-01 and HYG-02 remain UNPROVEN because both depend on user actions
(publication + the rig session), not on anything the agent can run.

> **This phase is removal-only, so its acceptance property is a negative:** nothing still
> reachable was removed, and nothing removed is still referenced. `autopilot` cannot be imported
> on this host (`npyscreen` absent), so `py_compile` / `compileall` plus AST scanning is the
> ceiling for agent-run verification. The rig session (HYG-02) is the only thing that proves
> dispatch still works, because the Pi has no `TASK_ERROR` emitter and every removal failure mode
> is silent by default.

---

## Per-requirement verdict

| Requirement | Verdict | Evidence |
|---|---|---|
| HYG-01 credential absent from the new repo's history | **UNPROVEN** | Probe captured (§3). The working tree is clean of both literals (0 hits, re-verified §7), but `.git` still carries them — which is why publication is a **fresh `git init`**. The history proof is a **user action**: `30-PUBLISH.md` step 3. |
| HYG-02 pilot starts and a real session completes | **UNPROVEN** | USER-RUN rig session, plan 09 (§5). Additionally blocked on clearing `ExtlinkDemo` off pilot 1. |
| HYG-03 plugin cluster removed, ordering held | **PROVEN** | 61 files / 1,118,442 B removed as one change, subclasses first: `pilot/plugins/` (28 `.py` + the extensionless `test` + `__pycache__`), then `tasks/learning_cage.py`, `tasks/mics_cage_task.py`, `hardware/unreal.py`. Every importer of each removed module (**13 / 11 / 9**, all inside `pilot/plugins/`) removed in the same change, counted by unfiltered AST scan. `PLUGINDIR` restored with `.gitkeep` so `plugins.py:46-48` never logs. C1/C2/C4 clean; **C3 is not clean** for `available_locked_states` and the 8 `elastic_test.py` toolkits — overridden by the locked user decision, quantified in §4 and §6.9. Plan 04. |
| HYG-04 empty HANDSHAKE is a no-op | **PROVEN** | `POST /pilots/1/tasks {"tasks": []}` → HTTP 200 `{"status":"ok","pilot_id":1,"tasks_received":0}`; 8 global + 4 per-pilot row counts identical before/after; pilot 1 `max(last_seen_at)` **unchanged** at `2026-08-09 14:46:41.268186`, proving no in-place row update (counts alone cannot distinguish "nothing written" from "rewritten in place"). Backend never prunes — confirmed, not fixed. Plan 04. |
| HYG-05 `cameras.py` + both import copies removed | **PROVEN** | Removed on **both sides of the DB boundary**. Pi copy: `hardware/cameras.py` (69,302 B), `hardware/usb.py` (10,546 B), `setup/setup_mlx90640.sh` (792 B); `i2c.py` three-part edit 35,934 → 28,423 B with exactly **3 delete opcodes, 0 insert/replace**, `MLX90640` cut **by AST span** so MPR121's `board`/`busio`/`adafruit_mpr121` imports survive. DB copy: `hardware_libs` id 9 active version 26 → **144**, `octet_length` **and** `sha256` equal to the disk file, `impact.affected_definition_ids` empty, versions 15/26 preserved. Guard `--final` F5 = 0. Plan 05. |
| HYG-06 sweep collateral removed, `tasks/` compiles | **PROVEN** | 7 modules / 60,505 B removed from `autopilot/tasks/`; `compileall` over the surviving directory exits 0 — the gate that matters, because `common.py:47-67`'s `list_classes` has no per-file guard. The one string-keyed dangler the AST guard structurally cannot see (`REGISTRIES.CHILDREN`, `utils/registry.py:42`) removed with a four-criteria verdict and a zero-hit `'child'`-key scan over `mics-backend`. Guard `--final` F4 = 0. Plan 05. |
| HYG-07 Terminal tree removed | **PROVEN** | 124 files / 18,143,253 B: `terminal/` (106 files, 17.86 MB), `run_terminal.sh`, `.vscode/`, and 16 Pi-side files. Cluster proven **self-contained by AST import graph** — every importer of every removed module was itself removed in the same change. `setup_autopilot.py:198`'s `autopilot.core.terminal` launcher string (invisible to any import-graph tool: it is a `.write()` argument) removed and the branch replaced by an explicit `ValueError`. Guard `--final` F1 re-asserts `terminal/` absent. Plan 03. |
| HYG-08 vendored/generated bulk removed | **PROVEN** | 27 paths / 97,691,320 B of installer, Sphinx output, upstream suites, submodule mounts, tilde-literal directories, build artifacts, CI dotfiles, zero-byte logger files and byte-identical wav duplicates (plan 02) — plus the tree-wide cache purge landed here. **Final budget: 1,097,505 B (1.05 MiB) excluding `.git` and `pilot/sounds/`, against an 8,388,608 B limit** (§1b). Guard `--final` F1 = 0. Plans 02 + 08. |
| HYG-09 root pytest config replaces `autopilot/pytest.ini` | **PROVEN** | Root `pytest.ini` + `conftest.py` with `collect_ignore` for the 2 Pi-only modules; `autopilot/pytest.ini` and `autopilot/.coveragerc` removed. Collection produces **no error** (was exit 2). 382 tests collect on this host today. Plan 01; re-verified §7. |
| HYG-10 no rig-specific config in `prefs.json` | **PROVEN** | `TERMINALIP` → `CHANGE_ME_terminal_ip`, `NAME` → `CHANGE_ME_pilot_name`; `SUBJECT`, `PORT_CALIBRATION` and the 17-entry `HARDWARE.UNREAL` group deleted; 16,966 → 12,668 B and the file now parses as **strict JSON** (the `NaN` literals went with `PORT_CALIBRATION`). All 28 pin values **kept on evidence**, not left undecided (§6.10). Guard `--final` F2 = 0. Plan 07. |
| HYG-11 dead commented-out lines removed | **PROVEN** | **238** dead commented lines across 14 files against an audit target of 244; the 2.5% shortfall itemised as **175 deliberately-kept candidates**, each with the live symbol that kept it (ledger `30-06` §B.7). `difflib`: **33 delete opcode groups, 0 insert, 0 replace** across all 13 swept files. Plan 06. |
| HYG-12 `Event_Dispatcher.py` drop counters survive | **PROVEN** | sha256 `1bfadc3313f3552f1d69057a91ce403ca8f2306c7fc874c0369fad9600adac68`, **identical to the Wave 0 baseline**; `_dropped_no_clock` and `_dropped_on_send` present. Excluded by name from the sweep's target list *and* re-checked against `tree_protect_list.json` before any write. Re-confirmed by the zero-drift manifest diff (§7). Plans 01 + 06. |
| HYG-13 survival manifest intact | **PROVEN** | **Zero drift across all 30 protected paths**, on md5 **and** sha256, against the §1 pre-sweep baseline (§7). The three Phase 26 `reserved_absent` names are still absent and were never reported as strays. Plan 08. |
| HYG-14 restorations applied, holds resolved | **PROVEN** | All three DELETE toggles retired tree-wide, asserted as **call forms, never bare tokens**. The HDF5 set removed whole across **four** sites (the fourth — the `run_task` docstring line — was outside the original scope). **Both restorations were DEFERRED BY THE USER on 2026-08-10 and are preserved verbatim**: HOLD 0 (`pilot.py:1071-1082`) and HOLD 1 (`station.py:1270-1283`). Neither uncommented, neither deleted. Guard `--final` F3 = 0, with **inverted** assertions on both holds (§6.7, §6.8). Plans 04/05/06. |

*Verdicts are PROVEN only against evidence recorded in this file.*

**12 PROVEN · 2 UNPROVEN (HYG-01, HYG-02 — both user actions).**

---

## §1 Pre-sweep baseline

Captured 2026-08-10, before any deletion.

### Sizes

| Measurement | Bytes |
|---|---|
| `du -sb --exclude=.git /home/ido/pi-mirror` | 202,630,324 |
| `du -sb /home/ido/pi-mirror/.git` | 197,550,529 |
| `du -sb /home/ido/pi-mirror/pilot/sounds` | 2,326,388 |
| HYG-08 budgeted size (tree − `.git` − `pilot/sounds`) | 200,303,936 → target ≤ 8,388,608 |

`pilot/sounds/` is excluded from the HYG-08 budget deliberately: it is reachable rig audio that
`mixer.py` resolves by bare filename through `SOUNDDIR`, not bulk, and no plan removes it.

> The phase plan records 202,275,257 for the first row. The 355,067-byte difference is plan 01's
> own additions (`tools/check_tree_integrity.py`, `tools/tree_integrity/`,
> `tools/tree_protect_list.json`, `tests/test_tree_integrity.py`, `pytest.ini`, `conftest.py`)
> plus the `__pycache__` written by `compileall`. Not a finding.

### File count

`find /home/ido/pi-mirror -name '*.py' -not -path '*/.git/*' | wc -l` → **202**

### Guard verdict — **1 known violation, exempted**

```
$ python3 tools/check_tree_integrity.py --strict
note: unparseable json (skipped for path check): .vscode/launch.json
OK: 40 closure members, 30 protected files, 1 known-dangling exemptions held, 0 violations
```

**Closure size: 40 members** from `autopilot/autopilot/core/pilot.py`.

The exemption, stated explicitly rather than folded into "0 violations":

| Field | Value |
|---|---|
| Module | `autopilot.autopilot.core.pilot` |
| Anchor | `autopilot/autopilot/tasks/mics_task.py:1589` |
| Reference | `from autopilot.autopilot.core.pilot import _write_hardware_libs` |
| Rationale | Deferred by name in 30-CONTEXT.md: `receive_hardware_libs()` raises `ModuleNotFoundError` and the exception dies unhandled in the `Net_Node` listen thread. Repairing it is an untested behavioural change to the rig and belongs to its own phase, not to a removal phase. |

The assertion is **inverted**: the reference must still be present *and* must still fail to
resolve. If a later plan "helpfully" repairs it, the guard fails. Verified by removing the
exemption from the protect-list in-memory and re-running: **exactly 1 raw violation**,
`autopilot/autopilot/tasks/mics_task.py:1589: dangling import: autopilot.autopilot.core.pilot`,
and nothing else.

### Guard calibration (measured, not argued)

The guard was checked in both directions — silent on the untouched tree, loud the instant a
survivor names a removed module. Removals were **simulated** by patching the resolver; nothing
was deleted.

| Scenario | Violations | Notes |
|---|---|---|
| Untouched tree | 1 raw → **0 after exemption** | the `known_dangling` entry |
| Simulated `rm hardware/unreal.py` | **13** | all `pilot/plugins/`; the 6 `terminal/plugins/` importers sit under the `terminal/` scan-skip and plan 03 removes them in Wave 1 |
| Simulated `rm hardware/cameras.py` | **5** | incl. `hardware/i2c.py:8` and `tasks/children.py:18` |
| Simulated `rm core/subject.py` | **4** | incl. `viz/psychometric.py:4` |
| Simulated `rm core/terminal.py` + `setup/request_helpers.py` | **3** | `setup_autopilot.py:198` (string literal in a `.write()` argument) and `install_pyspin.sh:64`/`:65` (shell) |

These reproduce the phase plan's independently measured numbers exactly.

### Protected-set md5 manifest (the "before" side of the HYG-13 diff)

sha256 of the same 30 paths is recorded in `tools/tree_protect_list.json` → `baseline_sha256`
and is what the guard actually asserts. md5 is recorded here for the house format.

| md5 | Path |
|---|---|
| `766b6360817d9b7cb1ad5ecf0576ff22` | `autopilot/autopilot/hardware/external_hardware.py` |
| `009e2c607e665c91184086a8e8701eff` | `autopilot/autopilot/hardware/external_hardware_binding.py` |
| `02131508390683ac12c35fdccb2ecb87` | `autopilot/autopilot/hardware/external_hardware_ingress.py` |
| `cbc5ad480b56a96ebafa110f01230308` | `autopilot/autopilot/hardware/external_hardware_runtime.py` |
| `76dd4f8dae27ca207720bd2980260928` | `autopilot/autopilot/hardware/external_hardware_wire.py` |
| `ffd4dddedc5354693c648d3162e426cd` | `autopilot/autopilot/tasks/fda_vocabulary.py` |
| `7477ed3889119735fa17644927653ffb` | `autopilot/autopilot/networking/Event_Dispatcher.py` |
| `544fe75a97938aa4802e0fc71077dc2f` | `autopilot/autopilot/utils/log_value.py` |
| `815ca599c9df247a0c7f619bab123dad` | `autopilot/LICENSE` |
| `6bcb5c6a156234f5f840ea732db76795` | `tests/test_check_for_detectors.py` |
| `ec7bb19e850eb6c41c183ff6b2e8733d` | `tests/test_compute_ops.py` |
| `e7620ecba46f1742cc2fae774a2d9621` | `tests/test_detector_view_keys.py` |
| `c9d65794fd4da30b45500ffd872fdbe8` | `tests/test_execute_trigger_guard.py` |
| `27d2c98a8bbfc9eeea96aff07fd52672` | `tests/test_extlink_decoder.py` |
| `be2a713ea153bb8b4e74aa7ab72cd0f3` | `tests/test_extlink_egress.py` |
| `6e5ab160301b29cf8504af364c09371b` | `tests/test_extlink_lifecycle.py` |
| `bfff1264af1d498ee6eb9335f58ff1bb` | `tests/test_extlink_liveness.py` |
| `d8fc467c40c1db05cd3870cc7513b7a7` | `tests/test_extlink_wire.py` |
| `3bf27c14c1d9ad9b64f2db17f3765ae0` | `tests/test_fda_vocabulary.py` |
| `a275ed49931998cd5b4030b21413edc7` | `tests/test_handshake_enrichment.py` |
| `c0a80885bb5c8dff677565426cf833be` | `tests/test_load_fda_from_json.py` |
| `7d5838d43154571d0ca2442b64c7a11b` | `tests/test_log_action_values.py` |
| `db7a7bb2f7b8e8e0e9bdbcbe8ee24572` | `tests/test_log_value.py` |
| `0bc7c132df3047544e004885658182a6` | `tests/test_mics_task_attrs.py` |
| `e77a400b1659dd4312a0347a4d6738bf` | `tests/test_mpr121_irq_hygiene.py` |
| `6bf9544bf4887180123f4f920ed217a7` | `tests/test_trigger_assignments.py` |
| `ef0238e33530e4aa3ec98d884818ab83` | `tests/test_validate_fda.py` |
| `b7796f43db9a3888ebc30308ba8a9a63` | `tests/test_view_detector_operand.py` |
| `ab2682009f087fc79701f10818cb5de6` | `tests/test_view_namespace_invariants.py` |
| `fb4f21933e1ee6dfe81ef1d79b1fae45` | `tests/test_wait_extlink_ready_transitions.py` |

### Pytest baseline (HYG-09)

Full record: `.planning/phases/30-pi-repo-cleanup/30-PYTEST-BASELINE.json`.

| Measurement | Value |
|---|---|
| Command | `cd /home/ido/pi-mirror && python3 -m pytest -q tests/` |
| Collected | 381 |
| Passed | 202 |
| Failed | **179** |
| Errors | 0 |
| Collectable modules | 20 |
| `collect_ignore`d (Pi-only) | `tests/test_compute_ops.py`, `tests/test_log_action_values.py` |

**This is pre-existing debt that predates Phase 30.** The suite has never been run to green
anywhere. The earlier "6 known-failing tests" framing was wrong — that was
`test_mics_task_attrs.py`'s share alone. Concentrations: `test_trigger_assignments.py` 51 ·
`test_load_fda_from_json.py` 48 · `test_validate_fda.py` 26 · `test_check_for_detectors.py` 17 ·
`test_view_detector_operand.py` 16 · `test_execute_trigger_guard.py` 11 ·
`test_mics_task_attrs.py` 6 · `test_handshake_enrichment.py` 4.

**No later gate may chain a bare `python3 -m pytest -q` with `&&`.** Gates assert a *delta*
against `failing_node_ids`, using the `delta_command` recorded in the baseline JSON.

The two `collect_ignore`d modules fail on `npyscreen`, not on `sys.path`; the bootstrap in
`conftest.py` does not and cannot help. They are expected to collect and pass on the Pi.

---

## §1b Post-sweep measurements (plan 08, after the authoritative cache purge)

| Measurement | Pre-sweep | Post-sweep | Delta |
|---|---:|---:|---:|
| `du -sb --exclude=.git .` | 202,630,324 | **3,423,893** | −199,206,431 (−98.31%) |
| `du -sb pilot/sounds` | 2,326,388 | **2,326,388** | **0 — byte-for-byte unchanged** |
| **HYG-08 budget** (tree − `.git` − `pilot/sounds`) | 200,303,936 | **1,097,505 B (1.05 MiB)** | limit 8,388,608 → **13.1% of budget** |
| `du -sb .git` | 197,550,529 | 197,550,529 | 0 — never touched; **never published** (§`30-PUBLISH.md` step 2) |
| `*.py` files excluding `.git` | 202 | **105** | −97 |
| All files excluding `.git` | — | **146** | — |

**Cache state after the authoritative purge:** `__pycache__` directories **0**, `*.pyc` files
**0**, `.pytest_cache` **absent** — all measured outside `.git` by an unfiltered `os.walk`, not
by `find`/`grep`.

### Reconciliation of the size delta against the per-plan ledgers

| Plan | Paths | Bytes removed (per-path, measured before each deletion) |
|---|---:|---:|
| 30-02 | 27 | 97,691,320 |
| 30-03 | 16 (124 files) | 18,143,253 |
| 30-04 | 4 (61 files) | 1,118,442 |
| 30-05 | 10 | 141,145 (+ 7,511 B in-file from `i2c.py`) |
| 30-06 | 0 (in-file only) | 322 lines across 14 files |
| 30-07 | 6 (186 files) | 79,515,555 |
| **Subtotal** | | **196,609,715** |
| Residual to the measured 199,206,431 | | **2,596,716** |

The residual is the `__pycache__` / `*.pyc` / `.pytest_cache` purge (the Wave 0 baseline was
measured *with* caches present and this plan removed them), plus plan 01's two deleted config
files (`autopilot/pytest.ini`, `autopilot/.coveragerc`), plus the in-file reductions of plans 05,
06 and 07 (`prefs.json` alone lost 4,298 B).

> **Two bookkeeping corrections made here rather than propagated.**
> 1. `30-02-SUMMARY.md` says "28 paths". Its ledger §B has 28 **rows**, but row 28 is the
>    `scan_skip` retirement *note*, not a path. The 27 real paths sum to exactly the stated
>    97,691,320 B, so the byte figure is right and only the path count was off by one.
> 2. `30-05-SUMMARY.md` says "10 files (150,687 bytes)". The md5-backed per-path tables in
>    `ledger/30-05-ledger.md` §A.1 and §B.2 sum to **141,145 B** (60,505 + 80,640). The 150,687
>    figure does not reconcile against them and is superseded by the per-path total.

---

## §2 Test-module count reconciliation

Three different numbers appear in the phase documents. All three are correct; none is a
deletion. The full chain:

```
23 (HYG-13)   = 21 pre-existing present + 2 Phase 26 reserved-absent
                (tests/test_openephys_client.py, tests/test_openephys_markers.py)

22 present    = 21 pre-existing + tests/test_tree_integrity.py
                (added by plan 01 Task 1 — the Wave 0 guard's own unit tests)

20 collectable here = 22 present − 2 Pi-only modules that cannot be COLLECTED on this host
                      (tests/test_compute_ops.py, tests/test_log_action_values.py — npyscreen)
```

The HYG-13 protect-list holds exactly the **21 pre-existing** modules plus 9 non-test files = 30
entries. `tests/test_tree_integrity.py` is deliberately **not** protected: it is this phase's own
instrument and later plans may need to extend it — and plan 08's own guard correction (§6.12)
extended it, which is exactly the case that would have become a manifest violation had it been
frozen.

> **Finding.** The phase plan's Task 2 `<done>` asserts "exactly 19 collectable modules". That
> arithmetic counts the 21 pre-existing modules but not the module plan 01 Task 1 itself creates.
> The measured, correct number is **20**. Recorded rather than silently adjusted — see
> `30-01-SUMMARY.md` Finding 1.
>
> Note the phase brief's *other* "19" — "19 collectable modules" in `30-08-PLAN.md` step 3 — is
> the same off-by-one and is superseded by the chain above.

---

## §3 Credential probe (HYG-01)

The Gmail address and 16-character Google app password at
`pilot/plugins/AssociationLearning.py:1323-1324` were captured **before** plan 04 deleted that
file, because the literal strings are what proves the new repo's history is clean.

| Property | Value |
|---|---|
| Path | `/home/ido/.hyg01-probe.txt` — **outside every repository**, by design |
| Mode | `600` |
| Lines | 2 literals, one per line, no surrounding quotes (suitable for `grep -F -f`) |
| Blank lines | **0**, including no trailing blank line — verified with `! grep -qc '^$'` and `wc -l == grep -c .` |
| sha256 | `63a70fd973793d19bfac8cbdc3e7ca4c258964e1123c12f548b2db1ba12992f4` |
| Still present at the exit gate | **yes** — re-asserted by plan 08 |

**The values themselves are never recorded here or anywhere under `.planning/`.** A blank line in
the probe would make `grep -F -f` match everything and silently invert every assertion that
depends on it, which is why the no-blank-line property is asserted rather than assumed.

**Working-tree status at the exit gate: clean.** A `grep -c -F -f` of the probe across the whole
surviving tree excluding `.git` returns **0** (§7). **`.git` is not clean and cannot be made
clean** — which is the entire reason publication is a fresh `git init`.

### To record at publication (user actions, `30-PUBLISH.md`)

| Field | Value |
|---|---|
| App password revoked at Google, date | _(pending — must be done **before** publication)_ |
| `git log -p --all \| grep -c -F -f /home/ido/.hyg01-probe.txt` over the new repo | _(pending — expect **0**)_ |
| `git log --oneline \| wc -l` over the new repo | _(pending — expect **1**)_ |
| HYG-01 verdict | flips to **PROVEN** when the two numbers above are 0 and 1 |

---

## §4 Removal ledger

Every removal in the phase, merged from the six per-plan ledger fragments (`ledger/30-0N-ledger.md`)
plus plan 01's own record above, sorted by path. This table is what makes HYG-07's "reproducible
from criteria, not from a hand-list" true rather than aspirational.

**Criterion key** — a path is removable when it satisfies **all four**:
C1 not in the static import closure of `python3 -m autopilot.core.pilot` ·
C2 not reachable dynamically (`PLUGINDIR` sweep, `autopilot/tasks/` AST sweep, `importlib`, a
string-keyed dispatch table) · C3 not named by the backend (no literal filename/module path/class
name in `mics-backend`, no row in `hardware_libs`, `hardware_modules`, `task_toolkits` or
`available_locked_states` resolving to it) · C4 not reserved by a pending phase.

**PASS** = criterion holds. **OVERRIDE** = criterion does **not** hold and is overridden by a
locked user decision, recorded rather than papered over.

| Path | Bytes | C1 | C2 | C3 | C4 | Plan |
|---|---:|---|---|---|---|---|
| `.vscode/` | (in Task 1 total) | PASS | PASS | PASS | PASS | 03 |
| `alt_blip8.wav` (repo root) | 661,814 | PASS | PASS — resolves through `SOUNDDIR` to `pilot/sounds/`, never the root | PASS — all 7 pi-tree hits are bare-filename refs; the `mics-backend` hits are **ES event payloads**, i.e. recorded data | PASS | 02 |
| `autopilot/.coveragerc` | — | PASS | PASS | PASS — named only by `autopilot/pytest.ini` (removed same change) and `autopilot/.travis.yml` (removed by plan 02) | PASS | 01 |
| `autopilot/.coveralls.yml` | 0 | PASS | PASS | PASS — 2 hits, neither naming the file (a README badge URL and the pip package name) | PASS | 02 |
| `autopilot/.gitmodules` | 221 | PASS | PASS | PASS — 0 hits | PASS | 02 |
| `autopilot/.pilot` | 0 | PASS | PASS | PASS | PASS | 02 |
| `autopilot/.readthedocs.yml` | 576 | PASS | PASS | PASS — 2 hits, both `picamera` doc URLs | PASS | 02 |
| `autopilot/.travis.yml` | 2,597 | PASS | PASS | PASS — 0 hits | PASS | 02 |
| `autopilot/CNAME` | 20 | PASS | PASS | PASS — 0 hits in the pi tree | PASS | 02 |
| `autopilot/Cow.wav` | 465,808 | PASS | PASS | PASS — 0 hits | PASS | 02 |
| `autopilot/Dying Light Bulb-SoundBible.com-742005847.wav` | 131,532 | PASS | PASS | PASS — 0 hits | PASS | 02 |
| `autopilot/Testing_stepper_motor_Hat/` (2 files) | 753 | PASS | PASS | PASS — 0 hits both trees | PASS | 02 |
| `autopilot/auto_pi_lot.egg-info/` | 15,567 | PASS | PASS | PASS — 1 badge URL + 2 exclusion rules | PASS | 02 |
| `autopilot/autopilot/core/gui.py` | (Task 2 total) | PASS | PASS | PASS | PASS | 03 |
| `autopilot/autopilot/core/plots.py` | ″ | PASS | PASS | PASS | PASS | 03 |
| `autopilot/autopilot/core/reward.py` | ″ | PASS — **zero** importers tree-wide | PASS | PASS | PASS | 03 |
| `autopilot/autopilot/core/styles.py` | ″ | PASS | PASS | PASS | PASS | 03 |
| `autopilot/autopilot/core/subject.py` | ″ | PASS — its **four** importers (`terminal.py:46`, `gui.py:43`, `viz/psychometric.py:4`, `viz/trial_viewer.py:26`) all removed in the same task | PASS | PASS — the 23 `pilot/plugins/` mentions are Sphinx **docstrings**, excluded by AST node identity | PASS | 03 |
| `autopilot/autopilot/core/terminal.py` | ″ | PASS | PASS | PASS | PASS | 03 |
| `autopilot/autopilot/core/utils.py` | ″ | PASS — **zero** importers tree-wide | PASS | PASS | PASS | 03 |
| `autopilot/autopilot/data_handlers/` (2 files) | ″ | PASS | PASS | PASS — the 5 `data_handlers` backend hits name the **orchestrator's own** `ElasticSearchDa**te**Handler.py`, not the Pi's `…Da**ta**Handler.py` | PASS | 03 |
| `autopilot/autopilot/hardware/cameras.py` | 69,302 | PASS — closure never contained it; caught by the **dangling-reference** check instead | PASS | PASS — no `hardware_libs`/`hardware_modules` row | PASS — Phase 26's `openephys_client.py` untouched | 05 |
| `autopilot/autopilot/hardware/unreal.py` | 6,939 | PASS | PASS — `autopilot.get_hardware()` resolves only names a task class's `HARDWARE` dict declares; **no surviving task class declares `UNREAL`** (verified by reading `Task.init_hardware`, not by trusting the plan) | PASS — absent from `hardware_libs` (7 rows) and `hardware_modules` (9 rows) | PASS | 04 |
| `autopilot/autopilot/hardware/usb.py` | 10,546 | PASS | PASS | PASS | PASS | 05 |
| `autopilot/autopilot/setup/install_pyspin.sh` | (Task 2 total) | PASS | PASS | PASS — its only other mention is a **docstring** at `cameras.py:1143`. Deleted **consumer-first**, immediately before `request_helpers.py`, because `:64-65` invoke it via `python -c` | PASS | 03 |
| `autopilot/autopilot/setup/request_helpers.py` | ″ | PASS | PASS | PASS | PASS | 03 |
| `autopilot/autopilot/setup/setup_mlx90640.sh` | 792 | PASS | PASS | PASS | PASS | 05 |
| `autopilot/autopilot/tasks/RecordingBox.py` | 3,542 | PASS | PASS | **OVERRIDE** — a stale `available_locked_states` row resolves to it; 0 toolkits reference it | PASS | 05 |
| `autopilot/autopilot/tasks/children.py` | 11,245 | PASS | PASS — the string-keyed `REGISTRIES.CHILDREN` dispatch removed in the same change | PASS — **zero** `'child'` keys anywhere in `mics-backend/api` or `orchestrator` | PASS | 05 |
| `autopilot/autopilot/tasks/free_water.py` | 5,916 | PASS | PASS | **OVERRIDE** — stale `available_locked_states` row, 0 toolkits | PASS | 05 |
| `autopilot/autopilot/tasks/gonogo.py` | 8,110 | PASS | PASS | **OVERRIDE** — as above | PASS | 05 |
| `autopilot/autopilot/tasks/learning_cage.py` | 7,991 | PASS | PASS — reachable only as its own class object once every subclass is gone | **OVERRIDE** — an `available_locked_states` row resolves to it | PASS | 04 |
| `autopilot/autopilot/tasks/mics_cage_task.py` | 17,028 | PASS | PASS — as above | **OVERRIDE** — as above | PASS | 04 |
| `autopilot/autopilot/tasks/nafc.py` | 16,768 | PASS | PASS | **OVERRIDE** — as above | PASS | 05 |
| `autopilot/autopilot/tasks/protocol_scripts.py` | 110 | PASS — no top-level classes at all | PASS | PASS | PASS | 05 |
| `autopilot/autopilot/tasks/test.py` | 14,814 | PASS | PASS | **OVERRIDE** — `DLC_Hand` / `DLC_Latency` rows, 0 toolkits | PASS | 05 |
| `autopilot/autopilot/utils/Event.py` | (Task 2 total) | PASS — **0** Python importers; the live twin `utils/Events.py` has **12** and survives | PASS | PASS | PASS | 03 |
| `autopilot/autopilot/utils/invoker.py` | ″ | PASS | PASS | PASS | PASS | 03 |
| `autopilot/autopilot/viz/` (3 files) | ″ | PASS — deleted **before** `core/subject.py`, inverting the plan's literal order to honour its own importers-first principle | PASS | PASS | PASS | 03 |
| `autopilot/code_2023.deb` | 87,013,118 | PASS — not a `.py` | PASS — a Debian package is not importable | PASS — 0 hits | PASS | 02 |
| `autopilot/docs/` | 9,095,683 | PASS | PASS | PASS — 2 hits, **both the guard's own assertion literals** | PASS | 02 |
| `autopilot/examples/` | 24,886 | PASS | PASS — `examples/tasks/` is not the swept `autopilot/autopilot/tasks/` | PASS — 2 hits, both guard self-literals | PASS | 02 |
| `autopilot/hardware.gpio` · `networking.node` · `networking.station_02` · `plugins` · `plugins.YoShiTask` · `registry` | 0 each | PASS | PASS | PASS — the matching strings in surviving code are **logger names** and **module imports**, never references to these files | PASS | 02 |
| `autopilot/home/` | 120,740 | PASS | PASS | PASS | PASS — its sole file is byte-identical (md5 `86e87279…`) to the reachable `pilot/sounds/lick.wav` | 02 |
| `autopilot/pytest.ini` | — | PASS | PASS | PASS | PASS — replaced by root `pytest.ini` + `conftest.py` **in the same change** (HYG-09) | 01 |
| `autopilot/src/` (2 uninitialised submodule mounts) | 0 | PASS | PASS | PASS — `src/pigpio` and `src/mlx90640` both 0 hits; `setup_mlx90640.sh` points at `autopilot/external/`, a **different** path | PASS | 02 |
| `autopilot/tests/` | 37,775 | PASS | PASS | PASS — 4 hits: 2 guard self-literals + 2 inside the guard's own synthetic-tree fixture | PASS — contains no `openephys` file | 02 |
| `autopilot/~/` | 13,791 | PASS | PASS | PASS | PASS | 02 |
| `blip.wav` (repo root) | 88,244 | PASS | PASS — as `alt_blip8.wav` | PASS — all 4 hits bare-filename or absolute `pilot/sounds/` | PASS | 02 |
| `environment.yml.save` | 1,583 | PASS | PASS | PASS — 0 hits | PASS — `environment.yml` kept | 02 |
| `output.txt` (repo root) | 16,612 | PASS | PASS | PASS — 0 hits | PASS | 02 |
| `pilot/logs/` **contents** (181 files) | 4,062,721 | PASS | PASS | PASS | PASS — directory retained behind `.gitkeep`; **3 behavioural CSVs were not logs** and were preserved to `/home/ido/pi-data-preserved/` on an explicit user decision before the purge | 07 |
| `pilot/data/` **contents** (1 file) | 75,425,210 | PASS | PASS | PASS | PASS — directory retained behind `.gitkeep` | 07 |
| `pilot/plugins/` (58 files: 28 `.py`, the extensionless `test`, `__pycache__`) | 1,086,484 | PASS — closure was 40 members before **and** after | PASS **by construction** — these *are* the `PLUGINDIR` sweep's inputs | **OVERRIDE** — 37 `available_locked_states` rows and **8 toolkits** with `locked_state_source='elastic_test.py'` resolve here (§6.9) | PASS | 04 |
| `pilot/port_calibration.json` | 330 | PASS | PASS | **named but safe** — all 4 consumers are `os.path.exists`-guarded or belong to the Terminal workflow removed in plan 03; the file was **degenerate** (one sample per port → `NaN` fit) | PASS | 07 |
| `pilot/port_calibration_fit.json` | 117 | PASS | PASS | as above (3 consumers) | PASS | 07 |
| `pilot/prefs_wsl.json` | 13,522 | PASS | PASS | PASS — **0 references** to `prefs_wsl` in either tree | PASS — read for the pin diff (§6.10) before removal | 07 |
| `pilot/prefs_wsl_office.json` | 13,655 | PASS | PASS | PASS — 0 references; also the last non-allowlisted carrier of `132.77.` | PASS | 07 |
| `run_terminal.sh` | (Task 1 total) | PASS | PASS | PASS | PASS | 03 |
| `terminal/` (106 files, incl. `terminal/~/`, `terminal/plugins/`, `terminal/protocols/`, 16.47 MB of rotated log spew) | 17,857,905 | PASS | PASS — `PLUGINDIR` is `…/pilot/plugins`, so the dynamic sweep never reached `terminal/` | PASS — `(DB filenames ∩ terminal/plugins) − pilot/plugins = ∅`; the 5 `pilot_db` backend hits are all `pilot_db_id`, a primary key | PASS | 03 |

**In-file removals (no path deleted) — same criteria, recorded for completeness:**

| Edit | Extent | Plan |
|---|---|---|
| `hardware/i2c.py` — the `cameras` import, the `mlx_cam` guard, the whole `MLX90640` class | −219 lines / −7,511 B; 3 delete opcodes, 0 insert/replace | 05 |
| `hardware_libs` id 9 (`i2c.py` in the DB) — the same three-part edit | active version 26 → 144, sha256-identical to disk | 05 |
| `utils/registry.py` — `REGISTRIES.CHILDREN = "autopilot.tasks.children.Child"` | 1 enum member | 05 |
| `setup/setup_autopilot.py` — the `autopilot.core.terminal` launcher string | branch → explicit `ValueError` | 03 |
| `core/pilot.py` — `open_file()`, the `self.h5f` cleanup, ~23 commented lines, the `run_task` docstring line, the `'child'` dispatch branch, `:49`'s hardcoded home directory | −85 lines (57 live + 28 comment/docstring) | 06 |
| 13 further files — the HYG-11 dead-comment sweep | −237 lines | 06 |
| `pilot/prefs.json` — `TERMINALIP`, `NAME`, `SUBJECT`, `PORT_CALIBRATION`, `HARDWARE.UNREAL` | 16,966 → 12,668 B | 07 |

**Additions (the sweep is not purely subtractive):** `pilot/plugins/.gitkeep` (plan 04),
`pilot/{data,logs,viz,calibration}/.gitkeep` (plan 07), `pilot/protocols/.gitkeep` (plan 08),
`.gitignore` hardening (plans 02 + 07 + 08), the two adafruit runtime deps in `requirements.txt`
(plan 08, §6.13), and the Wave 0 instrument itself (`tools/check_tree_integrity.py`,
`tools/tree_integrity/`, `tools/tree_protect_list.json`, `tests/test_tree_integrity.py`,
`pytest.ini`, `conftest.py`).

**Ordering is a hard constraint:** subclasses before base classes, always. `api/main.py:1059-1070`
raises 400 on an unresolvable `base_class`, and because the commit is at `:1117` inside
`orchestrator_station.py:85-183`'s single `try`, that 400 discards the tasks upsert, the toolkit
upsert, the hardware-config seed and the locked-states upsert together. Every plan that removed a
base class removed it **in the same change** as its subclasses; plan 03 additionally inverted its
own plan's literal ordering (`viz/` before `core/subject.py`) to keep the intermediate tree
consistent.

---

## §5 Rig session (HYG-02)

_Placeholder — filled by plan 09._

**USER-RUN.** The agent never starts or stops the pilot and never runs Python on the Pi.

Blocked until `ExtlinkDemo` is cleared off pilot 1: module 62 (`role: router_bind`,
`required: true`) is still assigned to toolkit 100 and configured on pilot 1, so every real
session there preflight-fails or hangs the full 30 s timeout. A TCP echo listener on the dev host
at `132.77.73.125:5597` is a second standing dependency. Teardown is in
`18-HARDWARE-VALIDATION.md` §3; DB rows to remove: module 62, lib 177, pilot config 21, task
def 434.

To record when it runs: run number, session id, `subject_key` for the ES query
(`{"term": {"subject": "bp_s<session>_r<run>"}}`), and the post-sweep md5 manifest.

**Watch-list for the rig proof — the phase's three behavioural changes.** Everything else is
subtractive; these are the only places behaviour moved:

1. **`l_start`'s START dispatch collapsed** to the unconditional
   `autopilot.get_task(value['task_type'])` (plan 06). The `else` body was byte-for-byte the
   unconditional form, so the surviving path is exact — but it is still a code change on the
   dispatch path.
2. **`Solenoid.dur_from_vol` now falls back to the documented default LUT** `y = 3.5x + 2`
   (plan 07). Before: an escaping `KeyError` (the calibration was keyed `L`/`C`/`R` while the
   hardware is `VALVE1`–`VALVE4`). After: a logged `TypeError` → documented default. An
   improvement, and still a behaviour change.
3. **The licker after the `i2c.py` surgery** (plan 05). `MPR121`'s `board`/`busio`/
   `adafruit_mpr121` imports survive by AST-span cutting; `py_compile` cannot prove this and only
   a real lick can.

---

## §6 Findings and corrections

### F6.1 — `known_dangling`: one deferred defect, asserted to stay broken

`autopilot.autopilot.core.pilot` referenced from `autopilot/autopilot/tasks/mics_task.py:1589`.
See §1. The guard asserts the anchor file exists, the reference text is still present, and the
module still does **not** resolve. A *working* import here is a failure, because it would mean an
untested behavioural change to the rig shipped under cover of a cleanup phase.

**Status at the exit gate: held.** `--strict` and `--final` both report
`1 known-dangling exemptions held`. The defect is intact and remains on the deferred list.

### F6.2 — `scan_skip`: four directories the scanner ignored during Waves 0–1, now retired

`autopilot/tests/`, `autopilot/examples/`, `autopilot/docs/` (removed by plan 02) and `terminal/`
(removed by plan 03).

Rationale for the skip: plans 02 and 03 ran in parallel in Wave 1.
`autopilot/tests/test_terminal.py:9` does a genuine `import autopilot.core.terminal`; if plan 03
landed first the guard would flag a file plan 02 deletes in the same wave — a false failure caused
only by intra-wave ordering. The three upstream vendored trees were never in the pilot's import
closure. `terminal/` was skipped for the same reason: its only clause-2(d) hits were dead
Terminal-host config in `terminal/prefs.json`.

**The skip was not a permanent hole.** `--final` F1 asserts all four paths are **gone**, and it
does so today: `test ! -e` passes for each, and F1 returns 0 violations. The entries were
deliberately **left in `tree_protect_list.json`** rather than edited out mid-phase — editing the
protect-list is forbidden by the phase, and the entries are now inert.

### F6.3 — `runtime_generated`: `pilot/plugin_db.json`

Referenced by `pilot/prefs.json` (`PLUGIN_DB`). Generated on the device at runtime by the plugin
scanner; it has never existed in the mirror. No plan creates it and plan 07 left the `PLUGIN_DB`
key alone by design, so without this exemption clause 2(d) flags `pilot/prefs.json` on the
untouched tree and stays red through `--final`.

### F6.4 — clause 2(d) parse skip, closed by `--final` F6

Three `.json` files did not parse and were skipped for the path check, each reported as a `note:`
rather than swallowed: `.vscode/launch.json` (JSONC — it has `//` comments),
`terminal/pilot_db1.json`, `terminal/pilot_db2.json`. **All three were deleted by plan 03**, the
`note:` line is gone from the guard's output, and `--final` F6 now asserts every surviving `.json`
parses — 0 violations.

### F6.5 — F3 asserts call forms, never bare tokens

`IR1` and `OG_TRIGGER` are **live GPIO pin declarations** in `pilot/prefs.json` that survive this
phase **by design** — HYG-10 deliberately leaves the `GPIO`, `I2C`, `Mixer`, `Timers` and
`Modules` groups intact. What HYG-14 retires is the commented-out *toggle*, not the pin. A
tree-wide `! grep -q 'OG_TRIGGER'` would therefore fail at the exit gate, after every destructive
plan has landed and before any rig proof, and the only compliant response would be stripping live
GPIO entries with no rig evidence. F3 asserts `set_cdc_manual(0x3f)`, `self.triggers['IR1']` and
`pulse_and_notify(...OG_TRIGGER...)` and nothing else.

**Verified at the exit gate:** `/usr/bin/grep -n 'OG_TRIGGER\|IR1' pilot/prefs.json` returns four
lines (`:107`, `:109` for `OG_TRIGGER`; `:144`, `:148` for `IR1`) — the live declarations, pin 33
and pin 15. **That output is correct and must never be "fixed".** F3 = 0 violations regardless.

### F6.6 — the guard excludes its own source from every tree-wide scan

`tools/check_tree_integrity.py`, `tools/tree_integrity/`, `tools/tree_protect_list.json` and
`tests/test_tree_integrity.py` necessarily *contain* the literals they search for. They are
excluded from F3, F5, the 2(b)/2(c) string scans and clause 2(d)'s path scan. 2(d) is included
deliberately: `tree_protect_list.json`'s own `scan_skip` values are repo-relative glob-free paths,
so the moment plans 02 and 03 deleted those trees the guard's protect-list would have become four
self-inflicted violations.

Two later plans hit the same class of problem in gates written *outside* the guard, and both were
answered by excluding the instrument rather than by weakening the assertion or editing the guard:
plan 03's `request_helpers` gate (after `install_pyspin.sh` went, the guard's own test fixture was
the sole remaining match tree-wide) and plan 07's `132.77.` allowlist (see F6.11).

### F6.7 — HOLD 0: the NTP restoration is deferred, so F3's NTP assertion is inverted

**User decision, 2026-08-10, mid-execution of plan 01.** The clock block in
`autopilot/autopilot/core/pilot.py` stays **commented out**; plan 06 no longer uncomments it and
the user will handle it separately.

F3 was amended before it ever ran in anger. It asserts that `self.enable_ntp_and_wait()` and
`self.disable_ntp()` each appear **only in commented form** and **never uncommented**, and that
both anchor comments survive (`# ---- CLOCK SETUP ----`, `# Freeze wall clock so it never jumps
during the task`).

Two failure modes are covered where the original wording covered neither: an accidental uncomment
(shipping an untested clock change to the rig under cover of a cleanup), and — **the likelier
accident** — HYG-11's dead-comment sweep eating the block, which would leave the deferred work
unrecoverable and invisible.

**Outcome:** the block survived plan 06's sweep verbatim and now sits at `pilot.py:1071-1082`,
still commented. F3 = 0.

### F6.8 — HOLD 1: the handshake-watchdog restoration is deferred, and F3 is inverted for it too

**User decision, 2026-08-10, three waves after F6.7.** The original framing was wrong: the retry
`self._handshake_callback()` is **already live and uncommented** and the watchdog re-arms every
10 s, so restoring the logger calls recovers no behaviour. The only real defect is
`except Exception: print("")`, and on this rig `logger.*` is the wrong remedy anyway — Pi log
files are 0 bytes by design and terminal output is the channel that works. The user chose to leave
`station.py` untouched rather than make a behavioural change inside a removal phase.

**The risk inverts:** the five commented `logger` lines sit in the file that contributes the most
(58 lines) to HYG-11's sweep, so they are a carve-out inside a file that is otherwise swept
normally. They now sit at `station.py:1270-1283`, byte-identical.

Plan 06's own Task 1 verify gate was **stale against this decision** and demanded the restoration
(`grep -Eq '^\s*logger\.(warning|exception)\('` plus `! grep -Eq '^\s*print\(""\)\s*$'`). The
executor **reported and inverted it rather than obeying it**. See F6.12 for the same staleness in
the built guard, fixed at the end of Wave 4.

### F6.9 — the `OG_TRIGGER` / `IR1` inventory correction — **OPEN against 30-CONTEXT.md**

30-CONTEXT.md states the `OG_TRIGGER` declarations live only at `mics_cage_task.py:97` and
`learning_cage.py:82`, *"so no orphan declaration survives"*. **That is wrong in two places.** The
three halves recorded by plans 04, 05 and 07, merged:

| Token | Site | Kind | Retired by |
|---|---|---|---|
| `OG_TRIGGER` | `pilot/prefs.json` (was `:241`/`:243`, now **`:107`/`:109`** after HYG-10 shrank the file) | **live GPIO pin declaration, pin 33** | **never — survives by design** |
| | `tasks/mics_cage_task.py:437-438` (the commented pulse) | commented toggle | plan 04 |
| | `autopilot/autopilot/tasks/RecordingBox.py:53` **and `:54`** | HARDWARE dict key + `gpio.Digital_Out` handler | **plan 05**, one wave later than the plugin sweep |
| `IR1` | `pilot/prefs.json` (was `:278`/`:282`, now **`:144`/`:148`**) | **live GPIO pin declaration, pin 15** | **never — survives by design** |
| | `tasks/learning_cage.py:141-147` (the `self.triggers['IR1']` registrations) | commented toggle | plan 04 |
| | `pilot/prefs_wsl.json:203,207` · `pilot/prefs_wsl_office.json:205,209` | dev-host prefs | plan 07 |
| | `autopilot/autopilot/tasks/RecordingBox.py:62`, `:63` | HARDWARE dict key + `gpio.Digital_In` handler | plan 05 |
| `set_cdc_manual(0x3f)` | `pilot/plugins/elastic_test.py:138`, `tasks/learning_cage.py:193` | commented toggle | plan 04 |
| | `autopilot/autopilot/tasks/RecordingBox.py:104` | commented toggle — the **last one in the tree** | plan 05 |

Two refinements beyond the CORRECTION block already in 30-CONTEXT.md, both measured: `RecordingBox.py`
carries the `OG_TRIGGER` declaration on **two** lines (`:53` and `:54`), not one, and its `IR1`
declaration sits at `:62`/`:63`.

**Status: OPEN.** 30-CONTEXT.md carries the general CORRECTION block (which is what forced F3 to
assert call forms) but not this full site table. It is recorded here rather than patched into
30-CONTEXT.md so the context file stays the record of what was *decided*, not of what was later
*measured*.

### F6.10 — HYG-10's judgement call was answered by measurement, and nothing was left undecided

The plan's escape hatch was "cannot tell → keep and record as undecided". It was not used. Every
`pin` in `HARDWARE` was diffed across all three independently authored prefs files **before the
other two were deleted**:

| Comparison | Differing pin values |
|---|---:|
| `prefs.json` vs `prefs_wsl.json` | **0** |
| `prefs.json` vs `prefs_wsl_office.json` | **0** |

Zero differences on every shared entry across three separately maintained files is positive
evidence the pin map is a cage/HAT wiring convention rather than this unit's identity. **All 28 pin
values kept; the "undecided" list is empty.** Membership differences are capability differences
(this rig has an opto trigger and a TTL line; the WSL rigs have door motors), not wiring
differences. A placeholder here would have been a silent wrong-GPIO-fires bug — the exact failure
class this phase exists to prevent.

Two related keeps, both recorded decisions rather than omissions:
- **`BASEDIR` / `REPODIR` / `VENV`** kept at the `/home/pi/Apps/mice_interactive_home_cage`
  convention, as an **install-path assumption a new unit must match**. `REPODIR` feeds
  `git_version()` at `prefs.py:599-606` and `BASEDIR` feeds the boot-time mkdir of seven directory
  prefs; a `CHANGE_ME` in either turns a working default into a guaranteed first-boot failure.
- **`HARDWARE.Modules` reuses two `GPIO` pins** (`Left_LED`/`Right_LED` → pin 11;
  `Solenoid`/`Mid_LED` → pin 12). Pre-existing, identical in all three prefs files, outside
  HYG-10's scope. Flagged, not changed.

### F6.11 — the four surviving `132.77.` carriers are decisions, not exemptions

| File | Decision |
|---|---|
| `tools/sync_pi.sh:11`, `:20`, `:22` | **KEEP** — `${PI_HOST:-…}` overridable defaults in developer tooling that runs on the developer's machine and never ships to the device. A one-line comment was added above each default; that insertion moved the `132.77.` lines from 11,18 → **11,20**. |
| `tools/deploy_pi.sh:21`, `:23` | **KEEP** — same category; the comment moved its line 19 → **21**. |
| `scripts/dev/extlink_smoke.py:21,26,30` | **KEEP** — inside a usage docstring; plan 02 Task 1 §C explicitly orders this file kept. |
| `tests/test_extlink_decoder.py` (7 lines) | **KEEP — mandatory.** On the HYG-13 protect-list with a sha256 baseline; editing it would break the zero-drift manifest diff. |

**Not a kept rig value:** `tools/tree_integrity/final_checks.py:106-107`, where the match *is* the
F2 assertion. Plan 07's gate string-compared `grep -rl` output against an exact four-file set and
could therefore never be true; the fix was to exclude the instrument
(`--exclude-dir=tree_integrity --exclude=check_tree_integrity.py`), consistent with `SELF_PATHS`.
**This was the third correction to the same allowlist — two files → four → four-with-the-instrument-excluded.**

### F6.12 — the mid-flight guard correction (plan 08 step 0g) — the **fourth** stale assertion

`--final` was red at the end of Wave 4 with two violations — `_handshake_watchdog logs nothing`
and `still has a bare print` — because the watchdog deferral (F6.8) had been applied to plan 01's
*specification* but not to the *built artifact*. The NTP deferral (F6.7) reached the guard only
because it arrived while Wave 0 was still running; the watchdog one arrived three waves later.
**The exit gate was demanding the restoration the user had cancelled.**

Fixed in the main session before plan 08 started: `tools/tree_integrity/final_checks.py`'s
`f3_toggles` now mirrors `_ntp_violations` — it flags an **uncommented**
`logger.warning`/`logger.exception`, and flags the **absence** of the four commented lines or of
the bare `print("")`, because the realistic accident is HYG-11's sweep eating a block it cannot
tell apart from its targets. Two guard unit tests written against the old expectation were fixed,
and a HOLD 1 discrimination test was added covering all four states (deferred-clean, uncommented,
swept, tidied-away print). Verified at the time: **22 guard tests pass**, `--strict` 0,
`--final` 0, Pi suite 179 → 179 with 0 new failures.

**The pattern this belongs to, stated so nobody re-runs these gates naively.** This was the
**fourth** assertion in the phase whose cheapest path to green was to *undo a decision*:

1. the bare-token `OG_TRIGGER` form (F6.5) — green by deleting live GPIO pin declarations;
2. the two-file `132.77.` allowlist (F6.11) — green by obfuscating or deleting the guard's own F2
   literal;
3. plan 06's stale `station.py` Task 1 gate (F6.8) — green by uncommenting the deferred logger
   lines and deleting the deferred `print("")`;
4. the built guard's own pre-deferral F3 (this entry) — the same, at the exit gate.

**Treat "the gate demands a restoration or a deletion of live code" as evidence the *gate* is
stale, not as an instruction.** In a removal phase the cheapest way to make any gate green is to
remove something, and the nearest removable thing is usually the thing someone deliberately kept.

### F6.13 — the two undeclared adafruit runtime deps (plan 08 step 0b)

Surfaced by plan 02 while removing `autopilot/Testing_stepper_motor_Hat/`, whose README was the
only record of the install. Re-verified against the surviving tree at the exit gate with an
unfiltered reader (line numbers shifted by plan 05's `i2c.py` surgery):

```
autopilot/autopilot/hardware/i2c.py:577   import adafruit_mpr121
autopilot/autopilot/hardware/i2c.py:671   from adafruit_motorkit import MotorKit
autopilot/autopilot/hardware/i2c.py:677   pip install adafruit-circuitpython-motorkit   (docstring)
requirements.txt            39 lines — no adafruit entry
autopilot/requirements.txt  21 lines — no adafruit entry
```

`i2c.py` survives the phase and **`MPR121` is the licker sensor** — live rig hardware, not an
optional extra. The rollout story is "new units get a fresh image + the new repo", and that path
installs from the root `requirements.txt`, so a repo whose declared deps do not cover its live
imports fails on first boot. Pre-existing bug; this phase is what makes it bite.

**Added to the root `requirements.txt` only** (`autopilot/requirements.txt` is upstream's and was
not touched), **deliberately unpinned**, with the reason written into the file: every other entry
there is pinned to a version resolved on the rig's Python 3.7.3, and pinning these from the dev
host would be a guess. **Nothing was pip-installed, here or on the Pi.** `30-PUBLISH.md` records
that the two pins must be resolved on the first fresh image before the repo is
provisioning-complete.

**Related, recorded and deliberately not acted on:** with the Terminal gone, `requirements.txt`
still carries its GUI-only stack (`npyscreen`, `PySide2`, `shiboken2`, `pyqtgraph`). Those are now
dead weight in the repo new units clone, and `npyscreen` is the very package whose absence makes
`autopilot` unimportable on this dev host. Removing them is a real improvement and **out of scope
for this phase** — see the deferred list below.

### F6.14 — test-module count reconciliation

All three numbers, in one place: `23 (HYG-13) = 21 present + 2 Phase 26 reserved-absent`;
`21 present = 19 collectable on this host + 2 Pi-only (npyscreen)`. The fuller chain, including
the guard's own test module which is present but deliberately unprotected, is in §2 — the number
that actually collects here today is **20 modules / 382 tests**, because plan 01 added
`tests/test_tree_integrity.py`.

### F6.15 — pytest baseline and delta

| Measurement | Failed | Passed | Collected |
|---|---:|---:|---:|
| Pre-Wave-0 (phase plan's own measurement) | 179 | 181 | 360 |
| **Wave 0 baseline** (`30-PYTEST-BASELINE.json`) | **179** | 202 | 381 |
| Exit gate (plan 08) | **179** | 203 | 382 |
| **New failing node ids vs baseline** | **0** | | |

The pass count grew twice, both times because this phase *added* tests: +21 guard tests in Wave 0,
+1 (the HOLD 1 discrimination test) in the F6.12 correction. **The 179 failures are pre-existing
debt predating Phase 30** — the suite has never been run to green anywhere, and no plan in this
phase touched a protect-listed test module.

### F6.16 — the "6-byte `hardware_libs` drift" never existed

30-CONTEXT.md, the phase brief and plan 05's own `<verified_db_state>` all record `i2c.py` as
"already drifted 6 bytes — 35,934 on disk vs 35,928 in the DB". Measured properly:

| | value |
|---|---:|
| `length(source_code)` — **characters** | 35,928 |
| `octet_length(source_code)` — **bytes** | **35,934** |
| disk `i2c.py` — bytes | **35,934** |

The 6 is exactly `3 × (3−1)`: `i2c.py` holds three em-dashes (U+2014), 1 character and 3 UTF-8
bytes each. The comparison was characters against bytes. Identity was then proven rather than
inferred from equal size: md5 `3c933d65eeac795d2bcabd8d5cc3c08f` on both sides, zero `difflib`
opcodes.

**Reconciliation decision:** the reconciliation went ahead and discarded nothing, because the check
ran first — plan 05's instruction was that HYG-05 "does not permit reconciling without knowing what
you overwrote". **The general deferred concern stands and is restated below without the number:**
there is still no process keeping the `exec()`'d DB copy in sync with the Pi file, and this phase
had to make the same edit twice by hand, which is the concern demonstrating itself.

### F6.17 — every kept-as-undecided line, and the files edited beyond a plan's declared scope

**Kept commented lines (HYG-11's 2.5% shortfall): 175 candidates**, each recorded in
`ledger/30-06-ledger.md` §B.7 with the live symbol that kept it. The rule that produced them, made
operational because the plan's own rule and its exclusion contradicted each other:

> **REMOVE** a multi-line commented block that is a complete superseded implementation — a live
> replacement performs its job, or its symbols are dead tree-wide — **plus** a single commented
> line whose named symbol exists nowhere else in the tree.
> **KEEP and record** every single disabled statement naming a still-live symbol, all prose /
> `TODO` / `FIXME` / banners, and the two user-deferred blocks.

It validates independently against the audit: `mics_task.py` comes out at exactly **11** and
`task.py` at exactly **28**, the two per-file numbers the audit predicted.

The largest kept groups:

| Group | Why kept |
|---|---|
| `hardware_state` — 8 sites in `gpio.py` + the `state_changing_methods` block at `logging_utils.py:59-77` | The attribute is **read live** at `gpio.py:439` and `logging_utils.py:95` (on **every** logged hardware event) but written live only at `gpio.py:877`. The commented code is the only surviving description of how it was meant to be maintained. **User-designated do-not-touch (§6.18).** |
| `core/pilot.py` — 24 remaining commented candidates | HYG-11's named scope for that file is `:49` only; the rest is the old terminal-DATA-return path in `run_task`, whose symbols (`self.node.send`, `self.logger.debug`, `self.stage_block`) are all live. |
| `gpio.py:1017/1021` (`_clean_value`, `set_PWM_dutycycle` → `set_servo_pulsewidth`) | Formally a directly-superseded single, but the supersession is a **hardware behaviour change** on a rig this phase does not exercise, and `_clean_value` is still live at `:1035`. |
| `import tables` + the PyTables warning filter in `pilot.py` | Vestigial after the HDF5 removal but **load-bearing for each other**: `:34` references `tables.NaturalNameWarning`, so dropping the import raises `NameError` at module-import time. |

**Prefs pin values kept as undecided: none** — see F6.10.

**Files plan 06 edited beyond its declared `files_modified`** (plan 08 read this list when diffing
the manifest; none is protect-listed, and the manifest diff is zero):
`external/__init__.py` (31 lines), `transform/image.py` (12), `tasks/mics_task.py` (11),
`networking/node.py` (7), `transform/selection.py` (6), `setup/forms.py` (4),
`stim/sound/base.py` (4), `stim/managers.py` (3), `core/loggers.py` (2). The plan anticipated
"11 smaller files"; the scan surfaced **9** with removable superseded blocks.

### F6.18 — `Message` and `hardware_state` are user-designated do-not-touch

**User directive, 2026-08-10.** `autopilot/autopilot/networking/message.py` and the
`hardware_state` machinery in `hardware/gpio.py` + `utils/logging_utils.py` are important classes
and were off-limits for the remainder of the phase — no edits, no comment sweeping, no
"while we're here" fixes.

Two defects were found in them during plan 06 and **recorded deliberately without fixing**. Both
are real, both belong to their own phase where they can be changed against a rig proof, and both
are carried into `30-PUBLISH.md` under *Known defects, deliberately not fixed*:

- **`Message.__setitem__` does not invalidate the serialization cache.** `message.py:111` is
  `# self.changed=True` (commented) while `serialize()` at `:199` short-circuits on
  `if not self.changed and self.serialized`, so mutating a `Message` after one serialization can
  put **stale bytes on the wire**.
- **`hardware_state` is read live and written almost nowhere.** Read at `gpio.py:439` and
  `logging_utils.py:95`; the only live write is `gpio.py:877`; its writer is the commented
  `state_changing_methods` block.

`gpio.py`'s `hardware_state` block was left fully intact, and `message.py` keeps its live code
byte-identical — the sweep removed comments only, which the user reviewed and chose to leave as-is
on 2026-08-10.

### F6.19 — the HYG-05 correction — **CLOSED**

An earlier reading claimed `Camera` was *"never used in `i2c.py`… only docstring prose. It is a
dead import."* **That was false.** `Camera` is the **base class of `MLX90640`** — `i2c.py:580
class MLX90640(Camera):`, body spanning `:580`–`:798`, directly above `MPR121` at `:799`. The claim
came from misreading filtered `grep` output that rendered line 580 as blank. Acting on it —
removing the import but keeping the class — leaves an undefined name evaluated at module-import
time, killing the pilot silently.

The correct edit was **three-part**: drop the import, drop the `MLX90640` class, drop `cameras.py`
— applied in both the Pi copy **and** `hardware_libs`.

**Status: CLOSED, and the amendment has already landed** — REQUIREMENTS.md HYG-05 carries it in the
row itself, and 30-CONTEXT.md carries it as an inline `> **CORRECTION, 2026-08-10 (planning).**`
block. Plan 05 executed all three parts, and its own execution surfaced a *second* trap of the same
family: the plan's literal cut boundary (*"through the last line before `class MPR121`"*) would
have eaten `i2c.py:792-796` — `import board`, `import busio`, `import adafruit_mpr121` — which
`MPR121.__init__` depends on. **`py_compile` would not have caught it**; the module still parses.
The class was cut to its AST `end_lineno` instead, with both ends asserted.

### F6.20 — `grep` on this host has corrupted three measurements in this phase

The shell's `grep` is rewritten to a compressing proxy. Its failures so far:

1. **It rendered a matching line blank** — the root cause of F6.19, which nearly deleted
   `MLX90640`'s base class.
2. **It stripped the `./` path prefix non-deterministically** — two runs in the same session
   rendered the same corpus once with and once without it, failing plan 07's exact-string gate
   while the underlying file set was already correct.
3. **`git status` returned the literal string `ok`** through it while the working tree had real
   content (plan 07), which nearly caused an already-committed ledger to be misread as uncommitted.

The same class of interception hit plan 08 directly: `find … -not … -exec` is refused by the proxy
with `rtk find does not support compound predicates or actions`, so the cache purge had to invoke
**`/usr/bin/find`** explicitly.

**Standing rule, applied throughout plan 08:** invoke `/usr/bin/grep` (and `/usr/bin/find`)
explicitly in any gate that string-compares their output; prefer comparing a **set of paths** over
a joined string, which is immune to prefix and ordering artefacts alike; and take every
load-bearing count from an unfiltered `python3 -c` reader, never from `grep` at all.

### F6.21 — the cache purge ran twice, and the second run is the authoritative one

Plan 02 deliberately deferred the purge: it shared Wave 1 with plan 03, whose `compileall`
regenerates `__pycache__`, so a purge-then-assert there would have been a race against a sibling
plan.

Plan 08 ran it **twice**:

| Run | When | Purpose |
|---|---|---|
| Preliminary | before `--final` | so the F1 size measurement reflects what will actually reach the repo |
| **Authoritative** | **after** this plan's `compileall`, the Pi suite, the backend suite **and `--final`** | the run `<done>` describes; the last thing in the plan that touches the tree |

**Ordering was the whole point.** `--final`'s F4 (HYG-06) shells out to
`python3 -m compileall -q autopilot/autopilot/tasks`, which **creates**
`autopilot/autopilot/tasks/__pycache__`. Purging before `--final` would have left a cache directory
behind and made the completion criterion false at plan end. The executed chain was
`compileall → backend pytest → Pi delta → tree-absence tests → --final → purge → assert clean → du`.

The cost is that F1's *internal* size measurement counts bytecode; harmless, since the measured
budget is 1.05 MiB against an 8 MiB limit and the authoritative `du` ran post-purge.

Deleting the caches costs no evidence: the audit used *which* `.cpython-37` pycs exist as evidence
of what actually loads on the device (it is what settled the `jackclient.py`/`pyoserver.py` vs
`sounds.py`/`base.py` question), and that evidence was already extracted into 30-CONTEXT.md.

---

## §7 Exit-gate verification (plan 08)

Every number below was produced at the exit gate, not carried forward.

| Gate | Result |
|---|---|
| `python3 -m compileall -q autopilot/autopilot tools tests` | **exit 0** |
| `docker compose exec -T api python -m pytest -q tests/` | **435 passed, 1 skipped** (the suite has grown past the 352 `CLAUDE.md` still quotes) |
| Pi suite, `delta_command` from `30-PYTEST-BASELINE.json` | **exit 0** — baseline 179, now 179, **0 new failing node ids**, 0 newly passing |
| Pi suite, raw counts | **179 failed / 203 passed / 382 collected** |
| Guard's own unit tests | **22 passed** |
| `test ! -e autopilot/{tests,examples,docs}` and `test ! -e terminal` | **all absent** |
| `python3 tools/check_tree_integrity.py --strict` | **exit 0** — `40 closure members, 30 protected files, 1 known-dangling exemptions held, 0 violations` |
| `python3 tools/check_tree_integrity.py --final` | **exit 0** |
| F1–F6 individually (`f1_bulk`, `f2_prefs`, `f3_toggles`, `f4_tasks_compile`, `f5_cameras`, `f6_json_parses`) | **0 violations each**, none weakened, no live code deleted to satisfy one |
| **HYG-13 manifest diff, 30 protected paths** | **zero drift on md5 AND sha256**; the md5 table in §1 and `tree_protect_list.json`'s `baseline_sha256` are the same 30-path set; 0 missing |
| Phase 26 `reserved_absent` names | all **3 still absent**, none reported as a stray |
| `__pycache__` / `*.pyc` / `.pytest_cache` outside `.git`, after the authoritative purge | **0 / 0 / absent** (unfiltered `os.walk`, not `find`) |
| `du -sb --exclude=.git .` − `du -sb pilot/sounds` | **1,097,505 B ≤ 8,388,608** |
| `/usr/bin/grep -n 'OG_TRIGGER\|IR1' pilot/prefs.json` | 4 lines — the **live** pin declarations, correct, not to be "fixed" |
| Credential probe still present at `/home/ido/.hyg01-probe.txt` | **yes** |
| Probe literals in the surviving tree excluding `.git` | **0 hits** |
| All five `Scopes.DIRECTORY` runtime dirs carry `.gitkeep` | `pilot/{data,logs,viz,calibration,protocols}` — **yes** |
| `--rebaseline` | **never run**, at any point in the phase |
| `tree_protect_list.json` edited | **never**, at any point in the phase |
| Git commands in `/home/ido/pi-mirror` | **none in plan 08.** One read-only `git log` rode a compound `cd` in plan 03 and is disclosed in `30-03-SUMMARY.md`; no index write, no ref update, no lock |
| Deployed to the Pi / `rsync` / pilot start-stop / Python run on the Pi | **none, at any point in the phase** |

---

## §8 Deferred — carried out of this phase, not fixed by it

Each of these was found or confirmed during the sweep and deliberately left. None is a regression
introduced by Phase 30.

| Item | Where | Why deferred |
|---|---|---|
| `LOAD_HARDWARE_LIBS` fails silently during a run | `mics_task.py:1589` imports `autopilot.autopilot.core.pilot`, which does not resolve | Deferred **by name** in 30-CONTEXT.md; the guard asserts it stays broken (F6.1). Undercuts the mechanism the whole hardware-centralization arc rests on. |
| No `TASK_ERROR` emitter on the Pi | `pilot.py:609` | The single largest silent-failure mode in the system; restoring it is a behavioural change. |
| `Message.__setitem__` cache invalidation | `message.py:111` vs `:199` | **User-designated do-not-touch** (F6.18). |
| `hardware_state` has no live writer | `gpio.py:877` is the only one | **User-designated do-not-touch** (F6.18). |
| NTP / clock-freeze block | `pilot.py:1071-1082` | **User-deferred 2026-08-10** (F6.7). Still a regression, and the user has taken it on. |
| `_handshake_watchdog`'s `except Exception: print("")` | `station.py:1270-1283` | **User-deferred 2026-08-10** (F6.8). |
| `i2c.py:819` `except(e):` on an undefined name | MPR121 init failures raise `NameError` | `i2c.py` off-limits under TRIGA-12. |
| `pilot.py` calls the undefined `get_hardware_class` | `STREAM_VIDEO` raises | Out of scope. |
| `hardware_libs` ↔ disk drift has no sync process | — | Restated **without** the "6 bytes apart" claim (F6.16). The general concern stands; the cited instance was a measurement artifact. |
| 8 toolkits + `available_locked_states` rows now resolve to deleted files | ids 88, 89, 92, 93, 96, 97, 98, 99 | Locked user decision: **document, do not do DB surgery**. Full consequence in `30-PUBLISH.md` under *Known consequences*. |
| GUI-only deps still in `requirements.txt` | `npyscreen`, `PySide2`, `shiboken2`, `pyqtgraph` | Dead weight now that the Terminal is gone; removing them is a real improvement and out of scope for a cleanup phase (F6.13). |
| The two adafruit pins are unresolved | `requirements.txt` | Deliberately unpinned; must be resolved on the first fresh image (F6.13). |
| `hardware/__init__.py:54`'s `META_CLASS_NAMES` | names `Camera`, `Directory_Writer`, `Video_Writer`, all removed | Read **nowhere** — an inert constant, not a dispatch table. |
| 3 newly-unused imports in `i2c.py` | `threading`, `product`, `griddata` | `i2c.py` off-limits under TRIGA-12; dropping `griddata` would change what the module demands of the rig's environment. |
| `trial_data` in `run_task` is write-only | `pilot.py` | Live code, so outside HYG-11's scope. |
| The `NOLOG` message flag is sent but not honoured | `station.py:315` logs unconditionally | The `log_this` gate is commented out; kept as a HYG-11 keep. |
| `autopilot/README.md` still links removed modules | `autopilot.core.terminal` / `.gui` / `.subject` / `viz` | `.md` is not in the guard's `SCAN_SUFFIXES`; belongs to whoever owns the upstream README. |
| `available_locked_states` spelling drift | `AppetitveTaskReal` vs disk `AppetitiveTaskReal`, etc. | Pre-existing; the backend never prunes handshake rows. |
| Roadmap bookkeeping corruption | phase-summary table rows 11–14, 16, 18 | Pre-existing. |

---

*Phase 30 · opened by plan 30-01 · closed by plan 30-08 · `.planning/phases/30-pi-repo-cleanup/`*
