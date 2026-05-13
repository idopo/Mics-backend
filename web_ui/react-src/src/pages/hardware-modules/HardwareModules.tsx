import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  listHardwareModules,
  createHardwareModule,
  updateHardwareModule,
  deleteHardwareModule,
} from '../../api/hardware_modules'
import { listHardwareLibs, getHardwareLib } from '../../api/hardware_libs'
import type { HardwareModule } from '../../types'

interface FormState {
  name: string
  display_name: string
  hardware_lib_id: string
  class_name: string
  description: string
}

const EMPTY_FORM: FormState = { name: '', display_name: '', hardware_lib_id: '', class_name: '', description: '' }

export default function HardwareModules(): JSX.Element {
  const qc = useQueryClient()
  const [editing, setEditing] = useState<HardwareModule | null>(null)
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [error, setError] = useState('')

  const { data: modules = [], isLoading } = useQuery({ queryKey: ['hardware-modules'], queryFn: listHardwareModules })
  const { data: libs = [] } = useQuery({ queryKey: ['hardware-libs'], queryFn: listHardwareLibs })

  const selectedLibId = parseInt(form.hardware_lib_id) || 0
  const { data: selectedLib } = useQuery({
    queryKey: ['hardware-lib', selectedLibId],
    queryFn: () => getHardwareLib(selectedLibId),
    enabled: selectedLibId > 0,
  })
  const availableClasses: string[] = selectedLib?.ast_metadata
    ? ((selectedLib.ast_metadata as { classes?: { name: string }[] }).classes ?? []).map(c => c.name)
    : []

  const saveMutation = useMutation({
    mutationFn: () => {
      const body = {
        name: form.name.trim(),
        hardware_lib_id: parseInt(form.hardware_lib_id),
        class_name: form.class_name,
        display_name: form.display_name.trim() || undefined,
        description: form.description.trim() || undefined,
      }
      return editing ? updateHardwareModule(editing.id, body) : createHardwareModule(body)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['hardware-modules'] })
      setEditing(null); setForm(EMPTY_FORM); setError('')
    },
    onError: (e: Error) => setError(e.message),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteHardwareModule(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['hardware-modules'] }),
    onError: (e: Error) => setError(e.message),
  })

  function startEdit(m: HardwareModule) {
    setEditing(m)
    setForm({
      name: m.name,
      display_name: m.display_name ?? '',
      hardware_lib_id: String(m.hardware_lib_id),
      class_name: m.class_name,
      description: m.description ?? '',
    })
    setError('')
  }

  function cancelEdit() {
    setEditing(null); setForm(EMPTY_FORM); setError('')
  }

  const libById = Object.fromEntries(libs.map(l => [l.id, l]))

  return (
    <div className="container split">
      <div className="card" style={{ flex: '0 0 360px', overflow: 'auto' }}>
        <h2 style={{ marginBottom: '1rem' }}>Hardware Modules</h2>
        {isLoading && <p>Loading…</p>}
        <ul className="scroll-list">
          {modules.map(m => (
            <li key={m.id} className="subject-item fade-in-item" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem' }}>
              <div style={{ minWidth: 0 }}>
                <strong>{m.name}</strong>
                <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', marginTop: '0.25rem' }}>
                  <span className="badge status-running">{libById[m.hardware_lib_id]?.name ?? `lib ${m.hardware_lib_id}`}</span>
                  <span className="badge status-completed">{m.class_name}</span>
                </div>
              </div>
              <div style={{ display: 'flex', gap: '0.4rem', flexShrink: 0 }}>
                <button className="button-secondary" onClick={() => startEdit(m)}>Edit</button>
                <button className="button-danger" onClick={() => deleteMutation.mutate(m.id)}>Del</button>
              </div>
            </li>
          ))}
        </ul>
      </div>

      <div className="card" style={{ flex: 1 }}>
        <h2 style={{ marginBottom: '1rem' }}>{editing ? `Edit: ${editing.name}` : 'New Module'}</h2>
        <div className="params-grid" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <div className="param-field">
            <span className="param-name">Name *</span>
            <input
              type="text"
              placeholder="e.g. Left_LED"
              value={form.name}
              onChange={e => { setForm(f => ({ ...f, name: e.target.value })); setError('') }}
            />
          </div>
          <div className="param-field">
            <span className="param-name">Display Name</span>
            <input
              type="text"
              placeholder="optional"
              value={form.display_name}
              onChange={e => setForm(f => ({ ...f, display_name: e.target.value }))}
            />
          </div>
          <div className="param-field">
            <span className="param-name">Hardware Lib *</span>
            <select
              value={form.hardware_lib_id}
              onChange={e => setForm(f => ({ ...f, hardware_lib_id: e.target.value, class_name: '' }))}
            >
              <option value="">— select —</option>
              {libs.map(l => <option key={l.id} value={String(l.id)}>{l.name}</option>)}
            </select>
          </div>
          <div className="param-field">
            <span className="param-name">Class *</span>
            <select
              value={form.class_name}
              disabled={!selectedLibId}
              onChange={e => { setForm(f => ({ ...f, class_name: e.target.value })); setError('') }}
            >
              <option value="">— select —</option>
              {availableClasses.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div className="param-field">
            <span className="param-name">Description</span>
            <input
              type="text"
              placeholder="optional"
              value={form.description}
              onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
            />
          </div>
          {error && <span className="badge status-error">{error}</span>}
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              className="button-primary"
              disabled={saveMutation.isPending || !form.name.trim() || !form.hardware_lib_id || !form.class_name}
              onClick={() => saveMutation.mutate()}
            >
              {saveMutation.isPending ? 'Saving…' : 'Save'}
            </button>
            {editing && <button className="button-secondary" onClick={cancelEdit}>Cancel</button>}
          </div>
        </div>
      </div>
    </div>
  )
}
