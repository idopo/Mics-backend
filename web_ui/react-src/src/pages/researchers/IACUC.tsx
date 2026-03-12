import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getIACUC, createIACUC, hideIACUC } from '../../api/lab'

export default function IACUC() {
  const qc = useQueryClient()

  const [number, setNumber] = useState('')
  const [title, setTitle] = useState('')
  const [expires, setExpires] = useState('')
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)

  const { data: iacucList, isLoading } = useQuery({
    queryKey: ['iacuc'],
    queryFn: getIACUC,
  })

  const removeMutation = useMutation({
    mutationFn: (id: number) => hideIACUC(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['iacuc'] }); setEditingId(null) },
  })

  const mutation = useMutation({
    mutationFn: () => createIACUC({
      number: number.trim(),
      title: title.trim(),
      expires_at: expires.trim() || undefined,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['iacuc'] })
      setNumber(''); setTitle(''); setExpires(''); setError('')
      setShowForm(false)
    },
    onError: (e: Error) => setError(e.message),
  })

  return (
    <div className="container">
      <section className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h2 style={{ margin: 0 }}>IACUC Protocols</h2>
          <button
            className="button-primary"
            style={{ width: '28px', height: '28px', padding: 0, fontSize: '18px', lineHeight: '1', borderRadius: '6px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
            title="Add IACUC protocol"
            onClick={() => setShowForm(v => !v)}
          >
            {showForm ? '✕' : '+'}
          </button>
        </div>

        {showForm && (
          <div style={{ background: 'var(--surface1)', padding: '1rem', borderRadius: '8px', marginBottom: '1rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <input type="text" placeholder="Protocol number * (e.g. IL-2024-001)" value={number} onChange={e => setNumber(e.target.value)} />
            <input type="text" placeholder="Title *" value={title} onChange={e => setTitle(e.target.value)} />
            <input type="text" placeholder="Expiry date (YYYY-MM-DD, optional)" value={expires} onChange={e => setExpires(e.target.value)} />
            {error && <p style={{ color: 'crimson', fontSize: '13px', margin: 0 }}>{error}</p>}
            <button
              className="button-primary"
              style={{ alignSelf: 'flex-start' }}
              disabled={!number.trim() || !title.trim() || mutation.isPending}
              onClick={() => mutation.mutate()}
            >
              {mutation.isPending ? 'Saving…' : 'Add'}
            </button>
          </div>
        )}

        {isLoading ? (
          <p className="muted">Loading…</p>
        ) : (iacucList ?? []).length === 0 ? (
          <p className="muted">No IACUC protocols yet.</p>
        ) : (
          <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
            {(iacucList ?? []).map(i => (
              <li key={i.id} style={{ padding: '8px 0', borderBottom: '1px solid var(--surface1)' }}>
                {editingId === i.id ? (
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <div style={{ fontWeight: 500, fontSize: '14px' }}>{i.number}</div>
                      <div style={{ fontSize: '12px', color: 'var(--subtext1)' }}>{i.title}</div>
                    </div>
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <button className="button-secondary" style={{ fontSize: '12px', padding: '3px 10px' }} onClick={() => setEditingId(null)}>
                        Cancel
                      </button>
                      <button
                        className="button-danger"
                        style={{ fontSize: '12px', padding: '3px 10px' }}
                        disabled={removeMutation.isPending}
                        onClick={() => removeMutation.mutate(i.id)}
                      >
                        {removeMutation.isPending ? 'Removing…' : 'Remove'}
                      </button>
                    </div>
                  </div>
                ) : (
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <div style={{ fontWeight: 500, fontSize: '14px' }}>{i.number}</div>
                      <div style={{ fontSize: '12px', color: 'var(--subtext1)' }}>{i.title}</div>
                    </div>
                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                      {i.expires_at && (
                        <span style={{ fontSize: '11px', color: 'var(--subtext0)' }}>expires {i.expires_at}</span>
                      )}
                      <button className="button-secondary" style={{ fontSize: '12px', padding: '3px 10px' }} onClick={() => setEditingId(i.id)}>
                        Edit
                      </button>
                    </div>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
