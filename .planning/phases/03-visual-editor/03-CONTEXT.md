# Phase 3: Visual FDA Editor — Context

**Gathered:** 2026-03-22
**Status:** Ready for planning
**Source:** Session continuation + codebase exploration

<domain>
## Phase Boundary

Deliver a visual FDA state machine editor at `/react/task-editor/:id`. Users can:
- View states as react-flow nodes and transitions as directed edges
- Drag-to-connect nodes to create new transitions
- Click a state node → state body editor panel (entry_actions list: add/remove/reorder)
- Click a transition edge → condition builder panel
- Add actions via picker: hardware / flag / special / method
- Smart arg inputs with literal / param-ref / flag-ref toggle
- Save edited fda_json back to DB via `PUT /api/task-definitions/:id`

Also deliver:
- Task definitions list page at `/react/task-definitions-ui` (list, click → editor)
- Passthrough state display: lock icon + `{py}` badge, state body panel read-only
- Semantic hardware overrides panel (per-task-def hw overrides)
- Variant picker when 2+ toolkit variants exist for same name (VAR-06)

Phase 3 does NOT include:
- Trigger assignment panel (UI-07) — deferred
- Push-to-pilot button (UI-09) — deferred
- If-condition blocks (UI-11) — deferred (complex nested structure)
</domain>

<decisions>
## Implementation Decisions

### Scope: Which Requirements Are In This Phase
- **In:** UI-01, UI-02, UI-03, UI-04, UI-05, UI-05a, UI-06, UI-08, UI-10, UI-12, VAR-06
- **Deferred:** UI-07 (trigger panel), UI-09 (push button), UI-11 (if-condition blocks)
- **Rationale:** User explicitly deferred trigger panel and push button; UI-11 (if-blocks) is
  complex nested UI that should come after core canvas works correctly.

### npm Dependency
- Add `@xyflow/react` to `web_ui/react-src/package.json` (react-flow v12)
- Import base CSS: `import '@xyflow/react/dist/style.css'` in editor page
- Use `ReactFlow`, `Background`, `Controls`, `MiniMap`, `Handle`, `Position`,
  `useNodesState`, `useEdgesState`, `addEdge` from `@xyflow/react`

### Visual Style (Turbo-flow inspired)
- Dark canvas background: `#0d1117`
- Node container: `background: #1e2130`, border-radius 8px, colored left border (4px solid)
  - Initial state: `--node-color: #7c3aed` (purple)
  - Regular state: `--node-color: #2563eb` (blue)
  - Passthrough: `--node-color: #6b7280` (gray)
- Glow: `box-shadow: 0 0 12px color-mix(in srgb, var(--node-color) 40%, transparent)`
- Node text: white, node width ~200px, padding 12px
- Use existing `style.css` classes for list page and panel UI (not for canvas)

### TypeScript Types (append to `web_ui/react-src/src/types/index.ts`)
```ts
export interface FdaCondition {
  view: string
  op: '==' | '!=' | '>=' | '<=' | '>' | '<'
  rhs: unknown
}

export interface FdaAction {
  type: 'hardware' | 'flag' | 'special' | 'method'
  ref?: string          // semantic hw key / flag name / callable method name
  method?: string       // e.g. "set", "toggle", "increment", "reset"
  args?: unknown[]      // each arg: literal scalar | { param: string } | { flag: string }
  action?: string       // for type=special, e.g. "INC_TRIAL_COUNTER"
}

export interface FdaState {
  entry_actions?: FdaAction[]
  wait_condition?: FdaCondition
  return_data?: unknown[]
  _passthrough?: boolean   // client-side flag for passthrough states
}

export interface FdaTransition {
  from_state: string
  condition: FdaCondition
  next_state: string
}

export interface FdaJson {
  version: 2
  initial_state: string
  states: Record<string, FdaState>
  transitions: FdaTransition[]
  trigger_assignments: Record<string, unknown>
  hw_overrides?: Record<string, unknown>  // per-def semantic hardware overrides (UI-08)
}

export interface ToolkitRead {
  id: number
  name: string
  hw_hash: string
  states: string[] | null
  flags: Record<string, unknown> | null
  params_schema: Record<string, unknown> | null
  semantic_hardware: Record<string, unknown> | null
  callable_methods: string[] | null
  required_packages: string[] | null
  pilot_origins: string[]
  fda_count: number
  created_at: string
  updated_at: string
}

export interface TaskDefinitionFull {
  id: number
  task_name: string
  display_name: string | null
  toolkit_name: string | null
  fda_json: FdaJson | null
  file_hash: string
  created_at: string
}
```

### API Helpers (new files)
- `web_ui/react-src/src/api/toolkits.ts`:
  ```ts
  export const getToolkits = () => apiFetch<ToolkitRead[]>('/api/toolkits')
  export const getToolkitsByName = (name: string) => apiFetch<ToolkitRead[]>(`/api/toolkits/by-name/${name}`)
  ```
- `web_ui/react-src/src/api/task-definitions.ts`:
  ```ts
  export const getTaskDefinitions = () => apiFetch<TaskDefinitionFull[]>('/api/task-definitions')
  export const getTaskDefinition = (id: number) => apiFetch<TaskDefinitionFull>(`/api/task-definitions/${id}`)
  export const updateTaskDefinition = (id: number, payload: { display_name?: string; fda_json?: FdaJson }) =>
    apiFetch<{ status: string; id: number }>(`/api/task-definitions/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
  ```
- Follow pattern of `api/lab.ts` (thin wrappers over `apiFetch<T>`)

### Routing (App.tsx)
Append two lazy imports and two routes inside the `<Route element={<Layout />}>` block:
```tsx
const TaskDefinitions = React.lazy(() => import('./pages/task-definitions/TaskDefinitions'))
const TaskEditor = React.lazy(() => import('./pages/task-editor/TaskEditor'))
// routes:
<Route path="task-definitions-ui" element={<TaskDefinitions />} />
<Route path="task-editor/:id" element={<TaskEditor />} />
```

### Nav (Nav.tsx)
Append to the `links` array:
```ts
{ to: '/task-definitions-ui', label: 'Tasks' }
```

### Task Definitions List Page
- File: `web_ui/react-src/src/pages/task-definitions/TaskDefinitions.tsx`
- Pattern: closest to `pages/researchers/Researchers.tsx` (simplest existing page)
- `useQuery(['task-definitions'], getTaskDefinitions)` from TanStack Query
- Layout: single-column scroll list (`scroll-list` CSS class)
- Each row: display_name (or task_name if null), toolkit_name badge, created_at date
- Click row → `navigate('/task-editor/:id')`
- Variant warning: if two TaskDefinitionFull rows share same toolkit_name AND toolkit has
  2+ hw_hash variants → show warning badge per row (VAR-06 partial)

### FDA Editor Page structure
- File: `web_ui/react-src/src/pages/task-editor/TaskEditor.tsx`
- Layout: full-height split — left canvas (flex: 1), right panel (320px fixed)
- Header: task display_name, breadcrumb link back to task-definitions-ui, "Save" button
- Queries:
  - `useQuery(['task-definition', id], () => getTaskDefinition(Number(id)))`
  - `useQuery(['toolkits-by-name', toolkitName], () => getToolkitsByName(toolkitName), { enabled: !!toolkitName })`
- Local state: `const [fdaJson, setFdaJson] = useState<FdaJson | null>(null)` — initialized from query data, edited locally, flushed on Save
- `useMutation` for save: calls `updateTaskDefinition`, invalidates query on success, shows "Saved ✓" message
- No `blocking` field anywhere — states only have `wait_condition` (optional)

### FDA JSON → react-flow conversion (in TaskEditor)
- Nodes: `Object.entries(fdaJson.states).map(([name, state], i) => ({ id: name, type: 'stateNode', position: { x: i * 250, y: 100 }, data: { name, state, isInitial: name === fdaJson.initial_state, toolkit } }))`
- Edges: `fdaJson.transitions.map((t, i) => ({ id: \`e-\${i}\`, source: t.from_state, target: t.next_state, label: \`\${t.condition.view} \${t.condition.op} \${t.condition.rhs}\`, data: { transition: t } }))`
- Use `useNodesState` and `useEdgesState` hooks from `@xyflow/react`
- On edge connect (`onConnect`): append new transition with default condition to fdaJson

### StateNode component
- File: `web_ui/react-src/src/components/StateNode.tsx`
- Props via `data`: `{ name, state, isInitial, toolkit }`
- Renders: Handle (target, top), node body (name + action count), Handle (source, bottom)
- Passthrough detection: `state.entry_actions` is undefined/empty AND state appears in `toolkit.states` — show lock icon + `{py}` badge
- Click: parent sets `selectedState` (prop drilling or callback via data)

### Right Panel Logic
- If nothing selected: placeholder ("Select a state or transition")
- If state selected: `StateBodyPanel` showing entry_actions
- If edge selected: `ConditionBuilder` showing condition fields

### StateBodyPanel component
- File: `web_ui/react-src/src/components/StateBodyPanel.tsx`
- Props: `{ stateName, state, toolkit, onChange }`
- Renders entry_actions list; each row: `ActionEditor` + remove button
- "Add action" button → appends `{ type: 'hardware', ref: '', method: 'set', args: [1] }`
- wait_condition section: read-only display below actions (view/op/rhs as text badges)
- return_data section: read-only display below wait_condition; shows items as comma-separated meta-pill, hidden if empty
- `onChange` called with updated FdaState; parent updates fdaJson.states[stateName]

### ActionEditor component
- File: `web_ui/react-src/src/components/ActionEditor.tsx`
- Props: `{ action, toolkit, onChange }`
- `type` select: hardware | flag | special | method
- Conditional fields by type:
  - hardware: `ref` select (toolkit.semantic_hardware keys), `method` select (set/toggle), `args[0]` via ArgInput
  - flag: `ref` select (toolkit.flags keys), `method` select (increment/reset/set)
  - special: `action` select (["INC_TRIAL_COUNTER"] or free text)
  - method: `ref` select (toolkit.callable_methods), optional args

### ArgInput component
- File: `web_ui/react-src/src/components/ArgInput.tsx`
- Props: `{ value, toolkit, onChange }`
- Detects current mode from value: literal (number/bool/string) | `{ param: string }` | `{ flag: string }`
- Toggle buttons: "Literal" | "Param" | "Flag"
- Literal: number input; Param: select from toolkit.params_schema keys; Flag: select from toolkit.flags keys

### ConditionBuilder component
- File: `web_ui/react-src/src/components/ConditionBuilder.tsx`
- Props: `{ condition, toolkit, onChange }`
- Implements UI-12: left dropdown (tracker/flag/param/hw view keys), op dropdown, right input
- Left side: combined list from toolkit.semantic_hardware keys + toolkit.flags keys + toolkit.params_schema keys
- Op: == | != | >= | <= | > | <
- Right side: literal input (for now; param/flag ref in later phase)
- `onChange` updates the transition's condition in parent fdaJson

### HwOverridesPanel (UI-08)
- File: `web_ui/react-src/src/components/HwOverridesPanel.tsx`
- Shown as collapsible section in right panel when no state/edge selected
- Lists toolkit.semantic_hardware keys; per key: optional override inputs for group+id
- Saves to `fda_json.hw_overrides` dict

### VAR-06: Variant Picker
- On list page: if `getToolkits()` shows 2+ rows with same name (different hw_hash) → show
  warning badge per task def row: "⚠ 2 toolkit variants"
- On editor page: if toolkit has multiple variants → show dismissible banner with link to
  diff view (just informational in this phase; binding to specific variant is Phase 4 scope)

### Save Flow
1. User edits actions / conditions / overrides in panel → local `fdaJson` updated via setFdaJson
2. "Save" button (top right) → `mutation.mutate({ fda_json: fdaJson })`
3. API: `PUT /api/task-definitions/:id` → `{ status: "ok", id }`
4. On success: show "Saved ✓" for 2s then clear; invalidate `['task-definition', id]`
5. On error: show error message in header area

### No `blocking` field
- FDA JSON v2 does NOT have a `blocking: "stage_block"` field anywhere
- States optionally have `wait_condition` (same shape as transition condition)
- The UI must never show or write a `blocking` field
- StateBodyPanel shows wait_condition as read-only in this phase (edit in Phase 4)

### Claude's Discretion
- Node layout algorithm (simple grid vs dagre auto-layout — either acceptable)
- Exact CSS for dark canvas area (inline styles on ReactFlow wrapper acceptable)
- Whether to use ReactFlow's built-in edge label rendering or a custom EdgeLabel component
- Toast/notification implementation (inline header message is fine, no external library)
- Whether HwOverridesPanel is a separate tab or collapsible section
</decisions>

<specifics>
## Specific File References

### Existing API (no backend changes needed)
- `GET /api/task-definitions` → `TaskDefinitionFull[]` (`api/routers/toolkits.py:196`)
- `GET /api/task-definitions/:id` → `TaskDefinitionFull` (line 272)
- `PUT /api/task-definitions/:id` → `{ status, id }` (line 295)
- `GET /api/toolkits` → `ToolkitRead[]` (line 59)
- `GET /api/toolkits/by-name/:name` → `ToolkitRead[]` (line 90)

### Existing React patterns to follow
- Page pattern: `web_ui/react-src/src/pages/researchers/Researchers.tsx` (simplest)
- Complex page: `web_ui/react-src/src/pages/protocols-create/ProtocolsCreate.tsx`
- API helper pattern: `web_ui/react-src/src/api/lab.ts`
- Types pattern: `web_ui/react-src/src/types/index.ts` (append, do not replace)
- Route registration: `web_ui/react-src/src/App.tsx` (lazy import + Route)
- Nav link: `web_ui/react-src/src/components/Nav.tsx` (append to links array)

### CSS classes available (from style.css — use these, don't invent)
- Layout: `container`, `container split`, `card`, `grid`
- Lists: `scroll-list`, `fade-in-item`, `subject-item selected`
- Buttons: `button-primary`, `button-secondary`, `button-danger`, `button-link`
- Badges: `badge`, `meta-pill`, `meta-date`
- Params: `params-grid`, `param-field`, `param-name`

### FDA JSON v2 schema (authoritative — no blocking field)
```json
{
  "version": 2,
  "initial_state": "WAIT_FOR_LICK",
  "states": {
    "WAIT_FOR_LICK": {
      "entry_actions": [
        { "type": "hardware", "ref": "led", "method": "set", "args": [1] }
      ],
      "wait_condition": { "view": "licker1", "op": "==", "rhs": 1 }
    }
  },
  "transitions": [
    { "from_state": "WAIT_FOR_LICK", "condition": { "view": "licker1", "op": "==", "rhs": 1 }, "next_state": "REWARD" }
  ],
  "trigger_assignments": {}
}
```
</specifics>

<deferred>
## Deferred to Later Phases

- **UI-07**: Trigger assignment panel (shows trigger hardware, handler type dropdowns)
- **UI-09**: Push-to-pilot button + hot-reload
- **UI-11**: If-condition action blocks with then/else lanes (complex nested structure)
- Editing wait_condition via UI (currently read-only display)
- Binding task definition to a specific toolkit variant (VAR-06 partial)

Note: The ROADMAP listed UI-07, UI-09 in Phase 3 but user explicitly deferred both.
Planner should note this scope reduction and may suggest a Phase 3.1 insert for deferred items.
</deferred>

---
*Phase: 03-visual-editor*
*Context gathered: 2026-03-22 from session continuation + codebase exploration*
