import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { patchToolkit } from '../../api/toolkits'
import { listHardwareModules } from '../../api/hardware_modules'
import type { ToolkitRead, FlagDefinition, ParamDefinition, BackendToolkitPatchPayload } from '../../types'

const TRACKER_TYPES = ['Counter_Tracker', 'Boolean_Tracker', 'Trial_Tracker', 'Tracker']

export function EditModal({ toolkit, onClose, onSaved }: {
  toolkit: ToolkitRead
  onClose: () => void
  onSaved: () => void
}) {
  const { data: hwModules = [] } = useQuery({ queryKey: ['hardware-modules'], queryFn: listHardwareModules })
  const qc = useQueryClient()

  const [selectedModuleIds, setSelectedModuleIds] = useState<number[]>(toolkit.hardware_module_ids ?? [])
  const [flags, setFlags] = useState<FlagDefinition[]>(() =>
    Object.entries(toolkit.flags ?? {}).map(([name, v]) => {
      const val = v as Record<string, unknown>
      return { name, tracker_type: String(val.tracker_type ?? 'Counter_Tracker'), initial_value: val.initial_value ?? 0 }
    })
  )
  const [params, setParams] = useState<ParamDefinition[]>(() =>
    Object.entries(toolkit.params_schema ?? {}).map(([name, v]) => {
      const val = v as Record<string, unknown>
      return { name, type: String(val.type ?? 'float'), default: val.default ?? null }
    })
  )
  const [error, setError] = useState('')

  const saveMutation = useMutation({
    mutationFn: (payload: BackendToolkitPatchPayload) => patchToolkit(toolkit.id, payload),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['toolkits'] }); onSaved() },
    onError: (e: Error) => setError(e.message),
  })

  const toggleModule = (id: number) =>
    setSelectedModuleIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id])

  const addFlag = () => setFlags(prev => [...prev, { name: '', tracker_type: 'Counter_Tracker', initial_value: 0 }])
  const updateFlag = (i: number, f: Partial<FlagDefinition>) => setFlags(prev => prev.map((x, idx) => idx === i ? { ...x, ...f } : x))
  const removeFlag = (i: number) => setFlags(prev => prev.filter((_, idx) => idx !== i))

  const addParam = () => setParams(prev => [...prev, { name: '', type: 'float', default: null }])
  const updateParam = (i: number, p: Partial<ParamDefinition>) => setParams(prev => prev.map((x, idx) => idx === i ? { ...x, ...p } : x))
  const removeParam = (i: number) => setParams(prev => prev.filter((_, idx) => idx !== i))

  const handleSave = () => {
    setError('')
    saveMutation.mutate({ hardware_module_ids: selectedModuleIds, flags, params_schema: params })
  }

  return (
    <div className="modal-overlay" style={{ alignItems: 'flex-start', paddingTop: '10vh' }}>
      <div className="modal" style={{ width: '640px', maxHeight: '80vh', display: 'flex', flexDirection: 'column' }}>
        <div className="modal-header">
          <span className="modal-title">Edit Toolkit: {toolkit.name}</span>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body" style={{ overflowY: 'auto', flexGrow: 1, display: 'flex', flexDirection: 'column', gap: '18px' }}>
          {/* HW Modules */}
          <div>
            <p style={{ fontSize: '12px', color: 'var(--muted)', marginBottom: '6px', marginTop: 0 }}>Hardware Modules</p>
            {hwModules.length === 0 ? <p className="muted" style={{ fontStyle: 'italic', fontSize: '12px' }}>No hardware modules defined.</p> : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                {hwModules.map(m => (
                  <label key={m.id} style={{ display: 'grid', gridTemplateColumns: '20px 1fr auto', alignItems: 'center', gap: '8px', fontSize: '13px', cursor: 'pointer', padding: '6px 8px', borderRadius: '4px', background: selectedModuleIds.includes(m.id) ? 'rgba(129,140,248,0.1)' : 'transparent', border: '1px solid transparent', borderColor: selectedModuleIds.includes(m.id) ? 'rgba(129,140,248,0.25)' : 'transparent', transition: 'background 0.1s' }}>
                    <input type="checkbox" checked={selectedModuleIds.includes(m.id)} onChange={() => toggleModule(m.id)} style={{ margin: 0 }} />
                    <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontWeight: 500 }}>{m.name}</span>
                    <span style={{ fontSize: '11px', color: 'var(--muted)', fontFamily: "'IBM Plex Mono', monospace" }}>{m.class_name}</span>
                  </label>
                ))}
              </div>
            )}
          </div>
          {/* Flags */}
          <div>
            <p style={{ fontSize: '12px', color: 'var(--muted)', marginBottom: '6px', marginTop: 0 }}>Flags</p>
            {flags.map((f, i) => (
              <div key={i} style={{ display: 'grid', gridTemplateColumns: '1fr 180px 80px 28px', gap: '4px', alignItems: 'center', marginBottom: '4px' }}>
                <input value={f.name} onChange={e => updateFlag(i, { name: e.target.value })} placeholder="flag_name" style={{ fontSize: '12px', fontFamily: "'IBM Plex Mono', monospace" }} />
                <select value={f.tracker_type} onChange={e => { const t = e.target.value; updateFlag(i, { tracker_type: t, initial_value: t === 'Boolean_Tracker' ? false : 0 }) }} style={{ fontSize: '12px' }}>
                  {TRACKER_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
                {f.tracker_type === 'Boolean_Tracker' ? (
                  <select value={String(f.initial_value)} onChange={e => updateFlag(i, { initial_value: e.target.value === 'true' })} style={{ fontSize: '12px' }}>
                    <option value="false">False</option><option value="true">True</option>
                  </select>
                ) : (
                  <input type="number" value={Number(f.initial_value)} onChange={e => updateFlag(i, { initial_value: Number(e.target.value) || 0 })} style={{ fontSize: '12px' }} />
                )}
                <button className="button-danger" style={{ fontSize: '11px', padding: '2px 6px', height: '28px' }} onClick={() => removeFlag(i)}>✕</button>
              </div>
            ))}
            <button className="button-secondary" style={{ fontSize: '12px', marginTop: '4px' }} onClick={addFlag}>+ Add Flag</button>
          </div>
          {/* Params */}
          <div>
            <p style={{ fontSize: '12px', color: 'var(--muted)', marginBottom: '6px', marginTop: 0 }}>Params</p>
            {params.map((p, i) => (
              <div key={i} style={{ display: 'flex', gap: '6px', alignItems: 'center', marginBottom: '6px' }}>
                <input value={p.name} onChange={e => updateParam(i, { name: e.target.value })} placeholder="name" style={{ flex: 1 }} />
                <input value={p.type} onChange={e => updateParam(i, { type: e.target.value })} placeholder="type" style={{ width: '80px' }} />
                <input value={p.default == null ? '' : String(p.default)} onChange={e => updateParam(i, { default: e.target.value || null })} placeholder="default" style={{ width: '80px' }} />
                <button className="button-danger" style={{ fontSize: '11px', padding: '2px 8px' }} onClick={() => removeParam(i)}>✕</button>
              </div>
            ))}
            <button className="button-secondary" style={{ fontSize: '12px' }} onClick={addParam}>+ Add Param</button>
          </div>
          {error && <p style={{ color: 'var(--error)', fontSize: '12px', margin: 0 }}>{error}</p>}
        </div>
        <div className="modal-actions ov-actions">
          <button className="button-secondary" onClick={onClose}>Cancel</button>
          <button className="button-primary" onClick={handleSave} disabled={saveMutation.isPending}>
            {saveMutation.isPending ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}
