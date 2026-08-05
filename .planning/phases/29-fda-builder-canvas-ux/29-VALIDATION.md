---
phase: 29
slug: fda-builder-canvas-ux
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-05
---

# Phase 29 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

**Framing.** This is a visual phase, so the instinct is "it's all manual". That is wrong here.
The *geometry decisions* — which edges belong to a parallel group, what offset each gets, what
column and row a state lands in, where a new node is placed — are pure functions of the FDA
graph. Extracting them into `.mts` modules is already required by CANVAS-11 (keep
`TaskEditor.tsx` from growing), and once extracted they are directly unit-testable with the
infrastructure this repo already runs. What genuinely cannot be automated is whether the
result *looks* right — that, and only that, is the manual set.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `node --test` (Node 20 built-in runner) on `.test.mts` files |
| **Config file** | `web_ui/react-src/package.json` → `scripts.test:unit` |
| **Quick run command** | `cd web_ui/react-src && npm run test:unit` |
| **Full suite command** | `cd web_ui/react-src && npm run test:unit && npx tsc -b` <br> `docker compose exec -T api python -m pytest -q tests/` |
| **Estimated runtime** | ~0.1 s frontend tests; ~1.2 s backend tests; ~5–10 s with typecheck |

Baseline verified 2026-08-05 before planning: **84 tests, 84 pass, 0 fail, 100 ms.**

Established repo pattern (7 existing modules): pure logic lives in
`web_ui/react-src/src/components/<name>.mts`, its test in
`web_ui/react-src/tests/<name>.test.mts`. New Phase 29 logic modules follow it exactly — this
is not new infrastructure, it is the same shape as `detectorOptions.mts` /
`detectorOptions.test.mts`.

**Correction (2026-08-05):** an earlier draft of this file claimed there is no backend test
suite, taking `CLAUDE.md`'s "No automated test suite — verify manually by calling relevant
endpoints after changes" at face value. That line is stale. `api/tests/` holds 12 pytest
modules; verified by running them:

```
docker compose exec -T api python -m pytest -q tests/
→ 352 passed, 1 skipped in 1.21s
```

Note the in-container path is `tests/`, not `api/tests/`. CANVAS-05 and CANVAS-06 are
therefore **automated** (see map below), not manual curl steps — CANVAS-06 in particular
("`file_hash` must not move on a layout-only PUT") is the kind of invariant that belongs in an
assertion, not in a human's eyeballs.

**Amendment (2026-08-05, after planning):** the phase gained two requirements,
**CANVAS-13** (back-edge routing) and **CANVAS-14** (orphan packing), added from real data —
definition 186's `rand → trial_onset` runs backward across two columns straight through
`play_led`, and definitions 172 / 161 / 155 each carry 11+ unreachable toolkit states that
CANVAS-07's single trailing column would render as an unbounded stack. Both land as additional
cases in `edgeGeometry.mts` (plan 29-02) and `fdaLayout.mts` (plan 29-03), so both are largely
**automatable** — the geometry decision is a pure function of the transition list plus the BFS
ranking, exactly like CANVAS-01. Rows for both appear in the maps below. The manual half moves
the walkthrough onto two named definitions (186 and 172) instead of "a definition with a
bidirectional pair".

---

## Sampling Rate

- **After every task commit:** `npm run test:unit` (100 ms — no reason to batch it); backend
  tasks additionally run `pytest -q tests/` (1.2 s)
- **After every plan wave:** `npm run test:unit && npx tsc -b` **and** `pytest -q tests/`
- **Before `/gsd:verify-work`:** both suites green, plus the CANVAS-12 walkthrough
- **Max feedback latency:** ~10 s

---

## Per-Task Verification Map

Task IDs are assigned by the planner; the **Requirement** column is the stable key. Every row
marked `unit` must end up attached to a real task, and the planner should extend this table
with its actual task IDs rather than replacing the requirement mapping.

| Plan (expected) | Requirement | Test Type | Automated Command | Notes |
|---|---|---|---|---|
| edge geometry | CANVAS-01 | unit | `npm run test:unit` | Grouping by unordered node pair; offset index assignment. Cases: single edge → offset 0; `A→B` + `B→A` → symmetric opposing offsets; two `A→B` → distinct offsets; three-plus group stays symmetric about centre. |
| edge geometry | CANVAS-02 | unit | `npm run test:unit` | Label position fraction differs per group member. Assert `condLabel` output is byte-identical to today for a set of trees incl. Phase 16 nested AND/OR — this phase must not alter label *text*. |
| edge geometry | CANVAS-03 | manual | — | Arrowhead presence is a render concern; tangent-vs-chord orientation is judged visually. |
| edge geometry | CANVAS-04 | unit | `npm run test:unit` | `A→A` classified as self-loop, not fed to the pair-offset path; N self-loops on one node get N distinct offsets. |
| layout | CANVAS-07 | unit | `npm run test:unit` | BFS rank from `initial_state` → column index; siblings get distinct rows; **unreachable states are placed, never dropped** (assert output node count == input state count); no two states share an (x,y); empty graph and single-state graph do not throw. |
| layout | CANVAS-08 | unit | `npm run test:unit` | Placing a new state returns a position colliding with no existing position, and returns the existing positions **unchanged** (deep-equal assertion — this is the regression that matters). |
| backend | CANVAS-05 | integration | `docker compose exec -T api python -m pytest -q tests/test_ui_layout.py` | `ADD COLUMN IF NOT EXISTS` migration + GET/PUT round-trip asserted in a new `api/tests/test_ui_layout.py`. |
| backend | CANVAS-06 | integration | `docker compose exec -T api python -m pytest -q tests/test_ui_layout.py` | Assert `file_hash` is **unchanged** across a `ui_layout`-only PUT, and **does** change on an `fda_json` PUT. Both directions — the whole reason the column exists. |
| backend | CANVAS-10 | integration | `docker compose exec -T api python -m pytest -q tests/test_ui_layout.py` | A layout-only PUT must succeed even when the stored `fda_json` would fail `reject_if_hard_errors`. Without a short-circuit, a drifted toolkit makes every node drag 4xx — a backend-origin CANVAS-10 violation. |
| edge geometry | CANVAS-13 | unit | `npm run test:unit` | Back-edge classification and routing. Cases: `backSpan = ranks[from] - ranks[to]`; `>= 2` → `kind:'back'`, `=== 1` → stays `pair` (the locked boundary); unranked endpoint → never `back`; back-edges partitioned OUT of pair groups so **definition 186's `play_led ⇄ rand` offsets are byte-identical with and without `ranks`**; achieved apex clearance ≥ 70px (assert the clearance, NOT the constant — the cubic gives `0.75 × controlOffset`); `pointOnCubic(...,0.99).x < b.x` so the arrowhead enters the target's left handle pointing inward. |
| layout | CANVAS-14 | unit | `npm run test:unit` | Orphan grid block. Named case is definition 172 (3 connected + 11 unreachable): all 14 placed; orphans occupy ≥ 2 distinct x; no orphan column holds more than `max(connectedRows, ceil(sqrt(orphanCount)))` = **4**; every orphan's x exceeds every connected state's x; zero coordinate collisions; `placeNewState` still returns a free slot around the block. |
| layout | CANVAS-13 | unit | `npm run test:unit` | `columnRanks` is the single BFS, exported from `fdaLayout.mts` and passed into `assignEdgeGeometry` as a parameter. Assert it returns exactly `{init:0, trial_onset:1, play_led:2, rand:3}` for the 186 topology, omits unreachable states, and that `layeredLayout`'s column for every reachable state equals its `columnRanks` value — two BFS implementations could disagree and bow the curve clear of the wrong band. |
| UI wiring | CANVAS-09 | manual | — | Pane context menu → restore → positions recomputed and persisted. |
| UI wiring | CANVAS-10 | manual | — | Drag-persists-while-autosave-held. See negative case below. |
| discipline | CANVAS-11 | automated | `wc -l web_ui/react-src/src/pages/task-editor/TaskEditor.tsx` | Gate: result must be **≤ 873**. Cheap, objective, and the requirement is otherwise easy to quietly violate. |
| proof | CANVAS-12 | manual | — | Full walkthrough, below — now run on definition **186**, whose 5 transitions exercise every routing case at once. |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] No framework install needed — `node --test` is built in and already wired to
      `scripts.test:unit`.
- [ ] Test files are created **alongside** their logic modules in the same task, following the
      existing `detectorOptions.mts` / `detectorOptions.test.mts` pairing. No separate stub wave.

*Existing infrastructure covers all automatable phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|---|---|---|---|
| Migration applied to the live DB | CANVAS-05 | Schema state is outside the test DB | After `docker compose up --build api`, confirm `\d task_definitions` shows `ui_layout jsonb`. The round-trip itself is automated (above); this checks the migration actually ran against the real database. |
| Arrowhead orientation | CANVAS-03 | Visual judgement on a curve | On a bidirectional pair, confirm each arrowhead sits at the target end and points along its own arc — not skewed toward the straight line between node centres. |
| Bidirectional readability | CANVAS-01, 02 | Visual | Open a task definition with a `CUE ⇄ TIMEOUT` pair. Both arcs separately traceable; both condition labels legible, neither clipped nor overlapping. |
| Self-loop | CANVAS-04 | Visual | A state with an `A→A` transition shows a visible loop carrying its own label and arrowhead. |
| Restore default layout | CANVAS-09 | Visual + interaction | Right-click empty canvas → menu appears in the same style as the node menu → "Restore default layout" → nodes snap to spaced layered arrangement → **hard-refresh → that arrangement persisted** (restore must save, not just redraw). |
| Drag persists while autosave is held | CANVAS-10 | Requires deliberately dirty FDA state | Add a trigger assignment and leave it unnamed so the header shows `Not saved — finish or remove trigger…`. **While that hold is active**, drag a node. Hard-refresh. Node is where it was left, and the incomplete trigger was *not* saved. This is the single most important negative case in the phase — it proves layout and FDA persistence are genuinely separate paths. |
| No FDA dirty-marking on drag | CANVAS-10 | Visual | With a clean saved FDA, drag a node → header must not flash "Unsaved…" for the drag itself. |
| Back-edge clears the states it spans | CANVAS-13 | Visual judgement on a curve; clearance in px is asserted in unit tests, but "does it read as a return path" is not | On definition **186**, `rand → trial_onset` must bow BELOW the row and pass clear of `play_led` — not through it, not clipping its border. Its arrowhead must arrive at `trial_onset`'s left handle pointing INTO the node, not away from it. Its condition label must be legible and not stacked on another. **Check 4 of plan 29-08's checkpoint — the only manual proof CANVAS-13 gets.** |
| Back-edge survives a restore | CANVAS-13 | Visual | After "Restore default layout" on 186, the back-edge must again route clear of `play_led`. A failure here means the layout and the routing disagree about columns — they share one BFS by design, so it is a real defect, not cosmetic. Check 12. |
| Orphan block is readable | CANVAS-14 | Visual — "readable" is the requirement, and it is a judgement | Open definition **172** (`bbb FDA`), right-click → "Restore default layout". The 3 connected states form a short chain; the 11 unreachable states must form a block of at most 4 per column beside it, not one 11-tall column running off-canvas. No overlap between orphans, or between an orphan and the chain. **Check 13 — the only look at CANVAS-14 anywhere in the phase.** |
| Full proof walkthrough | CANVAS-12 | End-to-end visual | Per CANVAS-12 as amended: on definition **186**, all five transitions separately traceable with none crossing a node → drag three nodes apart → hard-refresh → all three held → right-click → restore → refresh → restored arrangement held. |

---

## Validation Sign-Off

- [ ] All automatable geometry (CANVAS-01, 02, 04, 07, 08, 13, 14) has unit coverage in `tests/*.test.mts`
- [ ] `TaskEditor.tsx` line count ≤ 873 (CANVAS-11)
- [ ] `npm run test:unit` green — including the 84 pre-existing tests, no regressions
- [ ] `pytest -q tests/` green — including the 352 pre-existing tests, no regressions
- [ ] `npx tsc -b` clean
- [ ] Every manual row above executed and recorded
- [ ] CANVAS-10 negative case explicitly exercised, not assumed
- [ ] CANVAS-13 back-edge check (29-08 check 4) and CANVAS-14 orphan-block check (check 13)
      explicitly exercised — neither can be inferred from any other check
- [ ] All THIRTEEN rows of plan 29-08's checkpoint table have a recorded result

---

*Sampling continuity note:* every task in this phase has automated feedback. The geometry
modules run in 100 ms via `node --test`; the backend column work runs in 1.2 s via pytest.
No stretch of consecutive tasks relies on manual verification alone — the manual rows are
purely "does it look right", which is genuinely un-automatable and is deliberately the only
thing left to a human.
