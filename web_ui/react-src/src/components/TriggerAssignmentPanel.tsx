import { useState } from 'react'
import type { FdaTriggerAssignment, FdaAction, FdaVariable, ToolkitRead, HardwareModule, TriggerSource } from '../types'
import ActionEditor from './ActionEditor'
import { typeChipStyle, actionSummary } from './StateBodyPanel'
import DetectorWriteWidget, { matchesDetectorWrite, buildDetectorWrite } from './DetectorWriteWidget'

/**
 * Is this action configured enough for the backend to accept it?
 *
 * Deliberately shallow — only the identifier each action type cannot work without.
 * The backend gate (api/fda_validation.py) stays authoritative for whether the ref
 * actually resolves; duplicating that here would just create vocabulary drift.
 */
function isCompleteAction(action: FdaAction): boolean {
  switch (action.type) {
    // A hardware/timer call needs both the device and the method — `ref` alone would
    // save an action that does nothing on the Pi.
    case 'hardware':
    case 'timer':
      return Boolean(action.ref?.trim()) && Boolean(action.method?.trim())
    case 'method':
    case 'flag':
    case 'special':
      return Boolean(action.ref?.trim())
    case 'view':
      return Boolean(action.key_template?.trim())
    case 'if':
      return [...(action.then ?? []), ...(action.else ?? [])].every(isCompleteAction)
    default:
      return false
  }
}

/** A trigger assignment the backend will accept: named, with at least one configured action. */
export function isCompleteTrigger(a: FdaTriggerAssignment): boolean {
  return (
    Boolean(a.trigger_name?.trim()) &&
    Array.isArray(a.actions) &&
    a.actions.length > 0 &&
    a.actions.every(isCompleteAction)
  )
}

/**
 * Drop half-built trigger assignments from an FDA before saving.
 *
 * The editor autosaves 1.5s after any change, so a freshly-added assignment
 * ({trigger_name: '', actions: []}) would otherwise be PUT while still empty and
 * rejected with a 422 — blocking every later save until it is finished or removed.
 * Incomplete assignments stay in editor state and are flagged "unsaved" in the panel.
 */
export function stripIncompleteTriggers<T extends { trigger_assignments?: FdaTriggerAssignment[] }>(fda: T): T {
  if (!fda.trigger_assignments?.length) return fda
  return { ...fda, trigger_assignments: fda.trigger_assignments.filter(isCompleteTrigger) }
}

interface Props {
  assignments: FdaTriggerAssignment[]
  toolkit: ToolkitRead | null
  hwModules: HardwareModule[]
  taskDefId?: number
  versionStamp?: string
  variableNames: string[]
  variables: Record<string, FdaVariable>
  onVariablesChange: (updated: Record<string, FdaVariable>) => void
  onChange: (updated: FdaTriggerAssignment[]) => void
}

const sectionLabel: React.CSSProperties = {
  fontSize: '11px',
  color: 'var(--muted)',
  fontWeight: 600,
  letterSpacing: '0.08em',
  textTransform: 'uppercase',
  marginBottom: '10px',
}

const fieldLabel: React.CSSProperties = {
  fontSize: '11px',
  color: 'var(--muted)',
  display: 'block',
  marginBottom: '3px',
}

const NEW_ACTION: FdaAction = { type: 'hardware', ref: '', method: '', args: [] }

function nextTriggerName(existing: string[]): string {
  let n = 1
  while (existing.includes(`trigger${n}`)) n++
  return `trigger${n}`
}

/** First trigger source not already assigned, so a fresh assignment starts valid by
 *  construction — mirrors nextTriggerName's placeholder-seeding pattern for the free-text
 *  fallback (plan 05). */
function nextTriggerSourceId(sources: TriggerSource[], existing: string[]): string | null {
  return sources.find(s => !existing.includes(s.hw_id))?.hw_id ?? null
}

/**
 * A trigger assignment is exactly (trigger_name, actions) — the separation principle from
 * 24-CONTEXT.md: nothing hardware-specific lives here. A licker is reached by picking MPR121
 * as an ordinary hardware action inside `actions`, same as a valve or an LED. Every action is
 * edited through the SAME `ActionEditor` the state body panel uses (TRIGA-09).
 */
export default function TriggerAssignmentPanel({
  assignments,
  toolkit,
  hwModules,
  taskDefId,
  versionStamp,
  variableNames,
  variables,
  onVariablesChange,
  onChange,
}: Props): JSX.Element {
  const [expanded, setExpanded] = useState<Record<number, boolean>>({})

  const update = (i: number, patch: Partial<FdaTriggerAssignment>): void =>
    onChange(assignments.map((a, idx) => (idx === i ? { ...a, ...patch } : a)))

  const remove = (i: number): void => onChange(assignments.filter((_, idx) => idx !== i))

  const triggerSources = toolkit?.trigger_sources ?? []

  const add = (): void => {
    const existingNames = assignments.map(a => a.trigger_name)
    const seeded = nextTriggerSourceId(triggerSources, existingNames) ?? nextTriggerName(existingNames)
    onChange([...assignments, { trigger_name: seeded, actions: [] }])
  }

  const toggleExpand = (i: number): void => setExpanded(prev => ({ ...prev, [i]: !prev[i] }))

  const updateAction = (i: number, ai: number, updated: FdaAction): void =>
    update(i, { actions: assignments[i].actions.map((a, idx) => (idx === ai ? updated : a)) })

  const removeAction = (i: number, ai: number): void =>
    update(i, { actions: assignments[i].actions.filter((_, idx) => idx !== ai) })

  const addAction = (i: number): void =>
    update(i, { actions: [...assignments[i].actions, { ...NEW_ACTION }] })

  // The detector-write macro touches both actions and variables — emitted together through the
  // panel's existing update() funnel and the onVariablesChange wire (4b-bis), so autosave stays
  // the single existing debounced path rather than a second save mechanism.
  const pickDetector = (i: number, ref: string): void => {
    const built = buildDetectorWrite(ref, variables)
    update(i, { actions: built.actions })
    onVariablesChange(built.variables)
  }

  const moveAction = (i: number, ai: number, direction: 'up' | 'down'): void => {
    const actions = assignments[i].actions
    const j = direction === 'up' ? ai - 1 : ai + 1
    if (j < 0 || j >= actions.length) return
    const next = [...actions]
    ;[next[ai], next[j]] = [next[j], next[ai]]
    update(i, { actions: next })
  }

  return (
    <div>
      <div style={sectionLabel}>Trigger Assignments</div>

      {assignments.length === 0 ? (
        <p style={{ fontSize: '12px', color: 'var(--muted)', marginBottom: '12px' }}>
          No trigger assignments yet.
        </p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '12px' }}>
          {assignments.map((a, i) => (
            <div
              key={i}
              style={{
                padding: '10px',
                background: 'rgba(255,255,255,0.02)',
                borderRadius: '6px',
                border: '1px solid var(--border)',
                display: 'flex',
                flexDirection: 'column',
                gap: '6px',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: '2px',
                }}
              >
                <label style={fieldLabel}>Trigger name</label>
                <button
                  className="button-danger"
                  style={{ fontSize: '10px', padding: '1px 6px', lineHeight: 1.4 }}
                  onClick={() => remove(i)}
                >
                  ✕
                </button>
              </div>
              {triggerSources.length > 0 ? (
                <select
                  required
                  value={a.trigger_name}
                  onChange={e => update(i, { trigger_name: e.target.value })}
                  style={{
                    width: '100%',
                    fontFamily: "'IBM Plex Mono', monospace",
                    fontSize: '12px',
                    borderColor: a.trigger_name.trim() ? undefined : '#ef4444',
                  }}
                >
                  <option value="">— pick —</option>
                  {!triggerSources.some(s => s.hw_id === a.trigger_name) && a.trigger_name && (
                    <option value={a.trigger_name}>{a.trigger_name} (unknown)</option>
                  )}
                  {triggerSources.some(s => s.direction === 'input') && (
                    <optgroup label="Inputs">
                      {triggerSources.filter(s => s.direction === 'input').map(s => (
                        <option key={s.hw_id} value={s.hw_id}>{s.hw_id}</option>
                      ))}
                    </optgroup>
                  )}
                  {triggerSources.some(s => s.direction === 'output') && (
                    <optgroup label="Outputs">
                      {triggerSources.filter(s => s.direction === 'output').map(s => (
                        <option key={s.hw_id} value={s.hw_id}>{s.hw_id}</option>
                      ))}
                    </optgroup>
                  )}
                  {triggerSources.some(s => s.direction === null) && (
                    <optgroup label="Other">
                      {triggerSources.filter(s => s.direction === null).map(s => (
                        <option key={s.hw_id} value={s.hw_id}>{s.hw_id}</option>
                      ))}
                    </optgroup>
                  )}
                </select>
              ) : (
                <input
                  type="text"
                  required
                  value={a.trigger_name}
                  onChange={e => update(i, { trigger_name: e.target.value })}
                  placeholder="e.g. TOUCH_INT"
                  style={{
                    width: '100%',
                    fontFamily: "'IBM Plex Mono', monospace",
                    fontSize: '12px',
                    borderColor: a.trigger_name.trim() ? undefined : '#ef4444',
                  }}
                />
              )}
              {!a.trigger_name.trim() && (
                <span style={{ fontSize: '10px', color: '#ef4444' }}>Trigger name is required</span>
              )}
              <span style={{ fontSize: '10px', color: 'var(--muted)' }}>
                Only hardware whose class sets is_trigger can carry a trigger — that is what the Pi wires with assign_cb.
              </span>
              {!isCompleteTrigger(a) && (
                <span style={{ fontSize: '10px', color: 'var(--muted)' }}>
                  {!a.trigger_name.trim()
                    ? 'Not saved — incomplete'
                    : a.actions.length === 0
                      ? 'Not saved — add at least one action'
                      : 'Not saved — finish configuring every action'}
                </span>
              )}

              {matchesDetectorWrite(a.actions) ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <DetectorWriteWidget
                    actions={a.actions}
                    toolkit={toolkit}
                    variables={variables}
                    onChange={(nextActions, nextVariables) => {
                      update(i, { actions: nextActions })
                      onVariablesChange(nextVariables)
                    }}
                  />
                  <button
                    onClick={() => toggleExpand(i)}
                    style={{ background: 'none', border: 'none', color: 'var(--muted)', fontSize: '11px', textAlign: 'left', cursor: 'pointer', padding: '4px 0' }}
                  >
                    {expanded[i] ? '▾ Hide raw actions' : '▸ Edit as raw actions'}
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => toggleExpand(i)}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: 'var(--muted)',
                    fontSize: '11px',
                    textAlign: 'left',
                    cursor: 'pointer',
                    padding: '4px 0',
                  }}
                >
                  {expanded[i] ? '▾' : '▸'} Actions ({a.actions.length})
                </button>
              )}

              {expanded[i] && (
                <div>
                  {a.actions.length === 0 ? (
                    <p style={{ fontSize: '12px', color: 'var(--muted)', marginBottom: '8px' }}>
                      No actions. Add one below.
                    </p>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '8px' }}>
                      {a.actions.map((action, ai) => (
                        <div key={ai}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                            <span style={typeChipStyle(action.type)}>{action.type.toUpperCase()}</span>
                            <span style={{ fontSize: '11px', color: 'var(--muted)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {actionSummary(action)}
                            </span>
                            <button
                              onClick={() => moveAction(i, ai, 'up')}
                              disabled={ai === 0}
                              title="Move action up"
                              style={{ background: 'none', border: 'none', cursor: ai === 0 ? 'default' : 'pointer', color: ai === 0 ? 'var(--border)' : 'var(--muted)', padding: '0 2px', fontSize: '12px' }}
                            >
                              ▲
                            </button>
                            <button
                              onClick={() => moveAction(i, ai, 'down')}
                              disabled={ai === a.actions.length - 1}
                              title="Move action down"
                              style={{ background: 'none', border: 'none', cursor: ai === a.actions.length - 1 ? 'default' : 'pointer', color: ai === a.actions.length - 1 ? 'var(--border)' : 'var(--muted)', padding: '0 2px', fontSize: '12px' }}
                            >
                              ▼
                            </button>
                          </div>
                          <ActionEditor
                            action={action}
                            toolkit={toolkit}
                            hwModules={hwModules}
                            taskDefId={taskDefId}
                            versionStamp={versionStamp}
                            variableNames={variableNames}
                            allowTriggerContext
                            onChange={updated => updateAction(i, ai, updated)}
                          />
                          <button
                            className="button-danger"
                            style={{ fontSize: '11px', padding: '2px 6px', marginTop: '4px' }}
                            onClick={() => removeAction(i, ai)}
                          >
                            Remove
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                  <div style={{ display: 'flex', gap: '6px' }}>
                    {a.actions.length === 0 && (toolkit?.detector_refs?.length ?? 0) > 0 && (
                      <button
                        className="button-secondary"
                        style={{ fontSize: '12px', flex: 1 }}
                        onClick={() => pickDetector(i, toolkit!.detector_refs![0])}
                      >
                        + Read detector
                      </button>
                    )}
                    <button className="button-secondary" style={{ fontSize: '12px', flex: 1 }} onClick={() => addAction(i)}>
                      + Add action
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <button
        className="button-secondary"
        style={{ fontSize: '12px', width: '100%' }}
        onClick={add}
      >
        + Add trigger
      </button>
    </div>
  )
}
