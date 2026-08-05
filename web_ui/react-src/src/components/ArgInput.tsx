import type { ToolkitRead } from '../types'
import NumericInput from './NumericInput'
import StructuredInput from './StructuredInput'
import {
  type ArgMode,
  detectMode,
  annotationToInputKind,
  getParamKeys,
  MODE_COLORS,
  MODE_LABELS,
  MODE_TOOLTIPS,
  ALL_MODES,
} from './argModes.mts'

interface Props {
  value: unknown
  toolkit: ToolkitRead | null
  annotation?: string | null
  /** Declared FdaJson.variables names — merged into the flag-mode option list. */
  variableNames?: string[]
  /** Only true inside a trigger's action list — gates the `trigger` mode pill. */
  allowTriggerContext?: boolean
  onChange: (updated: unknown) => void
}

export default function ArgInput({ value, toolkit, annotation, variableNames, allowTriggerContext, onChange }: Props) {
  const mode = detectMode(value)
  const paramKeys = getParamKeys(toolkit)
  const flagKeys = [...new Set([...Object.keys(toolkit?.flags ?? {}), ...(variableNames ?? [])])]
  const inputKind = annotationToInputKind(annotation)

  // Defensive: if the stored value is already a trigger operand, keep offering the trigger
  // pill even when this editor wasn't opted into it (e.g. a state body re-opened after edits
  // made inside a trigger's action list) — never silently corrupt the stored value.
  const visibleModes = allowTriggerContext || mode === 'trigger' ? ALL_MODES : ALL_MODES.filter(m => m !== 'trigger')

  const switchMode = (next: ArgMode) => {
    if (next === 'literal') {
      if (inputKind === 'bool') onChange(false)
      else if (inputKind === 'number') onChange(0)
      else if (inputKind === 'structured') onChange([])   // never seed a list arg with a string
      else onChange('')
    } else if (next === 'param') {
      onChange({ param: paramKeys[0] ?? '' })
    } else if (next === 'flag') {
      onChange({ flag: flagKeys[0] ?? '' })
    } else {
      onChange({ trigger: 'tick' })
    }
  }

  const btnStyle = (m: ArgMode): React.CSSProperties => {
    const active = mode === m
    const color = MODE_COLORS[m]
    return {
      padding: '2px 8px',
      fontSize: '11px',
      borderRadius: '10px',
      border: `1px solid ${active ? color : 'var(--surface2)'}`,
      background: active ? `${color}22` : 'transparent',
      color: active ? color : 'var(--subtext0)',
      cursor: 'pointer',
      fontWeight: active ? 600 : 400,
      transition: 'all 0.1s ease',
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
      <div style={{ display: 'flex', gap: '4px' }}>
        {visibleModes.map(m => (
          <button
            key={m}
            style={btnStyle(m)}
            onClick={() => switchMode(m)}
            title={MODE_TOOLTIPS[m]}
          >
            {MODE_LABELS[m]}
          </button>
        ))}
      </div>

      {mode === 'literal' && inputKind === 'number' && (
        <NumericInput
          value={typeof value === 'number' ? value : 0}
          onChange={onChange}
          style={{ width: '100%' }}
        />
      )}

      {mode === 'literal' && inputKind === 'structured' && (
        <StructuredInput value={value} onChange={onChange} style={{ width: '100%' }} />
      )}

      {mode === 'literal' && inputKind === 'bool' && (
        <select
          value={value ? 'true' : 'false'}
          onChange={e => onChange(e.target.value === 'true')}
          style={{ width: '100%' }}
        >
          <option value="true">true</option>
          <option value="false">false</option>
        </select>
      )}

      {mode === 'literal' && inputKind === 'text' && (
        <input
          type="text"
          value={typeof value === 'string' ? value : (value === null || value === undefined ? '' : String(value))}
          onChange={e => onChange(e.target.value)}
          style={{ width: '100%' }}
        />
      )}

      {mode === 'param' && (
        paramKeys.length > 0 ? (
          <select
            value={(value as { param: string }).param ?? ''}
            onChange={e => onChange({ param: e.target.value })}
            style={{ width: '100%' }}
          >
            {paramKeys.map(k => <option key={k} value={k}>${k}</option>)}
          </select>
        ) : (
          <input
            type="text"
            value={(value as { param: string }).param ?? ''}
            onChange={e => onChange({ param: e.target.value })}
            placeholder="param name"
            style={{ width: '100%' }}
          />
        )
      )}

      {mode === 'flag' && (
        flagKeys.length > 0 ? (
          <select
            value={(value as { flag: string }).flag ?? ''}
            onChange={e => onChange({ flag: e.target.value })}
            style={{ width: '100%' }}
          >
            {/* Keep-current escape, same as ConditionBuilder's: a stored flag that is not in
                the option list — a hidden machinery variable like `level` inside its own
                trigger — must stay visible and round-trip, not render as a blank select. */}
            {!flagKeys.includes((value as { flag: string }).flag ?? '') && (value as { flag: string }).flag && (
              <option value={(value as { flag: string }).flag}>!{(value as { flag: string }).flag}</option>
            )}
            {flagKeys.map(k => (
              <option key={k} value={k}>
                !{k}{(variableNames ?? []).includes(k) && !(toolkit?.flags && k in toolkit.flags) ? ' (variable)' : ''}
              </option>
            ))}
          </select>
        ) : (
          <input
            type="text"
            value={(value as { flag: string }).flag ?? ''}
            onChange={e => onChange({ flag: e.target.value })}
            placeholder="flag name"
            style={{ width: '100%' }}
          />
        )
      )}

      {mode === 'trigger' && (
        <select
          value={(value as { trigger: string }).trigger ?? 'tick'}
          onChange={e => onChange({ trigger: e.target.value })}
          style={{ width: '100%' }}
        >
          <option value="level">level</option>
          <option value="tick">tick</option>
        </select>
      )}
    </div>
  )
}
