import { useRef, useEffect, useState, memo, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { useQuery } from '@tanstack/react-query'
import { getSessionDetail } from '../../api/sessions'
import { getProtocol } from '../../api/protocols'
import { getLeafTasks } from '../../api/tasks'
import { apiFetch } from '../../api/client'
import type { RunWithProgress, Overrides, StartOptions } from '../../types'
import OverridesModal from './OverridesModal'
import StartModeModal from './StartModeModal'

interface Props {
  sessionId: number
  latestRun: RunWithProgress | null | undefined
  pilotId: number
  activeRunId: number | null   // WebSocket authoritative run ID — always use for STOP
  activeSessionId: number | null
  filterSubjects: string[]
  onStart: (sessionId: number, pilotId: number, mode: string, overrides: Overrides | null) => void
  onStop: (runId: number) => void
  limit: <T>(fn: () => Promise<T>) => Promise<T>
}

const MAX_LABEL = 15
function norm(s: string) { return s.trim().toLowerCase() }
function sanitizeStepTitle(stepName: string, idx: number, taskType: string) {
  const s = stepName.trim().replace(/^step\s*\d+\s*[:\-–]?\s*/i, '').replace(/^\d+\.\s*/, '').trim()
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

function SessionCard({ sessionId, latestRun, pilotId, activeRunId, activeSessionId, filterSubjects, onStart, onStop, limit }: Props) {
  const cardRef = useRef<HTMLLIElement>(null)
  const [hydrated, setHydrated] = useState(false)
  const [showOverrides, setShowOverrides] = useState(false)
  const [overrides, setOverrides] = useState<Overrides>({})
  const [isDirty, setIsDirty] = useState(false)
  const [startModal, setStartModal] = useState<StartOptions | null>(null)
  const [starting, setStarting] = useState(false)
  const [localMsg, setLocalMsg] = useState('')
  const [localMsgError, setLocalMsgError] = useState(false)

  useEffect(() => {
    const el = cardRef.current
    if (!el) return
    const obs = new IntersectionObserver(
      (entries) => { if (entries[0]?.isIntersecting) { setHydrated(true); obs.unobserve(el) } },
      { rootMargin: '600px' }
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  const { data: detail } = useQuery({
    queryKey: ['session-detail', sessionId],
    queryFn: () => limit(() => getSessionDetail(sessionId)),
    enabled: hydrated,
    staleTime: Infinity,
  })

  const protocolId = detail?.runs[0]?.protocol_id
  const { data: protocol } = useQuery({
    queryKey: ['protocol', protocolId],
    queryFn: () => limit(() => getProtocol(protocolId!)),
    enabled: !!protocolId,
    staleTime: Infinity,
  })

  const { data: tasks } = useQuery({
    queryKey: ['tasks'],
    queryFn: getLeafTasks,
    enabled: hydrated,
    staleTime: Infinity,
  })
  const tasksByName = new Map((tasks ?? []).map(t => [norm(t.task_name), t]))

  const run = latestRun?.run
  const prog = latestRun?.progress
  const status = run?.status ?? 'never run'
  const isRunningHere = activeSessionId === sessionId
  const isPilotBusy = activeSessionId !== null && activeSessionId !== sessionId
  const started = run?.started_at ? new Date(run.started_at).toLocaleDateString() : ''
  const ended = run?.ended_at ? new Date(run.ended_at).toLocaleDateString() : ''

  const isFiltered = filterSubjects.length > 0 && detail !== undefined && !detail.runs.some(
    r => filterSubjects.some(f => norm(r.subject_name) === norm(f))
  )

  // Auto-clear overrides when run completes (case-insensitive — API returns uppercase)
  useEffect(() => {
    if (run?.status && norm(run.status) === 'completed') {
      setIsDirty(false)
      setOverrides({})
    }
  }, [run?.status])

  const handleSaveOverrides = useCallback((o: Overrides) => {
    setOverrides(o)
    setIsDirty(true)
  }, [])

  const handleStartClick = async () => {
    if (starting || !pilotId) return
    setStarting(true)
    setLocalMsg('Checking session status…')
    setLocalMsgError(false)

    let opts: StartOptions | null = null
    try {
      opts = await apiFetch<StartOptions>(`/api/sessions/${sessionId}/pilots/${pilotId}/start-options`)
    } catch (err) {
      setStarting(false)
      setLocalMsg(`Error: ${err instanceof Error ? err.message : String(err)}`)
      setLocalMsgError(true)
      return
    }

    setLocalMsg('')

    // A run is currently active on this pilot for this session — do not auto-start
    if (opts.active_run) {
      setStarting(false)
      setLocalMsg('A run is currently active. Stop it first.')
      setLocalMsgError(true)
      return
    }

    // Recoverable (STOPPED/ERROR) run found — but only offer resume/restart if it's
    // still the most recent run. If a newer completed run exists, the stopped run is
    // superseded and we should just start fresh.
    if (opts.recoverable_run) {
      const newerCompletedExists =
        (latestRun?.run?.id ?? 0) > opts.recoverable_run.id &&
        norm(latestRun?.run?.status ?? '') === 'completed'

      if (newerCompletedExists) {
        setStarting(false)
        onStart(sessionId, pilotId, 'new', isDirty ? overrides : null)
        return
      }

      setStartModal(opts)
      setStarting(false)
      return
    }

    // No prior run — fresh start
    setStarting(false)
    onStart(sessionId, pilotId, 'new', isDirty ? overrides : null)
  }

  const handleModalChoice = (choice: 'resume' | 'restart' | 'new' | null) => {
    setStartModal(null)
    if (!choice) return
    if (choice === 'resume' || choice === 'restart') {
      onStart(sessionId, pilotId, choice, null)
    } else {
      onStart(sessionId, pilotId, 'new', isDirty ? overrides : null)
    }
  }

  // The STOP run ID: WebSocket activeRunId is authoritative (stale polling data may have old ID)
  const stopRunId = activeRunId ?? run?.id ?? 0

  return (
    <>
      <li
        ref={cardRef}
        className={`session-card${!hydrated || !detail ? ' is-loading' : ''}`}
        data-session-id={sessionId}
        style={isFiltered ? { display: 'none' } : undefined}
      >
        {!hydrated || !detail ? (
          <div className="session-skel">
            <div className="session-skel-line w70" />
            <div className="session-skel-line w40" />
            <div className="session-skel-line w55" />
          </div>
        ) : (
          <div className="session-card-grid">
            <div className="session-left">
              <div className="session-header">
                <div className="session-title">
                  <a
                    href="#"
                    style={{ color: 'var(--lavender)', textDecoration: 'none' }}
                    onClick={(e) => { e.preventDefault(); setShowOverrides(true) }}
                    onMouseEnter={(e) => (e.currentTarget.style.textDecoration = 'underline')}
                    onMouseLeave={(e) => (e.currentTarget.style.textDecoration = 'none')}
                  >
                    {protocol?.name ?? `Session #${sessionId}`}
                  </a>
                </div>
              </div>

              <div className="subject-tags">
                {detail.runs.map((r) => (
                  <span key={r.run_id} className="subject-tag">{r.subject_name}</span>
                ))}
              </div>

              <div className="session-meta">
                <div className="meta-row meta-row-top">
                  <span className={`badge status-${norm(status)}`}>{status}</span>
                  {prog?.current_step != null && (
                    <span className="meta-pill">step {prog.current_step}, trial {prog.current_trial ?? '?'}</span>
                  )}
                  {run?.mode && <span className="meta-pill">mode: {run.mode}</span>}
                </div>
                {(started || ended) && (
                  <div className="meta-row meta-row-dates">
                    {started && <span className="meta-date">Started {started}</span>}
                    {ended && <span className="meta-date">Ended {ended}</span>}
                  </div>
                )}
              </div>

              <div className="session-actions">
                {isRunningHere ? (
                  <button
                    className="button-danger"
                    disabled={!stopRunId}
                    onClick={() => { if (stopRunId) onStop(stopRunId) }}
                  >
                    STOP
                  </button>
                ) : (
                  <button
                    className="button-primary"
                    disabled={isPilotBusy || starting || !pilotId}
                    title={isPilotBusy ? 'Another session is running on this pilot' : !pilotId ? 'Pilot not ready' : ''}
                    onClick={handleStartClick}
                  >
                    {starting ? 'Starting…' : 'START'}
                  </button>
                )}
                {localMsg && (
                  <div className="status-line" style={{ color: localMsgError ? 'crimson' : undefined, marginTop: '4px', fontSize: '12px' }}>
                    {localMsg}
                  </div>
                )}
              </div>
            </div>

            <div className="session-divider" aria-hidden="true" />

            <div className="session-right">
              <div className="right-title">Params</div>
              <div className="right-body">
                {protocol?.steps.map((step, i) => {
                  const protocolParams = step.params ?? {}
                  const task = tasksByName.get(norm(step.task_type))
                  const spec: Record<string, unknown> =
                    (task as { default_params?: Record<string, unknown> })?.default_params ?? {}

                  const keyMap = new Map<string, string>()
                  Object.keys(spec).forEach(k => { if (!keyMap.has(norm(k))) keyMap.set(norm(k), k) })
                  Object.keys(protocolParams).forEach(k => keyMap.set(norm(k), k))

                  const keys = Array.from(keyMap.values()).filter(
                    k => !['graduation', 'step_name', 'task_type'].includes(norm(k))
                  ).sort()

                  // Graduation — case-insensitive key lookup
                  const gradKey = Object.keys(protocolParams).find(k => norm(k) === 'graduation')
                  const gradVal = gradKey !== undefined ? protocolParams[gradKey] : undefined
                  const gradN = getGraduationN(gradVal)

                  const displayName = sanitizeStepTitle(step.step_name, i, step.task_type)
                  return (
                    <div key={i} className="step-box">
                      <div className="step-head">
                        <div className="step-name">{displayName}</div>
                      </div>
                      <div className="step-section">
                        <div className="params-grid params-grid-2col" style={{ marginTop: '4px' }}>
                          {keys.length === 0 && !gradN ? (
                            <div className="muted small">No params</div>
                          ) : keys.map(key => {
                            const protocolVal = protocolParams[key]
                            const specEntry = (spec[key] as { value?: unknown; default?: unknown; tag?: string; type?: string } | undefined)
                            const defaultVal = specEntry?.value ?? specEntry?.default
                            const val = protocolVal !== undefined ? protocolVal : defaultVal
                            const tag = specEntry?.tag ?? key
                            const typeHint = specEntry?.type ? ` – ${specEntry.type}` : ''
                            const isMissing = val === undefined || val === null || val === ''
                            return (
                              <div key={key} className="param-field">
                                <label>
                                  <span
                                    className={`param-name param-name-${protocolVal !== undefined ? 'protocol' : defaultVal !== undefined ? 'default' : 'missing'}`}
                                    title={key}
                                  >
                                    {key.length > MAX_LABEL ? key.slice(0, MAX_LABEL - 1) + '…' : key}
                                  </span>
                                </label>
                                <input
                                  type="text"
                                  disabled
                                  placeholder={`${tag}${typeHint}`}
                                  value={isMissing ? '' : String(val)}
                                  className={isMissing ? 'is-missing' : ''}
                                />
                              </div>
                            )
                          })}
                        </div>
                        {gradN && (
                          <div className="graduation-pill">⟳ {gradN} trials</div>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        )}
      </li>

      {/* Portals: render modals at document.body level to escape <ul> DOM constraints */}
      {showOverrides && protocolId && createPortal(
        <OverridesModal
          sessionId={sessionId}
          protocolId={protocolId}
          pilotId={pilotId}
          overrides={overrides}
          onSave={handleSaveOverrides}
          onClose={() => setShowOverrides(false)}
        />,
        document.body
      )}

      {startModal && startModal.recoverable_run && createPortal(
        <StartModeModal
          runId={startModal.recoverable_run.id}
          status={startModal.recoverable_run.status}
          step={startModal.progress?.current_step}
          trial={startModal.progress?.current_trial}
          canResume={startModal.can_resume}
          onChoice={handleModalChoice}
        />,
        document.body
      )}
    </>
  )
}

export default memo(SessionCard)
