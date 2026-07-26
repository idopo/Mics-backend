# Phase 23: Compute Primitives + Variables - Context

**Gathered:** 2026-06-01
**Status:** Ready for planning
**Source:** Approved design spec — `~/.claude/plans/i-realized-something-the-ancient-pnueli.md`

<domain>
## Phase Boundary

Deliver the full **no-Python computed-value loop** for GUI-assembled FDA-JSON-v2 tasks:
researchers can compute values (random draws, derived numbers/booleans) at state entry,
store them in named variables, and route on them via the existing guarded transitions —
without writing Python or editing locked, centralized toolkit source.

**Why now:** Phases 09–13 centralized hardware drivers, toolkits, and task definitions and
made tasks GUI-assembled instead of Pi-only Python source. That removed the old source
tasks' ability to do `self.target = random.choice([...])` in a state body and branch on it.
The current action vocabulary (`hardware`/`flag`/`timer`/`special`/`method`) can't express
value-producing computation; the only door, `type:"method"`, requires a developer to edit
locked toolkit source. This phase closes that gap.

Three plans (waves), one coherent capability:
- **23-01** Pi runtime — `variables` registry + `compute` action + curated stdlib primitives
- **23-02** Backend — task-definition validation + compute-library storage (reuse Phase-9 infra)
- **23-03** GUI — compute state-builder editor + inline variable auto-declare + transition wiring

> The sandboxed `expr` escape-hatch was **decoupled/deferred** (see Deferred Ideas). `compute`
> is self-sufficient — it rides entirely on the `variables`/`output` plumbing built in 23-01.

</domain>

<decisions>
## Implementation Decisions (LOCKED — confirmed with user)

### Mechanism
- Curated **compute primitives** (library-backed) are the mechanism for this phase. A `compute`
  entry-action writes a result into a named variable. (A sandboxed `expr` evaluator for the long
  tail was considered but decoupled/deferred — see Deferred Ideas.)

### Output binding — the `variables` registry
- New top-level `variables` in FDA-JSON-v2 alongside `states`/`transitions`:
  `"variables": { "<name>": {} }`. **Untyped generic scratch slots** — a name is enough.
- At `load_fda_from_json()`, each variable is instantiated as a generic `Tracker`
  (initial `None`) and registered in **BOTH** `self.flags` and `self.view.view` — identical
  to `init_flags()` (mics_task.py:268-280). Transitions then read variables via the existing
  `{"view": name}` / `{"flag": name}` operand path with **zero new transition-read code**.
- **Last-write-wins**: re-entering a state re-runs its compute action and overwrites the same
  slot (matches old instance-attribute behavior across trials). No reset between trials.
- **Inline auto-declare in the GUI**: typing a new `output` name in a compute action adds
  it to the `variables` registry and makes it immediately selectable as a transition operand.
  No separate declaration step.

### Action type
- `compute`: `{ "type": "compute", "op": "<primitive>", "args": [...], "output": "<var>" }`.
  Args resolve via existing `_resolve_arg` forms (literal / `{param}` / `{flag}` / variable).
  Evaluated **at state entry** → deterministic-safe (transition guards only read the stored
  result, so `check_determinism()` never re-runs randomness).

### Branching
- Branching stays in **FDA transitions (idiomatic)** — the pair of guarded transitions *is* the
  if/else. Compute primitives only produce values into variables. **No `if`-action type.**

### Compute library
- One **shared compute library** (pure functions) available to all toolkits, stored & versioned
  via the **existing Phase-9 hardware-lib DB infra** as a non-hardware library row (no new table);
  AST extraction reused so the GUI knows each primitive's signature. Not bolted onto hardware
  libs, not duplicated per toolkit.
- Curated set (stdlib `random`/`math` + builtins only — always present on Pi, no package dep):
  - random/copy: `random_choice(list)`, `random_int(min,max)`, `random_float(min,max)`,
    `random_bool(p)`, `assign(value)`.
  - numeric/util: `add(a,b)`, `subtract(a,b)`, `multiply(a,b)`, `divide(a,b)` (raise on /0),
    `modulo(a,b)` (raise on /0; "every Nth trial"), `minimum(a,b)`, `maximum(a,b)`,
    `clamp(value,lo,hi)`.
  - Numeric value-production only; NO comparison/boolean-logic ops (branching stays in
    transitions; Phase 15 DNF conditions already compose booleans).
  - A variable read back as an arg (`add(counter,1)→counter`) is the supported counter/tally
    pattern — one reused slot, so flag/variable count need not grow.

### Backend validation
- `_validate_task_definition()` rejects (422, hard — distinct from the soft hardware-drift path):
  a `compute` `output` not declared in `variables`; a variable name colliding with toolkit
  `FLAGS` / `SEMANTIC_HARDWARE` / view keys; a transition/condition referencing an undeclared
  variable. Logic lives in a new `api/fda_validation.py` sibling module (toolkits.py is already
  oversized — import + call only).
- `api/fda_utils.py` ref scanner extended to cover `compute` `output` names.

### Claude's Discretion
- Exact module name/path on the Pi (`compute_primitives.py` or equivalent).
- Internal structure of the primitive registry/dispatch.
- React component decomposition within the existing StateBodyPanel/ActionEditor/ConditionBuilder.
- Test harness shapes (negative-test cases, the gonogo-translation verification task).

</specifics>

<specifics>
## Specific Ideas

- **Canonical verification task**: translate `gonogo`'s random-target logic into FDA-JSON-v2 —
  `"variables": {"target": {}}`, a `trial_onset` state with
  `{ "type":"compute", "op":"random_bool", "args":[0.5], "output":"target" }`, and two guarded
  transitions on `{"view":"target","op":"==","rhs":{"literal":true}}` / `false`. Both branches
  must be reachable across trials; `target` recomputed once per entry.
- **Hot-reload**: new `variables`/`compute` flow through the existing `UPDATE_FDA` store;
  newly-added variables instantiated as Trackers **before** transitions referencing them rebuild.

</specifics>

<deferred>
## Deferred Ideas

- **`expr` escape-hatch (sandboxed restricted-AST evaluator + `type:"expr"` action)** —
  decoupled from this phase (former CMP-07–09). With arithmetic/min/max/clamp now in the curated
  set, `expr` would only cover the remaining long tail — multi-term expressions and boolean logic
  that don't map to a single primitive — via a free-typed expression over a whitelist
  (`random.*`/`math.*` + params/flags/variables), evaluated once at state entry. The
  library-backed `compute` path covers current needs; `expr` rides on the same
  `variables`/`output` plumbing, so it can be re-added as its own phase later with no rework to
  Phase 23. Full design: `~/.claude/plans/i-realized-something-the-ancient-pnueli.md`.
- **Per-Pi package management + in-UI terminal** — explicitly out of scope. Task logic depends
  only on the centrally-shipped runtime (stdlib `random`/`math`). Stays in `pi_code_editor_plan.md`
  for hardware-driver/dev use only; coupling task logic to per-Pi packages would reintroduce the
  per-rig fragility 09–13 removed.
- **`if`-action / nested then-else action branching** — transitions handle branching.
- **Typed variables** — untyped generic scratch for v1; revisit only on concrete need.

</deferred>

---

*Phase: 23-compute-primitives-variables*
*Context gathered: 2026-06-01 from approved design spec*
