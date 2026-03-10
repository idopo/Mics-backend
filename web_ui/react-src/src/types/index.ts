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
}

// params dict on a step: everything including graduation, step_name, task_type
export interface ProtocolStep {
  id?: number
  task_type: string
  step_name: string
  order_index?: number
  protocol_id?: number
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
