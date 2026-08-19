# Phase 31 — Hardware Validation Log

Evidence for the phase's hardware-gated requirements. **Nothing in this file may be
written from expectation.** Every number is pasted from a command the user actually ran on
the rig, with the command that produced it directly above it. A section with no output
under it stays marked NOT RUN — an empty section is a true statement; a plausible one is
not.

Created by plan 31-C4 Task 0 (2026-08-19) as the destination the C4 campaign fills.

---

## Status

| Requirement | Owner | Status |
|---|---|---|
| PLAT-17 — SCHED_FIFO measured, not assumed | C4 Task 2 §4 | **NOT RUN** |
| PLAT-24 — paired before/after regression gate | C4 Task 3 | **BLOCKED — no before arm** (see §0) |
| PLAT-25 — wall-clock step, both directions | C4 Tasks 1 §3 / 2 §5 | **NOT RUN** |
| PLAT-29 — ≥ 3 tick wraps observed | C4 Task 1 | **NOT RUN** |
| PLAT-30 — the two dispatch routes agree | C4 Task 1 §2 | **NOT RUN** |
| PLAT-31 — every event carries a provenance flag | C4 Task 1 §2 | **NOT RUN** |
| PLAT-32 — dropped samples counted, never silent | C4 Task 1 §6 | **NOT RUN** |
| Output fail-safe behaviour, per device | C4 Task 2 §6 | **NOT RUN** |

---

## §0 The before arm does not exist, and the confound in what does

**Plan 31-08 was skipped by user decision.** No `before_*.jsonl` capture was ever taken, so
`tools/pulse_timing/captures/` is empty and **PLAT-24's paired regression has no baseline**.
This is a stated limitation of the phase, not an oversight to be worked around, and no
G1-style comparison may be reported as if the baseline existed.

**Mitigation:** tag `phase-31-buster-before-arm` at commit `9fc8837` preserves the tree as
it stood before C2 touched `gpio.py`, so a `before` capture stays re-derivable on a Buster
card if one is ever wanted. **Do not move or delete that tag.**

**The confound, if a before arm is ever captured:** it would come from Buster / armhf /
Python 3.7.3 / kernel 5.10, while every `after` arm comes from Bookworm / aarch64 / Python
3.11 / a current kernel. A G1 result would therefore compare two whole platforms, of which
the clock layer is one difference among several. It would not invalidate the gate — a
regression is still a regression — but **G1 could not be quoted as "the clock refactor cost
nothing."** That sentence belongs directly beneath any G1 table.

---

## §1 Client provenance — what was actually measured

_C4 Task 1 step 1. Paste the full output. Both `hasattr` lines must read `False`._

```
NOT RUN
```

| Field | Value |
|---|---|
| `pigpio.__file__` | _NOT RUN_ |
| client sha256 | _NOT RUN_ |
| `hasattr(pi, 'synchronize')` | _NOT RUN_ (must be `False`) |
| `hasattr(pi, 'ticks_to_timestamp')` | _NOT RUN_ (must be `False`) |
| `pigpiod -v` | _NOT RUN_ |
| board / kernel / python | _NOT RUN_ |

---

## §2 after arm — the ≥ 3-wrap soak (PLAT-29, PLAT-30, PLAT-31)

_C4 Task 1. Artifact: `tools/pulse_timing/captures/soak_after.jsonl`, arm `soak-fifo10`,
4.33 h under `stress-ng` load._

**Soak gate output** (Task 3's verbatim gate, run on the artifact):

```
NOT RUN
```

| Measurement | Required | Observed |
|---|---|---|
| raw-tick wraps | ≥ 3 | _NOT RUN_ |
| backward jumps in `delivered` | 0 | _NOT RUN_ |
| `t_mono_ns` non-decreasing | yes | _NOT RUN_ |
| witness records lacking `ts_source` | 0 | _NOT RUN_ |
| route sample pairs | > 0 | _NOT RUN_ |
| two-route disagreements | 0 | _NOT RUN_ |
| `construction_drained` | `true` | _NOT RUN_ |

---

## §3 after arm — the forced wall-clock steps (PLAT-25)

_C4 Task 1 step 4 (in-soak, ±1 h) and Task 2 step 3 (four short `train` captures)._

**The six `date` lines from the in-soak steps:**

```
NOT RUN
```

| Capture | Applied step | `clock_step` record | `--check-step` verdict |
|---|---|---|---|
| in-soak, T+60 min | +1 h | _NOT RUN_ | _NOT RUN_ |
| in-soak, T+120 min | −1 h | _NOT RUN_ | _NOT RUN_ |
| `step_fwd_idle.jsonl` | +1 h | _NOT RUN_ | _NOT RUN_ |
| `step_bwd_idle.jsonl` | −1 h | _NOT RUN_ | _NOT RUN_ |
| `step_fwd_loaded.jsonl` | +1 h | _NOT RUN_ | _NOT RUN_ |
| `step_bwd_loaded.jsonl` | −1 h | _NOT RUN_ | _NOT RUN_ |

---

## §4 after arm — PLAT-17, does SCHED_FIFO reach the threads that matter

_C4 Task 2 step 2. `chrt -p` on **every** thread, pilot and `pigpiod`. POSIX threads
inherit policy by default, but "should" is not a measurement._

```
NOT RUN
```

**Verdict on the directive:** _NOT RUN._ If `after-fifo10` is not measurably better than
`after-other` on `err_p99`, `err_sd` and `n_missing`, **say so and recommend dropping
`CPUSchedulingPolicy=fifo`.** A max-priority CPython process can make the box unreachable;
quietly keeping an unjustified RT directive is the outcome PLAT-17 exists to avoid.

---

## §5 after arm — the paired campaign (PLAT-24, twenty captures)

_C4 Task 2 step 1: five profiles × two loads × two scheduling arms._

Read §0 first: **there is no before arm.** The twenty `after` captures are an internal
`fifo10`-vs-`other` comparison only.

| Profile | Load | `after-other` err_p99 / err_sd / n_missing | `after-fifo10` err_p99 / err_sd / n_missing |
|---|---|---|---|
| valve | idle | _NOT RUN_ | _NOT RUN_ |
| valve | loaded | _NOT RUN_ | _NOT RUN_ |
| valve_short | idle | _NOT RUN_ | _NOT RUN_ |
| valve_short | loaded | _NOT RUN_ | _NOT RUN_ |
| ttl | idle | _NOT RUN_ | _NOT RUN_ |
| ttl | loaded | _NOT RUN_ | _NOT RUN_ |
| train | idle | _NOT RUN_ | _NOT RUN_ |
| train | loaded | _NOT RUN_ | _NOT RUN_ |
| mixed | idle | _NOT RUN_ | _NOT RUN_ |
| mixed | loaded | _NOT RUN_ | _NOT RUN_ |

---

## §6 after arm — drop accounting (PLAT-32)

_C4 Task 1 steps 5–6. See `tools/pulse_timing/README.md` `## PLAT-32 accounting` for what
each signal can and cannot show. **`pigpiod` exposes no dropped-sample counter to the
client** — a "zero drops" claim cannot rest on reading one, because there is none to read._

| Signal | Class | Observed |
|---|---|---|
| `n_missing` (= commanded − observed) | **primary** | _NOT RUN_ |
| `ambiguous_gap` | FAULT — asserted zero | _NOT RUN_ |
| `monotonic_violation` | FAULT — asserted zero | _NOT RUN_ |
| `convert_failed` | FAULT — asserted zero | _NOT RUN_ |
| `heartbeat_missed` | FAULT — asserted zero | _NOT RUN_ |
| `wraps` / `out_of_order` / `duplicates` / `refits` | activity — printed, never asserted | _NOT RUN_ |
| `bracket_rejected` / `fit_rejected` | reported, not asserted | _NOT RUN_ |
| `_dropped_no_clock` / `_dropped_on_send` | dispatcher | _NOT RUN_ |
| `journalctl -u mics-pilot -b` over the window | daemon warnings | _NOT RUN_ |

A non-zero count is a **finding reported with its count**, not a number to average away:
it *satisfies* PLAT-32 ("never as silence") while *failing* the acceptance gate. Two
different verdicts — say which happened.

---

## §7 Output fail-safe, per device

_C4 Task 2 step 4. Meter across each output device, clean SIGTERM stop and then SIGKILL._

**Known before the measurement:** `start_pigpiod()`'s `kill_proc` hook cannot reach the
daemon at all — `subprocess.Popen(shell=True)` makes `proc` the shell wrapper, `pigpiod`
daemonises and is reparented to init, and it runs under `sudo`. This is **pre-existing and
unfixed**; PLAT-33 was withdrawn on the belief that this hook closes the solenoids at
session end, which it does not. Record what actually happens per device rather than what is
expected.

| Device | ARM 1 — `systemctl stop` (SIGTERM) | ARM 2 — `systemctl kill -s SIGKILL` |
|---|---|---|
| VALVE1 | _NOT RUN_ | _NOT RUN_ |
| VALVE2 | _NOT RUN_ | _NOT RUN_ |
| VALVE3 | _NOT RUN_ | _NOT RUN_ |
| VALVE4 | _NOT RUN_ | _NOT RUN_ |
| AIR_PUF | _NOT RUN_ | _NOT RUN_ |
| ODOR1–5 | _NOT RUN_ | _NOT RUN_ |

---

## §8 NOT PROVEN

Everything the campaign did **not** establish, listed plainly. This section is mandatory
and must not be left empty to imply completeness.

- **PLAT-24 paired regression** — no before arm exists (§0). Unproven, and not provable
  without a Buster capture off tag `phase-31-buster-before-arm`.
- Every row still reading NOT RUN above.
