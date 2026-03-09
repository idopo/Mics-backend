import { useMemo, useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useWebSocket } from '../../hooks/useWebSocket'
import type { PilotLive } from '../../types'

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

  return (
    <div
      className={cardClass}
      onClick={connected ? () => navigate(`/pilots/${name}/sessions-ui`) : undefined}
      style={connected ? { cursor: 'pointer' } : undefined}
    >
      <h2>{name}</h2>
      <div className={`status${!connected ? ' pilot-offline-badge' : isRunning ? ' connected' : ' disconnected'}`}>
        {!connected ? 'OFFLINE' : info.state}
      </div>

      {connected && run && (
        <>
          <div className="status-line" style={{ marginTop: '8px' }}>
            <strong>RUNNING</strong><br />
            Session: {run.session_id}<br />
            Subject: {run.subject_key ?? '—'}<br />
            Time: {elapsed}
          </div>
          <button
            className="button-secondary"
            onClick={(e) => {
              e.stopPropagation()
              fetch(`/api/session-runs/${run.id}/stop`, { method: 'POST' }).catch(() => {})
            }}
          >
            STOP
          </button>
        </>
      )}
    </div>
  )
}

export default function Index() {
  const { lastMessage, connected } = useWebSocket<Record<string, PilotLive>>('/ws/pilots')

  const pilots = useMemo(() => {
    if (!lastMessage) return []
    return Object.entries(lastMessage).map(([name, data]) => ({ name, data }))
  }, [lastMessage])

  return (
    <main>
      <span className="subtitle">
        Connected Pilots {connected ? '●' : '○'}
      </span>
      <div className="grid" style={{ marginTop: '1rem' }}>
        {pilots.length === 0 && (
          <p className="muted">No pilots connected.</p>
        )}
        {pilots.map(({ name, data }) => (
          <PilotCard key={name} name={name} info={data} />
        ))}
      </div>
    </main>
  )
}
