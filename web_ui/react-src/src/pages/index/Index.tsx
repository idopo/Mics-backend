import { useMemo, useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useWebSocket } from '../../hooks/useWebSocket'
import { apiFetch } from '../../api/client'
import type { PilotLive } from '../../types'

function GearIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  )
}

function useElapsed(startedAt: string | null | undefined): string {
  const [, setTick] = useState(0)
  useEffect(() => {
    if (!startedAt) return
    const id = setInterval(() => setTick(t => t + 1), 1000)
    return () => clearInterval(id)
  }, [startedAt])

  if (!startedAt) return '—'
  const started = Date.parse(startedAt)
  if (isNaN(started)) return '—'
  const sec = Math.max(0, Math.floor((Date.now() - started) / 1000))
  const min = Math.floor(sec / 60)
  return `${min}m ${sec % 60}s`
}

function PilotCard({ name, info }: { name: string; info: PilotLive }) {
  const navigate = useNavigate()
  const connected = info.connected === true
  const isRunning = info.state === 'RUNNING'
  const run = info.active_run ?? null
  const elapsed = useElapsed(run?.started_at)

  const cardClass = [
    'card pilot-card',
    !connected ? 'pilot-offline' : isRunning ? 'pilot-running' : 'pilot-idle',
  ].join(' ')

  const dotClass = !connected ? 'dot-offline' : isRunning ? 'dot-running' : 'dot-idle'

  return (
    <div
      className={cardClass}
      onClick={connected ? () => navigate(`/pilots/${name}/sessions-ui`) : undefined}
      style={connected ? { cursor: 'pointer' } : undefined}
    >
      <div className="pilot-card-header">
        <h2>{name}</h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Link
            to={`/pilots/${name}/hardware-config`}
            onClick={e => e.stopPropagation()}
            style={{ color: 'var(--text-muted)', lineHeight: 0 }}
            title="Hardware config"
          >
            <GearIcon />
          </Link>
          <span className={`pilot-status-dot ${dotClass}`} />
        </div>
      </div>
      <div className={`status${!connected ? ' pilot-offline-badge' : isRunning ? ' connected' : ' disconnected'}`}>
        {!connected ? 'OFFLINE' : info.state}
      </div>

      {connected && run && (
        <div className="pilot-run-info">
          <div className="pilot-run-grid">
            <span className="run-label">Session</span>
            <span className="run-value">{run.session_id}</span>
            <span className="run-label">Subject</span>
            <span className="run-value">{run.subject_key ?? '—'}</span>
            <span className="run-label">Elapsed</span>
            <span className="run-value run-elapsed">{elapsed}</span>
          </div>
          <button
            className="button-danger"
            style={{ marginTop: '12px', width: '100%' }}
            onClick={(e) => {
              e.stopPropagation()
              fetch(`/api/session-runs/${run.id}/stop`, { method: 'POST' }).catch(() => {})
            }}
          >
            ■ STOP
          </button>
        </div>
      )}
    </div>
  )
}

export default function Index() {
  const { lastMessage } = useWebSocket<Record<string, PilotLive>>('/ws/pilots')

  // Pre-fetch via REST so cards appear immediately (before WS delivers first message)
  const { data: restData } = useQuery({
    queryKey: ['pilots-live'],
    queryFn: () => apiFetch<Record<string, PilotLive>>('/api/pilots'),
    staleTime: 0,
  })

  const source = lastMessage ?? restData ?? null

  const pilots = useMemo(() => {
    if (!source) return []
    return Object.entries(source).map(([name, data]) => ({ name, data }))
  }, [source])

  return (
    <div className="pilots-page">
      <span className="subtitle">
        Connected Pilots
      </span>
      <div className="grid" style={{ marginTop: '1rem' }}>
        {pilots.length === 0 && (
          <p className="muted">No pilots connected.</p>
        )}
        {pilots.map(({ name, data }) => (
          <PilotCard key={name} name={name} info={data} />
        ))}
      </div>
    </div>
  )
}
