import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getProjects, createProject, getResearchers, getIACUC } from '../../api/lab'

export default function Projects() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [iacucId, setIacucId] = useState<number | ''>('')
  const [researcherId, setResearcherId] = useState<number | ''>('')
  const [notes, setNotes] = useState('')
  const [error, setError] = useState('')

  const { data: projects, isLoading } = useQuery({ queryKey: ['projects'], queryFn: getProjects })
  const { data: researchers } = useQuery({ queryKey: ['researchers'], queryFn: getResearchers })
  const { data: iacucList } = useQuery({ queryKey: ['iacuc'], queryFn: getIACUC })

  const mutation = useMutation({
    mutationFn: () => createProject({
      name: name.trim(),
      description: description.trim() || undefined,
      iacuc_id: iacucId !== '' ? iacucId : undefined,
      lead_researcher_id: researcherId !== '' ? researcherId : undefined,
      notes: notes.trim() || undefined,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projects'] })
      setShowForm(false)
      setName(''); setDescription(''); setIacucId(''); setResearcherId(''); setNotes(''); setError('')
    },
    onError: (e: Error) => setError(e.message),
  })

  const researcherName = (id?: number | null) =>
    researchers?.find(r => r.id === id)?.name ?? '—'
  const iacucNumber = (id?: number | null) =>
    iacucList?.find(i => i.id === id)?.number ?? '—'

  return (
    <div className="container">
      <section className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h2 style={{ margin: 0 }}>Projects</h2>
          <button className="button-primary" onClick={() => setShowForm(v => !v)}>
            {showForm ? 'Cancel' : '+ New Project'}
          </button>
        </div>

        {showForm && (
          <div style={{ background: 'var(--surface1)', padding: '1rem', borderRadius: '8px', marginBottom: '1rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <input type="text" placeholder="Project name *" value={name} onChange={e => setName(e.target.value)} />
            <input type="text" placeholder="Description" value={description} onChange={e => setDescription(e.target.value)} />
            <select value={researcherId} onChange={e => setResearcherId(e.target.value ? parseInt(e.target.value) : '')}>
              <option value="">Lead researcher (optional)</option>
              {(researchers ?? []).map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
            </select>
            <select value={iacucId} onChange={e => setIacucId(e.target.value ? parseInt(e.target.value) : '')}>
              <option value="">IACUC protocol (optional)</option>
              {(iacucList ?? []).map(i => <option key={i.id} value={i.id}>{i.number} — {i.title}</option>)}
            </select>
            <input type="text" placeholder="Notes" value={notes} onChange={e => setNotes(e.target.value)} />
            {error && <p style={{ color: 'crimson', fontSize: '13px', margin: 0 }}>{error}</p>}
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button className="button-primary" disabled={!name.trim() || mutation.isPending} onClick={() => mutation.mutate()}>
                {mutation.isPending ? 'Creating…' : 'Create'}
              </button>
            </div>
          </div>
        )}

        {isLoading ? (
          <p className="muted">Loading…</p>
        ) : (projects ?? []).length === 0 ? (
          <p className="muted">No projects yet.</p>
        ) : (
          <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '2px' }}>
            {(projects ?? []).map(p => (
              <li
                key={p.id}
                style={{ padding: '10px 12px', borderRadius: '6px', cursor: 'pointer', background: 'var(--surface1)' }}
                onClick={() => navigate(`/projects/${p.id}`)}
                onMouseEnter={e => (e.currentTarget.style.background = 'var(--surface2)')}
                onMouseLeave={e => (e.currentTarget.style.background = 'var(--surface1)')}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                  <span style={{ fontWeight: 500 }}>{p.name}</span>
                  <span style={{ fontSize: '11px', color: 'var(--subtext0)' }}>{new Date(p.created_at).toLocaleDateString()}</span>
                </div>
                {p.description && <div style={{ fontSize: '12px', color: 'var(--subtext1)', marginTop: '2px' }}>{p.description}</div>}
                <div style={{ fontSize: '11px', color: 'var(--subtext0)', marginTop: '4px', display: 'flex', gap: '12px' }}>
                  {p.lead_researcher_id && <span>PI: {researcherName(p.lead_researcher_id)}</span>}
                  {p.iacuc_id && <span>IACUC: {iacucNumber(p.iacuc_id)}</span>}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
