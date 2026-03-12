import { useState, useMemo } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getSubjectSessions } from '../../api/subjects'
import { getBackendPilots, stopRun } from '../../api/pilots'
import { getLatestRunsBulk, startSessionOnPilot } from '../../api/sessions'
import { useConcurrentFetch } from '../../hooks/useConcurrentFetch'
import { useWebSocket } from '../../hooks/useWebSocket'
import SessionCard from '../pilot-sessions/SessionCard'
import type { PilotLive, Overrides } from '../../types'

export default function SubjectSessions() {
  const { subject } = useParams<{ subject: string }>()
  const qc = useQueryClient()
  const { limit } = useConcurrentFetch(4)
  const [selectedPilotName, setSelectedPilotName] = useState('')
  const [statusMsg, setStatusMsg] = useState('')

  const { lastMessage } = useWebSocket<Record<string, PilotLive>>('/ws/pilots')
  const pilotLive = selectedPilotName ? (lastMessage?.[selectedPilotName] ?? null) : null

  const { data: pilots } = useQuery({
    queryKey: ['backend-pilots'],
    queryFn: getBackendPilots,
  })

  const pilotObj = (pilots ?? []).find(p => p.name === selectedPilotName) ?? null
  const pilotId = pilotObj?.id ?? null

  const { data: subjectRuns, isLoading, isError } = useQuery({
    queryKey: ['subject-sessions', subject],
    queryFn: () => getSubjectSessions(subject!),
    enabled: !!subject,
    retry: 1,
  })

  // Deduplicate session IDs, most recent first
  const sessionIds = useMemo(() => {
    const seen = new Set<number>()
    const ids: number[] = []
    for (const r of [...(subjectRuns ?? [])].reverse()) {
      if (!seen.has(r.session_id)) {
        seen.add(r.session_id)
        ids.push(r.session_id)
      }
    }
    return ids
  }, [subjectRuns])

  const { data: latestRuns } = useQuery({
    queryKey: ['latest-runs', pilotId, sessionIds.join(',')],
    queryFn: () => getLatestRunsBulk(pilotId!, sessionIds),
    enabled: pilotId != null && sessionIds.length > 0,
    refetchInterval: 5000,
  })

  const activeRunId = pilotLive?.active_run?.id ?? null

  const activeSessionId = useMemo(() => {
    if (pilotLive?.active_run?.session_id) return pilotLive.active_run.session_id
    if (!latestRuns) return null
    for (const [sid, entry] of Object.entries(latestRuns)) {
      if (entry?.run?.status?.toLowerCase() === 'running') return Number(sid)
    }
    return null
  }, [pilotLive, latestRuns])

  const refetchLatestRuns = () => qc.invalidateQueries({ queryKey: ['latest-runs'] })

  const startMutation = useMutation({
    mutationFn: ({ sessionId, pId, mode, overrides }: {
      sessionId: number; pId: number; mode: string; overrides: Overrides | null
    }) => startSessionOnPilot(sessionId, pId, mode, overrides ?? undefined),
    onSuccess: (data) => { setStatusMsg(`Started run #${data.run_id}`); refetchLatestRuns() },
    onError: (e: Error) => setStatusMsg(`Error: ${e.message}`),
  })

  const stopMutation = useMutation({
    mutationFn: (runId: number) => stopRun(runId),
    onSuccess: () => { setStatusMsg('Run stopped.'); refetchLatestRuns() },
    onError: (e: Error) => setStatusMsg(`Stop error: ${e.message}`),
  })

  const handleStart = (sessionId: number, pId: number, mode: string, overrides: Overrides | null) => {
    startMutation.mutate({ sessionId, pId, mode, overrides })
  }
  const handleStop = (runId: number) => stopMutation.mutate(runId)

  const isOffline = pilotLive !== null && !pilotLive?.connected

  return (
    <div className="container">
      <section className="card">
        {/* Header */}
        <div style={{ marginBottom: '1rem' }}>
          <div style={{ fontSize: '12px', color: 'var(--subtext0)', marginBottom: '4px' }}>
            <Link to="/subjects-ui" style={{ color: 'var(--lavender)', textDecoration: 'none' }}>Subjects</Link>
            {' / '}
            <span>{subject}</span>
          </div>
          <h2 style={{ margin: 0 }}>Sessions for {subject}</h2>
        </div>

        {/* Pilot selector */}
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', marginBottom: '1.25rem', padding: '8px 12px', background: 'var(--surface1)', borderRadius: '8px', flexWrap: 'wrap' }}>
          <label style={{ color: 'var(--subtext0)', fontSize: '13px', whiteSpace: 'nowrap', fontWeight: 500, lineHeight: '28px', margin: 0 }}>
            Run on pilot:
          </label>
          <select
            value={selectedPilotName}
            onChange={e => setSelectedPilotName(e.target.value)}
            style={{ flex: '0 0 auto', minWidth: '180px', height: '28px', lineHeight: '28px', padding: '0 8px', margin: 0, letterSpacing: '0.02em' }}
          >
            <option value="">select pilot</option>
            {(pilots ?? []).map(p => <option key={p.id} value={p.name}>{p.name}</option>)}
          </select>
          <span
            className={`badge status-${pilotLive ? (pilotLive.connected ? (pilotLive.state?.toLowerCase() ?? 'idle') : 'offline') : 'idle'}`}
            style={{
              alignSelf: 'center',
              opacity: pilotLive ? 1 : 0,
              transition: 'opacity 0.2s ease',
              pointerEvents: pilotLive ? 'auto' : 'none',
            }}
          >
            {pilotLive ? (pilotLive.connected ? (pilotLive.state ?? 'idle') : 'offline') : 'idle'}
          </span>
        </div>

        {statusMsg && <div className="status-line" style={{ marginBottom: '0.75rem' }}>{statusMsg}</div>}
        {isOffline && <p className="muted">Pilot is offline.</p>}

        {isError ? (
          <p className="muted">Could not load sessions for this subject.</p>
        ) : isLoading ? (
          <ul className="sessions-scroll">
            {[...Array(4)].map((_, i) => (
              <li key={i} className="session-card is-loading">
                <div className="session-skel">
                  <div className="session-skel-line w70" />
                  <div className="session-skel-line w40" />
                  <div className="session-skel-line w55" />
                </div>
              </li>
            ))}
          </ul>
        ) : sessionIds.length === 0 ? (
          <div style={{ padding: '2rem 0', textAlign: 'center' }}>
            <p className="muted" style={{ marginBottom: '0.5rem' }}>No sessions for <strong>{subject}</strong> yet.</p>
            <p style={{ fontSize: '12px', color: 'var(--subtext0)' }}>
              Go to <Link to="/protocols-ui" style={{ color: 'var(--lavender)' }}>Protocols</Link> to assign a protocol to this subject.
            </p>
          </div>
        ) : (
          <ul id="sessions" className="sessions-scroll" style={{ maxHeight: 'calc(100vh - 300px)', overflowY: 'auto' }}>
            {sessionIds.map(sessionId => (
              <SessionCard
                key={sessionId}
                sessionId={sessionId}
                latestRun={latestRuns?.[String(sessionId)] ?? null}
                pilotId={pilotId ?? 0}
                activeRunId={activeRunId}
                activeSessionId={activeSessionId}
                filterSubjects={[]}
                onStart={handleStart}
                onStop={handleStop}
                limit={limit}
              />
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
