# Phase 3: Visual FDA Editor — Context

**Gathered:** 2026-03-22
**Revised:** 2026-03-23 (unified condition schema; from/to transitions; UI-11 in scope; SEMANTIC_HARDWARE fallback; elastic_test guard; added Plan 03-00 Pi wave)
**Status:** Ready for execution (03-00 next)
**Source:** Session continuation + codebase exploration

<domain>
## Phase Boundary

Deliver a visual FDA state machine editor at `/react/task-editor/:id`. Users can:
- View states as react-flow nodes and transitions as directed edges
- Drag-to-connect nodes to create new transitions
- Click a state node → state body editor panel (entry_actions list: add/remove/reorder)
- Click a transition edge → condition builder panel
- Add actions via picker: hardware / flag / timer / special / method
- Smart arg inputs with literal / param-ref / flag-ref toggle
- Configure trigger assignments (which hardware interrupt fires which handler)
- Save edited fda_json back to DB via `PUT /api/task-definitions/:id`

Also deliver:
- Task definitions list page at `/react/task-definitions-ui` (list, click → editor)
- Passthrough state display: lock icon + `{py}` badge, state body panel read-only
- Variant picker when 2+ toolkit variants exist for same name (VAR-06)

Phase 3 does NOT include:
- Hardware semantic overrides panel (UI-08) — removed. Toolkit file is the source of
  truth for hardware mapping; if you need to change hardware, edit the toolkit file and
  re-HANDSHAKE. No per-task-definition override stored in fda_json.
- Push-to-pilot button (UI-09) — deferred
- If-condition blocks (UI-11) — deferred (complex nested structure)
</domain>

<decisions>
## Implementation Decisions

### Scope: Which Requirements Are In This Phase
- **In:** UI-01, UI-02, UI-03, UI-04, UI-05, UI-05a, UI-06, UI-07, UI-10, UI-11, UI-12, VAR-06
- **Removed:** UI-08 (hw overrides panel) — edit toolkit file directly instead
- **Deferred:** UI-09 (push button)
- **UI-11 reinstated:** if-condition blocks — Pi already implements `_build_if_action`.
  Added to Plan 03-03 as `IfActionEditor` recursive component inside `ActionEditor`.
- **UI-07 reinstated:** trigger panel — primary way to wire GPIO callbacks without Python.

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

**Canonical FDA condition format (unified — same for transitions AND if-actions):**
```ts
// An operand in a condition. Each side of the comparison can be any of these.
export type FdaOperand =
  | { view: string }       // reads self.view.get_value(key) — hardware & flag states
  | { tracker: string }    // alias for view; reads self.flags[key].value
  | { flag: string }       // reads self.flags[key].value
  | { param: string }      // reads self.params[key]
  | { hardware: string }   // reads self._semantic_hw[key].value
  | number | boolean | string | null  // bare literal

export interface FdaCondition {
  left: FdaOperand
  op: '==' | '!=' | '>=' | '<=' | '>' | '<'
  right: FdaOperand
}

export interface FdaAction {
  type: 'hardware' | 'flag' | 'timer' | 'special' | 'method' | 'if'
  ref?: string          // semantic hw key / flag name / callable method name
  method?: string       // e.g. "set", "toggle", "increment", "reset"
  args?: unknown[]      // each arg: literal scalar | { param: string } | { flag: string }
  action?: string       // for type=special, e.g. "INC_TRIAL_COUNTER"
  duration?: unknown    // for type=timer: literal ms value or { param: string }
  // if-action fields (type='if' only):
  condition?: FdaCondition
  then?: FdaAction[]
  else?: FdaAction[]
}

export interface FdaState {
  entry_actions?: FdaAction[]
  wait_condition?: FdaCondition
  return_data?: unknown[]
  _passthrough?: boolean   // client-side flag for passthrough states
}

export interface FdaTransition {
  from: string           // was from_state in old plan docs — now matches Pi code
  to: string             // was next_state in old plan docs — now matches Pi code
  conditions: FdaCondition[]   // plural array; all must be true (AND logic)
  description?: string
}

export interface FdaTriggerAssignment {
  trigger_name: string                                          // hardware key, e.g. "TOUCH_INT"
  handler: 'touch_detector' | 'digital_input' | 'default' | 'log_only'
  config?: {
    hardware_ref?: string   // semantic hw key for touch_detector (which MPR121 to read)
    view_key?: string       // view key to update on digital_input
  }
}

export interface FdaJson {
  version: 2
  initial_state: string
  states: Record<string, FdaState>
  transitions: FdaTransition[]              // each uses {from, to, conditions[]}
  trigger_assignments: FdaTriggerAssignment[]   // array, NOT a dict
  hw_overrides?: Record<string, unknown>    // legacy field — pass through, never write/display
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
- If nothing selected: placeholder ("Select a state or transition") + TriggerAssignmentPanel
- If state selected: `StateBodyPanel` showing entry_actions
- If edge selected: `ConditionBuilder` showing condition fields

### StateBodyPanel component
- File: `web_ui/react-src/src/components/StateBodyPanel.tsx`
- Props: `{ stateName, state, toolkit, onChange }`
- Renders entry_actions list; each row: `ActionEditor` + remove button
- "Add action" button → appends `{ type: 'hardware', ref: '', method: 'set', args: [1] }`
- wait_condition section: read-only display below actions (left/op/right as text badges)
- return_data section: read-only display below wait_condition; shows items as comma-separated meta-pill, hidden if empty
- `onChange` called with updated FdaState; parent updates fdaJson.states[stateName]

### ActionEditor component
- File: `web_ui/react-src/src/components/ActionEditor.tsx`
- Props: `{ action, toolkit, onChange }`
- `type` select: hardware | flag | timer | special | method | if
- Conditional fields by type:
  - hardware: `ref` select (toolkit.semantic_hardware keys), `method` select (set/toggle), `args[0]` via ArgInput
  - flag: `ref` select (toolkit.flags keys), `method` select (increment/reset/set)
  - timer: `duration` via ArgInput (literal ms or param-ref)
  - special: `action` select (["INC_TRIAL_COUNTER"] or free text)
  - method: `ref` select (toolkit.callable_methods), optional args
  - **if (UI-11):** renders `IfActionEditor` sub-component (see below)

### IfActionEditor component (UI-11)
- File: `web_ui/react-src/src/components/IfActionEditor.tsx`
- Props: `{ action, toolkit, onChange }` where `action.type === 'if'`
- Renders:
  - `ConditionBuilder` for `action.condition` (reuses the same component as transition conditions)
  - "then" section: collapsible list of `ActionEditor` rows (recursive — supports nested if-actions)
  - "else" section: same, collapsible, hidden if empty (toggle to add)
  - Add then/else action buttons append default `{type: 'hardware', ...}` to the branch
- Visual nesting: indent each level by 12px with a left border in a lighter color; cap display at 3 levels (deeper levels collapsed by default)
- `onChange` called with updated FdaAction (preserves all other fields, replaces condition/then/else)

### ArgInput component
- File: `web_ui/react-src/src/components/ArgInput.tsx`
- Props: `{ value, toolkit, onChange }`
- Detects current mode from value: literal (number/bool/string) | `{ param: string }` | `{ flag: string }`
- Toggle buttons: "Literal" | "Param" | "Flag"
- Literal: number input; Param: select from toolkit.params_schema keys; Flag: select from toolkit.flags keys

### ConditionBuilder component (manages FdaCondition — used for transitions AND if-actions)
- File: `web_ui/react-src/src/components/ConditionBuilder.tsx`
- Props: `{ condition, toolkit, onChange }`
- Implements UI-12: each side is an OperandEditor; op dropdown between them
- **OperandEditor** — type selector (View / Flag / Param / Hardware / Literal) + type-specific input:
  - View: free-text input for view key (most common — covers hardware and flag states)
  - Flag: select from toolkit.flags keys → produces `{flag: name}`
  - Param: select from toolkit.params_schema keys → produces `{param: name}`
  - Hardware: select from toolkit.semantic_hardware keys → produces `{hardware: name}`
  - Literal: number/text input → bare value
- Op: `==` | `!=` | `>=` | `<=` | `>` | `<`
- `onChange` called with updated FdaCondition; parent updates fdaJson accordingly
- **Reused by IfActionEditor** (Plan 03-03) for if-action condition editing — same component, no duplication

### TriggerAssignmentPanel component (UI-07)
- File: `web_ui/react-src/src/components/TriggerAssignmentPanel.tsx`
- Props: `{ assignments, toolkit, onChange }`
- Shown in right panel when nothing is selected (below the placeholder text)
- Renders current `fdaJson.trigger_assignments` array; each row:
  - `trigger_name`: text input (free-form; the hardware key like "TOUCH_INT")
  - `handler`: select from `['touch_detector', 'digital_input', 'default', 'log_only']`
  - `config.hardware_ref` (optional): select from `toolkit.semantic_hardware` keys, shown only for `touch_detector` handler
  - Remove button
- "Add trigger" button appends `{ trigger_name: '', handler: 'touch_detector' }`
- `onChange` called with updated `FdaTriggerAssignment[]`; parent updates `fdaJson.trigger_assignments`
- Real-world example: TOUCH_INT → touch_detector with hardware_ref pointing to the MPR121
  semantic key maps directly to `self.triggers['TOUCH_INT'] = [self.detectedLick]` in learning_cage.py

### Save Flow
1. User edits actions / conditions / triggers in panel → local `fdaJson` updated via setFdaJson
2. "Save" button (top right) → `mutation.mutate({ fda_json: fdaJson })`
3. API: `PUT /api/task-definitions/:id` → `{ status: "ok", id }`
4. On success: show "Saved ✓" for 2s then clear; invalidate `['task-definition', id]`
5. On error: show error message in header area

### No `blocking` field, no `hw_overrides` field
- FDA JSON v2 does NOT have a `blocking` field anywhere
- FDA JSON v2 does NOT have `hw_overrides` — to change hardware mapping, edit the toolkit
  Python file directly and HANDSHAKE again
- States optionally have `wait_condition`
- The UI must never show or write `blocking` or `hw_overrides`

### Claude's Discretion
- Node layout algorithm (simple grid vs dagre auto-layout — either acceptable)
- Exact CSS for dark canvas area (inline styles on ReactFlow wrapper acceptable)
- Whether to use ReactFlow's built-in edge label rendering or a custom EdgeLabel component
- Toast/notification implementation (inline header message is fine, no external library)
- TriggerAssignmentPanel as collapsible or always-visible section
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

### FDA JSON v2 schema (authoritative)
Key rules:
- No `blocking` field anywhere
- No `hw_overrides` — pass through if present, never write or display
- `trigger_assignments` is an array (not a dict)
- Transitions use `from`/`to` (not from_state/next_state)
- Conditions use unified `{left, op, right}` format with `>=` style operators
- Each side of a condition is an FdaOperand: `{view/flag/param/hardware: key}` or literal

```json
{
  "version": 2,
  "initial_state": "WAIT_FOR_LICK",
  "states": {
    "WAIT_FOR_LICK": {
      "entry_actions": [
        { "type": "hardware", "ref": "led", "method": "set", "args": [1] },
        {
          "type": "if",
          "condition": { "left": {"flag": "hit"}, "op": ">=", "right": 3 },
          "then": [ { "type": "special", "ref": "INC_TRIAL_COUNTER" } ],
          "else": []
        }
      ],
      "wait_condition": { "left": {"view": "licker1"}, "op": "==", "right": 1 }
    },
    "REWARD": {}
  },
  "transitions": [
    {
      "from": "WAIT_FOR_LICK",
      "to": "REWARD",
      "conditions": [
        { "left": {"view": "licker1"}, "op": "==", "right": 1 }
      ],
      "description": "lick detected"
    }
  ],
  "trigger_assignments": [
    {
      "trigger_name": "TOUCH_INT",
      "handler": "touch_detector",
      "config": { "hardware_ref": "touch_sensor" }
    }
  ]
}
```

### Trigger assignment real-world mapping
`learning_cage.py` wires: `self.triggers['TOUCH_INT'] = [self.detectedLick]`
This is equivalent to a trigger_assignment: `{ trigger_name: "TOUCH_INT", handler: "touch_detector" }`
The handler type determines the callback: touch_detector calls `hardware.detect_change()` then
updates the view; digital_input simply sets `view[trigger_name] = level`.
</specifics>

<deferred>
## Deferred to Later Phases

- **UI-08**: Hardware semantic overrides — removed entirely. Edit the toolkit file.
- **UI-09**: Push-to-pilot button + hot-reload
- Editing wait_condition via UI (currently read-only display)
- Binding task definition to a specific toolkit variant (VAR-06 partial)
</deferred>

---
## Plan Wave Order

| Plan | Wave | Contents |
|---|---|---|
| 03-00 | 0 | Pi: unified condition eval, SEMANTIC_HARDWARE fallback, elastic_test guard |
| 03-01 | 1 | React: npm dep, TypeScript types, API helpers, routing, TaskDefinitions list page |
| 03-02 | 2 | React: react-flow canvas, StateNode, ConditionBuilder (OperandEditor), drag-connect |
| 03-03 | 3 | React: StateBodyPanel, ActionEditor, IfActionEditor (UI-11), ArgInput, TriggerPanel, Save |

---
*Phase: 03-visual-editor*
*Context gathered: 2026-03-22 from session continuation + codebase exploration*
*Revised: 2026-03-23 — unified condition schema (left/op/right, >= operators); from/to transitions; UI-11 in scope; SEMANTIC_HARDWARE Pi fallback; elastic_test guard; Plan 03-00 added*
