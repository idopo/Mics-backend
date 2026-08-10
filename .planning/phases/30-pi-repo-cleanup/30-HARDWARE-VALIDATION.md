# Phase 30 — Hardware Validation Log

**Opened:** 2026-08-10 (plan 30-01, Wave 0)
**Tree under test:** `/home/ido/pi-mirror` — untouched apart from the Wave 0 instrument itself
**Undo:** `~/pi-mirror.bak-2026-08-10` (plain copy; `pi-mirror` has no agent-managed git)
**Status:** baseline captured. No removal has happened yet. Every requirement below is UNPROVEN
by construction — later plans flip rows as they land.

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
| HYG-01 credential absent from the new repo's history | UNPROVEN | probe captured (§3); proof runs in plan 08/09 against the new repo |
| HYG-02 pilot starts and a real session completes | UNPROVEN | USER-RUN rig session, plan 09. Blocked on clearing `ExtlinkDemo` off pilot 1 |
| HYG-03 plugin cluster removed, ordering held | UNPROVEN | `check_tree_integrity.py --strict` after plan 04 |
| HYG-04 empty HANDSHAKE is a no-op | UNPROVEN | live API check, plan 08 |
| HYG-05 `cameras.py` + both import copies removed | UNPROVEN | guard `--final` F5 + backend pytest (`hardware_libs` v26) |
| HYG-06 sweep collateral removed, `tasks/` compiles | UNPROVEN | guard `--final` F4 (`compileall`) |
| HYG-07 Terminal tree removed | UNPROVEN | guard check 2 + `--final` F1 |
| HYG-08 vendored/generated bulk removed | UNPROVEN | guard `--final` F1 — ≤ 8 MB excluding `.git` **and** `pilot/sounds/` |
| HYG-09 root pytest config replaces `autopilot/pytest.ini` | UNPROVEN | landed in plan 01; see §1. Flips to PROVEN at the exit gate |
| HYG-10 no rig-specific config in `prefs.json` | UNPROVEN | guard `--final` F2 |
| HYG-11 244 dead lines removed | UNPROVEN | `compileall` + guard check 1 |
| HYG-12 `Event_Dispatcher.py` drop counters survive | UNPROVEN | guard core check 4 — green today, must stay green |
| HYG-13 survival manifest intact | UNPROVEN | guard core check 3 against the §1 md5/sha256 manifest |
| HYG-14 restorations applied, holds resolved | UNPROVEN | guard `--final` F3 — **call forms, never bare tokens**; NTP assertion **inverted** (§6.7) |

*Verdicts are PROVEN only against evidence recorded in this file.*

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

> The phase plan records 202,275,257 for the first row. The 355,067-byte difference is this
> plan's own additions (`tools/check_tree_integrity.py`, `tools/tree_integrity/`,
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

Corroboration that the pre-existing failure set is bit-for-bit unchanged by plan 01: the phase
plan measured 179 failed / 181 passed over 360 collected *before* the guard's own tests existed;
this run is 179 failed / 202 passed over 381 — the same 179 failures plus the 21 new guard tests,
all passing.

The two `collect_ignore`d modules fail on `npyscreen`, not on `sys.path`; the bootstrap in
`conftest.py` does not and cannot help. They are expected to collect and pass on the Pi.

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
instrument and later plans may need to extend it.

> **Finding.** The phase plan's Task 2 `<done>` asserts "exactly 19 collectable modules". That
> arithmetic counts the 21 pre-existing modules but not the module plan 01 Task 1 itself creates.
> The measured, correct number is **20**. Recorded rather than silently adjusted — see
> `30-01-SUMMARY.md` Finding 1.

---

## §3 Credential probe (HYG-01)

The Gmail address and 16-character Google app password at
`pilot/plugins/AssociationLearning.py:1323-1324` were captured **before** plan 04 deletes that
file, because the literal strings are what proves the new repo's history is clean.

| Property | Value |
|---|---|
| Path | `/home/ido/.hyg01-probe.txt` — **outside every repository**, by design |
| Mode | `600` |
| Lines | 2 literals, one per line, no surrounding quotes (suitable for `grep -F -f`) |
| Blank lines | **0**, including no trailing blank line — verified with `! grep -qc '^$'` and `wc -l == grep -c .` |
| sha256 | `63a70fd973793d19bfac8cbdc3e7ca4c258964e1123c12f548b2db1ba12992f4` |

**The values themselves are never recorded here or anywhere under `.planning/`.** A blank line in
the probe would make `grep -F -f` match everything and silently invert every assertion that
depends on it, which is why the no-blank-line property is asserted rather than assumed.

**Still open (human action, outside any repo):** revoke the app password at Google → account →
app passwords. Must happen **before** publication, not after. Deleting the file is not
sufficient — the credential is in `.git`, which is why publication is a fresh `git init` and
never a clone or a filtered history.

---

## §4 Removal ledger

Every later plan appends its removals here. This table is what makes HYG-07's "reproducible from
criteria, not from a hand-list" true rather than aspirational.

| Path | C1 not in static closure | C2 not dynamically reached | C3 not named by backend | C4 not reserved | Plan |
|---|---|---|---|---|---|
| _(empty — no removals yet)_ | | | | | |

**Ordering is a hard constraint:** subclasses before base classes, always. `api/main.py:1059-1070`
raises 400 on an unresolvable `base_class`, and because the commit is at `:1117` inside
`orchestrator_station.py:85-183`'s single `try`, that 400 discards the tasks upsert, the toolkit
upsert, the hardware-config seed and the locked-states upsert together.

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

---

## §6 Findings and corrections

_Filled progressively; plan 08 completes it._ Seeded now with the instrument-level exemptions so
they are visible rather than buried in JSON.

### F6.1 — `known_dangling`: one deferred defect, asserted to stay broken

`autopilot.autopilot.core.pilot` referenced from `autopilot/autopilot/tasks/mics_task.py:1589`.
See §1. The guard asserts the anchor file exists, the reference text is still present, and the
module still does **not** resolve. A *working* import here is a failure, because it would mean an
untested behavioural change to the rig shipped under cover of a cleanup phase.

### F6.2 — `scan_skip`: four directories the scanner ignores during Waves 0–1

`autopilot/tests/`, `autopilot/examples/`, `autopilot/docs/`, `terminal/`.

Rationale: plans 02 and 03 run in parallel in Wave 1. `autopilot/tests/test_terminal.py:9` does a
genuine `import autopilot.core.terminal`; if plan 03 lands first the guard flags a file plan 02
deletes in the same wave — a false failure caused only by intra-wave ordering. The three upstream
vendored trees are never in the pilot's import closure. `terminal/` is skipped for the same
reason: its only clause-2(d) hits are dead Terminal-host config in `terminal/prefs.json`
(runtime-generated `calibration`/`sounds`/`viz` dirs and the upstream `termina/plugin_db.json`
typo), and plan 03 removes the whole tree.

**The skip is not a permanent hole:** `--final` F1 asserts all four paths are *gone*. The scanner
may ignore them during Wave 1; it may not ignore their survival at the exit gate.

### F6.3 — `runtime_generated`: `pilot/plugin_db.json`

Referenced by `pilot/prefs.json` (`PLUGIN_DB`). Generated on the device at runtime by the plugin
scanner; it has never existed in the mirror. No plan creates it and plan 07 leaves the
`PLUGIN_DB` key alone by design, so without this exemption clause 2(d) flags `pilot/prefs.json`
on the untouched tree and stays red through `--final`.

### F6.4 — clause 2(d) parse skip, closed by `--final` F6

Three `.json` files do not parse and are skipped for the path check, each reported as a `note:`
rather than swallowed: `.vscode/launch.json` (JSONC — it has `//` comments),
`terminal/pilot_db1.json`, `terminal/pilot_db2.json`. **All three are deleted by plan 03**, and
`--final` F6 asserts every surviving `.json` parses — the same bargain F1 strikes for `scan_skip`.

### F6.5 — F3 asserts call forms, never bare tokens

`IR1` and `OG_TRIGGER` are **live GPIO pin declarations** in `pilot/prefs.json`
(`HARDWARE.GPIO.IR1` at `:278`/`:282`, `HARDWARE.GPIO.OG_TRIGGER` at `:241`/`:243`) that survive
this phase by design — HYG-10 deliberately leaves the `GPIO`, `I2C`, `Mixer`, `Timers` and
`Modules` groups intact. What HYG-14 retires is the commented-out *toggle*, not the pin. A
tree-wide `! grep -q 'OG_TRIGGER'` would therefore fail at the exit gate, after every destructive
plan has landed and before any rig proof, and the only compliant response would be stripping live
GPIO entries with no rig evidence. F3 asserts `set_cdc_manual(0x3f)`, `self.triggers['IR1']` and
`pulse_and_notify(...OG_TRIGGER...)` and nothing else.

### F6.6 — the guard excludes its own source from every tree-wide scan

`tools/check_tree_integrity.py`, `tools/tree_integrity/`, `tools/tree_protect_list.json` and
`tests/test_tree_integrity.py` necessarily *contain* the literals they search for. They are
excluded from F3, F5, the 2(b)/2(c) string scans and clause 2(d)'s path scan. 2(d) is included
deliberately: `tree_protect_list.json`'s own `scan_skip` values are repo-relative glob-free paths,
so the moment plans 02 and 03 delete those trees the guard's protect-list would become four
self-inflicted violations and every wave from 1 onward would fail on the instrument rather than
the tree.

### F6.7 — the NTP restoration is deferred, so F3's NTP assertion is inverted

**User decision, 2026-08-10, mid-execution of plan 01.** The clock block in
`autopilot/autopilot/core/pilot.py:1137-1148` stays **commented out**; plan 06 no longer
uncomments it and the user will handle it separately.

F3 was amended before it ever ran in anger. It now asserts that `self.enable_ntp_and_wait()` and
`self.disable_ntp()` each appear **only in commented form** (`^\s*#\s*self\.…`) and **never
uncommented** (`^\s*self\.…`), and that the two surrounding comments survive:
`# ---- CLOCK SETUP ----` and `# Freeze wall clock so it never jumps during the task`.

Two failure modes are now covered where the original wording covered neither:
1. an accidental uncomment — shipping an untested clock change to the rig under cover of a cleanup;
2. **the likelier accident** — plan 06's 244-line dead-comment sweep eating the block, which
   would leave the deferred work unrecoverable and invisible.

Had F3 kept asserting the calls are *live*, `--final` would have failed at plan 08 — after every
destructive plan had landed and before any rig proof — over a change the phase deliberately no
longer makes. Measured after the amendment: F3 reports **26** violations on the untouched tree,
**none of them NTP-related**; all 26 belong to plans 04, 05 and 06 and are expected to clear as
those land.

---

*Phase 30 · opened by plan 30-01 · `.planning/phases/30-pi-repo-cleanup/`*
