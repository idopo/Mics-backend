import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getProtocols, assignProtocol } from '../../api/protocols'
import { getSubjects } from '../../api/subjects'

export default function Protocols() {
  const qc = useQueryClient()
  const [selectedProtocol, setSelectedProtocol] = useState<number | null>(null)
  const [selectedSubjects, setSelectedSubjects] = useState<Set<string>>(new Set())
  const [message, setMessage] = useState('')

  const { data: protocols, isLoading: loadingProtos } = useQuery({
    queryKey: ['protocols'],
    queryFn: getProtocols,
  })

  const { data: subjects, isLoading: loadingSubjects } = useQuery({
    queryKey: ['subjects'],
    queryFn: getSubjects,
  })

  const mutation = useMutation({
    mutationFn: () => assignProtocol(selectedProtocol!, Array.from(selectedSubjects)),
    onSuccess: (data) => {
      const sid = data?.session?.session_id
      setMessage(`Session ${sid} created. Go to a pilot to start it.`)
      setSelectedSubjects(new Set())
      // Invalidate so PilotSessions picks up the new session card
      qc.invalidateQueries({ queryKey: ['sessions'] })
      qc.invalidateQueries({ queryKey: ['subjects'] })
    },
    onError: (e: Error) => setMessage(`Error: ${e.message}`),
  })

  const toggleSubject = (name: string) => {
    setSelectedSubjects(prev => {
      const next = new Set(prev)
      next.has(name) ? next.delete(name) : next.add(name)
      return next
    })
  }

  return (
    <div className="container split">
      {/* LEFT: Protocol list */}
      <section className="card">
        <h2>Protocols</h2>
        {loadingProtos ? (
          <ul className="scroll-list skeleton-list">
            {[...Array(6)].map((_, i) => <li key={i} className="skeleton-row" />)}
          </ul>
        ) : (
          <ul className="scroll-list">
            {protocols?.map((p, idx) => (
              <li
                key={p.id}
                className={`fade-in-item${selectedProtocol === p.id ? ' selected' : ''}`}
                style={{ animationDelay: `${Math.min(idx * 18, 180)}ms`, cursor: 'pointer' }}
                onClick={() => setSelectedProtocol(p.id)}
              >
                {p.name}
              </li>
            ))}
          </ul>
        )}
        <hr />
        <Link to="/protocols-create" className="button-link button-secondary">
          + Create New Protocol
        </Link>
      </section>

      {/* RIGHT: Assign protocol */}
      <section className="card">
        <h2>Assign Protocol</h2>
        <p className="muted">Assigning will immediately create a new session.</p>

        {loadingSubjects ? (
          <ul className="scroll-list skeleton-list">
            {[...Array(4)].map((_, i) => <li key={i} className="skeleton-row" />)}
          </ul>
        ) : (
          <ul id="subjects-list" className="scroll-list">
            {subjects?.map((s) => (
              <li
                key={s.id}
                className={`subject-item${selectedSubjects.has(s.name) ? ' selected' : ''}`}
                onClick={() => toggleSubject(s.name)}
              >
                {s.name}
                {s.protocol_name && <span className="muted" style={{ marginLeft: '8px' }}>{s.protocol_name}</span>}
              </li>
            ))}
          </ul>
        )}

        <button
          id="assign-btn"
          type="button"
          className="button-primary"
          disabled={!selectedProtocol || selectedSubjects.size === 0 || mutation.isPending}
          onClick={() => mutation.mutate()}
        >
          {mutation.isPending ? 'Assigning…' : 'Assign Selected'}
        </button>

        {message && <div className="status-line">{message}</div>}
      </section>
    </div>
  )
}
