# Phase 29: FDA Builder Canvas UX - Context

**Gathered:** 2026-08-05
**Status:** Ready for planning
**Source:** Direct user session (decisions captured live, not via /gsd:discuss-phase)

<domain>
## Phase Boundary

The task editor canvas — `web_ui/react-src/src/pages/task-editor/TaskEditor.tsx` and the
components it renders — is hard to read on any graph with more than a couple of transitions.
This phase makes it readable and makes the reader's spatial arrangement stick.

**In scope:** edge rendering (offset, labels, arrowheads, self-loops), node placement
(layered default, persistence, restore action), and the small backend surface needed to store
positions.

**Explicitly out of scope — stated by the user as "this is a pure ux ui phase":**
- FDA semantics. No change to how states, transitions, conditions, actions, triggers, or
  variables behave.
- Validation. `api/fda_validation.py` and `validation_status` are untouched.
- The Pi payload. Nothing new reaches `load_fda_from_json`. Layout never leaves the browser
  and the backend row it is stored in.
- The condition label *text*. `condLabel` / `renderTreeLabel` (`TaskEditor.tsx:82-103`) keep
  producing exactly the strings they produce today, Phase 16 parenthesisation included. This
  phase changes *where* the label is drawn, never *what* it says.
- `StateNode`'s handle model. Left target / Right source stays.

</domain>

<decisions>
## Implementation Decisions

### The four defects (root-caused against the code, not reported symptoms)

1. **Hourglass on bidirectional pairs.** `fdaToEdges` (`TaskEditor.tsx:153`) emits plain
   default edges. `StateNode` exposes one target handle (`Position.Left`) and one source
   handle (`Position.Right`). So `A→B` leaves A's right edge into B's left, and `B→A` leaves
   B's right edge and doubles all the way back to A's left — the two paths cross.
2. **Only one condition label readable.** Both edges of a pair place their label at the same
   path midpoint; they are drawn on top of each other.
3. **No arrowheads.** No `markerEnd` is set anywhere. Direction is only discoverable by
   clicking an edge and reading `from → to` in the right panel.
4. **Layout resets on refresh.** `fdaToNodes` (`TaskEditor.tsx:144`) computes
   `position: { x: (i % 4) * 270, y: Math.floor(i / 4) * 170 }` from the array index on every
   mount. Dragging only mutates react-flow's local node state, which dies on unmount. Nothing
   is ever read from or written to storage.

### Locked decision 1 — Layout persistence: new DB column

`task_definitions.ui_layout JSONB`, shape `{"nodes": {"<state>": {"x": n, "y": n}}}`.
Added via the existing `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` pattern in `api/db.py`
(`run_toolkit_migrations`). Returned by `GET /api/task-definitions/{id}`, accepted by `PUT`.

**Rejected: storing it inside `fda_json`.** `file_hash = sha256(json.dumps(fda_json,
sort_keys=True))` (`api/routers/toolkits.py:590`, reassigned on update at `:838`) and is
`unique` on the table (`api/models.py:522`). Layout inside `fda_json` means every node drag
rewrites the task definition's content hash and ships canvas coordinates to the Pi.

**Rejected: browser localStorage.** Per-browser and per-machine. This is a shared lab account
— positions must follow the task definition to whoever opens it next.

Implementation note: `fda_json`, `display_name`, and `toolkit_name` are **not declared on the
`TaskDefinition` ORM class** — they are read and written by raw SQL against the migrated
columns. `ui_layout` follows that same pattern.

*Corrected 2026-08-05 (plan-checker):* an earlier draft of this note also listed `toolkit_id`
as raw-SQL-only. It is not — `toolkit_id`, `validation_status`, and `validation_message` are
declared `Column`s (`api/models.py:526-528`). The raw-SQL-only set is exactly `fda_json`,
`display_name`, `toolkit_name`. No plan action changes as a result; `ui_layout` is raw-SQL
either way.

### Locked decision 2 — Default layout: hand-rolled layered, no new dependency

BFS-rank states from `initial_state` along transitions to assign a column (x); spread siblings
vertically within the column (y); states unreachable from `initial_state` go in a trailing
column rather than being dropped.

**Rejected: adding `@dagrejs/dagre`.** It would give crossing minimisation and tighter packing,
but `web_ui/react-src` has no lockfile and the Dockerfile runs a bare `npm install` on every
image build — a new dep is a new build-time network fetch. FDA graphs here are a handful of
states, so the packing gain does not pay for that.

### Locked decision 3 — Edge rework: custom edge component, existing handles

One `TransitionEdge` component. Edges grouped by unordered node pair; each member gets a
perpendicular offset proportional to its index in the group, so opposing pairs bow apart and
same-direction duplicates separate too. Each label rides at a staggered position along its own
curve. Arrowhead at the target end, oriented to the curve's tangent — not the straight-line
angle, or it will visibly disagree with the offset curve it sits on.

**Rejected: 4-side / floating handles on `StateNode`.** Cleanest result for right-to-left
transitions, but it rewrites `StateNode`'s handle model and changes how drag-to-connect feels.
Not worth it for this phase.

### Constraint — layout persistence must not reuse the FDA autosave

The autosave at `TaskEditor.tsx:318-351` debounces on `fdaJson` and holds the PUT behind two
guards: an incomplete `trigger_assignment` (`isCompleteTrigger`) and a half-built
`entry_action` (`isCompleteAction`). Both exist for good reasons — the backend 422s on either,
and filtering them out of the payload would delete already-saved rows.

A node drag is not an FDA edit. If layout rode that path, dragging a node while a trigger is
half-built would silently refuse to save the position, and every drag would flash "Unsaved…"
for a change with no semantic content. Layout gets its own debounced PUT and its own status
handling; dragging must never mark the FDA dirty.

### Constraint — file size

`TaskEditor.tsx` is 873 lines. The project's standard is 300 lines with a 500-line hard limit,
and `CLAUDE.md` calls this file out by name under "Avoid". The layered layout algorithm, the
`TransitionEdge` component, and the layout-persistence hook each go in their own new module.
Net change to `TaskEditor.tsx` must not increase its line count.

### Locked decision 4 — Back-edge routing and orphan packing are in scope (added 2026-08-05)

Added after the plans were written and verified, on the user's question "are we built to deal
with multiple edges crossing other nodes?" The answer against the plan as it stood was no, and
the evidence came from real definitions rather than a hypothetical:

**Task definition 186 (`source_less_toolkit FDA_tes_interuuppt`)** — the graph the user named.
BFS layout gives four single-node columns:

```
[init] ──▶ [trial_onset] ──▶ [play_led] ⇄ [rand]
              ▲                              │
              └──────────────────────────────┘
                     rand → trial_onset
```

Of its 5 transitions, CANVAS-01 handles four. The fifth, `rand → trial_onset`, runs backward
across two columns straight through `play_led` — and is **unpaired** (there is no
`trial_onset → rand`), so the pair-grouping rule never even considers it. This is structural,
not a tuning problem: pair offset only ever separates edges that share a node pair.

→ **CANVAS-13.** Detect a backward edge (target column strictly left of source column) and bow
it clear of the intervening band on one consistent side, magnitude scaled to columns spanned.
A backward edge spanning one column stays on the CANVAS-01 pair path — it is adjacent and has
nothing to clear.

**Task definitions 172 / 161 / 155** — 14, 11, and 11 states respectively, with only **3**
appearing in any transition. CANVAS-07's "unreachable states go in a trailing column" would
render an 11-node vertical stack beside a 3-node graph. These are toolkit states appended by
the sync effect (`TaskEditor.tsx:268-300`) that were never wired into the FDA.

→ **CANVAS-14.** Unreachable states wrap into a grid block rather than one unbounded column.

Both land as additional cases in `edgeGeometry.mts` (29-02) and `fdaLayout.mts` (29-03) — the
modules those plans already create. No new architecture, no new dependency; locked decisions
1–3 are untouched.

**Also noted, deliberately accepted:** for a linear chain every column holds one node, so all
nodes sit at y=0 — the flat row the user originally objected to. For a chain that *is* the
correct reading; the objection was really that the old index grid produced a row that carried
no meaning. What made the flat row unreadable here was the back-edges crossing it, which is
what CANVAS-13 fixes.

### Claude's Discretion

- Exact offset geometry (curvature, px separation per index, label stagger fractions) — tune
  to what actually reads well at default zoom.
- Column/row spacing constants for the layered layout.
- Debounce interval for the layout PUT.
- Whether `ui_layout` is returned as a nested object or flattened on the task-definition
  response, so long as `GET` round-trips what `PUT` accepts.
- Module names and file placement for the three new modules.
- How a self-loop is drawn geometrically, so long as it is legible and carries its own label
  and arrowhead.

</decisions>

<specifics>
## Specific Ideas

- The existing node context menu (`TaskEditor.tsx:679-710`) already has the right look for a
  canvas menu — reuse its styling for the pane menu rather than inventing a second style.
- `addState` (`TaskEditor.tsx:423`) and the toolkit-sync effect (`TaskEditor.tsx:268-300`) both
  stamp new nodes onto the index grid today. With positions now persisted, that can drop a new
  node directly on top of a positioned one. Both must route through the same placement logic,
  and placing a new node must not move any existing one.
- Self-transitions (`A→A`) currently degenerate. They need a real loop.
- Verification is manual — the project has no automated test suite (`CLAUDE.md`). The proof
  path is CANVAS-12: open a definition with a bidirectional pair, confirm both arcs/labels/
  arrows, drag three nodes, hard-refresh, confirm they held, then right-click → restore →
  refresh again. Negative case: with an unfinished trigger assignment present, dragging a node
  still persists.

</specifics>

<deferred>
## Deferred Ideas

- 4-side / floating handles on `StateNode` (considered and rejected above; revisit only if
  offset curves prove insufficient on denser graphs).
- Dagre or ELK layout with crossing minimisation — revisit if FDA graphs grow past what the
  simple layered algorithm arranges cleanly.
- ~~Edge routing that avoids passing *through* unrelated nodes.~~ **Partially pulled into scope
  2026-08-05 — see "Locked decision 4" below.** The *backward-edge* case (CANVAS-13) is now in
  scope because real data showed it is not an edge case. What remains deferred is general
  obstacle avoidance: a *forward* edge spanning several columns can still pass near a node in
  between, and nothing routes around arbitrary geometry after the user drags nodes manually.
- Per-user layouts. `ui_layout` is one shared arrangement per task definition, matching how the
  lab shares one account.

</deferred>

---

*Phase: 29-fda-builder-canvas-ux*
*Context gathered: 2026-08-05 — decisions taken live with the user; three alternatives were presented and explicitly rejected (see Locked decisions 1–3)*
