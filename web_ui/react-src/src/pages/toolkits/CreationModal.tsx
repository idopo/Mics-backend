import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { getLockedStates, createBackendToolkit } from '../../api/toolkits'
import { listHardwareModules } from '../../api/hardware_modules'
import { listHardwareLibs, linkLib } from '../../api/hardware_libs'
import type {
  FlagDefinition, ParamDefinition, BackendToolkitCreatePayload,
} from '../../types'

const TRACKER_TYPES = ['Counter_Tracker', 'Boolean_Tracker', 'Trial_Tracker', 'Tracker']

// Steps with no file selected: 1 (name+file) → 3 (hw-modules) → 4 (flags) → 5 (params)
// Steps with file selected:    1 (name+file) → 2 (locked states) → 3 (hw-modules) → 4 (flags) → 5 (params)

export function CreationModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [step, setStep] = useState(1)
  const [name, setName] = useState('')
  const [selectedFile, setSelectedFile] = useState('')
  const [selectedStates, setSelectedStates] = useState<string[]>([])
  const [selectedModuleIds, setSelectedModuleIds] = useState<number[]>([])
  const [flags, setFlags] = useState<FlagDefinition[]>([])
  const [params, setParams] = useState<ParamDefinition[]>([])
  const [error, setError] = useState('')

  const { data: lockedStates } = useQuery({ queryKey: ['locked-states'], queryFn: getLockedStates })
  const { data: hwModules = [] } = useQuery({ queryKey: ['hardware-modules'], queryFn: listHardwareModules })
  const { data: hwLibs = [] } = useQuery({ queryKey: ['hardware-libs'], queryFn: listHardwareLibs })
  const createMutation = useMutation({
    mutationFn: (payload: BackendToolkitCreatePayload) => createBackendToolkit(payload),
    onSuccess: async (toolkit) => {
      // Auto-link all hardware libraries using their stable version, falling back to active
      if (hwLibs.length > 0) {
        await Promise.all(
          hwLibs.map(lib =>
            linkLib(toolkit.id, lib.id, lib.stable_version_id ?? lib.active_version_id ?? null)
          )
        )
      }
      onCreated()
    },
    onError: (e: Error) => setError(e.message),
  })

  const fileEntry = selectedFile ? lockedStates?.by_file[selectedFile] : null
  const availableStates = fileEntry?.state_names ?? []
  const fileOptions = Object.keys(lockedStates?.by_file ?? {})

  const handleFileSelect = (fname: string) => {
    setSelectedFile(fname)
    setSelectedStates(lockedStates?.by_file[fname]?.state_names ?? [])
  }

  const toggleState = (s: string) =>
    setSelectedStates(prev => prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s])

  const toggleModule = (id: number) =>
    setSelectedModuleIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id])

  const addFlag = () => setFlags(prev => [...prev, { name: '', tracker_type: 'Counter_Tracker', initial_value: 0 }])
  const updateFlag = (i: number, f: Partial<FlagDefinition>) => setFlags(prev => prev.map((x, idx) => idx === i ? { ...x, ...f } : x))
  const removeFlag = (i: number) => setFlags(prev => prev.filter((_, idx) => idx !== i))

  const addParam = () => setParams(prev => [...prev, { name: '', type: 'float', default: null }])
  const updateParam = (i: number, p: Partial<ParamDefinition>) => setParams(prev => prev.map((x, idx) => idx === i ? { ...x, ...p } : x))
  const removeParam = (i: number) => setParams(prev => prev.filter((_, idx) => idx !== i))

  const handleNext = () => {
    // Skip step 2 (locked-states) when no source file selected
    if (step === 1 && !selectedFile) {
      setStep(3)
    } else {
      setStep(s => s + 1)
    }
  }

  const handleBack = () => {
    // Skip back over step 2 when no source file selected
    if (step === 3 && !selectedFile) {
      setStep(1)
    } else {
      setStep(s => s - 1)
    }
  }

  const handleCreate = () => {
    setError('')
    createMutation.mutate({
      name: name.trim(),
      locked_state_source: selectedFile || null,
      selected_states: selectedStates,
      hardware_module_ids: selectedModuleIds,
      flags,
      params_schema: params,
    })
  }

  const canNext1 = name.trim().length > 0
  const totalSteps = selectedFile ? 5 : 4
  // Map internal step number to visible step position when file is not selected (step 3→2, 4→3, 5→4)
  const visibleStep = (!selectedFile && step > 2) ? step - 1 : step

  return (
    <div className="modal-overlay" style={{ alignItems: 'flex-start', paddingTop: '10vh' }}>
      <div className="modal" style={{ width: '640px', maxHeight: '80vh', display: 'flex', flexDirection: 'column' }}>
        <div className="modal-header">
          <span className="modal-title">New Backend Toolkit — Step {visibleStep} of {totalSteps}</span>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body" style={{ overflowY: 'auto', flexGrow: 1 }}>
          {step === 1 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <label style={{ fontSize: '13px' }}>Toolkit name
                <input value={name} onChange={e => setName(e.target.value)} placeholder="e.g. AppetitiveV2" style={{ display: 'block', width: '100%', marginTop: '4px' }} />
              </label>
              <label style={{ fontSize: '13px' }}>Task source file <span style={{ fontSize: '11px', color: 'var(--muted)' }}>(optional — populated from Pi HANDSHAKE)</span>
                <select value={selectedFile} onChange={e => handleFileSelect(e.target.value)} style={{ display: 'block', width: '100%', marginTop: '4px' }}>
                  <option value="">— none (base mics_task) —</option>
                  {fileOptions.map(f => {
                    const entry = lockedStates!.by_file[f]
                    return <option key={f} value={f}>{f}{entry.is_legacy_filename ? ' (legacy filename)' : ''} — {entry.pilots.join(', ')}</option>
                  })}
                </select>
                {fileEntry?.is_legacy_filename && (
                  <p style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '4px' }}>
                    Warning: this filename was reconstructed from the task class name and may not match the actual Pi source file.
                  </p>
                )}
              </label>
            </div>
          )}
          {step === 2 && (
            <div>
              <p style={{ fontSize: '12px', color: 'var(--muted)', marginBottom: '8px' }}>Select states from {selectedFile}</p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                {availableStates.map(s => (
                  <label key={s} style={{ display: 'grid', gridTemplateColumns: '20px 1fr', alignItems: 'center', gap: '8px', fontSize: '13px', cursor: 'pointer', padding: '6px 8px', borderRadius: '4px', background: selectedStates.includes(s) ? 'rgba(129,140,248,0.1)' : 'transparent', border: '1px solid transparent', transition: 'background 0.1s', borderColor: selectedStates.includes(s) ? 'rgba(129,140,248,0.25)' : 'transparent' }}>
                    <input type="checkbox" checked={selectedStates.includes(s)} onChange={() => toggleState(s)} style={{ margin: 0 }} />
                    <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontWeight: 500 }}>{s}</span>
                  </label>
                ))}
              </div>
            </div>
          )}
          {step === 3 && (
            <div>
              <p style={{ fontSize: '12px', color: 'var(--muted)', marginBottom: '8px' }}>Select hardware modules to include</p>
              {hwModules.length === 0 ? <p className="muted" style={{ fontStyle: 'italic', fontSize: '12px' }}>No hardware modules defined yet.</p> : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                  {hwModules.map(m => (
                    <label key={m.id} style={{ display: 'grid', gridTemplateColumns: '20px 1fr auto', alignItems: 'center', gap: '8px', fontSize: '13px', cursor: 'pointer', padding: '6px 8px', borderRadius: '4px', background: selectedModuleIds.includes(m.id) ? 'rgba(129,140,248,0.1)' : 'transparent', border: '1px solid transparent', transition: 'background 0.1s', borderColor: selectedModuleIds.includes(m.id) ? 'rgba(129,140,248,0.25)' : 'transparent' }}>
                      <input type="checkbox" checked={selectedModuleIds.includes(m.id)} onChange={() => toggleModule(m.id)} style={{ margin: 0 }} />
                      <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontWeight: 500 }}>{m.name}</span>
                      <span style={{ fontSize: '11px', color: 'var(--muted)', fontFamily: "'IBM Plex Mono', monospace" }}>{m.class_name}</span>
                    </label>
                  ))}
                </div>
              )}
            </div>
          )}
          {step === 4 && (
            <div>
              <p style={{ fontSize: '12px', color: 'var(--muted)', marginBottom: '8px' }}>Define flags (optional)</p>
              {flags.length > 0 && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 180px 80px 28px', gap: '4px', marginBottom: '4px' }}>
                  <span style={{ fontSize: '10px', color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.05em', paddingLeft: '4px' }}>Name</span>
                  <span style={{ fontSize: '10px', color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Tracker type</span>
                  <span style={{ fontSize: '10px', color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Init</span>
                  <span />
                </div>
              )}
              {flags.map((f, i) => (
                <div key={i} style={{ display: 'grid', gridTemplateColumns: '1fr 180px 80px 28px', gap: '4px', alignItems: 'center', marginBottom: '4px' }}>
                  <input value={f.name} onChange={e => updateFlag(i, { name: e.target.value })} placeholder="flag_name" style={{ fontSize: '12px', fontFamily: "'IBM Plex Mono', monospace" }} />
                  <select value={f.tracker_type} onChange={e => {
                    const t = e.target.value
                    updateFlag(i, { tracker_type: t, initial_value: t === 'Boolean_Tracker' ? false : 0 })
                  }} style={{ fontSize: '12px' }}>
                    {TRACKER_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                  </select>
                  {f.tracker_type === 'Boolean_Tracker' ? (
                    <select value={String(f.initial_value)} onChange={e => updateFlag(i, { initial_value: e.target.value === 'true' })} style={{ fontSize: '12px' }}>
                      <option value="false">False</option>
                      <option value="true">True</option>
                    </select>
                  ) : (
                    <input type="number" value={Number(f.initial_value)} onChange={e => updateFlag(i, { initial_value: Number(e.target.value) || 0 })} placeholder="0" style={{ fontSize: '12px', fontFamily: "'IBM Plex Mono', monospace" }} />
                  )}
                  <button className="button-danger" style={{ fontSize: '11px', padding: '2px 6px', height: '28px' }} onClick={() => removeFlag(i)}>✕</button>
                </div>
              ))}
              <button className="button-secondary" style={{ fontSize: '12px', marginTop: '4px' }} onClick={addFlag}>+ Add Flag</button>
            </div>
          )}
          {step === 5 && (
            <div>
              <p style={{ fontSize: '12px', color: 'var(--muted)', marginBottom: '8px' }}>Define params (optional)</p>
              {params.map((p, i) => (
                <div key={i} style={{ display: 'flex', gap: '6px', alignItems: 'center', marginBottom: '6px' }}>
                  <input value={p.name} onChange={e => updateParam(i, { name: e.target.value })} placeholder="name" style={{ flex: 1 }} />
                  <input value={p.type} onChange={e => updateParam(i, { type: e.target.value })} placeholder="type" style={{ width: '80px' }} />
                  <input value={p.default == null ? '' : String(p.default)} onChange={e => updateParam(i, { default: e.target.value || null })} placeholder="default" style={{ width: '80px' }} />
                  <button className="button-danger" style={{ fontSize: '11px', padding: '2px 8px' }} onClick={() => removeParam(i)}>✕</button>
                </div>
              ))}
              <button className="button-secondary" style={{ fontSize: '12px' }} onClick={addParam}>+ Add Param</button>
              {error && <p style={{ color: 'var(--error)', fontSize: '12px', marginTop: '8px' }}>{error}</p>}
            </div>
          )}
        </div>
        <div className="modal-actions ov-actions">
          {step > 1 && <button className="button-secondary" onClick={handleBack}>Back</button>}
          {step < 5 && <button className="button-primary" onClick={handleNext} disabled={step === 1 && !canNext1}>Next</button>}
          {step === 5 && <button className="button-primary" onClick={handleCreate} disabled={createMutation.isPending}>{createMutation.isPending ? 'Creating…' : 'Create Toolkit'}</button>}
        </div>
      </div>
    </div>
  )
}
