import { useState, useEffect } from 'react'
import type { FdaAction, ToolkitRead, HardwareModule, AstMethod } from '../types'
import { getHardwareModuleMethods } from '../api/hardware_modules'
import ArgInput, { getParamKeys } from './ArgInput'
import IfActionEditor from './IfActionEditor'

// Module-level method cache: avoids re-fetching within the same session
const METHOD_CACHE: Record<number, AstMethod[]> = {}

// ── Action type metadata ────────────────────────────────────────────────────

const TYPE_COLORS: Record<string, string> = {
  hardware: '#3b82f6',
  flag: '#f59e0b',
  timer: '#14b8a6',
  method: '#a78bfa',
  if: '#22c55e',
  special: '#94a3b8',
}

const TYPE_LABELS: Record<string, string> = {
  hardware: 'HARDWARE',
  flag: 'FLAG',
  timer: 'TIMER',
  method: 'METHOD',
  if: 'IF',
  special: 'SPECIAL',
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
    { name: 'reset', hasArg: false, description: 'Reset to its starting value' },
    { name: 'set', hasArg: true, description: 'Set to an exact value' },
  ],
  Boolean_Tracker: [
    { name: 'set', hasArg: true, description: 'Set to an exact value' },
    { name: 'toggle', hasArg: false, description: 'Flip between true and false' },
  ],
  Trial_Tracker: [
    { name: 'increment', hasArg: false, description: 'Add 1 (dispatches INC_TRIAL_COUNTER to orchestrator)' },
    { name: 'set', hasArg: true, description: 'Set to an exact value' },
  ],
  Tracker: [
    { name: 'increment', hasArg: false, description: 'Add 1 to this counter' },
    { name: 'set', hasArg: true, description: 'Set to an exact value' },
  ],
}

const TIMER_METHOD_DESC: Record<string, string> = {
  start: 'Start counting down with the given duration',
  stop: 'Stop the timer (does not reset)',
  reset: 'Reset the timer to zero',
  set: 'Set the duration without starting',
}

function getTrackerMethods(trackerType: string): TrackerMethod[] {
  return TRACKER_METHODS[trackerType] ?? TRACKER_METHODS['Tracker']
}

function isTimerModule(mod: HardwareModule): boolean {
  // Primary signal: lib filename "timer.py" is not available here,
  // but class_name is a reasonable heuristic for now.
  // The plan says: class_name in ["Timer", "CountdownTimer"] OR lib filename == "timer.py"
  // Since we only have class_name here, use that as the signal.
  return mod.class_name === 'Timer' || mod.class_name === 'CountdownTimer'
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
  onChange: (updated: FdaAction) => void
}

// ── Component ────────────────────────────────────────────────────────────────

export default function ActionEditor({ action, toolkit, hwModules, onChange }: Props) {
  const isBackendAuthored = toolkit?.is_backend_authored ?? false

  // Hardware module state (for backend-authored toolkits)
  const [methods, setMethods] = useState<AstMethod[]>([])
  const [methodsLoading, setMethodsLoading] = useState(false)

  const flagKeys = Object.keys(toolkit?.flags ?? {})
  const callableMethods = toolkit?.callable_methods ?? []

  // Filter toolkit modules (those in toolkit.hardware_module_ids)
  const toolkitModules = hwModules.filter(m => toolkit?.hardware_module_ids?.includes(m.id))
  const timerModules = toolkitModules.filter(isTimerModule)
  const hwOnlyModules = toolkitModules.filter(m => !isTimerModule(m))

  // Legacy path: semantic hardware keys
  const semanticKeys = Object.keys(toolkit?.semantic_hardware ?? {})

  const update = (patch: Partial<FdaAction>) => onChange({ ...action, ...patch })

  // Fetch methods for the currently selected hardware module
  function selectedModule(ref: string): HardwareModule | undefined {
    return toolkitModules.find(m => m.name === ref)
  }

  async function fetchMethods(moduleId: number): Promise<void> {
    if (METHOD_CACHE[moduleId]) {
      setMethods(METHOD_CACHE[moduleId])
      return
    }
    setMethodsLoading(true)
    try {
      const res = await getHardwareModuleMethods(moduleId)
      // Filter out __init__ and private methods
      const pub = res.methods.filter(m => !m.name.startsWith('_'))
      METHOD_CACHE[moduleId] = pub
      setMethods(pub)
    } catch {
      setMethods([])
    } finally {
      setMethodsLoading(false)
    }
  }

  // Load methods when a hardware action's ref changes or component mounts with a ref
  useEffect(() => {
    if (action.type !== 'hardware' || !isBackendAuthored) return
    const mod = selectedModule(action.ref ?? '')
    if (mod) fetchMethods(mod.id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [action.type, action.ref, isBackendAuthored])

  // Type change handler
  function handleTypeChange(t: string) {
    const newType = t as FdaAction['type']
    if (newType === 'hardware') {
      const firstMod = isBackendAuthored ? (hwOnlyModules[0]?.name ?? '') : (semanticKeys[0] ?? '')
      onChange({ type: newType, ref: firstMod, method: '', args: [] })
    } else if (newType === 'flag') {
      const firstFlag = flagKeys[0] ?? ''
      const trackerType = toolkit?.flags?.[firstFlag]?.tracker_type ?? 'Counter_Tracker'
      const firstMethod = getTrackerMethods(trackerType)[0]?.name ?? 'increment'
      onChange({ type: newType, ref: firstFlag, method: firstMethod, args: [] })
    } else if (newType === 'timer') {
      const firstTimer = timerModules[0]?.name ?? ''
      onChange({ type: newType, ref: firstTimer, method: 'start', args: [] })
    } else if (newType === 'if') {
      onChange({ type: newType, condition: undefined, then: [], else: undefined })
    } else if (newType === 'method') {
      onChange({ type: newType, ref: callableMethods[0] ?? '', args: [] })
    } else {
      onChange({ type: newType, ref: '', args: [] })
    }
  }

  // Handle module selection change for hardware actions
  function handleModuleChange(modName: string) {
    const mod = toolkitModules.find(m => m.name === modName)
    update({ ref: modName, method: '', args: [] })
    setMethods([])
    if (mod) fetchMethods(mod.id)
  }

  // Handle flag change — auto-update method to first valid for tracker type
  function handleFlagChange(flagName: string) {
    const trackerType = toolkit?.flags?.[flagName]?.tracker_type ?? 'Counter_Tracker'
    const firstMethod = getTrackerMethods(trackerType)[0]?.name ?? 'increment'
    update({ ref: flagName, method: firstMethod, args: [] })
  }

  // Current method args from AST (for hardware actions)
  function currentMethodArgs(): AstMethod['args'] {
    if (!methods.length || !action.method) return []
    const m = methods.find(m => m.name === action.method)
    return m?.args ?? []
  }

  // Auto-select first method when methods load
  useEffect(() => {
    if (action.type !== 'hardware' || !isBackendAuthored || !methods.length) return
    if (!action.method || !methods.find(m => m.name === action.method)) {
      update({ method: methods[0]?.name ?? '', args: [] })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [methods])

  // ── Legacy special action read-only chip ──────────────────────────────────
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

  const flagTrackerType = action.type === 'flag' && action.ref
    ? (toolkit?.flags?.[action.ref]?.tracker_type ?? 'Counter_Tracker')
    : 'Counter_Tracker'
  const flagMethodDefs = getTrackerMethods(flagTrackerType)
  const currentFlagMethodDef = flagMethodDefs.find(m => m.name === action.method)
  const flagMethodNeedsArg = currentFlagMethodDef?.hasArg ?? false

  const argList = currentMethodArgs()

  return (
    <div style={cardStyle(action.type)}>
      {/* Header row: colored chip + type selector */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span
          style={typeChipStyle(action.type)}
          title="What kind of action executes when this state is entered?"
        >
          {TYPE_LABELS[action.type] ?? action.type.toUpperCase()}
        </span>
        <select
          value={action.type}
          onChange={e => handleTypeChange(e.target.value)}
          style={{ fontSize: '11px', flex: 1 }}
          title="What kind of action executes when this state is entered?"
        >
          <option value="hardware">hardware</option>
          <option value="flag">flag</option>
          <option value="timer">timer</option>
          <option value="method">method</option>
          <option value="if">if</option>
          {/* Render special option only if current action is special (legacy read-only handled above) */}
        </select>
      </div>

      {/* ── Hardware action ─────────────────────────────────────────────── */}
      {action.type === 'hardware' && (
        <>
          {isBackendAuthored ? (
            /* Backend-authored: module picker from toolkit.hardware_module_ids */
            <div>
              <label
                style={labelStyle}
                title="Which physical device should respond? Devices come from the toolkit's hardware module list."
              >
                Device ⓘ
              </label>
              {hwOnlyModules.length > 0 ? (
                <select
                  value={action.ref ?? ''}
                  onChange={e => handleModuleChange(e.target.value)}
                  style={{ width: '100%' }}
                >
                  {!hwOnlyModules.find(m => m.name === action.ref) && action.ref && (
                    <option value={action.ref}>{action.ref}</option>
                  )}
                  {hwOnlyModules.map(m => (
                    <option key={m.id} value={m.name}>{m.display_name ?? m.name}</option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  value={action.ref ?? ''}
                  onChange={e => update({ ref: e.target.value })}
                  placeholder="module name"
                  style={{ width: '100%' }}
                />
              )}
            </div>
          ) : (
            /* Legacy: semantic_hardware dropdown */
            <div>
              <label
                style={labelStyle}
                title="Which physical device should respond? Devices come from the toolkit's semantic hardware list."
              >
                Hardware ref ⓘ
              </label>
              {semanticKeys.length > 0 ? (
                <select
                  value={action.ref ?? ''}
                  onChange={e => update({ ref: e.target.value })}
                  style={{ width: '100%' }}
                >
                  {!semanticKeys.includes(action.ref ?? '') && (
                    <option value={action.ref ?? ''}>{action.ref ?? '—'}</option>
                  )}
                  {semanticKeys.map(k => <option key={k} value={k}>{k}</option>)}
                </select>
              ) : (
                <input
                  type="text"
                  value={action.ref ?? ''}
                  onChange={e => update({ ref: e.target.value })}
                  style={{ width: '100%' }}
                />
              )}
            </div>
          )}

          <div>
            <label
              style={labelStyle}
              title="What the device should do. Options come from the hardware library's Python class methods."
            >
              Action ⓘ
            </label>
            {isBackendAuthored ? (
              methodsLoading ? (
                <select disabled style={{ width: '100%' }}>
                  <option>Loading…</option>
                </select>
              ) : methods.length > 0 ? (
                <select
                  value={action.method ?? ''}
                  onChange={e => update({ method: e.target.value, args: [] })}
                  style={{ width: '100%' }}
                >
                  {methods.map(m => <option key={m.name} value={m.name}>{m.name}</option>)}
                </select>
              ) : (
                <input
                  type="text"
                  value={action.method ?? ''}
                  onChange={e => update({ method: e.target.value })}
                  placeholder="method name"
                  style={{ width: '100%' }}
                />
              )
            ) : (
              <input
                type="text"
                value={action.method ?? ''}
                onChange={e => update({ method: e.target.value })}
                style={{ width: '100%' }}
              />
            )}
          </div>

          {/* Args from AST (backend-authored only) */}
          {isBackendAuthored && argList.map((arg, i) => (
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

          {/* Legacy path: single arg input */}
          {!isBackendAuthored && (
            <div>
              <label style={labelStyle}>Arg</label>
              <ArgInput
                value={(action.args ?? [])[0] ?? 1}
                toolkit={toolkit}
                annotation={null}
                onChange={v => update({ args: [v] })}
              />
            </div>
          )}
        </>
      )}

      {/* ── Flag action ─────────────────────────────────────────────────── */}
      {action.type === 'flag' && (
        <>
          <div>
            <label
              style={labelStyle}
              title="Which counter, boolean, or trial marker to update?"
            >
              Flag ⓘ
            </label>
            {flagKeys.length > 0 ? (
              <select
                value={action.ref ?? ''}
                onChange={e => handleFlagChange(e.target.value)}
                style={{ width: '100%' }}
              >
                {!flagKeys.includes(action.ref ?? '') && (
                  <option value={action.ref ?? ''}>{action.ref ?? '—'}</option>
                )}
                {flagKeys.map(k => (
                  <option key={k} value={k}>
                    {k} ({toolkit?.flags?.[k]?.tracker_type ?? 'Tracker'})
                  </option>
                ))}
              </select>
            ) : (
              <input
                type="text"
                value={action.ref ?? ''}
                onChange={e => update({ ref: e.target.value })}
                style={{ width: '100%' }}
              />
            )}
          </div>

          <div>
            <label style={labelStyle} title={currentFlagMethodDef?.description ?? ''}>
              Operation ⓘ
            </label>
            <select
              value={action.method ?? flagMethodDefs[0]?.name ?? ''}
              onChange={e => update({ method: e.target.value, args: [] })}
              style={{ width: '100%' }}
            >
              {flagMethodDefs.map(m => (
                <option key={m.name} value={m.name} title={m.description}>
                  {m.name}
                </option>
              ))}
            </select>
          </div>

          {flagMethodNeedsArg && (
            <div>
              <label style={labelStyle}>Value</label>
              <ArgInput
                value={(action.args ?? [])[0] ?? 0}
                toolkit={toolkit}
                annotation={null}
                onChange={v => update({ args: [v] })}
              />
            </div>
          )}
        </>
      )}

      {/* ── Timer action ─────────────────────────────────────────────────── */}
      {action.type === 'timer' && (
        <>
          <div>
            <label style={labelStyle} title="Which timer device to control?">
              Timer ⓘ
            </label>
            {timerModules.length > 0 ? (
              <select
                value={action.ref ?? ''}
                onChange={e => update({ ref: e.target.value })}
                style={{ width: '100%' }}
              >
                {!timerModules.find(m => m.name === action.ref) && action.ref && (
                  <option value={action.ref}>{action.ref}</option>
                )}
                {timerModules.map(m => (
                  <option key={m.id} value={m.name}>{m.display_name ?? m.name}</option>
                ))}
              </select>
            ) : toolkitModules.length > 0 ? (
              <select
                value={action.ref ?? ''}
                onChange={e => update({ ref: e.target.value })}
                style={{ width: '100%' }}
              >
                {toolkitModules.map(m => (
                  <option key={m.id} value={m.name}>{m.display_name ?? m.name}</option>
                ))}
              </select>
            ) : (
              <input
                type="text"
                value={action.ref ?? ''}
                onChange={e => update({ ref: e.target.value })}
                placeholder="timer module name"
                style={{ width: '100%' }}
              />
            )}
          </div>

          <div>
            <label
              style={labelStyle}
              title={TIMER_METHOD_DESC[action.method ?? ''] ?? 'Timer operation'}
            >
              Operation ⓘ
            </label>
            <select
              value={action.method ?? 'start'}
              onChange={e => update({ method: e.target.value, args: [] })}
              style={{ width: '100%' }}
            >
              {Object.entries(TIMER_METHOD_DESC).map(([m, desc]) => (
                <option key={m} value={m} title={desc}>{m}</option>
              ))}
            </select>
          </div>

          {(action.method === 'start' || action.method === 'set' || !action.method) && (
            <div>
              <label style={labelStyle}>Duration</label>
              <ArgInput
                value={(action.args ?? [])[0] ?? 500}
                toolkit={toolkit}
                annotation="float"
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
              <select
                value={action.ref ?? ''}
                onChange={e => update({ ref: e.target.value })}
                style={{ width: '100%' }}
              >
                {!callableMethods.includes(action.ref ?? '') && (
                  <option value={action.ref ?? ''}>{action.ref ?? '—'}</option>
                )}
                {callableMethods.map(k => <option key={k} value={k}>{k}</option>)}
              </select>
            ) : (
              <input
                type="text"
                value={action.ref ?? ''}
                onChange={e => update({ ref: e.target.value })}
                placeholder="method name"
                style={{ width: '100%' }}
              />
            )}
          </div>
          {(action.args ?? []).map((arg, i) => (
            <div key={i}>
              <label style={labelStyle}>Arg {i + 1}</label>
              <ArgInput
                value={arg}
                toolkit={toolkit}
                annotation={null}
                onChange={v => {
                  const newArgs = [...(action.args ?? [])]
                  newArgs[i] = v
                  update({ args: newArgs })
                }}
              />
            </div>
          ))}
        </>
      )}

      {/* ── If action ─────────────────────────────────────────────────────── */}
      {action.type === 'if' && (
        <IfActionEditor
          action={action}
          toolkit={toolkit}
          hwModules={hwModules}
          onChange={onChange}
        />
      )}
    </div>
  )
}
