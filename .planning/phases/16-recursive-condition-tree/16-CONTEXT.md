# Phase 16: Recursive Condition Tree - Context

**Gathered:** 2026-05-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the flat DNF `condition_groups` field with a recursive `condition_tree` field on `FdaTransition`. The editor gets per-row +AND/+OR buttons (Kibana FiltersBuilder model) where visual nesting depth (via background opacity/shading) IS the parentheses. The Pi evaluator gets simpler — a recursive `_build_tree_lambda()` that maps directly to Python `all()` / `any()` calls. Backward-compat migration of legacy `condition_groups` and `conditions[]` on load.

</domain>

<decisions>
## Implementation Decisions

### UI Model — Kibana FiltersBuilder
- Each condition row has both +AND and +OR buttons (inline, not a footer button)
- +AND: appends a new sibling leaf inside the same AND-context as the current row
- +OR: appends a new leaf at the OR level (creates or extends an OR-branch above)
- Visual nesting depth encoded via background opacity/shading — subdued panel = deeper nesting; this IS the visual representation of parentheses
- No explicit "( )" text in the editor — shading communicates grouping
- Match app visual aesthetic (existing `var(--border)`, `var(--accent)`, panel/card style from `ConditionGroupsEditor`)

### Tree Data Model
- `ConditionNode`: leaf = `FdaCondition` | branch = `{ op: 'AND' | 'OR', children: ConditionNode[] }`
- `FdaTransition.condition_tree?: ConditionNode` — new canonical field
- Legacy fields `condition_groups` and `conditions[]` remain on the type as optional for Pi backward compat

### Migration (`normaliseTransition`)
- `condition_tree` present → use as-is
- `condition_groups` present (no tree) → convert to OR-of-AND-nodes tree
- `conditions[]` only → single AND-leaf or empty tree
- Re-save always writes `condition_tree`; never writes back `condition_groups`

### Pi Evaluation — Simplified
- New `_build_tree_lambda(node)`:
  - Leaf node → `_build_transition_lambda(node)` (existing single-condition evaluator)
  - AND-node → `lambda: all(f() for f in children_lambdas)` 
  - OR-node → `lambda: any(f() for f in children_lambdas)`
- This is strictly simpler than the current DNF evaluator — no special-casing needed
- Fallback chain: `condition_tree` → `condition_groups` → `conditions[]`

### `condLabel()` — Parenthesized rendering
- Flat AND: `A ∧ B` (no parens)
- Flat OR: `A ∨ B` (no parens)
- OR nested inside AND: `(A ∨ B) ∧ C` (parens around OR child)
- AND nested inside OR: `A ∨ (B ∧ C)` — parens when AND child of OR is ambiguous
- Recursive traversal; add parens when a child's operator has lower precedence than parent's

### File Strategy
- Rewrite `ConditionGroupsEditor.tsx` in-place — rename to `ConditionTreeEditor` internally, same filename to avoid import churn
- `IfActionEditor` uses a single `ConditionRow` (flat single condition) — leave untouched

### Nesting Depth
- Arbitrary depth (no artificial cap) — the Kibana model handles this cleanly via recursive render
- In practice behavioral conditions stay shallow (≤ 3 levels), but no enforced limit

### Deletion & Simplification
- Deleting the last child of a branch → remove the branch node entirely (auto-collapse)
- Single-child AND/OR branch → collapse to its child (avoid pointless wrapper)
- Empty tree → "unconditional" hint (same as current)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ConditionRow` (exported from `ConditionBuilder.tsx`): renders a single `FdaCondition` with field/op/value selectors + delete; reuse as leaf renderer in tree
- `operandLabel()` (ConditionBuilder.tsx): used by `condLabel()` — keep
- `var(--border)`, `var(--accent)`, `var(--text-muted)`: CSS vars already used in ConditionGroupsEditor; keep same aesthetic

### Established Patterns
- Panel nesting already done in `ConditionGroupsEditor`: outer `div` with `border + borderRadius`, inner rows. Phase 16 extends this to recursive depth with opacity stepping.
- Button style: `background:none; border:none; color:var(--accent); cursor:pointer` — match existing +AND/+OR button style

### Integration Points
- `TaskEditor.tsx`: calls `normaliseTransition()` (update to handle `condition_tree`), `condLabel()` (update for parens), `updateTransitionGroups()` → replace with `updateTransitionTree()`
- `ConditionGroupsEditor` import in TaskEditor → same filename, just internal rename
- `~/pi-mirror/autopilot/autopilot/tasks/mics_task.py`: add `_build_tree_lambda()`, update transition registration fallback chain

</code_context>

<specifics>
## Specific Ideas

- Visual reference: Kibana FiltersBuilder HTML (user provided) — subdued `euiPanel--subdued` class for nested groups; each row has inline +AND/+OR; nesting shown by background shade not indent
- App aesthetic: keep existing color scheme, don't introduce new CSS variables — use opacity stepping on the existing `var(--border)` panel background
- Pi simplification: the recursive `all()`/`any()` approach is cleaner than the current DNF loop — this is a feature, not a concern

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 16-recursive-condition-tree*
*Context gathered: 2026-05-27*
