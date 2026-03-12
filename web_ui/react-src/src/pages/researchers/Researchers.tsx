import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getResearchers, createResearcher, updateResearcher, hideResearcher } from '../../api/lab'

function InlineError({ message }: { message: string }) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'flex-start',
      gap: '8px',
      padding: '8px 10px',
      borderRadius: '6px',
      background: 'rgba(243, 139, 168, 0.08)',
      border: '1px solid rgba(243, 139, 168, 0.25)',
      borderLeft: '3px solid #f38ba8',
    }}>
      <span style={{ fontSize: '13px', lineHeight: '1', marginTop: '1px', flexShrink: 0, color: '#f38ba8' }}>⚠</span>
      <span style={{ fontSize: '12px', color: 'var(--subtext1)', lineHeight: '1.4' }}>{message}</span>
    </div>
  )
}

export default function Researchers() {
  const qc = useQueryClient()

  const [resName, setResName] = useState('')
  const [resEmail, setResEmail] = useState('')
  const [resError, setResError] = useState('')
  const [showResForm, setShowResForm] = useState(false)

  const [editingId, setEditingId] = useState<number | null>(null)
  const [editName, setEditName] = useState('')
  const [editEmail, setEditEmail] = useState('')
  const [editError, setEditError] = useState('')

  const { data: researchers, isLoading: loadingRes } = useQuery({
    queryKey: ['researchers'],
    queryFn: getResearchers,
  })

  const resMutation = useMutation({
    mutationFn: () => createResearcher({ name: resName.trim(), email: resEmail.trim() || undefined }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['researchers'] })
      setResName(''); setResEmail(''); setResError('')
      setShowResForm(false)
    },
    onError: (e: Error) => setResError(e.message),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, name, email }: { id: number; name: string; email: string }) =>
      updateResearcher(id, { name: name.trim(), email: email.trim() || undefined }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['researchers'] })
      setEditingId(null)
      setEditError('')
    },
    onError: (e: Error) => setEditError(e.message),
  })

  const hideMutation = useMutation({
    mutationFn: (id: number) => hideResearcher(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['researchers'] }),
  })

  const startEdit = (id: number, name: string, email: string) => {
    setEditingId(id)
    setEditName(name)
    setEditEmail(email)
    setEditError('')
  }

  return (
    <div className="container">
      <section className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h2 style={{ margin: 0 }}>Researchers</h2>
          <button className="button-primary" onClick={() => { setShowResForm(v => !v); setResError('') }}>
            {showResForm ? 'Cancel' : '+ Add Researcher'}
          </button>
        </div>

        {showResForm && (
          <div style={{ background: 'var(--surface1)', padding: '1rem', borderRadius: '8px', marginBottom: '1rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <input type="text" placeholder="Full name *" value={resName} onChange={e => setResName(e.target.value)} />
            <input type="email" placeholder="Email (optional)" value={resEmail} onChange={e => { setResEmail(e.target.value); setResError('') }} />
            {resError && <InlineError message={resError} />}
            <button
              className="button-primary"
              style={{ alignSelf: 'flex-start' }}
              disabled={!resName.trim() || resMutation.isPending}
              onClick={() => resMutation.mutate()}
            >
              {resMutation.isPending ? 'Saving…' : 'Add'}
            </button>
          </div>
        )}

        {loadingRes ? (
          <p className="muted">Loading…</p>
        ) : (researchers ?? []).length === 0 ? (
          <p className="muted">No researchers yet.</p>
        ) : (
          <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
            {(researchers ?? []).map(r => (
              <li key={r.id} style={{ padding: '8px 0', borderBottom: '1px solid var(--surface1)' }}>
                {editingId === r.id ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <input type="text" value={editName} onChange={e => setEditName(e.target.value)} />
                    <input type="email" placeholder="Email (optional)" value={editEmail} onChange={e => { setEditEmail(e.target.value); setEditError('') }} />
                    {editError && <InlineError message={editError} />}
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <button
                        className="button-primary"
                        style={{ fontSize: '12px', padding: '3px 10px' }}
                        disabled={!editName.trim() || updateMutation.isPending}
                        onClick={() => updateMutation.mutate({ id: r.id, name: editName, email: editEmail })}
                      >
                        {updateMutation.isPending ? 'Saving…' : 'Save'}
                      </button>
                      <button className="button-secondary" style={{ fontSize: '12px', padding: '3px 10px' }} onClick={() => { setEditingId(null); setEditError('') }}>
                        Cancel
                      </button>
                      <button
                        className="button-danger"
                        style={{ fontSize: '12px', padding: '3px 10px', marginLeft: 'auto' }}
                        disabled={hideMutation.isPending}
                        onClick={() => hideMutation.mutate(r.id)}
                      >
                        {hideMutation.isPending ? 'Removing…' : 'Remove'}
                      </button>
                    </div>
                  </div>
                ) : (
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <div style={{ fontWeight: 500, fontSize: '14px' }}>{r.name}</div>
                      {r.email && <div style={{ fontSize: '12px', color: 'var(--subtext0)' }}>{r.email}</div>}
                    </div>
                    <button
                      className="button-secondary"
                      style={{ fontSize: '12px', padding: '3px 10px' }}
                      onClick={() => startEdit(r.id, r.name, r.email ?? '')}
                    >
                      Edit
                    </button>
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
