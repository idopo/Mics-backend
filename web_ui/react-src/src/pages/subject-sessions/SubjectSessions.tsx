import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { getSubjectSessions } from '../../api/subjects'
import { getBackendPilots } from '../../api/pilots'
import { startSessionOnPilot } from '../../api/sessions'
import Skeleton from '../../components/Skeleton'
import type { SessionSummary } from '../../types'

export default function SubjectSessions() {
  const { subject } = useParams<{ subject: string }>()
  const [selectedSession, setSelectedSession] = useState<SessionSummary | null>(null)
  const [selectedPilotId, setSelectedPilotId] = useState<number | null>(null)
  const [message, setMessage] = useState('')

  const { data: sessions, isLoading: loadingSessions } = useQuery({
    queryKey: ['subject-sessions', subject],
    queryFn: () => getSubjectSessions(subject!),
    enabled: !!subject,
  })

  const { data: pilots, isLoading: loadingPilots } = useQuery({
    queryKey: ['backend-pilots'],
    queryFn: getBackendPilots,
  })

  const mutation = useMutation({
    mutationFn: () => startSessionOnPilot(selectedSession!.session_id, selectedPilotId!),
    onSuccess: (data) => setMessage(`Started run #${data.run_id}`),
    onError: (e: Error) => setMessage(`Error: ${e.message}`),
  })

  return (
    <div className="page">
      <h1>Sessions — {subject}</h1>

      {loadingSessions ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {[...Array(3)].map((_, i) => <Skeleton key={i} style={{ height: '2.5rem' }} />)}
        </div>
      ) : (
        <ul className="session-list">
          {sessions?.map((s) => (
            <li
              key={s.session_id}
              className={`session-item ${selectedSession?.session_id === s.session_id ? 'selected' : ''}`}
              onClick={() => setSelectedSession(s)}
            >
              <span>#{s.session_id}</span>
              <span className="muted">{new Date(s.started_at).toLocaleDateString()}</span>
            </li>
          ))}
        </ul>
      )}

      {selectedSession && (
        <div className="start-panel">
          <h2>Start on pilot</h2>
          {loadingPilots ? (
            <Skeleton style={{ height: '2.5rem' }} />
          ) : (
            <select
              className="select"
              value={selectedPilotId ?? ''}
              onChange={(e) => setSelectedPilotId(Number(e.target.value))}
            >
              <option value="">Select pilot…</option>
              {pilots?.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          )}
          <button
            className="btn btn-primary"
            disabled={!selectedPilotId || mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            {mutation.isPending ? 'Starting…' : 'Start'}
          </button>
          {message && <p className="message">{message}</p>}
        </div>
      )}
    </div>
  )
}
