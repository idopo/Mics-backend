---
phase: 29-fda-builder-canvas-ux
plan: 04
subsystem: api
tags: [fda-editor, canvas, task-definitions, migrations]
requires: []
provides:
  - "task_definitions.ui_layout JSONB column"
  - "GET/PUT /api/task-definitions/{id} ui_layout surface"
  - "TypeScript UiLayout type + updateTaskDefinition ui_layout payload"
affects:
  - "plan 29-06 (canvas persistence, not yet built — this plan ships the surface only)"
tech-stack:
  added: []
  patterns:
    - "Migrated columns (raw SQL, not declared on the ORM class) — same pattern as fda_json/display_name"
    - "Layout-only PUT fast path returns before reject_if_hard_errors/_validate_task_definition run"
key-files:
  created:
    - api/tests/test_ui_layout.py
  modified:
    - api/db.py
    - api/models.py
    - api/routers/toolkits.py
    - web_ui/react-src/src/types/index.ts
    - web_ui/react-src/src/api/task-definitions.ts
decisions:
  - "ui_layout NOT added to list_task_definitions (GET /api/task-definitions) — only the editor's GET-by-id needs it; adding a second JSONB blob per row to a list response is cost with no consumer"
  - "ui_layout NOT added to TaskDefinitionCreate or the ORM class — a fresh definition has no arrangement yet, and migrated columns are deliberately raw-SQL-only, matching fda_json/display_name"
  - "ui_layout NOT added to FdaJson (TypeScript) — that interface mirrors exactly what reaches the Pi"
metrics:
  duration: "~25 min"
  completed: "2026-08-05"
---

# Phase 29 Plan 04: task_definitions.ui_layout column + GET/PUT surface Summary

Added a `task_definitions.ui_layout` JSONB column, deliberately outside `fda_json`, with a
GET/PUT API surface and TypeScript types — proven by a real-DB pytest that a layout-only PUT
never moves `file_hash` or re-runs FDA validation, while an `fda_json` PUT still does both.

## What Was Built

**Task 1 — column, request field, GET surface** (`api/db.py`, `api/models.py`,
`api/routers/toolkits.py::get_task_definition`): one migration tuple
(`("task_definitions", "ui_layout", "JSONB")`) added to the existing idempotent
`run_toolkit_migrations` loop; `ui_layout: Optional[Dict[str, Any]] = None` added to
`TaskDefinitionUpdate` only (not `TaskDefinitionCreate`, not the ORM class); `GET` returns the
raw stored value (`None` when never arranged), mirroring the `fda_json` `json.loads` idiom
exactly. Verified live: `\d task_definitions` shows `ui_layout | jsonb`, survives an `api`
container restart (migration is idempotent, not one-shot), no tracebacks in `docker compose
logs`.

**Task 2 — PUT + layout-only fast path (TDD)** (`api/routers/toolkits.py::update_task_definition`,
new `api/tests/test_ui_layout.py`): wrote the 7-case test file first against a real, disposable
task definition (POST → PUT → GET → DELETE teardown); confirmed 3 of 7 cases RED for the
expected reason (`ui_layout` silently ignored by PUT; a monkeypatched
`reject_if_hard_errors` raised through a layout-only PUT because the old code path always ran
it). Implemented the fast path: when a PUT carries `ui_layout` and nothing else
(`fda_json`/`display_name`/`toolkit_id` all `None`), the handler writes the column directly and
returns **before** `reject_if_hard_errors` / `_validate_task_definition` run — this is the
CANVAS-10 guarantee that a node drag can never be rejected or re-flagged by unrelated FDA state.
A PUT carrying `fda_json` (with or without `ui_layout`) is untouched: it still rehashes and
re-validates exactly as before. `defn.validation_status` is read directly off the ORM object (it
*is* declared on the `TaskDefinition` class, unlike the migrated raw-SQL columns), so the fast
path never fabricates a hardcoded `"ok"`.

**Task 3 — TypeScript types** (`web_ui/react-src/src/types/index.ts`,
`web_ui/react-src/src/api/task-definitions.ts`): new `UiLayout` interface
(`{ nodes: Record<string, {x,y}> }`), optional `ui_layout` on `TaskDefinitionFull`, and
`updateTaskDefinition`'s payload type widened to accept it. `FdaJson` is untouched — it mirrors
what ships to the Pi.

## Verification

- `docker compose exec -T db psql ... -c '\d task_definitions'` → `ui_layout | jsonb` present,
  survives an `api` container restart.
- `docker compose exec -T api python -m pytest -q tests/test_ui_layout.py` → **7 passed**.
- `docker compose exec -T api python -m pytest -q tests/` → **359 passed, 1 skipped** (up from
  the 352 passed / 1 skipped baseline — the 7 new cases, no regressions).
- `cd web_ui/react-src && npx tsc -b && npm run build` → clean.
- `grep -rn "ui_layout" api/fda_validation.py orchestrator/` → no matches — layout never reaches
  validation or the Pi.
- `wc -l api/routers/toolkits.py`: **992 → 1005** (net +13 lines across both tasks, under the
  20-line budget `<known_debt>` set for this plan). Still double the 500-line hard limit;
  splitting it remains a deferred, separate refactor — not attempted here per the plan's explicit
  instruction.

## Deviations from Plan

None — plan executed exactly as written, including both deliberate scope exclusions the plan
called out (`ui_layout` absent from `list_task_definitions` and from `TaskDefinitionCreate`/the
ORM class).

### Out-of-scope discovery (logged, not fixed)

A concurrent session was executing plan 29-01 (canvas context-menu/label extraction) against the
same working tree during this plan's execution — its commits interleave in `git log` by
timestamp but touch entirely disjoint files from this plan's four commits (verified via
`git show --stat` on each). Its in-progress, uncommitted work left two frontend test files
(`fdaLayout.test.mts`, `edgeGeometry.test.mts`) with 1 failing case each at the time `npm run
test:unit` was run here (146/147 passing). Logged in
`.planning/phases/29-fda-builder-canvas-ux/deferred-items.md` — out of this plan's scope per the
scope-boundary rule, not touched.

## Self-Check

- `FOUND: api/tests/test_ui_layout.py`
- `FOUND: api/db.py` (modified)
- `FOUND: api/models.py` (modified)
- `FOUND: api/routers/toolkits.py` (modified)
- `FOUND: web_ui/react-src/src/types/index.ts` (modified)
- `FOUND: web_ui/react-src/src/api/task-definitions.ts` (modified)
- Commits `0e4b0c7`, `775ffb7`, `6572f40`, `b5860ba` all present in `git log --oneline --all`.

## Self-Check: PASSED
