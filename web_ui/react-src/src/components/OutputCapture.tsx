import type { FdaAction } from '../types'
import { labelStyle } from './ActionEditor'

interface Props {
  action: FdaAction
  /** Declared FdaJson.variables names — the only valid capture targets. */
  variableNames?: string[]
  onChange: (patch: Partial<FdaAction>) => void
}

/**
 * Collapsed-by-default toggle for hardware/timer/method actions: captures the call's
 * return value into a declared variable, single (`output: 'name'`) or positionally
 * unpacked (`output: ['a', 'b']`) for tuple-returning methods like detect_change().
 */
export default function OutputCapture({ action, variableNames, onChange }: Props) {
  const names = variableNames ?? []
  const output = action.output
  const isOn = output !== undefined
  const isMulti = Array.isArray(output)

  const turnOn = () => onChange({ output: names[0] ?? '' })
  const turnOff = () => onChange({ output: undefined })
  const toMulti = () => onChange({ output: [names[0] ?? '', names[1] ?? names[0] ?? ''] })
  const toSingle = () => onChange({ output: names[0] ?? '' })
  const setSingle = (name: string) => onChange({ output: name })

  const setSlot = (i: number, name: string) => {
    const next = [...(isMulti ? (output as string[]) : [])]
    next[i] = name
    onChange({ output: next })
  }
  const addSlot = () => onChange({ output: [...(isMulti ? (output as string[]) : []), names[0] ?? ''] })
  const removeSlot = (i: number) =>
    onChange({ output: (isMulti ? (output as string[]) : []).filter((_, idx) => idx !== i) })

  if (names.length === 0) {
    return (
      <div>
        <label style={labelStyle}>Capture return value</label>
        <p style={{ fontSize: '11px', color: 'var(--muted)', margin: 0 }}>
          No variables declared. Add one in the Variables panel first.
        </p>
      </div>
    )
  }

  return (
    <div>
      <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--muted)', cursor: 'pointer' }}>
        <input type="checkbox" checked={isOn} onChange={e => (e.target.checked ? turnOn() : turnOff())} />
        Capture return value
      </label>

      {isOn && (
        <div style={{ marginTop: '6px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--muted)', cursor: 'pointer' }}>
            <input type="checkbox" checked={isMulti} onChange={e => (e.target.checked ? toMulti() : toSingle())} />
            Unpack tuple positionally
          </label>
          {isMulti && (
            <p style={{ fontSize: '10px', color: 'var(--muted)', margin: 0 }}>
              detect_change() returns (electrode_index, new_value) — two slots
            </p>
          )}

          {!isMulti ? (
            <select value={(output as string) ?? ''} onChange={e => setSingle(e.target.value)} style={{ width: '100%' }}>
              {names.map(n => <option key={n} value={n}>{n}</option>)}
            </select>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {(output as string[]).map((slot, i) => (
                <div key={i} style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
                  <select value={slot} onChange={e => setSlot(i, e.target.value)} style={{ flex: 1 }}>
                    {names.map(n => <option key={n} value={n}>{n}</option>)}
                  </select>
                  <button className="button-danger" style={{ fontSize: '10px', padding: '1px 6px' }} onClick={() => removeSlot(i)}>
                    −
                  </button>
                </div>
              ))}
              <button className="button-secondary" style={{ fontSize: '11px' }} onClick={addSlot}>
                + Add slot
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
