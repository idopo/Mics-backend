import { useState } from 'react'
import { useQueries } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import type { FdaAction, ToolkitRead, HardwareModule, AstMethod } from '../types'
import { getHardwareModuleMethods } from '../api/hardware_modules'
import { isComputeModule, labelStyle } from './ActionEditor'
import ArgInput from './ArgInput'

interface Props {
  action: FdaAction
  toolkit: ToolkitRead | null
  hwModules: HardwareModule[]
  taskDefId?: number
  versionStamp?: string
  /** Declared FdaJson.variables names — the output combobox's option list. */
  variableNames?: string[]
  /** Declares a new name into FdaJson.variables the moment it's typed (CMP-13). */
  onDeclareVariable?: (name: string) => void
  onChange: (patch: Partial<FdaAction>) => void
}

const NEW_VARIABLE_SENTINEL = '__new_variable__'

/** release()/__init__ are required Hardware-subclass plumbing, not compute operations. */
function isOperationName(name: string): boolean {
  return name !== 'release' && name !== '__init__' && !name.startsWith('_')
}

/**
 * The compute row: `[output] = [op ▾] ( [args] )`. One flattened op <select> grouped by
 * lib (an <optgroup> per compute module) rather than a two-step module-then-method picker —
 * a compute lib is many small ops in one class, not one device with a handful of methods.
 */
export default function ComputeActionFields({ action, toolkit, hwModules, taskDefId, variableNames, onDeclareVariable, onChange }: Props): JSX.Element {
  const names = variableNames ?? []
  const flagKeys = Object.keys(toolkit?.flags ?? {})

  const computeModules = hwModules
    .filter(m => toolkit?.hardware_module_ids?.includes(m.id))
    .filter(isComputeModule)

  // Same query key shape ['hardware-module-methods', id] the rest of the app uses
  // (PilotHardwareConfig.tsx) — no second fetch is introduced.
  const methodQueries = useQueries({
    queries: computeModules.map(mod => ({
      queryKey: ['hardware-module-methods', mod.id],
      queryFn: () => getHardwareModuleMethods(mod.id, taskDefId),
    })),
  })

  const [isAddingNew, setIsAddingNew] = useState(false)
  const [outputError, setOutputError] = useState<string | null>(null)

  if (computeModules.length === 0) {
    return (
      <p style={{ fontSize: '11px', color: 'var(--muted)', margin: 0 }}>
        No compute library is linked to this toolkit. Link one on the{' '}
        <Link to="/hardware-libs-ui">Hardware Libraries</Link> page.
      </p>
    )
  }

  const methodsByModule: Record<string, AstMethod[]> = {}
  computeModules.forEach((mod, i) => {
    const methods = methodQueries[i]?.data?.methods ?? []
    methodsByModule[mod.name] = methods.filter(m => isOperationName(m.name))
  })

  const opValue = action.ref && action.method ? `${action.ref}::${action.method}` : ''
  const argList = action.ref && action.method
    ? methodsByModule[action.ref]?.find(m => m.name === action.method)?.args ?? []
    : []

  function handleOpChange(value: string): void {
    const [modName, methodName] = value.split('::')
    onChange({ ref: modName, method: methodName, args: [] })
  }

  function commitOutputName(rawName: string): void {
    const name = rawName.trim()
    if (!name) {
      setOutputError('Variable name cannot be empty')
      return
    }
    if (names.includes(name) || flagKeys.includes(name)) {
      setOutputError(`"${name}" is already in use`)
      return
    }
    setOutputError(null)
    setIsAddingNew(false)
    onDeclareVariable?.(name)
    onChange({ output: name })
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-end' }}>
        <div style={{ flex: 1 }}>
          <label style={labelStyle} title="The variable this compute op writes its result into — mandatory.">
            Output ⓘ
          </label>
          {isAddingNew ? (
            <input
              type="text"
              autoFocus
              placeholder="new variable name"
              defaultValue=""
              onBlur={e => commitOutputName(e.target.value)}
              style={{ width: '100%' }}
            />
          ) : (
            <select
              value={typeof action.output === 'string' ? action.output : ''}
              onChange={e => {
                if (e.target.value === NEW_VARIABLE_SENTINEL) setIsAddingNew(true)
                else onChange({ output: e.target.value })
              }}
              style={{ width: '100%' }}
            >
              {!action.output && <option value="">—</option>}
              {typeof action.output === 'string' && action.output && !names.includes(action.output) && (
                <option value={action.output}>{action.output}</option>
              )}
              {names.map(n => <option key={n} value={n}>{n}</option>)}
              <option value={NEW_VARIABLE_SENTINEL}>— new variable… —</option>
            </select>
          )}
        </div>

        <span style={{ fontSize: '13px', color: 'var(--muted)', paddingBottom: '6px' }}>=</span>

        <div style={{ flex: 2 }}>
          <label style={labelStyle} title="The compute operation to run, grouped by library.">Op ⓘ</label>
          <select value={opValue} onChange={e => handleOpChange(e.target.value)} style={{ width: '100%' }}>
            {!opValue && <option value="">—</option>}
            {computeModules.map(mod => (
              <optgroup key={mod.id} label={mod.display_name ?? mod.name}>
                {(methodsByModule[mod.name] ?? []).map(m => (
                  <option key={m.name} value={`${mod.name}::${m.name}`}>{m.name}</option>
                ))}
              </optgroup>
            ))}
          </select>
        </div>
      </div>

      {outputError && <span style={{ fontSize: '10px', color: '#ef4444' }}>{outputError}</span>}
      {!outputError && !action.output && (
        <span style={{ fontSize: '10px', color: '#ef4444' }}>
          A compute action must write a variable — pick or declare one above.
        </span>
      )}

      {argList.map((arg, i) => (
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
            onChange={v => {
              const newArgs = [...(action.args ?? [])]
              newArgs[i] = v
              onChange({ args: newArgs })
            }}
          />
        </div>
      ))}
    </div>
  )
}
