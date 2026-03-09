import { useState, useEffect, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getProtocol } from '../../api/protocols'
import { getLeafTasks } from '../../api/tasks'
import { apiFetch } from '../../api/client'
import type { Overrides, SessionRun } from '../../types'

interface Props {
  sessionId: number
  protocolId: number
  pilotId: number
  overrides: Overrides
  onSave: (overrides: Overrides) => void
  onClose: () => void
}

function norm(s: string) { return s.trim().toLowerCase() }

function sanitizeStepTitle(stepName: string, idx: number, taskType: string) {
  const s = stepName.trim().replace(/^step\s*\d+\s*[:\-–]?\s*/i, '').trim()
  const label = s || taskType.trim() || 'Unnamed step'
  const clean = taskType && label.toLowerCase() === taskType.toLowerCase() ? taskType : label
  return `Step ${idx + 1}: ${clean}`
}

function getGraduationN(val: unknown): string {
  if (val == null) return ''
  if (typeof val === 'number' && isFinite(val)) return String(val)
  if (typeof val === 'string' && /^\d+$/.test(val.trim())) return val.trim()
  if (typeof val === 'object' && val !== null) {
    const obj = val as Record<string, unknown>
    const v = (obj.value ?? obj) as Record<string, unknown>
    const n = v?.current_trial ?? v?.n_trials ?? v?.n
    if (n != null) return String(n)
  }
  return ''
}

function parseByType(raw: string, type: string): { value: unknown } | { invalid: true } {
  const t = type.trim().toLowerCase()
  const s = raw.trim()
  if (t.includes('int')) {
    const n = Number(s)
    if (!Number.isFinite(n) || !Number.isInteger(n)) return { invalid: true }
    return { value: n }
  }
  if (t.includes('float') || t.includes('number') || t.includes('double')) {
    const n = Number(s)
    if (!Number.isFinite(n)) return { invalid: true }
    return { value: n }
  }
  if (t.includes('bool')) {
    if (['true', '1', 'yes', 'y'].includes(s.toLowerCase())) return { value: true }
    if (['false', '0', 'no', 'n'].includes(s.toLowerCase())) return { value: false }
    return { invalid: true }
  }
  if (t.includes('json') || t.includes('dict') || t.includes('list') || t.includes('object')) {
    try { return { value: JSON.parse(s) } } catch { return { invalid: true } }
  }
  return { value: s }
}

export default function OverridesModal({ sessionId, protocolId, pilotId, overrides, onSave, onClose }: Props) {
  const [tab, setTab] = useState<'overrides' | 'history'>('overrides')

  // draft: what will be sent on Apply — stores parsed values (or raw strings)
  const [draft, setDraft] = useState<Overrides>(() => JSON.parse(JSON.stringify(overrides ?? {})))
  // rawValues[stepIdx][key] = raw string currently typed in input
  const [rawValues, setRawValues] = useState<Record<string, Record<string, string>>>({})
  // invalidKeys[stepIdx][key] = true if invalid
  const [invalidKeys, setInvalidKeys] = useState<Record<string, Record<string, boolean>>>({})
  // which steps are expanded: first open by default, rest collapsed
  const [openSteps, setOpenSteps] = useState<Set<number>>(new Set([0]))

  const [runs, setRuns] = useState<SessionRun[] | null>(null)
  const [historyError, setHistoryError] = useState('')

  const { data: protocol } = useQuery({
    queryKey: ['protocol', protocolId],
    queryFn: () => getProtocol(protocolId),
    staleTime: Infinity,
  })

  const { data: tasks } = useQuery({
    queryKey: ['tasks'],
    queryFn: getLeafTasks,
    staleTime: Infinity,
  })

  const tasksByName = useMemo(
    () => new Map((tasks ?? []).map(t => [norm(t.task_name), t])),
    [tasks]
  )

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey, true)
    return () => document.removeEventListener('keydown', onKey, true)
  }, [onClose])

  const loadHistory = async () => {
    try {
      const data = await apiFetch<SessionRun[]>(`/api/sessions/${sessionId}/pilots/${pilotId}/runs`)
      setRuns(data)
    } catch {
      setHistoryError('Failed to load run history')
    }
  }

  const switchTab = (t: 'overrides' | 'history') => {
    setTab(t)
    if (t === 'history' && runs === null && !historyError) loadHistory()
  }

  const toggleStep = (idx: number) => {
    setOpenSteps(prev => {
      const next = new Set(prev)
      next.has(idx) ? next.delete(idx) : next.add(idx)
      return next
    })
  }

  const handleParamChange = (stepIdx: number, key: string, raw: string, specType?: string) => {
    const sidx = String(stepIdx)

    // Update raw display value
    setRawValues(prev => ({
      ...prev,
      [sidx]: { ...(prev[sidx] ?? {}), [key]: raw },
    }))

    const trimmed = raw.trim()

    if (trimmed === '') {
      // Clear from draft
      setDraft(prev => {
        const steps = { ...(prev.steps ?? {}) }
        if (steps[sidx]) {
          const { [key]: _removed, ...rest } = steps[sidx]
          steps[sidx] = rest
        }
        return { ...prev, steps }
      })
      setInvalidKeys(prev => ({ ...prev, [sidx]: { ...(prev[sidx] ?? {}), [key]: false } }))
      return
    }

    // Graduation special handling
    if (norm(key) === 'graduation') {
      if (/^\d+$/.test(trimmed)) {
        setDraft(prev => ({
          ...prev,
          steps: {
            ...(prev.steps ?? {}),
            [sidx]: {
              ...(prev.steps?.[sidx] ?? {}),
              [key]: { type: 'NTrials', value: { current_trial: Number(trimmed) } },
            },
          },
        }))
        setInvalidKeys(prev => ({ ...prev, [sidx]: { ...(prev[sidx] ?? {}), [key]: false } }))
      } else {
        setInvalidKeys(prev => ({ ...prev, [sidx]: { ...(prev[sidx] ?? {}), [key]: true } }))
      }
      return
    }

    // Type validation
    if (specType) {
      const parsed = parseByType(trimmed, specType)
      if ('invalid' in parsed) {
        setInvalidKeys(prev => ({ ...prev, [sidx]: { ...(prev[sidx] ?? {}), [key]: true } }))
        return
      }
      setInvalidKeys(prev => ({ ...prev, [sidx]: { ...(prev[sidx] ?? {}), [key]: false } }))
      setDraft(prev => ({
        ...prev,
        steps: {
          ...(prev.steps ?? {}),
          [sidx]: { ...(prev.steps?.[sidx] ?? {}), [key]: parsed.value },
        },
      }))
    } else {
      setInvalidKeys(prev => ({ ...prev, [sidx]: { ...(prev[sidx] ?? {}), [key]: false } }))
      setDraft(prev => ({
        ...prev,
        steps: {
          ...(prev.steps ?? {}),
          [sidx]: { ...(prev.steps?.[sidx] ?? {}), [key]: raw },
        },
      }))
    }
  }

  const steps = protocol?.steps ?? []

  // Build display value for a field: raw override string > protocol value > spec default
  const getDisplayValue = (stepIdx: number, key: string, protocolVal: unknown, specDefault: unknown): string => {
    const sidx = String(stepIdx)
    const raw = rawValues[sidx]?.[key]
    if (raw !== undefined) return raw
    // pre-fill from existing draft
    const draftVal = draft.steps?.[sidx]?.[key]
    if (draftVal !== undefined) {
      if (norm(key) === 'graduation') return getGraduationN(draftVal)
      return String(draftVal)
    }
    // fall back to protocol value, then spec default
    if (norm(key) === 'graduation') return getGraduationN(protocolVal ?? specDefault)
    if (protocolVal !== undefined && protocolVal !== null) return String(protocolVal)
    if (specDefault !== undefined && specDefault !== null) return String(specDefault)
    return ''
  }

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        className="modal overrides-modal"
        style={{ maxWidth: '1080px', width: 'min(1080px, calc(100vw - 24px))', display: 'flex', flexDirection: 'column', maxHeight: '90vh' }}
      >
        <div className="modal-header">
          <div className="modal-title">Session {sessionId}</div>
          <button className="modal-close" type="button" onClick={onClose}>✕</button>
        </div>

        <div className="modal-tabs">
          <button className={`modal-tab${tab === 'overrides' ? ' active' : ''}`} onClick={() => switchTab('overrides')}>Overrides</button>
          <button className={`modal-tab${tab === 'history' ? ' active' : ''}`} onClick={() => switchTab('history')}>Run History</button>
        </div>

        {/* Scrollable body */}
        <div className="modal-body" style={{ overflowY: 'auto', flex: '1 1 0', minHeight: 0 }}>
          {tab === 'overrides' && (
            <div>
              {steps.length === 0 && <div className="muted">Loading…</div>}
              {steps.map((step, idx) => {
                const task = tasksByName.get(norm(step.task_type))
                const spec: Record<string, { tag?: string; type?: string; value?: unknown; default?: unknown }> =
                  (task as { default_params?: Record<string, { tag?: string; type?: string }> })?.default_params ?? {}
                const protocolParams = step.params ?? {}

                // Union: spec keys + protocol param keys, include graduation, exclude step_name/task_type
                const keyMap = new Map<string, string>()
                Object.keys(spec).forEach(k => { if (!keyMap.has(norm(k))) keyMap.set(norm(k), k) })
                Object.keys(protocolParams).forEach(k => keyMap.set(norm(k), k))
                const keys = Array.from(keyMap.values())
                  .filter(k => !['step_name', 'task_type'].includes(norm(k)))
                  .sort()

                const isOpen = openSteps.has(idx)
                const displayName = sanitizeStepTitle(step.step_name, idx, step.task_type)
                const sidx = String(idx)

                return (
                  <div key={idx} className="step-box">
                    <div
                      className="step-head"
                      role="button"
                      aria-expanded={isOpen}
                      style={{ cursor: 'pointer' }}
                      onClick={(e) => {
                        if ((e.target as HTMLElement).tagName === 'INPUT' || (e.target as HTMLElement).tagName === 'BUTTON') return
                        toggleStep(idx)
                      }}
                    >
                      <div style={{ minWidth: 0 }}>
                        <div className="step-name">{displayName}</div>
                      </div>
                      <button
                        className="button-secondary step-toggle-btn"
                        type="button"
                        aria-label="Toggle step"
                        onClick={(e) => { e.stopPropagation(); toggleStep(idx) }}
                      >
                        {isOpen ? '▾' : '▸'}
                      </button>
                    </div>

                    {isOpen && (
                      <div className="step-section">
                        <div className="params-grid params-grid-2col">
                          {keys.length === 0 ? (
                            <div className="muted small">No params</div>
                          ) : keys.map(key => {
                            const s = spec[key] ?? {}
                            const protocolVal = protocolParams[key]
                            const specDefault = (s as { default?: unknown; value?: unknown })?.default ?? (s as { value?: unknown })?.value
                            const displayVal = getDisplayValue(idx, key, protocolVal, specDefault)
                            const isGrad = norm(key) === 'graduation'
                            const typeHint = !isGrad && s.type ? ` – ${s.type}` : ''
                            const tag = !isGrad ? (s.tag ?? key) : 'NTrials n'
                            const isInvalid = invalidKeys[sidx]?.[key]

                            return (
                              <div key={key} className="param-field">
                                <label>
                                  <span className="param-name" title={`${tag}${typeHint}`}>
                                    {key.length > 15 ? key.slice(0, 14) + '…' : key}
                                  </span>
                                </label>
                                <input
                                  type="text"
                                  placeholder={`${tag}${typeHint}`}
                                  value={displayVal}
                                  className={isInvalid ? 'is-invalid' : ''}
                                  onChange={(e) => handleParamChange(idx, key, e.target.value, isGrad ? undefined : s.type)}
                                />
                              </div>
                            )
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}

          {tab === 'history' && (
            <div>
              {historyError ? (
                <div className="muted">{historyError}</div>
              ) : runs === null ? (
                <div className="muted">Loading…</div>
              ) : runs.length === 0 ? (
                <div className="muted">No runs yet</div>
              ) : (
                <table className="runs-table">
                  <thead>
                    <tr><th>ID</th><th>Status</th><th>Mode</th><th>Started</th><th>Ended</th></tr>
                  </thead>
                  <tbody>
                    {runs.map(r => (
                      <tr key={r.id}>
                        <td>{r.id}</td>
                        <td><span className={`badge status-${r.status}`}>{r.status}</span></td>
                        <td>{r.mode ?? ''}</td>
                        <td>{r.started_at ? new Date(r.started_at).toLocaleDateString() : ''}</td>
                        <td>{r.ended_at ? new Date(r.ended_at).toLocaleDateString() : ''}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </div>

        {tab === 'overrides' && (
          <div className="modal-actions ov-actions">
            <button className="button-primary" type="button" onClick={() => { onSave(draft); onClose() }}>
              Apply overrides
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
