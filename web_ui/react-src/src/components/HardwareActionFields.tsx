import { useState, useEffect } from 'react'
import type { FdaAction, ToolkitRead, HardwareModule, AstMethod } from '../types'
import { getHardwareModuleMethods } from '../api/hardware_modules'
import ArgInput from './ArgInput'
import { labelStyle, isTimerModule, type TrackerMethod } from './ActionEditor'

// Module-level method cache: keyed by "moduleId/versionStamp" to stay version-aware.
// versionStamp changes whenever the version assignment for the task def changes.
const METHOD_CACHE: Record<string, AstMethod[]> = {}

const TIMER_METHODS: TrackerMethod[] = [
  { name: 'start', hasArg: true,  description: 'Start counting down with the given duration' },
  { name: 'stop',  hasArg: false, description: 'Stop the timer (does not reset)' },
  { name: 'reset', hasArg: false, description: 'Reset the timer to zero' },
  { name: 'set',   hasArg: true,  description: 'Set the duration without starting' },
]

interface Props {
  action: FdaAction
  toolkit: ToolkitRead | null
  hwModules: HardwareModule[]
  taskDefId?: number
  versionStamp?: string
  /** Declared FdaJson.variables names — merged into ArgInput's flag-mode option list. */
  variableNames?: string[]
  allowTriggerContext?: boolean
  onChange: (patch: Partial<FdaAction>) => void
}

export default function HardwareActionFields({ action, toolkit, hwModules, taskDefId, versionStamp, variableNames, allowTriggerContext, onChange }: Props) {
  const isBackendAuthored = toolkit?.is_backend_authored ?? false
  const toolkitModules = hwModules.filter(m => toolkit?.hardware_module_ids?.includes(m.id))
  // Legacy semantic hardware keys
  const semanticKeys = Object.keys(toolkit?.semantic_hardware ?? {})

  const [methods, setMethods] = useState<AstMethod[]>([])
  const [methodsLoading, setMethodsLoading] = useState(false)

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

  function handleModuleChange(modName: string) {
    const mod = toolkitModules.find(m => m.name === modName)
    const isTimer = mod ? isTimerModule(mod) : false
    onChange({ ref: modName, type: isTimer ? 'timer' : 'hardware', method: isTimer ? 'start' : '', args: [] })
    setMethods([])
    if (mod && !isTimer) fetchMethods(mod.id)
  }

  function currentMethodArgs(): AstMethod['args'] {
    if (!methods.length || !action.method) return []
    return methods.find(m => m.name === action.method)?.args ?? []
  }

  // Determine if the current hardware module is a timer
  const currentMod = selectedHwModule()
  const currentIsTimer = currentMod ? isTimerModule(currentMod) : (action.type === 'timer')

  const argList = currentMethodArgs()

  // Current timer method meta
  const timerMethodDef = TIMER_METHODS.find(m => m.name === (action.method ?? 'start'))
  const timerNeedsArg = timerMethodDef?.hasArg ?? false

  return (
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
            <input type="text" value={action.ref ?? ''} onChange={e => onChange({ ref: e.target.value })} placeholder="module name" style={{ width: '100%' }} />
          )}
        </div>
      ) : (
        <div>
          <label style={labelStyle} title="Hardware ref from toolkit semantic_hardware.">Hardware ref ⓘ</label>
          {semanticKeys.length > 0 ? (
            <select value={action.ref ?? ''} onChange={e => onChange({ ref: e.target.value })} style={{ width: '100%' }}>
              {!semanticKeys.includes(action.ref ?? '') && <option value={action.ref ?? ''}>{action.ref ?? '—'}</option>}
              {semanticKeys.map(k => <option key={k} value={k}>{k}</option>)}
            </select>
          ) : (
            <input type="text" value={action.ref ?? ''} onChange={e => onChange({ ref: e.target.value })} style={{ width: '100%' }} />
          )}
        </div>
      )}

      {/* Method dropdown */}
      <div>
        <label style={labelStyle} title="What the device should do.">Action ⓘ</label>
        {currentIsTimer ? (
          /* Timer: fixed method list */
          <select value={action.method ?? 'start'} onChange={e => onChange({ method: e.target.value, args: [] })} style={{ width: '100%' }}>
            {TIMER_METHODS.map(m => <option key={m.name} value={m.name} title={m.description}>{m.name}</option>)}
          </select>
        ) : isBackendAuthored ? (
          methodsLoading ? (
            <select disabled style={{ width: '100%' }}><option>Loading…</option></select>
          ) : methods.length > 0 ? (
            <select value={action.method ?? ''} onChange={e => onChange({ method: e.target.value, args: [] })} style={{ width: '100%' }}>
              {action.method && !methods.find(m => m.name === action.method) && (
                <option value={action.method} style={{ color: '#ef4444' }}>
                  ⚠ {action.method} (not in this version)
                </option>
              )}
              {methods.map(m => <option key={m.name} value={m.name}>{m.name}</option>)}
            </select>
          ) : (
            <input type="text" value={action.method ?? ''} onChange={e => onChange({ method: e.target.value })} placeholder="method name" style={{ width: '100%' }} />
          )
        ) : (
          <input type="text" value={action.method ?? ''} onChange={e => onChange({ method: e.target.value })} style={{ width: '100%' }} />
        )}
      </div>

      {/* Timer duration arg */}
      {currentIsTimer && timerNeedsArg && (
        <div>
          <label style={labelStyle}>Duration</label>
          <ArgInput
            value={(action.args ?? [])[0] ?? 500}
            toolkit={toolkit}
            annotation="float"
            variableNames={variableNames}
            allowTriggerContext={allowTriggerContext}
            onChange={v => onChange({ args: [v] })}
          />
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
            variableNames={variableNames}
            allowTriggerContext={allowTriggerContext}
            onChange={v => {
              const newArgs = [...(action.args ?? [])]
              newArgs[i] = v
              onChange({ args: newArgs })
            }}
          />
        </div>
      ))}

      {/* Legacy: single arg */}
      {!isBackendAuthored && !currentIsTimer && (
        <div>
          <label style={labelStyle}>Arg</label>
          <ArgInput
            value={(action.args ?? [])[0] ?? 1}
            toolkit={toolkit}
            annotation={null}
            variableNames={variableNames}
            allowTriggerContext={allowTriggerContext}
            onChange={v => onChange({ args: [v] })}
          />
        </div>
      )}
    </>
  )
}
