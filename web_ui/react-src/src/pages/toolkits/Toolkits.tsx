import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { getToolkits, getLockedStates, createBackendToolkit } from '../../api/toolkits'
import { getTaskDefinitions, createTaskDefinition } from '../../api/task-definitions'
import { listHardwareModules } from '../../api/hardware_modules'
import { EditModal } from './EditModal'
import type {
  ToolkitRead, TaskDefinitionFull, FlagDefinition, ParamDefinition, BackendToolkitCreatePayload,
} from '../../types'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function emptySkeletonFor(toolkit: ToolkitRead): Record<string, unknown> {
  return {
    version: 2,
    initial_state: toolkit.states?.[0] ?? '',
    states: Object.fromEntries((toolkit.states ?? []).map(s => [s, {}])),
    transitions: [],
    trigger_assignments: [],
  }
}

function MetaChips({ label, items }: { label: string; items: string[] }) {
  if (items.length === 0) return (
    <div style={{ display: 'flex', gap: '6px', alignItems: 'baseline' }}>
      <span style={{ fontSize: '11px', color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em', minWidth: '80px', flexShrink: 0 }}>{label}</span>
      <span style={{ fontSize: '12px', color: 'var(--muted)', fontStyle: 'italic' }}>—</span>
    </div>
  )
  return (
    <div style={{ display: 'flex', gap: '6px', alignItems: 'baseline', flexWrap: 'wrap' }}>
      <span style={{ fontSize: '11px', color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em', minWidth: '80px', flexShrink: 0 }}>{label}</span>
      <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
        {items.map(item => (
          <span key={item} style={{ fontSize: '11px', fontFamily: "'IBM Plex Mono', monospace", padding: '1px 6px', borderRadius: '3px', background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border)', color: 'var(--text)' }}>
            {item}
          </span>
        ))}
      </div>
    </div>
  )
}

function DefinitionRow({ def, onClick }: { def: TaskDefinitionFull; onClick: () => void }) {
  const name = def.display_name || def.task_name
  const date = new Date(def.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
  return (
    <li onClick={onClick} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '7px 10px', borderRadius: '5px', cursor: 'pointer', border: '1px solid transparent', transition: 'background 0.1s, border-color 0.1s' }}
      onMouseEnter={e => { (e.currentTarget as HTMLLIElement).style.background = 'rgba(129,140,248,0.08)'; (e.currentTarget as HTMLLIElement).style.borderColor = 'rgba(129,140,248,0.2)' }}
      onMouseLeave={e => { (e.currentTarget as HTMLLIElement).style.background = 'transparent'; (e.currentTarget as HTMLLIElement).style.borderColor = 'transparent' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
        <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--lavender)', flexShrink: 0, boxShadow: '0 0 6px rgba(129,140,248,0.5)' }} />
        <span style={{ fontSize: '13px', fontWeight: 500, color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{name}</span>
      </div>
      <span className="meta-date" style={{ flexShrink: 0, marginLeft: '12px' }}>{date}</span>
    </li>
  )
}

// ---------------------------------------------------------------------------
// Legacy toolkit card (HANDSHAKE-registered)
// ---------------------------------------------------------------------------

function LegacyToolkitRow({ toolkit }: { toolkit: ToolkitRead }) {
  const stateCount = (toolkit.states ?? []).length
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 12px', background: 'rgba(0,0,0,0.15)', borderRadius: '6px', border: '1px solid var(--border)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: '13px', color: 'var(--text)' }}>{toolkit.name}</span>
        <span className="badge" style={{ fontSize: '10px', color: 'var(--muted)', borderColor: 'var(--border)' }}>legacy</span>
        <span style={{ fontSize: '11px', color: 'var(--muted)' }}>{stateCount} states</span>
        {toolkit.pilot_origins.map(p => (
          <span key={p} className="meta-pill" style={{ fontSize: '10px' }}>{p}</span>
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Backend-authored toolkit card
// ---------------------------------------------------------------------------

function BackendToolkitCard({ toolkit, definitions, onNewDefinition, onOpenDefinition, creating, onEdit }: {
  toolkit: ToolkitRead
  definitions: TaskDefinitionFull[]
  onNewDefinition: (tk: ToolkitRead) => void
  onOpenDefinition: (id: number) => void
  creating: boolean
  onEdit: (tk: ToolkitRead) => void
}) {
  const stateNames = toolkit.states ?? []
  const flagKeys = Object.keys(toolkit.flags ?? {})
  const paramKeys = Object.keys(toolkit.params_schema ?? {})
  return (
    <div className="card fade-in-item" style={{ borderLeft: '3px solid rgba(129,140,248,0.5)', display: 'flex', flexDirection: 'column', gap: '0' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
            <h2 style={{ margin: 0, fontFamily: "'IBM Plex Mono', monospace", fontSize: '1rem', fontWeight: 600, color: 'var(--text)' }}>{toolkit.name}</h2>
            {definitions.length > 0 && <span className="badge" style={{ fontSize: '11px', color: 'var(--lavender)', borderColor: 'rgba(129,140,248,0.3)' }}>{definitions.length} {definitions.length === 1 ? 'definition' : 'definitions'}</span>}
            {toolkit.locked_state_source && <span className="meta-pill" style={{ fontSize: '10px' }}>{toolkit.locked_state_source}</span>}
          </div>
          {toolkit.pilot_origins.length > 0 && (
            <div style={{ display: 'flex', gap: '4px', marginTop: '5px', flexWrap: 'wrap' }}>
              {toolkit.pilot_origins.map(p => <span key={p} className="meta-pill" style={{ fontSize: '11px' }}>{p}</span>)}
            </div>
          )}
        </div>
      </div>
      <div style={{ background: 'rgba(0,0,0,0.2)', borderRadius: '6px', padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '12px', border: '1px solid var(--border)' }}>
        <MetaChips label="States" items={stateNames} />
        <MetaChips label="Flags" items={flagKeys} />
        <MetaChips label="Params" items={paramKeys} />
        {(toolkit.hardware_module_ids?.length ?? 0) > 0 && (
          <div style={{ display: 'flex', gap: '6px', alignItems: 'baseline' }}>
            <span style={{ fontSize: '11px', color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em', minWidth: '80px', flexShrink: 0 }}>HW Modules</span>
            <span style={{ fontSize: '12px', color: 'var(--text)' }}>{toolkit.hardware_module_ids.length} module{toolkit.hardware_module_ids.length !== 1 ? 's' : ''}</span>
          </div>
        )}
      </div>
      <div style={{ marginBottom: '12px' }}>
        <div style={{ fontSize: '11px', color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '6px', paddingLeft: '2px' }}>Task Definitions</div>
        {definitions.length === 0 ? (
          <p className="muted" style={{ margin: '4px 0 0 2px', fontSize: '12px', fontStyle: 'italic' }}>No definitions yet — create one below.</p>
        ) : (
          <ul style={{ margin: 0, padding: 0 }}>{definitions.map(def => <DefinitionRow key={def.id} def={def} onClick={() => onOpenDefinition(def.id)} />)}</ul>
        )}
      </div>
      <div style={{ display: 'flex', gap: '8px' }}>
        <button className="button-primary" style={{ fontSize: '13px' }} disabled={creating} onClick={() => onNewDefinition(toolkit)}>
          {creating ? 'Creating…' : '+ New Task Definition'}
        </button>
        <button className="button-secondary" style={{ fontSize: '13px' }} onClick={() => onEdit(toolkit)}>
          Edit
        </button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// 5-step creation modal
// ---------------------------------------------------------------------------

const TRACKER_TYPES = ['Counter_Tracker', 'Boolean_Tracker', 'Trial_Tracker', 'Tracker']

function CreationModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
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
  const createMutation = useMutation({
    mutationFn: (payload: BackendToolkitCreatePayload) => createBackendToolkit(payload),
    onSuccess: () => { onCreated() },
    onError: (e: Error) => setError(e.message),
  })

  const fileEntry = selectedFile ? lockedStates?.by_file[selectedFile] : null
  const availableStates = fileEntry?.state_names ?? []
  const fileOptions = Object.keys(lockedStates?.by_file ?? {})

  const handleFileSelect = (fname: string) => {
    setSelectedFile(fname)
    // Select all states by default
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

  const handleCreate = () => {
    setError('')
    createMutation.mutate({
      name: name.trim(),
      locked_state_source: selectedFile,
      selected_states: selectedStates,
      hardware_module_ids: selectedModuleIds,
      flags,
      params_schema: params,
    })
  }

  const canNext1 = name.trim().length > 0
  const canCreate = true

  return (
    <div className="modal-overlay" style={{ alignItems: 'flex-start', paddingTop: '10vh' }}>
      <div className="modal" style={{ width: '640px', maxHeight: '80vh', display: 'flex', flexDirection: 'column' }}>
        <div className="modal-header">
          <span className="modal-title">New Backend Toolkit — Step {step} of 5</span>
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
              {!selectedFile ? (
                <p style={{ fontSize: '12px', color: 'var(--muted)', fontStyle: 'italic' }}>
                  No task source file selected — toolkit will run the base <code>mics_task</code> class with no locked states.
                </p>
              ) : (
                <>
                  <p style={{ fontSize: '12px', color: 'var(--muted)', marginBottom: '8px' }}>Select states from {selectedFile}</p>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                    {availableStates.map(s => (
                      <label key={s} style={{ display: 'grid', gridTemplateColumns: '20px 1fr', alignItems: 'center', gap: '8px', fontSize: '13px', cursor: 'pointer', padding: '6px 8px', borderRadius: '4px', background: selectedStates.includes(s) ? 'rgba(129,140,248,0.1)' : 'transparent', border: '1px solid transparent', transition: 'background 0.1s', borderColor: selectedStates.includes(s) ? 'rgba(129,140,248,0.25)' : 'transparent' }}>
                        <input type="checkbox" checked={selectedStates.includes(s)} onChange={() => toggleState(s)} style={{ margin: 0 }} />
                        <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontWeight: 500 }}>{s}</span>
                      </label>
                    ))}
                  </div>
                </>
              )}
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
          {step > 1 && <button className="button-secondary" onClick={() => setStep(s => s - 1)}>Back</button>}
          {step < 5 && <button className="button-primary" onClick={() => setStep(s => s + 1)} disabled={step === 1 && !canNext1}>Next</button>}
          {step === 5 && <button className="button-primary" onClick={handleCreate} disabled={!canCreate || createMutation.isPending}>{createMutation.isPending ? 'Creating…' : 'Create Toolkit'}</button>}
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function Toolkits() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [showCreationModal, setShowCreationModal] = useState(false)
  const [editingToolkit, setEditingToolkit] = useState<ToolkitRead | null>(null)

  const { data: toolkits, isLoading: loadingToolkits, isError: errorToolkits } = useQuery({
    queryKey: ['toolkits'], queryFn: getToolkits,
  })
  const { data: taskDefs } = useQuery({
    queryKey: ['task-definitions'], queryFn: getTaskDefinitions,
  })

  const createMutation = useMutation({
    mutationFn: createTaskDefinition,
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ['task-definitions'] })
      qc.invalidateQueries({ queryKey: ['toolkits'] })
      navigate(`/task-editor/${result.id}`)
    },
    onError: (e: Error) => alert(`Failed to create task definition: ${e.message}`),
  })

  const handleNewDefinition = (toolkit: ToolkitRead) => {
    createMutation.mutate({
      display_name: toolkit.name + ' FDA',
      toolkit_name: toolkit.name,
      fda_json: emptySkeletonFor(toolkit),
    })
  }

  const allToolkits = toolkits ?? []
  const legacyToolkits = allToolkits.filter(t => !t.is_backend_authored)
  const backendToolkits = allToolkits.filter(t => t.is_backend_authored)

  return (
    <div className="container" style={{ paddingTop: '1rem' }}>
      <div style={{ marginBottom: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 700, fontFamily: "'IBM Plex Sans', sans-serif", color: 'var(--text)' }}>Toolkits</h1>
          <p className="muted" style={{ marginTop: '4px', fontSize: '13px' }}>
            Backend-authored toolkits are created here. Legacy toolkits are registered automatically from HANDSHAKE.
          </p>
        </div>
        <button className="button-primary" style={{ fontSize: '13px', flexShrink: 0 }} onClick={() => setShowCreationModal(true)}>
          + New Toolkit
        </button>
      </div>

      {loadingToolkits ? (
        <p className="muted">Loading toolkits…</p>
      ) : errorToolkits ? (
        <p className="error">Failed to load toolkits.</p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Backend-authored section */}
          <div>
            <div style={{ fontSize: '11px', color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '10px' }}>Backend-Authored</div>
            {backendToolkits.length === 0 ? (
              <div className="card" style={{ borderLeft: '3px solid var(--border)' }}>
                <p className="muted" style={{ margin: 0, fontSize: '13px' }}>No backend-authored toolkits yet. Click "+ New Toolkit" to create one.</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {backendToolkits.map(toolkit => {
                  const defs = (taskDefs ?? []).filter(d => d.toolkit_name === toolkit.name && d.fda_json !== null)
                  return (
                    <BackendToolkitCard
                      key={toolkit.id}
                      toolkit={toolkit}
                      definitions={defs}
                      onNewDefinition={handleNewDefinition}
                      onOpenDefinition={id => navigate(`/task-editor/${id}`)}
                      creating={createMutation.isPending}
                      onEdit={setEditingToolkit}
                    />
                  )
                })}
              </div>
            )}
          </div>

          {/* Legacy section */}
          {legacyToolkits.length > 0 && (
            <div>
              <div style={{ fontSize: '11px', color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '10px' }}>Legacy (HANDSHAKE-registered)</div>
              <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {legacyToolkits.map(t => <LegacyToolkitRow key={t.id} toolkit={t} />)}
              </div>
            </div>
          )}
        </div>
      )}

      {showCreationModal && (
        <CreationModal
          onClose={() => setShowCreationModal(false)}
          onCreated={() => {
            setShowCreationModal(false)
            qc.invalidateQueries({ queryKey: ['toolkits'] })
          }}
        />
      )}
      {editingToolkit && (
        <EditModal
          toolkit={editingToolkit}
          onClose={() => setEditingToolkit(null)}
          onSaved={() => setEditingToolkit(null)}
        />
      )}
    </div>
  )
}
