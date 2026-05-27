import { useState, useEffect } from 'react'
import type { FdaAction, ToolkitRead, HardwareModule, AstMethod } from '../types'
import { getHardwareModuleMethods } from '../api/hardware_modules'
import ArgInput from './ArgInput'
import IfActionEditor from './IfActionEditor'

// Module-level method cache: keyed by "moduleId/versionStamp" to stay version-aware.
// versionStamp changes whenever the version assignment for the task def changes.
const METHOD_CACHE: Record<string, AstMethod[]> = {}

// ── Action type metadata ────────────────────────────────────────────────────

const TYPE_COLORS: Record<string, string> = {
  hardware: '#3b82f6',
  trial:    '#0ea5e9',   // sky blue — distinct from flag amber
  flag:     '#f59e0b',
  method:   '#a78bfa',
  if:       '#22c55e',
  special:  '#94a3b8',
}

const TYPE_LABELS: Record<string, string> = {
  hardware: 'HARDWARE',
  trial:    'TRIAL CTR',
  flag:     'FLAG',
  method:   'METHOD',
  if:       'IF',
  special:  'SPECIAL',
}

// ── Tracker method tables ────────────────────────────────────────────────────

interface TrackerMethod {
  name: string
  hasArg: boolean
  description: string
}

const TRACKER_METHODS: Record<string, TrackerMethod[]> = {
  Counter_Tracker: [
    { name: 'increment', hasArg: false, description: 'Add 1 to this counter' },
    { name: 'decrement', hasArg: false, description: 'Subtract 1 from this counter' },
    { name: 'reset',     hasArg: false, description: 'Reset to its starting value' },
    { name: 'set',       hasArg: true,  description: 'Set to an exact value' },
  ],
  Boolean_Tracker: [
    { name: 'set',    hasArg: true,  description: 'Set to an exact value' },
    { name: 'toggle', hasArg: false, description: 'Flip between true and false' },
  ],
  Trial_Tracker: [
    { name: 'increment', hasArg: false, description: 'Increment trial count (dispatches INC_TRIAL_COUNTER to orchestrator)' },
    { name: 'set',       hasArg: true,  description: 'Set trial count to an exact value' },
  ],
  Tracker: [
    { name: 'increment', hasArg: false, description: 'Add 1 to this tracker' },
    { name: 'set',       hasArg: true,  description: 'Set to any value' },
  ],
}

const TIMER_METHODS: TrackerMethod[] = [
  { name: 'start', hasArg: true,  description: 'Start counting down with the given duration' },
  { name: 'stop',  hasArg: false, description: 'Stop the timer (does not reset)' },
  { name: 'reset', hasArg: false, description: 'Reset the timer to zero' },
  { name: 'set',   hasArg: true,  description: 'Set the duration without starting' },
]

function getTrackerMethods(trackerType: string): TrackerMethod[] {
  return TRACKER_METHODS[trackerType] ?? TRACKER_METHODS['Tracker']
}

function defaultArgForTrackerType(trackerType: string): unknown {
  return trackerType === 'Boolean_Tracker' ? false : 0
}

function isTimerModule(mod: HardwareModule): boolean {
  return mod.lib_filename === 'timer.py'
}

// ── Style helpers ────────────────────────────────────────────────────────────

const labelStyle: React.CSSProperties = {
  fontSize: '11px',
  color: 'var(--muted)',
  display: 'block',
  marginBottom: '2px',
}

function cardStyle(type: string): React.CSSProperties {
  const color = TYPE_COLORS[type] ?? '#94a3b8'
  const rgb = hexToRgb(color)
  return {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    padding: '8px',
    background: rgb ? `rgba(${rgb}, 0.06)` : 'rgba(255,255,255,0.03)',
    borderRadius: '6px',
    border: `1px solid ${rgb ? `rgba(${rgb}, 0.25)` : 'var(--border)'}`,
    borderLeft: `3px solid ${color}`,
  }
}

function hexToRgb(hex: string): string | null {
  const m = /^#([0-9a-f]{6})$/i.exec(hex)
  if (!m) return null
  const n = parseInt(m[1], 16)
  return `${(n >> 16) & 0xff}, ${(n >> 8) & 0xff}, ${n & 0xff}`
}

function typeChipStyle(type: string): React.CSSProperties {
  const color = TYPE_COLORS[type] ?? '#94a3b8'
  return {
    display: 'inline-block',
    padding: '1px 6px',
    borderRadius: '3px',
    fontSize: '9px',
    fontWeight: 700,
    fontFamily: "'IBM Plex Mono', monospace",
    letterSpacing: '0.08em',
    background: `${color}22`,
    color,
    border: `1px solid ${color}44`,
  }
}

// ── Props ────────────────────────────────────────────────────────────────────

interface Props {
  action: FdaAction
  toolkit: ToolkitRead | null
  hwModules: HardwareModule[]
  taskDefId?: number
  versionStamp?: string
  onChange: (updated: FdaAction) => void
}

// ── Component ────────────────────────────────────────────────────────────────

export default function ActionEditor({ action, toolkit, hwModules, taskDefId, versionStamp, onChange }: Props) {
  const isBackendAuthored = toolkit?.is_backend_authored ?? false

  const [methods, setMethods] = useState<AstMethod[]>([])
  const [methodsLoading, setMethodsLoading] = useState(false)

  const flagKeys = Object.keys(toolkit?.flags ?? {})
  // Split flags: trial counter flags vs regular flags
  const trialFlagKeys  = flagKeys.filter(k => toolkit?.flags?.[k]?.tracker_type === 'Trial_Tracker')
  const regularFlagKeys = flagKeys.filter(k => toolkit?.flags?.[k]?.tracker_type !== 'Trial_Tracker')
  const callableMethods = toolkit?.callable_methods ?? []

  const toolkitModules = hwModules.filter(m => toolkit?.hardware_module_ids?.includes(m.id))

  const update = (patch: Partial<FdaAction>) => onChange({ ...action, ...patch })

  // ── Normalise stored FDA types for display ───────────────────────────────
  // type:timer in FDA → show as hardware (timer is a hw module sub-type)
  // type:flag with Trial_Tracker ref → show as trial
  function effectiveUiType(): string {
    if (action.type === 'timer') return 'hardware'
    if (action.type === 'flag' && trialFlagKeys.includes(action.ref ?? '')) return 'trial'
    return action.type
  }
  const uiType = effectiveUiType()

  // ── Method fetching ──────────────────────────────────────────────────────

  async function fetchMethods(moduleId: number): Promise<void> {
    const key = `${moduleId}/${versionStamp ?? taskDefId ?? 'active'}`
    if (METHOD_CACHE[key]) {
      setMethods(METHOD_CACHE[key])
      return
    }
    setMethodsLoading(true)
    try {
      const res = await getHardwareModuleMethods(moduleId, taskDefId)
      const pub = res.methods.filter(m => !m.name.startsWith('_'))
      METHOD_CACHE[key] = pub
      setMethods(pub)
    } catch {
      setMethods([])
    } finally {
      setMethodsLoading(false)
    }
  }

  function selectedHwModule(): HardwareModule | undefined {
    return toolkitModules.find(m => m.name === (action.ref ?? ''))
  }

  // Re-fetch when ref, hwModules, or versionStamp changes.
  // versionStamp changes when the user saves a different version in the version modal,
  // causing a cache miss and a fresh fetch from the correct version's AST.
  useEffect(() => {
    if ((action.type !== 'hardware' && action.type !== 'timer') || !isBackendAuthored) return
    const mod = selectedHwModule()
    if (mod && !isTimerModule(mod)) fetchMethods(mod.id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [action.type, action.ref, isBackendAuthored, hwModules, versionStamp])

  // NOTE: Intentionally no auto-reset here. If the stored method isn't in the current
  // version's methods list, we keep it as-is and let the warning badge signal the issue.
  // Auto-resetting would silently corrupt the user's task definition.

  // ── Type change handler ──────────────────────────────────────────────────

  function handleTypeChange(t: string) {
    if (t === 'hardware') {
      const firstMod = isBackendAuthored ? (toolkitModules[0]?.name ?? '') : (Object.keys(toolkit?.semantic_hardware ?? {})[0] ?? '')
      const isTimer = toolkitModules[0] ? isTimerModule(toolkitModules[0]) : false
      onChange({ type: isTimer ? 'timer' : 'hardware', ref: firstMod, method: isTimer ? 'start' : '', args: [] })
    } else if (t === 'trial') {
      onChange({ type: 'flag', ref: trialFlagKeys[0] ?? '', method: 'increment', args: [] })
    } else if (t === 'flag') {
      const firstFlag = regularFlagKeys[0] ?? ''
      const trackerType = toolkit?.flags?.[firstFlag]?.tracker_type ?? 'Counter_Tracker'
      const firstMethodDef = getTrackerMethods(trackerType)[0]
      const firstMethod = firstMethodDef?.name ?? 'increment'
      const args = firstMethodDef?.hasArg ? [defaultArgForTrackerType(trackerType)] : []
      onChange({ type: 'flag', ref: firstFlag, method: firstMethod, args })
    } else if (t === 'if') {
      onChange({ type: 'if', condition: undefined, then: [], else: undefined })
    } else if (t === 'method') {
      onChange({ type: 'method', ref: callableMethods[0] ?? '', args: [] })
    } else {
      onChange({ type: t as FdaAction['type'], ref: '', args: [] })
    }
  }

  function handleModuleChange(modName: string) {
    const mod = toolkitModules.find(m => m.name === modName)
    const isTimer = mod ? isTimerModule(mod) : false
    update({ ref: modName, type: isTimer ? 'timer' : 'hardware', method: isTimer ? 'start' : '', args: [] })
    setMethods([])
    if (mod && !isTimer) fetchMethods(mod.id)
  }

  function handleFlagChange(flagName: string) {
    const trackerType = toolkit?.flags?.[flagName]?.tracker_type ?? 'Counter_Tracker'
    const firstMethodDef = getTrackerMethods(trackerType)[0]
    const firstMethod = firstMethodDef?.name ?? 'increment'
    const args = firstMethodDef?.hasArg ? [defaultArgForTrackerType(trackerType)] : []
    update({ ref: flagName, method: firstMethod, args })
  }

  function currentMethodArgs(): AstMethod['args'] {
    if (!methods.length || !action.method) return []
    return methods.find(m => m.name === action.method)?.args ?? []
  }

  // Legacy semantic hardware keys
  const semanticKeys = Object.keys(toolkit?.semantic_hardware ?? {})

  // Determine if the current hardware module is a timer
  const currentMod = selectedHwModule()
  const currentIsTimer = currentMod ? isTimerModule(currentMod) : (action.type === 'timer')

  const argList = currentMethodArgs()

  // Current timer method meta
  const timerMethodDef = TIMER_METHODS.find(m => m.name === (action.method ?? 'start'))
  const timerNeedsArg = timerMethodDef?.hasArg ?? false

  // Current flag method meta (for regular flags)
  const flagTrackerType = action.type === 'flag'
    ? (toolkit?.flags?.[action.ref ?? '']?.tracker_type ?? 'Counter_Tracker')
    : 'Counter_Tracker'
  const flagMethodDefs = getTrackerMethods(flagTrackerType)
  const currentFlagMethodDef = flagMethodDefs.find(m => m.name === action.method)
  const flagMethodNeedsArg = currentFlagMethodDef?.hasArg ?? false

  // Auto-initialize args for flag actions loaded from DB where args is empty but method needs one.
  // The display default in ArgInput is only cosmetic; args stays [] unless we write it here.
  useEffect(() => {
    if (action.type !== 'flag' || uiType !== 'flag') return
    if (!flagMethodNeedsArg || (action.args ?? []).length > 0) return
    update({ args: [defaultArgForTrackerType(flagTrackerType)] })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [action.method, action.ref, flagMethodNeedsArg])

  // ── Legacy special action ────────────────────────────────────────────────
  if (action.type === 'special') {
    return (
      <div style={{ ...cardStyle('special'), flexDirection: 'row', alignItems: 'center', gap: '8px' }}>
        <span style={typeChipStyle('special')}>LEGACY</span>
        <span style={{ fontSize: '11px', color: '#f59e0b' }}>
          Legacy special action: {action.action} — replace with a Trial_Tracker flag increment.
        </span>
      </div>
    )
  }

  return (
    <div style={cardStyle(uiType)}>
      {/* Header: colored chip + type selector */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span style={typeChipStyle(uiType)} title="What kind of action executes when this state is entered?">
          {TYPE_LABELS[uiType] ?? uiType.toUpperCase()}
        </span>
        <select
          value={uiType}
          onChange={e => handleTypeChange(e.target.value)}
          style={{ fontSize: '11px', flex: 1 }}
          title="What kind of action executes when this state is entered?"
        >
          <option value="hardware">hardware</option>
          <option value="trial">trial counter</option>
          <option value="flag">flag</option>
          <option value="method">method</option>
          <option value="if">if</option>
        </select>
      </div>

      {/* ── Hardware action (includes timer modules) ─────────────────────── */}
      {(action.type === 'hardware' || action.type === 'timer') && (
        <>
          {isBackendAuthored ? (
            <div>
              <label style={labelStyle} title="Which physical device should respond?">Device ⓘ</label>
              {toolkitModules.length > 0 ? (
                <select
                  value={action.ref ?? ''}
                  onChange={e => handleModuleChange(e.target.value)}
                  style={{ width: '100%' }}
                >
                  {!toolkitModules.find(m => m.name === action.ref) && action.ref && (
                    <option value={action.ref}>{action.ref}</option>
                  )}
                  {toolkitModules.map(m => (
                    <option key={m.id} value={m.name}>
                      {m.display_name ?? m.name}{m.lib_filename === 'timer.py' ? ' (timer)' : ''}
                    </option>
                  ))}
                </select>
              ) : (
                <input type="text" value={action.ref ?? ''} onChange={e => update({ ref: e.target.value })} placeholder="module name" style={{ width: '100%' }} />
              )}
            </div>
          ) : (
            <div>
              <label style={labelStyle} title="Hardware ref from toolkit semantic_hardware.">Hardware ref ⓘ</label>
              {semanticKeys.length > 0 ? (
                <select value={action.ref ?? ''} onChange={e => update({ ref: e.target.value })} style={{ width: '100%' }}>
                  {!semanticKeys.includes(action.ref ?? '') && <option value={action.ref ?? ''}>{action.ref ?? '—'}</option>}
                  {semanticKeys.map(k => <option key={k} value={k}>{k}</option>)}
                </select>
              ) : (
                <input type="text" value={action.ref ?? ''} onChange={e => update({ ref: e.target.value })} style={{ width: '100%' }} />
              )}
            </div>
          )}

          {/* Method dropdown */}
          <div>
            <label style={labelStyle} title="What the device should do.">Action ⓘ</label>
            {currentIsTimer ? (
              /* Timer: fixed method list */
              <select value={action.method ?? 'start'} onChange={e => update({ method: e.target.value, args: [] })} style={{ width: '100%' }}>
                {TIMER_METHODS.map(m => <option key={m.name} value={m.name} title={m.description}>{m.name}</option>)}
              </select>
            ) : isBackendAuthored ? (
              methodsLoading ? (
                <select disabled style={{ width: '100%' }}><option>Loading…</option></select>
              ) : methods.length > 0 ? (
                <select value={action.method ?? ''} onChange={e => update({ method: e.target.value, args: [] })} style={{ width: '100%' }}>
                  {action.method && !methods.find(m => m.name === action.method) && (
                    <option value={action.method} style={{ color: '#ef4444' }}>
                      ⚠ {action.method} (not in this version)
                    </option>
                  )}
                  {methods.map(m => <option key={m.name} value={m.name}>{m.name}</option>)}
                </select>
              ) : (
                <input type="text" value={action.method ?? ''} onChange={e => update({ method: e.target.value })} placeholder="method name" style={{ width: '100%' }} />
              )
            ) : (
              <input type="text" value={action.method ?? ''} onChange={e => update({ method: e.target.value })} style={{ width: '100%' }} />
            )}
          </div>

          {/* Timer duration arg */}
          {currentIsTimer && timerNeedsArg && (
            <div>
              <label style={labelStyle}>Duration</label>
              <ArgInput value={(action.args ?? [])[0] ?? 500} toolkit={toolkit} annotation="float" onChange={v => update({ args: [v] })} />
            </div>
          )}

          {/* AST args (non-timer backend-authored) */}
          {isBackendAuthored && !currentIsTimer && argList.map((arg, i) => (
            <div key={i}>
              <label
                style={labelStyle}
                title={`${arg.annotation ?? 'unknown type'}${arg.default !== undefined ? ` — Default: ${arg.default}` : ''}`}
              >
                {arg.name} {arg.annotation ? `(${arg.annotation})` : ''} ⓘ
              </label>
              <ArgInput
                value={(action.args ?? [])[i] ?? (arg.default !== undefined ? arg.default : 0)}
                toolkit={toolkit}
                annotation={arg.annotation ?? null}
                onChange={v => {
                  const newArgs = [...(action.args ?? [])]
                  newArgs[i] = v
                  update({ args: newArgs })
                }}
              />
            </div>
          ))}

          {/* Legacy: single arg */}
          {!isBackendAuthored && !currentIsTimer && (
            <div>
              <label style={labelStyle}>Arg</label>
              <ArgInput value={(action.args ?? [])[0] ?? 1} toolkit={toolkit} annotation={null} onChange={v => update({ args: [v] })} />
            </div>
          )}
        </>
      )}

      {/* ── Trial counter action ─────────────────────────────────────────── */}
      {action.type === 'flag' && uiType === 'trial' && (
        <>
          <div>
            <label style={labelStyle} title="Which Trial_Tracker flag to update? increment dispatches INC_TRIAL_COUNTER to the orchestrator.">
              Trial counter ⓘ
            </label>
            {trialFlagKeys.length === 1 ? (
              <div style={{ fontSize: '12px', fontFamily: 'monospace', color: 'var(--text)' }}>
                {trialFlagKeys[0]}
              </div>
            ) : trialFlagKeys.length > 1 ? (
              <select value={action.ref || trialFlagKeys[0]} onChange={e => update({ ref: e.target.value, method: 'increment', args: [] })} style={{ width: '100%' }}>
                {trialFlagKeys.map(k => <option key={k} value={k}>{k}</option>)}
              </select>
            ) : (
              <input type="text" value={action.ref ?? ''} onChange={e => update({ ref: e.target.value })} placeholder="trial flag name" style={{ width: '100%' }} />
            )}
          </div>
          <div>
            <label style={labelStyle}>Operation</label>
            <select value={action.method ?? 'increment'} onChange={e => update({ method: e.target.value, args: [] })} style={{ width: '100%' }}>
              {TRACKER_METHODS['Trial_Tracker'].map(m => (
                <option key={m.name} value={m.name} title={m.description}>{m.name}</option>
              ))}
            </select>
          </div>
          {action.method === 'set' && (
            <div>
              <label style={labelStyle}>Value</label>
              <ArgInput value={(action.args ?? [])[0] ?? 0} toolkit={toolkit} annotation="int" onChange={v => update({ args: [v] })} />
            </div>
          )}
        </>
      )}

      {/* ── Flag action (Counter / Boolean / base Tracker — not Trial) ────── */}
      {action.type === 'flag' && uiType === 'flag' && (
        <>
          <div>
            <label style={labelStyle} title="Which counter, boolean, or value tracker to update?">Flag ⓘ</label>
            {regularFlagKeys.length > 0 ? (
              <select value={action.ref ?? ''} onChange={e => handleFlagChange(e.target.value)} style={{ width: '100%' }}>
                {!regularFlagKeys.includes(action.ref ?? '') && <option value={action.ref ?? ''}>{action.ref ?? '—'}</option>}
                {regularFlagKeys.map(k => (
                  <option key={k} value={k}>{k} ({toolkit?.flags?.[k]?.tracker_type ?? 'Tracker'})</option>
                ))}
              </select>
            ) : (
              <input type="text" value={action.ref ?? ''} onChange={e => update({ ref: e.target.value })} style={{ width: '100%' }} />
            )}
          </div>
          <div>
            <label style={labelStyle} title={currentFlagMethodDef?.description ?? ''}>Operation ⓘ</label>
            <select
              value={action.method ?? flagMethodDefs[0]?.name ?? ''}
              onChange={e => {
                const newMethodDef = flagMethodDefs.find(m => m.name === e.target.value)
                const args = newMethodDef?.hasArg ? [defaultArgForTrackerType(flagTrackerType)] : []
                update({ method: e.target.value, args })
              }}
              style={{ width: '100%' }}
            >
              {flagMethodDefs.map(m => <option key={m.name} value={m.name} title={m.description}>{m.name}</option>)}
            </select>
          </div>
          {flagMethodNeedsArg && (
            <div>
              <label style={labelStyle}>Value</label>
              <ArgInput
                value={(action.args ?? [])[0] ?? (flagTrackerType === 'Boolean_Tracker' ? false : 0)}
                toolkit={toolkit}
                annotation={flagTrackerType === 'Boolean_Tracker' ? 'bool' : null}
                onChange={v => update({ args: [v] })}
              />
            </div>
          )}
        </>
      )}

      {/* ── Method action ────────────────────────────────────────────────── */}
      {action.type === 'method' && (
        <>
          <div>
            <label style={labelStyle}>Method name</label>
            {callableMethods.length > 0 ? (
              <select value={action.ref ?? ''} onChange={e => update({ ref: e.target.value })} style={{ width: '100%' }}>
                {!callableMethods.includes(action.ref ?? '') && <option value={action.ref ?? ''}>{action.ref ?? '—'}</option>}
                {callableMethods.map(k => <option key={k} value={k}>{k}</option>)}
              </select>
            ) : (
              <input type="text" value={action.ref ?? ''} onChange={e => update({ ref: e.target.value })} placeholder="method name" style={{ width: '100%' }} />
            )}
          </div>
          {(action.args ?? []).map((arg, i) => (
            <div key={i}>
              <label style={labelStyle}>Arg {i + 1}</label>
              <ArgInput value={arg} toolkit={toolkit} annotation={null} onChange={v => {
                const newArgs = [...(action.args ?? [])]
                newArgs[i] = v
                update({ args: newArgs })
              }} />
            </div>
          ))}
        </>
      )}

      {/* ── If action ─────────────────────────────────────────────────────── */}
      {action.type === 'if' && (
        <IfActionEditor action={action} toolkit={toolkit} hwModules={hwModules} taskDefId={taskDefId} versionStamp={versionStamp} onChange={onChange} />
      )}
    </div>
  )
}
