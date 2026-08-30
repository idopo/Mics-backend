---
phase: 34-mics-link-sdk-client-package
verified: 2026-08-30T10:22:12Z
status: human_needed
score: 10/15 roadmap success criteria verified locally; 5 depend on the unrun 34-09 hardware/Windows checkpoint
overrides_applied: 0
human_verification:
  - test: "Ten-line sender drives a real FDA transition on pilot 1 (extlink_demo, task def 434) — success criterion 3"
    expected: "wait -> armed -> fired -> wait visible in Elasticsearch (event_log_v2 on 132.77.73.217), no latency number printed"
    why_human: "Requires a live rig and a running pilot; the agent cannot start/stop the pilot or send to real hardware (34-09 is autonomous: false)"
  - test: "Heartbeat keeps a quiet source alive on the rig — success criterion 5"
    expected: "demo.alive stays true for >3x stale_ms (3000ms) with no signals sent, while individual signals go stale under their own policy"
    why_human: "Requires observing pilot_hardware_config liveness state on the real rig over wall-clock time"
  - test: "Pi restart mid-session does not require restarting the sender — success criterion 6"
    expected: "on_state_change logs disconnect then reconnect, sending resumes automatically, seq keeps climbing rather than resetting"
    why_human: "Only the user may restart the pilot process (hard project rule); the agent never starts/stops pilots"
  - test: "Soak at the arc's real send rate — success criterion 12"
    expected: "Pilot stays up, FDA keeps transitioning, drop counter reported, ES ingestion keeps up, no latency number printed"
    why_human: "Requires sustained load against the live rig for a realistic session length"
  - test: "Windows install + replay + rig send inside the DeepLabCut conda environment — success criterion 13 / SDK-14"
    expected: "python -m pip install <wheel-url> is a dependency no-op (pyzmq/msgpack already satisfied, no upgrade proposed), pip check clean, mics-link-replay or python -m mics_link.replay drives the same FDA cycle as from Linux, a backslash+space path works, the printed summary survives cp1252, Ctrl+C stops cleanly"
    why_human: "No agent on this Linux dev host can run Windows; a Linux venv proves nothing about cp1252 console encoding, WinAPI sleep granularity, or console-script PATH placement"
  - test: "msgpack version matrix (1.0.3 / 1.0.5 / 1.2.1) — SDK-02(a)"
    expected: "The frozen golden corpus packs/unpacks identically under all four msgpack versions in the matrix (vision box, Pi pin, this dev host, mics_core's resolved version)"
    why_human: "This dev host only has msgpack 1.2.1 installed; 1.0.3/1.0.5 require the vision-box / Pi environments to actually exercise, which 34-09 is scoped to do"
---

# Phase 34: MICS-Link SDK Client Package Verification Report

**Phase Goal:** An external computer that is not a Pi and knows nothing about MICS can push data
into a running task's View / FDA framework in ten lines of Python — `pip install mics-link`, point
it at a pilot's `listen_port` with the configured `source_id`, call `send_signal("left_paw_x", 0.7)`
— and an FDA transition fires on the rig. One supported wire implementation on the sender side.
No DeepLabCut and no trained model in this phase.

**Verified:** 2026-08-30T10:22:12Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Summary of method

This was not a documentation review. Every claim below with a "Command run" line was executed
fresh in this session: the wheel was built and installed with `pip --target` into a throwaway
venv, `import mics_link` was run with zero prior imports of `zmq`/`msgpack` to prove the module is
importable with neither installed, `numpy.float64` was fed to `validate_value` live and rejected,
the wire-parity suite was run against the real, read-only Pi reference tree at
`/home/ido/mics_core/autopilot/autopilot/hardware/external_hardware_wire.py` (never edited), and a
deliberately mutated frame was shown to fail the golden-hex comparison to prove the byte-level
assertion is actually sensitive to drift, not a decode-then-compare test that would paper over it.
Six of the seven 34-REVIEW.md findings were confirmed fixed in the shipped code (not just claimed
fixed in a commit message); the seventh (IN-01) was confirmed genuinely still present, matching the
phase's own stated deferral.

**34-09 (the hardware/Windows checkpoint, `autonomous: false`) has not run.** No
`34-HARDWARE-VALIDATION.md` and no `sdk/examples/rig_checkpoint_sender.py` exist on disk. This is
not treated as a gap in the other 8 plans' work — it is the phase's own designed checkpoint,
requiring the user physically at pilot 1's rig and a Windows box neither this agent nor this dev
host can reach. Its absence is why this report's status is `human_needed`, not `passed`.

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `pip install` on a foreign machine, exactly pyzmq+msgpack, Python 3.8+, no upper cap | ✓ VERIFIED | Built `py3-none-any` wheel, `pip install --target` into a throwaway venv with zero repo access: `Requires-Dist: pyzmq>=22`, `msgpack>=1.0`, `Requires-Python: >=3.8`, no upper bound. Full install closure = exactly `msgpack`, `pyzmq`(+`.libs`) — no numpy anywhere, confirmed by `grep -rn numpy sdk/src/` returning zero import hits (prose mentions only). `import mics_link` succeeds with `numpy` absent from `sys.modules` afterward. |
| 2 | Wire parity enforced by a test, byte-for-byte, against `external_hardware_wire.py`; CMD decodes | ✓ VERIFIED | `sdk/tests/test_wire_parity.py` — 22/22 pass, live-run against the real read-only file at `/home/ido/mics_core/autopilot/autopilot/hardware/external_hardware_wire.py` (md5 `76dd4f8d...`, confirmed identical to the pi-mirror secondary today). Assertions are raw `bytes ==` comparisons, not unpack-then-compare — proven sensitive by feeding a 1-bit-mutated frame through the same comparison and watching it fail. |
| 3 | Ten-line sender drives a real FDA transition on the rig, observed in ES | ? UNCERTAIN | Code-level pieces (client, dtype validation, transport) are fully unit-tested and the "ten real lines" claim is mechanically enforced (`test_readme_contract.py::test_ten_line_sender_is_ten_lines_or_fewer`, counts 4). **No rig send has occurred.** This is exactly 34-09's Task 3/4, unrun. |
| 4 | Sends never block; bounded queue drops NEWEST, counted, surfaced | ✓ VERIFIED | `sender.py`'s `BoundedSender` uses `queue.Queue.put_nowait` + `queue.Full` (drop-newest, not deque's drop-oldest); `stats.dropped`/`on_drop` both exercised in `test_sender_bounded_drop.py`. `_send_frame` in `client.py` now counts a `transport.send()` failure into `stats.send_failed` rather than discarding it (CR-01 fix, confirmed live in the shipped code, not just the commit message). |
| 5 | Heartbeat keeps a quiet source `alive` past the Pi's `stale_ms` | ? UNCERTAIN | `heartbeat.py`'s scheduling logic is pure-function tested (`test_heartbeat_scheduling.py`) with a documented 1:3 heartbeat:`stale_ms` ratio. **Never observed against a real Pi's liveness poller.** 34-09 Manual-Only row, unrun. |
| 6 | Pi restart mid-session survives without restarting the sender | ? UNCERTAIN | `reconnect.py`'s state machine and `seq` continuity are unit-tested (`test_reconnect_state_machine.py`, `test_client_integration.py`) over a fake transport / synthetic monitor events. **Never observed against an actual pilot restart.** 34-09 Manual-Only row, unrun. |
| 7 | `@link.command(...)` dispatch + `ACK`, handler-raises → error `ACK`, no client crash | ✓ VERIFIED (with a stated, permanent evidence gap) | `test_command_dispatch.py` — 19 tests, off-hot-path dispatch, error-ACK, unregistered-command, unencodable-result, KeyboardInterrupt-propagates, all pass. `commands.py`'s own module docstring states plainly: zero Pi-side CMD sender exists anywhere in either autopilot tree (verified by the plan's own grep), so this requirement is provable **only** by synthetic frames — a permanent limitation, not a gap this phase can close. |
| 8 | Exactly one sender-side wire implementation; POC driver deleted | ✓ VERIFIED | `tools/extlink_driver/extlink_wire.py`, `extlink_driver.py`, `test_extlink_wire.py` confirmed absent from the working tree (git log shows the deletion commit `144bbe2`); `extlink_demo_fda.json` + a redirect `README.md` retained as required. Repo-wide grep for `extlink_wire`/`extlink_driver` imports returns only historical comments in the SDK's own docstrings pointing at the deleted path — nothing imports them. No second `msgpack`-based sender codec exists anywhere else in the repo (only vendored `pip`/`jupyter_client` copies inside unrelated `.venv` directories, not application code). |
| 9 | Whole SDK unit-testable with no socket, no network, no Pi | ✓ VERIFIED | `test_import_hygiene.py::test_wire_importable_with_zmq_unavailable` runs a real subprocess with a `sys.meta_path` finder that raises `ImportError` for `zmq` before import — passes. `zmq` import is confined to function bodies inside `transport.py` only (AST-checked across the whole package). Full offline suite: **280 passed, 1 deselected** (fresh run, this session), plus the opt-in `zmq_loopback` test passes separately. |
| 10 | Replay entry point plays a `(t, signal, value)` file at real time / scaled / fast | ✓ VERIFIED | `test_replay.py` — 31 tests, long+wide CSV/JSONL parsing, origin-relative `Pacer` timing (realtime/scaled/fast), malformed-row counting, CLI exit codes. `mics-link-replay --help` and `python -m mics_link.replay` both resolve and run from a fresh `pip install`ed venv in this session. |
| 11 | README a non-MICS programmer can follow end to end | ✓ VERIFIED | Read `sdk/README.md` in full (329 lines, above the 120-line contract minimum). Contains all required sections: install (2 paths, public-repo/token risk stated), rig prerequisites, exact `pilot_hardware_config.config` shape with a warning about the `host` field trap, pull-loop + callback/push senders, FDA/ES observability section, replay section, 8 numbered pitfalls, and a "why no latency readout" section. `test_readme_contract.py` (47 tests) mechanically enforces markers, device-neutrality, ASCII-only, and that every `mics_link.__all__` name is documented — all pass. |
| 12 | Soak from a non-Pi machine at the arc's real rate | ? UNCERTAIN | No soak has been run against a live pilot. 34-09 Manual-Only row, unrun. |
| 13 | Windows proven, or recorded as unproven — never asserted | ? UNCERTAIN (design proven, hardware unproven) | `SDK-14`'s Linux-checkable design constraints are all met and tested: `tcp://`-only (`endpoint()` never emits `ipc://`), no `os.fork`/`signal.SIGALRM`/`resource`/`os.getuid`/`fcntl`/`termios` anywhere in the package (`test_import_hygiene.py`), explicit `encoding="utf-8"` (+`newline=""` for CSV) on every file open in `replay_io.py`, ASCII-only README/examples (`test_readme_and_examples_are_ascii_only`), daemon IO thread (`test_io_thread_is_created_as_a_daemon_thread`), `python -m mics_link.replay` documented as the PATH-independent fallback. **The actual Windows machine has never been touched by any agent** — this dev host is Linux, and no Linux venv can prove cp1252 console behavior, WinAPI sleep granularity, or a real DLC-env dependency resolution. 34-09's Windows checkpoint is unrun. |
| 14 | Send path survives a foreign callback thread at frame rate (SDK-15) | ✓ VERIFIED | `test_client_integration.py::test_concurrent_senders_from_8_threads_produce_no_duplicate_or_out_of_order_seq` — 8 threads × 500 sends, re-ran fresh in this session: 0 errors, `seq` strictly increasing with no duplicates. `send_signal`/`send_event` hold only small locks (`_seq_lock`, `BoundedSender`'s internal stats lock) and never touch the transport directly (decision 1, `client.py` module docstring). |
| 15 | `mics_link.timing.Pacer` is public; replay accepts wide files alongside long | ✓ VERIFIED | `from mics_link import Pacer` succeeds (`__all__` includes it); `test_timing.py` and `test_replay.py` (`test_wide_csv_produces_the_same_tuples_as_long_csv`, `test_wide_jsonl_produces_the_same_tuples_as_long_csv`) both pass. Wide-format fixtures exist and are exercised: `sdk/tests/fixtures/replay_sample_wide.csv`, `.jsonl`. |

**Score:** 10/15 verified locally; 5 (#3, #5, #6, #12, #13) are explicitly rig- or Windows-dependent and gated behind the unrun 34-09 checkpoint.

### Requirements Coverage (SDK-01 .. SDK-15)

| Requirement | Source Plan | Status | Evidence |
|---|---|---|---|
| SDK-01 | 34-01, 34-08 | ✓ SATISFIED (foreign-machine leg UNCERTAIN) | Wheel build + `pip --target` install verified this session on this dev host; the "foreign machine that has never seen MICS" leg and the Windows leg are 34-09's job, unrun. |
| SDK-02 | 34-01 | ✓ SATISFIED (msgpack version matrix UNCERTAIN) | Byte-parity + live-interop tests pass against the real Pi file; `selfcheck()` runs inside `connect()` and via `python -m mics_link.selfcheck` (verified, prints `OK`). The 4-point msgpack version matrix (1.0.3/1.0.5/1.2.1/mics_core's resolved) is only exercised at 1.2.1 on this host — the other three points are 34-09's job. |
| SDK-03 | 34-02 | ✓ SATISFIED | `test_transport_config.py` — identity=source_id, `router_bind`-only, no public identity setter, all pass. |
| SDK-04 | 34-02 | ✓ SATISFIED | Exact-type check (`type(value) is dtype`, not `isinstance`) confirmed by live test in this session: `numpy.float64` rejected with a message naming `as_scalar`; `as_scalar(np.float64(1.5))` returns a genuine `float`. |
| SDK-05 | 34-03 | ✓ SATISFIED (rig behavior UNCERTAIN) | Pure scheduling logic tested offline; never observed against a real Pi liveness poller (34-09). |
| SDK-06 | 34-02 | ✓ SATISFIED | Drop-newest via `queue.Queue`/`put_nowait`, locked counters, `on_drop` callback exception-swallowed — all tested. |
| SDK-07 | 34-03, 34-06 | ✓ SATISFIED (real Pi-restart UNCERTAIN) | State machine + seq continuity over fake transport tested; real pilot restart is 34-09's job. |
| SDK-08 | 34-04 | ✓ SATISFIED, with a stated permanent evidence gap | Synthetic-frame-only by design — no Pi-side CMD sender exists anywhere; the module's own docstring states this plainly rather than implying rig-proof. |
| SDK-09 | 34-06 | ✓ SATISFIED | `test_lifecycle.py` — 12 tests: context manager, idempotent `close()`, drain-then-abandon, daemon thread, `close()` from a second thread while IO thread running. CR-02's fix (never close the transport from outside the IO thread while it may still be using it) confirmed present in `client.py`. |
| SDK-10 | 34-05 | ✓ SATISFIED | Deletion confirmed on disk and in git log; no remaining imports anywhere in the repo. |
| SDK-11 | 34-01 | ✓ SATISFIED | Subprocess-level proof (`test_wire_importable_with_zmq_unavailable`) plus this session's own zero-zmq/zero-msgpack `--target` install-and-import. |
| SDK-12 | 34-07 | ✓ SATISFIED | 31 tests across long/wide CSV/JSONL, three timing modes, CLI exit codes. |
| SDK-13 | 34-08 | ✓ SATISFIED | README read in full; 47-test contract suite passes; meets the 120-line minimum at 329 lines. |
| SDK-14 | 34-01, 34-03, 34-06, 34-07, 34-08 (amendments) | ⚠ PARTIAL — design/Linux-testable half SATISFIED, Windows-hardware half UNCERTAIN | Every Linux-checkable clause (a–e, g, h) has a passing automated test. Clause (f) (`time.sleep` granularity) and the live Windows install/replay/Ctrl+C behavior (34-09's Windows checkpoint) are unrun and explicitly UNPROVEN, not asserted. No plan's `requirements-completed` frontmatter lists SDK-14 — it is threaded through as cross-cutting amendments rather than owned by one plan, which matches the roadmap's own framing ("Windows... never asserted") but is worth naming as a bookkeeping gap. |
| SDK-15 | 34-06 (amendment) | ✓ SATISFIED | Concurrent-senders test passes (re-run fresh this session). Not listed in any plan's `requirements-completed` frontmatter either — same bookkeeping note as SDK-14; the functional evidence exists regardless. |

**No requirement ID is orphaned** — SDK-01 through SDK-15 all appear in at least one plan's `requirements:` frontmatter or CONTEXT.md amendment, and REQUIREMENTS.md's Phase 34 rows all trace to a plan. The only process-level note is that SDK-14/SDK-15 never appear in any plan's `requirements-completed:` summary field despite genuine, passing test coverage — a documentation gap, not a functional one.

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `sdk/pyproject.toml` | PEP 621, src layout, exactly 2 deps, no upper bound | ✓ VERIFIED | `requires-python = ">=3.8"`, `dependencies = ["pyzmq>=22", "msgpack>=1.0"]` |
| `sdk/src/mics_link/wire.py` | Pure codec, no zmq | ✓ VERIFIED | 136 lines, byte-parity proven live against the real Pi file |
| `sdk/src/mics_link/client.py` | Public `MicsLink`, one IO thread | ✓ VERIFIED | 299 lines (under the 300-line project limit), CR-01/CR-02 fixes present |
| `sdk/src/mics_link/selfcheck.py` | msgpack-numpy corruption detector | ✓ VERIFIED | Runs inside `connect()`; `python -m mics_link.selfcheck` prints `OK` from a real pip-installed venv |
| `sdk/README.md` | End-to-end researcher doc | ✓ VERIFIED | 329 lines, all required sections present, 47-test contract passing |
| `sdk/examples/ten_line_sender.py` | ≤10 real lines, standalone | ✓ VERIFIED | 4 counted real lines (import, `with connect`, `for`, `send_signal`); `my_existing_loop()` is an explicitly-labeled placeholder for the researcher's own acquisition loop, not elided SDK code |
| `sdk/examples/callback_sender.py` | Push-shape example (SDK-15) | ✓ VERIFIED | Present, parses, device-neutral, exempt from line-count bar per its own test |
| `tools/extlink_driver/extlink_wire.py` etc. | Deleted | ✓ VERIFIED | Absent from disk, deletion commit `144bbe2` in git log |
| `.planning/phases/.../34-HARDWARE-VALIDATION.md` | 34-09's evidence log | ✗ MISSING | 34-09 has not run (`autonomous: false`, not a gap in the other plans) |
| `sdk/examples/rig_checkpoint_sender.py` | 34-09's rig script | ✗ MISSING | Same — 34-09 has not run |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `sdk/tests/test_wire_parity.py` | `/home/ido/mics_core/autopilot/autopilot/hardware/external_hardware_wire.py` | `importlib.util.spec_from_file_location` | ✓ WIRED | File exists, is read-only (not touched), loads successfully, 22/22 parity tests pass against it live in this session |
| `sdk/src/mics_link/__init__.py:connect()` | `sdk/src/mics_link/selfcheck.py` | `_run_selfcheck()` call inside `connect()` | ✓ WIRED | Confirmed at `__init__.py:65`, inside the function body (not import-time) |
| `sdk/src/mics_link/client.py` | `sdk/src/mics_link/transport.py` | dependency-injected `Transport` seam | ✓ WIRED | `zmq` import confined to `transport.py` function bodies; `test_transport_module_importable_with_zmq_unavailable` passes |
| `[project.scripts] mics-link-replay` | `mics_link.replay:main` | setuptools entry point | ✓ WIRED | Console script resolves and runs `--help` from a real pip-installed venv in this session |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Build `py3-none-any` wheel | `python -m build --wheel` (throwaway venv) | `Successfully built mics_link-0.1.0-py3-none-any.whl` | ✓ PASS |
| Zero-dependency-closure install | `pip install --target <dir> <wheel>` (no-deps) then `import mics_link` | `['connect', 'MicsLink', 'MicsLinkError', 'InvalidValueError', 'SenderStats', 'Pacer', '__version__']` printed, no zmq/msgpack needed | ✓ PASS |
| Full dependency closure = exactly pyzmq+msgpack | `pip install --target <dir> <wheel>` (with deps); `ls <dir>` | `mics_link, msgpack, pyzmq, pyzmq.libs` — no numpy | ✓ PASS |
| `import mics_link` never imports numpy | live Python check after import | `'numpy' in sys.modules` → `False` | ✓ PASS |
| numpy.float64 rejected, `as_scalar` fixes it | live call to `validate_value`/`as_scalar` | Rejected with a message naming `as_scalar`; `as_scalar(...)` returns plain `float` which then validates | ✓ PASS |
| Wire byte-sensitivity | mutate one byte of an encoded frame, compare to golden hex | Original matches, mutated does not | ✓ PASS |
| Full offline test suite | `cd sdk && python3 -m pytest` | `280 passed, 1 deselected` | ✓ PASS |
| Opt-in loopback test | `cd sdk && python3 -m pytest -q -m zmq_loopback` | `1 passed` | ✓ PASS |
| Wire parity suite alone, against the real Pi file | `pytest tests/test_wire_parity.py -v` | `22 passed` (live interop group ran, not skipped — reference file present) | ✓ PASS |
| Concurrent-senders (SDK-15) | `pytest tests/test_client_integration.py::test_concurrent_senders_...` | `1 passed` | ✓ PASS |
| Console script + `pip check` from a real install | `pip install <wheel>; mics-link-replay --help; pip check` | Help text printed; `No broken requirements found.` | ✓ PASS |
| `python -m mics_link.selfcheck` from a real install | same venv | Prints `OK` (with a benign, cosmetic `runpy` re-import `RuntimeWarning` — not a functional failure) | ✓ PASS |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| `sdk/src/mics_link/replay_io.py` | 204-231 | Wide-format JSONL doesn't reject EVT-shaped dict values the way long-format does (IN-01) | ℹ️ Info | No data-loss risk (caught downstream by `validate_value`); inconsistent counter attribution between long/wide malformed rows. Consciously deferred by the phase's own review, confirmed still present, non-blocking. |
| — | — | No `TBD`/`FIXME`/`XXX`/`TODO`/`HACK` markers found anywhere in `sdk/src`, `sdk/tests`, `sdk/examples` | — | — | Clean |

No blocker-level anti-patterns found. Both CR-01 and CR-02 (the review's two Critical findings) are confirmed fixed in the shipped code, not merely claimed fixed.

### Requirements Coverage — Orphaned Check

REQUIREMENTS.md's Phase 34 block (lines 320-334) contains exactly SDK-01 through SDK-15; all 15 appear in at least one plan's `requirements:` frontmatter (34-01 through 34-09) or as an explicit amendment cited in `34-CONTEXT.md`. No orphaned requirement IDs found.

### Human Verification Required

See frontmatter `human_verification:` — six items, all gated behind the unrun 34-09 plan (`autonomous: false`). These are not code gaps; they are the phase's own designed hardware/OS checkpoint that only the user can execute (live rig, Pi restart, Windows box). Running them and recording results in `34-HARDWARE-VALIDATION.md` is what would move this phase from `human_needed` to `passed`.

### Gaps Summary

No code-level gap was found. Every artifact the 8 autonomous plans (34-01..34-08) claimed to build exists, is substantive, is wired, and its automated tests pass when re-run fresh in this session — including a live, byte-level check against the real (read-only) Pi reference file. The code-review's two Critical and three Warning findings are all confirmed fixed in the shipped code; the one Info-level finding left unfixed (IN-01) is exactly as small and as consciously deferred as the review said.

What is **not** proven, stated plainly per the verification brief: nothing in this phase has touched a real Pi or a real rig. The goal sentence's final clause — "an FDA transition fires on the rig" — together with the heartbeat-liveness, Pi-restart-survival, soak, and Windows-install/replay claims (roadmap success criteria 3, 5, 6, 12, 13) are all local-only evidence today: unit tests over fake transports and synthetic frames, not a rig observation. SDK-08's inbound-CMD evidence is permanently synthetic-only because no Pi-side CMD sender exists anywhere in either autopilot tree — this is not a Phase 34 gap, it is a stated, permanent scope boundary. The msgpack version matrix (SDK-02a) is verified only at the one msgpack version installed on this dev host (1.2.1); the vision-box (1.0.3) and Pi (1.0.5) points are unverified here.

All of this converges on plan **34-09**, which is `autonomous: false` and has not been run. Its absence is the sole reason this report is `human_needed` rather than `passed` — there is no other blocking gap.

---

_Verified: 2026-08-30T10:22:12Z_
_Verifier: Claude (gsd-verifier)_
