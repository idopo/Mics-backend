import { useState } from 'react'
import type { FdaVariable, ToolkitRead } from '../types'

interface Props {
  variables: Record<string, FdaVariable>
  toolkit: ToolkitRead | null
  onChange: (updated: Record<string, FdaVariable>) => void
}

const sectionLabel: React.CSSProperties = {
  fontSize: '11px',
  color: 'var(--muted)',
  fontWeight: 600,
  letterSpacing: '0.08em',
  textTransform: 'uppercase',
  marginBottom: '10px',
}

function nextVariableName(existing: string[]): string {
  let i = 1
  while (existing.includes(`variable${i}`)) i++
  return `variable${i}`
}

/** Best-effort parse of a free-text initial-value input into a JS primitive. */
function parseInitialValue(raw: string): unknown {
  if (raw === 'true') return true
  if (raw === 'false') return false
  const asNumber = Number(raw)
  if (raw.trim() !== '' && !Number.isNaN(asNumber)) return asNumber
  return raw
}

/**
 * Declares named value slots (FdaJson.variables) that hardware/method actions can capture
 * a return value into (`output`) and that view/flag actions can read as {token} values.
 * Renaming rejects collisions with existing variable names or toolkit.flags — the Pi raises
 * ValueError on that collision at load time and the backend 422s, so this catches it first.
 */
export default function VariablesPanel({ variables, toolkit, onChange }: Props): JSX.Element {
  const [renameErrors, setRenameErrors] = useState<Record<string, string>>({})
  const names = Object.keys(variables)
  const flagKeys = Object.keys(toolkit?.flags ?? {})

  const add = (): void => {
    const name = nextVariableName(names)
    onChange({ ...variables, [name]: {} })
  }

  const remove = (name: string): void => {
    const rest = { ...variables }
    delete rest[name]
    onChange(rest)
    setRenameErrors(prev => {
      const next = { ...prev }
      delete next[name]
      return next
    })
  }

  const rename = (oldName: string, rawNewName: string): void => {
    const newName = rawNewName.trim()
    if (!newName || newName === oldName) return
    if (names.includes(newName) || flagKeys.includes(newName)) {
      setRenameErrors(prev => ({ ...prev, [oldName]: `"${newName}" is already in use` }))
      return
    }
    setRenameErrors(prev => {
      const next = { ...prev }
      delete next[oldName]
      return next
    })
    const rebuilt: Record<string, FdaVariable> = {}
    for (const key of names) {
      rebuilt[key === oldName ? newName : key] = variables[key]
    }
    onChange(rebuilt)
  }

  const setInitialValue = (name: string, raw: string): void => {
    const trimmed = raw.trim()
    if (trimmed === '') {
      onChange({ ...variables, [name]: {} })
      return
    }
    onChange({ ...variables, [name]: { initial_value: parseInitialValue(trimmed) } })
  }

  return (
    <div>
      <div style={sectionLabel}>Variables</div>
      <p style={{ fontSize: '11px', color: 'var(--muted)', marginBottom: '10px', lineHeight: 1.4 }}>
        Named value slots shared between the task&apos;s flags and the view. Use them as{' '}
        <code>output</code> targets and in <code>{'{token}'}</code> keys.
      </p>

      {names.length === 0 ? (
        <p style={{ fontSize: '12px', color: 'var(--muted)', marginBottom: '12px' }}>
          No variables. Add one to capture a hardware call&apos;s return value.
        </p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '12px' }}>
          {names.map(name => (
            <div key={name} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                <input
                  type="text"
                  defaultValue={name}
                  onBlur={e => rename(name, e.target.value)}
                  style={{ flex: 1, fontFamily: "'IBM Plex Mono', monospace", fontSize: '12px' }}
                />
                <input
                  type="text"
                  defaultValue={
                    variables[name]?.initial_value !== undefined
                      ? String(variables[name].initial_value)
                      : ''
                  }
                  onBlur={e => setInitialValue(name, e.target.value)}
                  placeholder="initial value"
                  style={{ width: '110px', fontSize: '12px' }}
                />
                <button
                  className="button-danger"
                  style={{ fontSize: '10px', padding: '1px 6px', lineHeight: 1.4 }}
                  onClick={() => remove(name)}
                >
                  ✕
                </button>
              </div>
              {renameErrors[name] && (
                <span style={{ fontSize: '10px', color: '#ef4444' }}>{renameErrors[name]}</span>
              )}
            </div>
          ))}
        </div>
      )}

      <button className="button-secondary" style={{ fontSize: '12px', width: '100%' }} onClick={add}>
        + Add variable
      </button>
    </div>
  )
}
