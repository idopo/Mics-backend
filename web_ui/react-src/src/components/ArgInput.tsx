import type { ToolkitRead } from '../types'

type ArgMode = 'literal' | 'param' | 'flag'

/** Handles both array [{name}] and dict {name:{}} shapes for params_schema. */
export function getParamKeys(toolkit: ToolkitRead | null | undefined): string[] {
  const schema = toolkit?.params_schema
  if (!schema) return []
  if (Array.isArray(schema)) return schema.map((p: { name: string }) => p.name)
  return Object.keys(schema)
}

type LiteralInputKind = 'number' | 'bool' | 'text'

function annotationToInputKind(ann: string | null | undefined): LiteralInputKind {
  if (!ann) return 'text'
  const base = ann.replace(/Optional\[|\]/g, '').trim()
  if (base === 'bool') return 'bool'
  if (base === 'int' || base === 'float') return 'number'
  return 'text'
}

interface Props {
  value: unknown
  toolkit: ToolkitRead | null
  annotation?: string | null
  onChange: (updated: unknown) => void
}

function detectMode(value: unknown): ArgMode {
  if (value !== null && typeof value === 'object') {
    if ('param' in (value as object)) return 'param'
    if ('flag' in (value as object)) return 'flag'
  }
  return 'literal'
}

// ── Colors for mode pills ───────────────────────────────────────────────────
const MODE_COLORS: Record<ArgMode, string> = {
  literal: '#6b7280',
  param: '#22c55e',
  flag: '#f59e0b',
}

const MODE_LABELS: Record<ArgMode, string> = {
  literal: '# Literal',
  param: '$ Param',
  flag: '! Flag',
}

const MODE_TOOLTIPS: Record<ArgMode, string> = {
  literal: 'A fixed value baked into the FDA. Does not change between runs.',
  param: 'Resolved from a protocol parameter at runtime. Set in the protocol step config.',
  flag: "Resolved from a flag's current value at runtime. Changes during the session.",
}

export default function ArgInput({ value, toolkit, annotation, onChange }: Props) {
  const mode = detectMode(value)
  const paramKeys = getParamKeys(toolkit)
  const flagKeys = Object.keys(toolkit?.flags ?? {})
  const inputKind = annotationToInputKind(annotation)

  const switchMode = (next: ArgMode) => {
    if (next === 'literal') {
      if (inputKind === 'bool') onChange(false)
      else if (inputKind === 'number') onChange(0)
      else onChange('')
    } else if (next === 'param') {
      onChange({ param: paramKeys[0] ?? '' })
    } else {
      onChange({ flag: flagKeys[0] ?? '' })
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
        {(['literal', 'param', 'flag'] as ArgMode[]).map(m => (
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
        <input
          type="number"
          step="any"
          value={typeof value === 'number' ? value : 0}
          onChange={e => onChange(Number(e.target.value))}
          style={{ width: '100%' }}
        />
      )}

      {mode === 'literal' && inputKind === 'bool' && (
        <select
          value={String(value)}
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
            {flagKeys.map(k => <option key={k} value={k}>!{k}</option>)}
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
    </div>
  )
}
