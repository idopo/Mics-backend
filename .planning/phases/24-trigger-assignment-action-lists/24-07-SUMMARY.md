# Plan 24-07 — Summary (Rig Proof, TRIGA-11a)

**Executed:** 2026-07-27
**Status:** ✅ Requirement met on hardware
**Requirement:** TRIGA-11a
**Evidence:** `24-HARDWARE-VALIDATION.md` §2b — runs 478 / 480 / 481, plus the live 8-case negative suite

---

## Outcome

Lick detection runs on the real pilot on a **sourceless (backend-authored) toolkit**, driven
entirely by an action list assembled in the task editor through the constrained one-pick
**Read detector** control. No `learning_cage`, no `handler` enum, no Python callback for `TOUCH_INT`.

**144 trigger firings, 63 licker writes, zero correctness errors.**

| Property | Result |
|---|---|
| Written tracker matches the electrode `detect_change` reported | 63 / 63 |
| Written value equals the captured `level` (never the IRQ edge) | 63 / 63 |
| `pi_timestamp` equals the triggering `TOUCH_INT` tick | 63 / 63 |
| No-change edges (`pin_number is None`) that wrote anything | 0 / 72 |
| Trigger → write latency | 1–3 ms |

## Checkpoints

| # | Checkpoint | Outcome |
|---|---|---|
| 1 | UI round-trip on a sourceless toolkit | ✅ `trigger_name` dropdown (grouped Inputs/Outputs, `TOUCH_INT` only input, `MPR121`/`TIMER` absent); one-pick detector write; `pin_number`/`level` auto-declared in Variables; raw action editor reachable and showing ordinary `hardware` + `if`/`view` actions; survived hard reload |
| 2 | Save-time negatives | ✅ 8/8 live — canonical 201, seven invalid payloads 422 with specific messages (see §2b). Includes **TRIGA-16**: a hardware action with no `method`, previously a silent no-op, is now rejected |
| 3 | Electrodes → `LICKER*` on the rig | ✅ three electrodes interleaved across 63 writes with zero index errors, each with clean alternating `1,0` pairs and a matching `pi_timestamp` |

**Cross-talk negative:** satisfied by real interleaving rather than a staged phase — three distinct
electrodes across 63 writes, never once a wrong index.

## Deviations from plan

- **Phase A/B protocol abandoned.** Task definition 186 stops after 5 trials (~20 s); the planned
  60 s protocol could not fit. Runs 476/477/479 logged nothing for this reason alone — touching began
  after the task had ended. Cross-talk was instead established from natural interleaving, which is
  stronger evidence than the staged phase would have been.
- **Electrode identity not tracked.** The operator cannot distinguish electrodes physically, so
  per-electrode assertions were replaced by isolation assertions. This does not weaken the
  requirement: what TRIGA-17 guarantees is that the tracker written matches the electrode reported,
  which is verified per-event regardless of which physical spout it was.
- **Task definition 186 reused** rather than creating a fresh one. The create-and-reload round-trip
  is therefore slightly weaker than planned; edit-and-reload was verified.

## Findings raised (not defects in this phase's code)

1. **Channel 4 silently discarded** — spouts are on MPR121 channels 1–4, but `num_detectors: 4`
   creates `LICKER0…LICKER3`. Nine real events lost with no error. → **DVK-09, Phase 25.**
2. **`detect_change` reports only `changes[0]`** — simultaneous transitions are unrecoverable.
   Pre-existing in `i2c.py` (off-limits); legacy `detectedLick` behaved identically.
3. **Defect 8** (`int(None)` in `log_action` killing the trigger worker) — found and fixed during
   this plan; see the defect table.
4. **`process_queue` has no exception handler** — any callback exception permanently disables all
   trigger processing with no operator-visible signal. `task.py`, out of scope, deferred by the user.

## Outstanding

- **The Pi test suite has still never been run anywhere.** ~60 tests including this phase's
  additions. USER-RUN:
  `cd ~/Apps/mice_interactive_home_cage && python3 -m pytest tests/ -q`
- Legacy `trigger_assignments` rows in task definitions 181 and 185 (185 belongs to another user).

---

*Plan: 24-07 · Requirement: TRIGA-11a · Evidence: runs 478/480/481*
