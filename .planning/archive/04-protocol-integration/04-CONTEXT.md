# Phase 4: Protocol Integration — Context

**Gathered:** 2026-03-23
**Status:** Ready for planning
**Source:** User session conversation + codebase exploration

<domain>
## Phase Boundary

Replace the raw task-type palette in `/react/protocols-create` with named task definitions.
A protocol step will reference a task definition by ID; the FDA JSON flows end-to-end from DB → orchestrator → Pi START payload.

Params schema for a step comes from the linked toolkit (`toolkit.params_schema`), same editor UI as today.
Graduation (NTrials) logic is unchanged.
Existing protocols (with `task_type` string, no `task_definition_id`) continue to display and run correctly.

</domain>

<decisions>
## Implementation Decisions

### Protocol Step → Task Definition Link
- Add `task_definition_id INT NULL` FK column to `protocol_step_templates` via `run_lab_column_migrations()` in `api/db.py` (IF NOT EXISTS pattern — same as `display_name`/`toolkit_name`/`fda_json` on `task_definitions`)
- Keep `task_type` column; derive its value from `task_definition.toolkit_name` when a task definition is picked
- Backward compat: existing rows have `task_definition_id = NULL`, `task_type` still valid for Pi runtime

### Params Source
- For new steps: load `toolkit.params_schema` via toolkit_name → same `{key: {tag, type, default}}` structure
- Editor UI (param inputs, graduation NTrials) unchanged — only data source changes
- Client-side join: load `GET /api/task-definitions` + `GET /api/toolkits`, join on `toolkit_name`

### Task Palette
- Replace current `/api/tasks/leaf` fetch with task definitions list (filter: `fda_json != null`)
- Group by toolkit name in the left panel
- Display `display_name` as the step label; store `toolkit_name` as `task_type`
- `GET /api/tasks/leaf` deprecated but NOT removed (backward compat for any callers)

### Session Start / Orchestrator
- `create_session_run()` in `api/main.py` (or router): when step has `task_definition_id`, resolve `fda_json` and include as `state_machine` key in START payload
- If `task_definition_id` is NULL (legacy step), fall back to current behavior

### Protocol Viewer
- In protocol list and detail views: show `display_name` of the task definition when `task_definition_id` is present; fallback to `task_type`

### VAR-07 (canonical variant)
- `PATCH /api/toolkits/{id}/set-canonical` endpoint marks one toolkit variant as canonical
- FDAs bound to non-canonical variants get flagged `needs_migration: true` in their response
- Low priority within this phase; implement after core PROTO requirements

### Claude's Discretion
- API router placement: new protocol-related routes go in `api/routers/` (NOT `api/main.py` which is at 2100+ lines)
- TypeScript type for `ProtocolStep`: add `task_definition_id?: number | null`
- Loading state / error handling in ProtocolsCreate.tsx follows existing patterns (useQuery, isLoading, isError)

</decisions>

<specifics>
## Specific Data Shapes (verified via exploration)

### Current ProtocolStepTemplate DB model
```python
class ProtocolStepTemplate(SQLModel, table=True):
    __tablename__ = "protocol_step_templates"
    id: Optional[int]
    order_index: int
    step_name: str
    task_type: str          # Python class name (kept for Pi runtime)
    params: Optional[Dict]  # JSON: task params + graduation
    protocol_id: int
```

### TaskDefinitionFull (React type)
```typescript
interface TaskDefinitionFull {
  id: number
  task_name: string
  display_name: string | null
  toolkit_name: string | null   // = task_type for Pi
  fda_json: FdaJson | null
  created_at: string
}
```

### ToolkitRead.params_schema
Same `{key: {tag, type, default}}` structure as current `TaskDef.default_params`

### Graduation storage (unchanged)
Stored inside `params.graduation = { type: 'NTrials', value: { current_trial: N } }`

### Existing API helpers (reuse)
- `getTaskDefinitions()` → `/api/task-definitions` — already in `src/api/task-definitions.ts`
- `getToolkits()` → `/api/toolkits` — already in `src/api/toolkits.ts`
- No new API helper files needed

</specifics>

<deferred>
## Deferred

- Push-to-pilot button on the protocol run screen (UI-09) — separate phase
- VAR-07 canonical variant picker may be simplified or deferred if complex
- Hard removal of `/api/tasks/leaf` — deprecate only, remove in a future cleanup phase

</deferred>

---

*Phase: 04-protocol-integration*
*Context gathered: 2026-03-23 via conversation + codebase exploration*
