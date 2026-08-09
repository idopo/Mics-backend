export interface PilotLive {
  connected: boolean
  state: string          // "IDLE" | "RUNNING" | "UNKNOWN"
  active_run: ActiveRun | null
  updated_at: string | null
}

export interface Pilot {
  id: number
  name: string
}

export interface ActiveRun {
  id: number
  session_id: number
  subject_key: string
  started_at: string
  status: string
}

export interface Subject {
  id: number
  name: string
  protocol_id?: number | null
  protocol_name?: string | null
  strain?: string | null
  sex?: string | null
  group_type?: string | null
}

export interface SubjectProtocolRunItem {
  id: number
  subject_id: number
  protocol_id: number
  session_id: number
  current_step: number
  started_at: string
  finished_at: string | null
}

export interface ResearcherRead {
  id: number
  name: string
  email?: string | null
}

export interface IACUCRead {
  id: number
  number: string
  title: string
  expires_at?: string | null
}

export interface WeightRead {
  id: number
  subject_id: number
  measured_at: string
  weight_grams: number
  notes?: string | null
}

export interface SurgeryRead {
  id: number
  subject_id: number
  procedure_type: string
  performed_at?: string | null
  notes?: string | null
}

export interface ProjectRead {
  id: number
  name: string
  description?: string | null
  iacuc_id?: number | null
  lead_researcher_id?: number | null
  results_notes?: string | null
  notes?: string | null
  created_at: string
}

export interface ExperimentRead {
  id: number
  name: string
  project_id: number
  description?: string | null
  notes?: string | null
  created_at: string
}

export interface SubjectExtendedRead {
  id: number
  name: string
  strain?: string | null
  genotype?: string | null
  mother_name?: string | null
  father_name?: string | null
  dob?: string | null
  sex?: string | null
  rfid?: number | null
  lead_researcher_id?: number | null
  arrival_date?: string | null
  in_quarantine?: boolean | null
  location?: string | null
  holding_conditions?: string | null
  group_type?: string | null
  group_details?: string | null
  notes?: string | null
  weights: WeightRead[]
  surgeries: SurgeryRead[]
  projects: ProjectRead[]
}

// params dict on a step: everything including graduation, step_name, task_type
export interface ProtocolStep {
  id?: number
  task_type: string
  step_name: string
  order_index?: number
  protocol_id?: number
  task_definition_id?: number | null
  params: Record<string, unknown>
}

export interface Protocol {
  id: number
  name: string
  description?: string
  created_at?: string
  steps: ProtocolStep[]
}

// Returned by /api/sessions (list)
export interface SessionSummary {
  session_id: number
  started_at: string
  n_runs: number
}

// Returned by /api/sessions/{id} (detail)
export interface SessionDetailRun {
  run_id: number
  subject_id: number
  subject_name: string
  protocol_id: number
  protocol_name: string
  started_at: string
  finished_at: string | null
}

export interface SessionDetail {
  session_id: number
  started_at: string
  n_runs: number
  runs: SessionDetailRun[]
}

export interface SessionRun {
  id: number
  session_id: number
  pilot_id: number
  status: string
  mode?: string
  started_at: string
  ended_at?: string | null
  overrides?: Record<string, unknown>
}

export interface RunProgress {
  current_step?: number | null
  current_trial?: number | null
}

export interface RunWithProgress {
  run: SessionRun
  progress: RunProgress | null
}

export interface TaskParam {
  type: string
  tag?: string
  default?: unknown
  value?: unknown
  description?: string
  minimum?: number
  maximum?: number
  enum?: unknown[]
}

export interface TaskDef {
  task_name: string
  base_class?: string | null
  hardware?: Record<string, unknown>
  file_hash?: string
  pilots?: string[]
  default_params?: Record<string, TaskParam>
  params?: Record<string, TaskParam>
}

export interface StartOptions {
  session_id: number
  pilot_id: number
  active_run: { id: number; status: string } | null
  recoverable_run: { id: number; status: string } | null
  progress: { current_step?: number | null; current_trial?: number | null } | null
  can_resume: boolean
  can_start_over: boolean
}

export interface Overrides {
  global?: Record<string, unknown>
  steps?: Record<string, Record<string, unknown>>
}

// --- FDA Editor types (Phase 3, v2 schema) ---

export type FdaOperand =
  | { view: string }
  /** A detector reference, never a resolved per-pilot key (DVK-11). The name that appears at
   *  `view.view[...]` on the pilot is resolved from `ref` + `channel` at build time on the Pi —
   *  the same stored operand reads "LICKER2" on one pilot and "TONGUE2" on another. */
  | { view_detector: { ref: string; channel: number } }
  | { tracker: string }
  | { flag: string }
  | { param: string }
  | { hardware: string }
  | { trigger: 'level' | 'tick' }
  | number | boolean | string | null

export interface FdaCondition {
  left: FdaOperand
  op: '==' | '!=' | '>=' | '<=' | '>' | '<'
  right: FdaOperand
}

export interface FdaAction {
  type: 'hardware' | 'flag' | 'timer' | 'special' | 'method' | 'if' | 'view' | 'compute'
  ref?: string
  method?: string
  args?: unknown[]
  action?: string
  duration?: unknown
  /** Capture the call's return value: string = whole value, string[] = positional tuple unpack.
   *  Targets must be declared in FdaJson.variables (or be an existing toolkit flag).
   *  MANDATORY for `type: 'compute'` — a compute action that writes nothing is meaningless.
   *  Optional for every other action type. */
  output?: string | string[]
  /** view action: target key in view.view; may contain {name} tokens resolved from variables/flags. */
  key_template?: string
  /** view action: hardware ref whose device_name resolves a {device_name} token in key_template
   *  at runtime — required whenever that runtime token is used (TRIGA-17/18, 24-CONTEXT.md R5). */
  source_ref?: string
  /** view action: the value to write. */
  value?: unknown
  /** view action: keyword args forwarded to Tracker.set (e.g. { pi_timestamp: { trigger: 'tick' } }). */
  kwargs?: Record<string, unknown>
  // if-action fields:
  condition?: FdaCondition
  then?: FdaAction[]
  else?: FdaAction[]
}

export interface FdaState {
  entry_actions?: FdaAction[]
  wait_condition?: FdaCondition
  return_data?: unknown[]
  _passthrough?: boolean
}

export interface ConditionGroup {
  conditions: FdaCondition[]   // all must be true (AND within group)
}

/** Recursive condition tree node. Leaf = a single FdaCondition; branch = AND/OR of children. */
export type ConditionNode =
  | FdaCondition                                          // leaf: has left/op/right
  | { op: 'AND' | 'OR'; children: ConditionNode[] }      // branch

/** Type guard: is this a branch node (not a leaf FdaCondition)? */
export function isConditionBranch(node: ConditionNode): node is { op: 'AND' | 'OR'; children: ConditionNode[] } {
  return typeof node === 'object' && node !== null && ('op' in node) && (node.op === 'AND' || node.op === 'OR') && 'children' in node
}

export interface FdaTransition {
  from: string
  to: string
  condition_tree?: ConditionNode        // canonical recursive tree (Phase 16+)
  condition_groups?: ConditionGroup[]   // legacy DNF — kept for Pi backward compat
  conditions?: FdaCondition[]           // legacy flat — kept for Pi backward compat
  description?: string
}

/** A named value slot shared between task.flags and view.view on the Pi. */
export interface FdaVariable {
  initial_value?: unknown
}

/** One variable's writer/reader locations, from GET /api/task-definitions/{id}/variable-usage. */
export interface VariableUsage {
  writers: string[]
  readers: string[]
  never_written: boolean
  initial_value: unknown
}

export interface VariableUsageResponse {
  variables: Record<string, VariableUsage>
}

export interface FdaTriggerAssignment {
  trigger_name: string   // hardware key that fires the interrupt, e.g. "TOUCH_INT"
  /** Ordered action list using the same schema as a state's entry_actions. The ONLY vocabulary. */
  actions: FdaAction[]
  /** @deprecated Phase 24 dropped the handler enum. Optional only so stored rows still parse;
   *  normaliseFda strips it. Never write it. */
  handler?: string
  /** @deprecated Belonged to the handler enum. Stripped by normaliseFda. Never write it. */
  config?: {
    hardware_ref?: string  // semantic hw key; used by touch_detector to pick which device to read
    view_key?: string      // view key to update; used by digital_input
  }
}

export interface FdaJson {
  version: 2
  initial_state: string
  states: Record<string, FdaState>
  transitions: FdaTransition[]
  trigger_assignments: FdaTriggerAssignment[]  // array — NOT a dict
  /** Phase 24 value-capture registry; Phase 23's `compute` writes into the same slots. */
  variables?: Record<string, FdaVariable>
  hw_overrides?: Record<string, unknown>       // optional; legacy field — pass through unchanged, never write or display
}

export interface ToolkitFlag {
  tracker_type: string    // "Counter_Tracker" | "Boolean_Tracker" | "Trial_Tracker" | "Tracker"
  initial_value: number | boolean
}

/** A hardware module whose class sets `is_trigger` — reported truthfully, grouped by direction. */
export interface TriggerSource {
  hw_id: string
  module_id: number
  class_name: string
  direction: 'input' | 'output' | null
}

/** One pilot's declared wiring for a detector channel group — provenance behind `conflict`. */
export interface DetectorChannelPilot {
  pilot_id: number
  pilot_name: string
  device_name: string
  channels: number[]
  keys: string[]
}

/** Advisory, cross-pilot union of a detector module's channels (plan 03's derivation). */
export interface DetectorChannelGroup {
  module_name: string
  /** User-chosen prefix(es) — e.g. "LICKER" on this rig. Not a constant; never hardcode it. */
  device_names: string[]
  /** WHAT IS STORED (DVK-11). `keys` below is only a preview of the resolved names. */
  channels: number[]
  keys: string[]
  conflict: boolean
  by_pilot: DetectorChannelPilot[]
}

/** One pilot's resolved extlink keys — provenance behind `conflict` (18-13's aggregation). */
export interface ExtlinkSignalPilot {
  pilot_id: number
  pilot_name: string
  source_id: string
  keys: string[]
}

/** Cross-pilot union of one ExternalHardware module's declared signals + `<source_id>.alive`. */
export interface ExtlinkSignalGroup {
  module_name: string
  /** Per-pilot source_id(s) configured for this module — >1 means the pilots disagree. */
  source_ids: string[]
  /** Pilot-invariant — declared once on the lib version, not per pilot. */
  signals: { name: string; dtype: string | null }[]
  /** WHAT IS STORED (matches the detector-channel `keys` contract): `${source_id}.${name}` + `.alive`. */
  keys: string[]
  conflict: boolean
  by_pilot: ExtlinkSignalPilot[]
}

export interface ToolkitRead {
  id: number
  name: string
  hw_hash: string
  states: string[] | null
  flags: Record<string, ToolkitFlag>
  params_schema: Record<string, unknown> | null
  semantic_hardware: Record<string, unknown> | null
  callable_methods: string[] | null
  required_packages: string[] | null
  pilot_origins: string[]
  fda_count: number
  is_backend_authored: boolean
  hardware_module_ids: number[]
  locked_state_source: string | null
  created_at: string
  updated_at: string
  /** Older API responses predate this column — always optional. */
  trigger_sources?: TriggerSource[]
  detector_refs?: string[]
  /** Older API responses predate this column — always optional. */
  detector_channels?: DetectorChannelGroup[]
  /** Older API responses predate this column — always optional (18-13). */
  extlink_signals?: ExtlinkSignalGroup[]
}

// Locked states (Phase 11)
export interface LockedStateEntry {
  state_names: string[]
  pilots: string[]
  pilot_ids: number[]
  is_legacy_filename: boolean
  updated_at: string
}

export interface LockedStatesResponse {
  by_file: Record<string, LockedStateEntry>
}

// Toolkit creation payload types
export interface FlagDefinition {
  name: string
  tracker_type: string
  initial_value: unknown
}

export interface ParamDefinition {
  name: string
  type: string
  default: unknown
}

export interface BackendToolkitCreatePayload {
  name: string
  locked_state_source: string | null
  selected_states: string[]
  hardware_module_ids: number[]
  flags: FlagDefinition[]
  params_schema: ParamDefinition[]
}

export interface BackendToolkitPatchPayload {
  hardware_module_ids?: number[]
  flags?: FlagDefinition[]
  params_schema?: ParamDefinition[]
}

/** Canvas node positions for the FDA editor. Stored in task_definitions.ui_layout — never in
 *  fda_json, which is content-hashed and shipped to the Pi (CANVAS-06). */
export interface UiLayout {
  nodes: Record<string, { x: number; y: number }>
}

export interface TaskDefinitionFull {
  id: number
  task_name: string
  display_name: string | null
  toolkit_name: string | null
  fda_json: FdaJson | null
  file_hash: string
  created_at: string
  validation_status: "ok" | "broken"
  validation_message: string | null
  ui_layout?: UiLayout | null
}

// --- Hardware Libs (Phase 9) ---

export type LibState = 'unvalidated' | 'beta' | 'stable'
export type LibKind = 'hardware' | 'compute'

export interface HardwareLib {
  id: number
  name: string
  filename: string
  kind: LibKind
  ast_metadata: Record<string, unknown> | null
  active_version_id: number | null
  stable_version_id: number | null
  active_state: LibState | null
  source_code: string | null
  validation_error: string | null
  created_at: string
  updated_at: string | null
}

export interface HardwareLibVersion {
  id: number
  hardware_lib_id: number
  version_number: number
  source_code: string
  sha256_hash: string
  state: LibState
  declared_imports: string[] | null
  ast_metadata: Record<string, unknown> | null
  created_at: string
  stable_at: string | null
  stable_reason: string | null
  stable_pilot: string | null
  validation_error: string | null
}

// --- Hardware Modules (Phase 10) ---

export interface AstMethodArg {
  name: string
  annotation: string | null
  default?: string
}

export interface AstMethod {
  name: string
  args: AstMethodArg[]
}

export interface HardwareModule {
  id: number
  name: string
  display_name: string | null
  hardware_lib_id: number
  class_name: string
  description: string | null
  created_at: string
  lib_filename: string | null
  // Joined from the module's lib; the FDA editor's compute op picker (plan 23-08) filters on this.
  lib_kind: LibKind | null
}

export interface HardwareModuleMethods {
  module_id: number
  module_name: string
  class_name: string
  methods: AstMethod[]
  is_detector: boolean
}

export interface PilotHardwareConfigRow {
  id: number
  pilot_id: number
  name: string
  config: Record<string, unknown>
}

// --- Hw Lib Version Selections (TaskEditor) ---

export interface HwLibVersionEntry {
  hardware_lib_id: number
  lib_name: string
  lib_filename: string
  selected_version_id: number | null
  selected_version_number: number | null
  selected_version_state: string | null
  active_version_id: number | null
  active_version_number: number | null
  active_version_state: string | null
}

export interface HwLibDiffItem {
  class_name: string
  method_name: string
}

export interface HwLibDiffChangedItem extends HwLibDiffItem {
  old_args: unknown[]
  new_args: unknown[]
}

export interface HwLibDiff {
  removed_methods: HwLibDiffItem[]
  changed_signatures: HwLibDiffChangedItem[]
  added_methods: HwLibDiffItem[]
}
