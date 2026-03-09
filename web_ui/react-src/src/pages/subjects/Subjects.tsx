import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getSubjects, createSubject } from '../../api/subjects'

export default function Subjects() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [error, setError] = useState('')

  const { data: subjects, isLoading } = useQuery({ queryKey: ['subjects'], queryFn: getSubjects })

  const mutation = useMutation({
    mutationFn: (n: string) => createSubject(n),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['subjects'] }); setName(''); setError('') },
    onError: (e: Error) => setError(e.message),
  })

  return (
    <div className="container">
      <section className="card">
        <h2>Create Subject</h2>
        <form id="create-form" onSubmit={(e) => { e.preventDefault(); const t = name.trim(); if (t) mutation.mutate(t) }}>
          <input
            id="subject-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Subject name"
            disabled={mutation.isPending}
            required
          />
          <button type="submit" className="button-primary" disabled={mutation.isPending}>
            {mutation.isPending ? 'Creating…' : 'Create'}
          </button>
          {error && <div className="error">{error}</div>}
        </form>
      </section>

      <section className="card" style={{ marginTop: '1rem' }}>
        <h2>Existing Subjects</h2>
        {isLoading ? (
          <ul>
            <li className="skeleton-wrap" style={{ listStyle: 'none', padding: 0, margin: 0 }}>
              <div className="skeleton-list">
                {[...Array(8)].map((_, i) => <div key={i} className="skeleton-row" />)}
              </div>
            </li>
          </ul>
        ) : subjects?.length === 0 ? (
          <p className="muted">No subjects yet</p>
        ) : (
          <ul id="subjects-list">
            {subjects?.map((s, idx) => (
              <li
                key={s.id}
                className="subject-item fade-in-item"
                style={{ animationDelay: `${Math.min(idx * 14, 180)}ms`, cursor: 'pointer' }}
                onClick={() => navigate(`/subjects/${s.name}/sessions-ui`)}
              >
                {s.name}
                {s.protocol_name && (
                  <span className="muted" style={{ marginLeft: '8px', fontSize: '0.85em' }}>{s.protocol_name}</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
