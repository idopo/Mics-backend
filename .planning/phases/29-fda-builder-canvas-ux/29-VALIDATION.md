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
| **Full suite command** | `cd web_ui/react-src && npm run test:unit && npx tsc -b` |
| **Estimated runtime** | ~0.1 s tests; ~5–10 s with typecheck |

Baseline verified 2026-08-05 before planning: **84 tests, 84 pass, 0 fail, 100 ms.**

Established repo pattern (7 existing modules): pure logic lives in
`web_ui/react-src/src/components/<name>.mts`, its test in
`web_ui/react-src/tests/<name>.test.mts`. New Phase 29 logic modules follow it exactly — this
is not new infrastructure, it is the same shape as `detectorOptions.mts` /
`detectorOptions.test.mts`.

There is **no backend test suite** (`CLAUDE.md`: "No automated test suite — verify manually by
calling relevant endpoints after changes"). The `ui_layout` column and its GET/PUT round-trip
are verified by direct endpoint calls, recorded in the manual table below.

---

## Sampling Rate

- **After every task commit:** `npm run test:unit` (100 ms — no reason to batch it)
- **After every plan wave:** `npm run test:unit && npx tsc -b`
- **Before `/gsd:verify-work`:** full suite green, plus the CANVAS-12 walkthrough
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
| backend | CANVAS-05 | manual | — | `ADD COLUMN IF NOT EXISTS` migration + GET/PUT round-trip via curl. |
| backend | CANVAS-06 | manual | — | Assert `file_hash` is unchanged across a `ui_layout`-only PUT — the whole reason the column exists. Compare hash before/after via the task-definitions list endpoint. |
| UI wiring | CANVAS-09 | manual | — | Pane context menu → restore → positions recomputed and persisted. |
| UI wiring | CANVAS-10 | manual | — | Drag-persists-while-autosave-held. See negative case below. |
| discipline | CANVAS-11 | automated | `wc -l web_ui/react-src/src/pages/task-editor/TaskEditor.tsx` | Gate: result must be **≤ 873**. Cheap, objective, and the requirement is otherwise easy to quietly violate. |
| proof | CANVAS-12 | manual | — | Full walkthrough, below. |

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
| Migration + round-trip | CANVAS-05 | No backend test suite in this repo | `docker compose up --build api`; confirm column: `\d task_definitions` shows `ui_layout jsonb`. `PUT /api/task-definitions/{id}` with `{"ui_layout":{"nodes":{"CUE":{"x":10,"y":20}}}}` → `GET` returns it verbatim. Restart api → still there. |
| Layout does not touch content hash | CANVAS-06 | Requires comparing DB state across requests | `GET /api/task-definitions` → note `file_hash` for the row. PUT a `ui_layout`-only change. `GET` again → **`file_hash` identical**. Then PUT an `fda_json` change → `file_hash` *does* change. Both directions matter. |
| Arrowhead orientation | CANVAS-03 | Visual judgement on a curve | On a bidirectional pair, confirm each arrowhead sits at the target end and points along its own arc — not skewed toward the straight line between node centres. |
| Bidirectional readability | CANVAS-01, 02 | Visual | Open a task definition with a `CUE ⇄ TIMEOUT` pair. Both arcs separately traceable; both condition labels legible, neither clipped nor overlapping. |
| Self-loop | CANVAS-04 | Visual | A state with an `A→A` transition shows a visible loop carrying its own label and arrowhead. |
| Restore default layout | CANVAS-09 | Visual + interaction | Right-click empty canvas → menu appears in the same style as the node menu → "Restore default layout" → nodes snap to spaced layered arrangement → **hard-refresh → that arrangement persisted** (restore must save, not just redraw). |
| Drag persists while autosave is held | CANVAS-10 | Requires deliberately dirty FDA state | Add a trigger assignment and leave it unnamed so the header shows `Not saved — finish or remove trigger…`. **While that hold is active**, drag a node. Hard-refresh. Node is where it was left, and the incomplete trigger was *not* saved. This is the single most important negative case in the phase — it proves layout and FDA persistence are genuinely separate paths. |
| No FDA dirty-marking on drag | CANVAS-10 | Visual | With a clean saved FDA, drag a node → header must not flash "Unsaved…" for the drag itself. |
| Full proof walkthrough | CANVAS-12 | End-to-end visual | Per CANVAS-12: bidirectional pair reads correctly → drag three nodes apart → hard-refresh → all three held → right-click → restore → refresh → restored arrangement held. |

---

## Validation Sign-Off

- [ ] All automatable geometry (CANVAS-01, 02, 04, 07, 08) has unit coverage in `tests/*.test.mts`
- [ ] `TaskEditor.tsx` line count ≤ 873 (CANVAS-11)
- [ ] `npm run test:unit` green — including the 84 pre-existing tests, no regressions
- [ ] `npx tsc -b` clean
- [ ] Every manual row above executed and recorded
- [ ] CANVAS-10 negative case explicitly exercised, not assumed

---

*Sampling continuity note:* the geometry modules are testable in isolation and run in 100 ms,
so there is no stretch of consecutive tasks without automated feedback except the backend
column work (CANVAS-05/06), which is two tasks and is covered by explicit curl steps above.
