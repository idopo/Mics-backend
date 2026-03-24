import type { ToolkitRead } from '../types'

type ArgMode = 'literal' | 'param' | 'flag'

interface Props {
  value: unknown
  toolkit: ToolkitRead | null
  onChange: (updated: unknown) => void
}

function detectMode(value: unknown): ArgMode {
  if (value !== null && typeof value === 'object') {
    if ('param' in (value as object)) return 'param'
    if ('flag' in (value as object)) return 'flag'
  }
  return 'literal'
}

export default function ArgInput({ value, toolkit, onChange }: Props) {
  const mode = detectMode(value)
  const paramKeys = Object.keys(toolkit?.params_schema ?? {})
  const flagKeys = Object.keys(toolkit?.flags ?? {})

  const switchMode = (next: ArgMode) => {
    if (next === 'literal') onChange(0)
    else if (next === 'param') onChange({ param: paramKeys[0] ?? '' })
    else onChange({ flag: flagKeys[0] ?? '' })
  }

  const btnStyle = (active: boolean): React.CSSProperties => ({
    padding: '2px 8px',
    fontSize: '11px',
    borderRadius: '4px',
    border: '1px solid var(--surface2)',
    background: active ? 'var(--surface2)' : 'transparent',
    color: active ? 'var(--text)' : 'var(--subtext0)',
    cursor: 'pointer',
  })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
      <div style={{ display: 'flex', gap: '4px' }}>
        {(['literal', 'param', 'flag'] as ArgMode[]).map(m => (
          <button key={m} style={btnStyle(mode === m)} onClick={() => switchMode(m)}>
            {m.charAt(0).toUpperCase() + m.slice(1)}
          </button>
        ))}
      </div>

      {mode === 'literal' && (
        <input
          type="number"
          value={typeof value === 'number' ? value : 0}
          onChange={e => onChange(Number(e.target.value))}
          style={{ width: '100%' }}
        />
      )}

      {mode === 'param' && (
        paramKeys.length > 0 ? (
          <select
            value={(value as { param: string }).param}
            onChange={e => onChange({ param: e.target.value })}
            style={{ width: '100%' }}
          >
            {paramKeys.map(k => <option key={k} value={k}>{k}</option>)}
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
            value={(value as { flag: string }).flag}
            onChange={e => onChange({ flag: e.target.value })}
            style={{ width: '100%' }}
          >
            {flagKeys.map(k => <option key={k} value={k}>{k}</option>)}
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
