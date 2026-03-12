import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getExperiment, getExperimentProtocols, getProject } from '../../api/lab'
import { apiFetch } from '../../api/client'

export default function ExperimentDetail() {
  const { experimentId } = useParams<{ experimentId: string }>()
  const id = parseInt(experimentId!)
  const qc = useQueryClient()
  const [protocolIdInput, setProtocolIdInput] = useState('')

  const { data: experiment, isLoading } = useQuery({
    queryKey: ['experiment', id],
    queryFn: () => getExperiment(id),
  })

  const { data: protocols } = useQuery({
    queryKey: ['experiment-protocols', id],
    queryFn: () => getExperimentProtocols(id),
    enabled: !isLoading && !!experiment,
  })

  const { data: project } = useQuery({
    queryKey: ['project', experiment?.project_id],
    queryFn: () => getProject(experiment!.project_id),
    enabled: !!experiment?.project_id,
  })

  const assignMutation = useMutation({
    mutationFn: (pid: number) =>
      apiFetch<void>(`/api/experiments/${id}/protocols/${pid}`, { method: 'POST' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['experiment-protocols', id] })
      setProtocolIdInput('')
    },
  })

  const unassignMutation = useMutation({
    mutationFn: (pid: number) =>
      apiFetch<void>(`/api/experiments/${id}/protocols/${pid}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['experiment-protocols', id] }),
  })

  if (isLoading) return <div className="container"><section className="card"><p className="muted">Loading…</p></section></div>
  if (!experiment) return <div className="container"><section className="card"><p className="muted">Experiment not found.</p></section></div>

  return (
    <div className="container">
      <section className="card">
        <div style={{ fontSize: '12px', color: 'var(--subtext0)', marginBottom: '0.5rem' }}>
          <Link to="/projects-ui" style={{ color: 'var(--lavender)', textDecoration: 'none' }}>Projects</Link>
          {project && (
            <>
              {' / '}
              <Link to={`/projects/${project.id}`} style={{ color: 'var(--lavender)', textDecoration: 'none' }}>{project.name}</Link>
            </>
          )}
          {' / '}
          <span>{experiment.name}</span>
        </div>

        <h2 style={{ marginTop: 0 }}>{experiment.name}</h2>
        {experiment.description && <p style={{ color: 'var(--subtext1)', marginTop: '0.25rem' }}>{experiment.description}</p>}
        <div style={{ fontSize: '13px', color: 'var(--subtext0)', marginTop: '0.5rem' }}>
          Created: {new Date(experiment.created_at).toLocaleDateString()}
        </div>
        {experiment.notes && (
          <div style={{ marginTop: '0.75rem', padding: '8px 12px', background: 'var(--surface1)', borderRadius: '6px', fontSize: '13px' }}>
            {experiment.notes}
          </div>
        )}
      </section>

      <section className="card" style={{ marginTop: '1rem' }}>
        <h3 style={{ marginTop: 0 }}>Protocols</h3>

        {(protocols ?? []).length === 0 ? (
          <p className="muted">No protocols assigned.</p>
        ) : (
          <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {(protocols ?? []).map(p => (
              <li key={p.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 12px', background: 'var(--surface1)', borderRadius: '6px' }}>
                <div>
                  <div style={{ fontWeight: 500, fontSize: '13px' }}>{p.name}</div>
                  <div style={{ fontSize: '11px', color: 'var(--subtext0)' }}>{p.steps?.length ?? 0} steps</div>
                </div>
                <button
                  className="button-danger"
                  style={{ fontSize: '11px', padding: '2px 8px' }}
                  disabled={unassignMutation.isPending}
                  onClick={() => unassignMutation.mutate(p.id)}
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}

        <div style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <input
            type="number"
            placeholder="Protocol ID"
            value={protocolIdInput}
            onChange={e => setProtocolIdInput(e.target.value)}
            style={{ width: '120px' }}
          />
          <button
            className="button-secondary"
            disabled={!protocolIdInput || assignMutation.isPending}
            onClick={() => assignMutation.mutate(parseInt(protocolIdInput))}
          >
            Assign
          </button>
        </div>
      </section>
    </div>
  )
}
