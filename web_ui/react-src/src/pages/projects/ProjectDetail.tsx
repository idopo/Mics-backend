import { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getProject, getExperiments, createExperiment, getResearchers, getIACUC } from '../../api/lab'

export default function ProjectDetail() {
  const { projectId } = useParams<{ projectId: string }>()
  const id = parseInt(projectId!)
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [showExpForm, setShowExpForm] = useState(false)
  const [expName, setExpName] = useState('')
  const [expDesc, setExpDesc] = useState('')
  const [expNotes, setExpNotes] = useState('')
  const [expError, setExpError] = useState('')

  const { data: project, isLoading: loadingProject } = useQuery({
    queryKey: ['project', id],
    queryFn: () => getProject(id),
  })

  const { data: experiments, isLoading: loadingExps } = useQuery({
    queryKey: ['experiments', id],
    queryFn: () => getExperiments(id),
  })

  const { data: researchers } = useQuery({ queryKey: ['researchers'], queryFn: getResearchers })
  const { data: iacucList } = useQuery({ queryKey: ['iacuc'], queryFn: getIACUC })

  const createExpMutation = useMutation({
    mutationFn: () => createExperiment({
      name: expName.trim(),
      project_id: id,
      description: expDesc.trim() || undefined,
      notes: expNotes.trim() || undefined,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['experiments', id] })
      setShowExpForm(false)
      setExpName(''); setExpDesc(''); setExpNotes(''); setExpError('')
    },
    onError: (e: Error) => setExpError(e.message),
  })

  const researcherName = (rid?: number | null) =>
    researchers?.find(r => r.id === rid)?.name
  const iacucInfo = (iid?: number | null) => {
    const i = iacucList?.find(x => x.id === iid)
    return i ? `${i.number} — ${i.title}` : null
  }

  if (loadingProject) return <div className="container"><section className="card"><p className="muted">Loading…</p></section></div>
  if (!project) return <div className="container"><section className="card"><p className="muted">Project not found.</p></section></div>

  return (
    <div className="container">
      <section className="card">
        <div style={{ fontSize: '12px', color: 'var(--subtext0)', marginBottom: '0.5rem' }}>
          <Link to="/projects-ui" style={{ color: 'var(--lavender)', textDecoration: 'none' }}>Projects</Link>
          {' / '}
          <span>{project.name}</span>
        </div>
        <h2 style={{ marginTop: 0 }}>{project.name}</h2>
        {project.description && <p style={{ color: 'var(--subtext1)', marginTop: '0.25rem' }}>{project.description}</p>}

        <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', marginTop: '0.75rem', fontSize: '13px', color: 'var(--subtext0)' }}>
          {project.lead_researcher_id && <span>PI: {researcherName(project.lead_researcher_id) ?? `#${project.lead_researcher_id}`}</span>}
          {project.iacuc_id && <span>IACUC: {iacucInfo(project.iacuc_id) ?? `#${project.iacuc_id}`}</span>}
          <span>Created: {new Date(project.created_at).toLocaleDateString()}</span>
        </div>

        {project.notes && (
          <div style={{ marginTop: '0.75rem', padding: '8px 12px', background: 'var(--surface1)', borderRadius: '6px', fontSize: '13px' }}>
            {project.notes}
          </div>
        )}
      </section>

      <section className="card" style={{ marginTop: '1rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h3 style={{ margin: 0 }}>Experiments</h3>
          <button className="button-primary" onClick={() => setShowExpForm(v => !v)}>
            {showExpForm ? 'Cancel' : '+ New Experiment'}
          </button>
        </div>

        {showExpForm && (
          <div style={{ background: 'var(--surface1)', padding: '1rem', borderRadius: '8px', marginBottom: '1rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <input type="text" placeholder="Experiment name *" value={expName} onChange={e => setExpName(e.target.value)} />
            <input type="text" placeholder="Description" value={expDesc} onChange={e => setExpDesc(e.target.value)} />
            <input type="text" placeholder="Notes" value={expNotes} onChange={e => setExpNotes(e.target.value)} />
            {expError && <p style={{ color: 'crimson', fontSize: '13px', margin: 0 }}>{expError}</p>}
            <button className="button-primary" disabled={!expName.trim() || createExpMutation.isPending} onClick={() => createExpMutation.mutate()}>
              {createExpMutation.isPending ? 'Creating…' : 'Create'}
            </button>
          </div>
        )}

        {loadingExps ? (
          <p className="muted">Loading…</p>
        ) : (experiments ?? []).length === 0 ? (
          <p className="muted">No experiments yet.</p>
        ) : (
          <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '2px' }}>
            {(experiments ?? []).map(exp => (
              <li
                key={exp.id}
                style={{ padding: '10px 12px', borderRadius: '6px', cursor: 'pointer', background: 'var(--surface1)' }}
                onClick={() => navigate(`/experiments/${exp.id}`)}
                onMouseEnter={e => (e.currentTarget.style.background = 'var(--surface2)')}
                onMouseLeave={e => (e.currentTarget.style.background = 'var(--surface1)')}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                  <span style={{ fontWeight: 500 }}>{exp.name}</span>
                  <span style={{ fontSize: '11px', color: 'var(--subtext0)' }}>{new Date(exp.created_at).toLocaleDateString()}</span>
                </div>
                {exp.description && <div style={{ fontSize: '12px', color: 'var(--subtext1)', marginTop: '2px' }}>{exp.description}</div>}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
