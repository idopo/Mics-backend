import type { FdaCondition, FdaOperand, ToolkitRead } from '../types'

const OPS = ['==', '!=', '>=', '<=', '>', '<'] as const
type OperandType = 'view' | 'literal' | 'param' | 'flag' | 'hardware'

function getOperandType(op: FdaOperand): OperandType {
  if (op === null || typeof op !== 'object') return 'literal'
  if ('view' in op || 'tracker' in op) return 'view'
  if ('flag' in op) return 'flag'
  if ('param' in op) return 'param'
  if ('hardware' in op) return 'hardware'
  return 'literal'
}

function getOperandKey(op: FdaOperand): string {
  if (op === null || typeof op !== 'object') return String(op ?? '')
  if ('view' in op) return op.view
  if ('tracker' in op) return op.tracker
  if ('flag' in op) return op.flag
  if ('param' in op) return op.param
  if ('hardware' in op) return op.hardware
  return ''
}

function buildOperand(type: OperandType, value: string): FdaOperand {
  if (type === 'literal') {
    const n = Number(value)
    return value === '' ? 0 : !isNaN(n) ? n : value
  }
  if (type === 'flag') return { flag: value }
  if (type === 'param') return { param: value }
  if (type === 'hardware') return { hardware: value }
  return { view: value }
}

export function operandLabel(op: FdaOperand): string {
  if (op === null || op === undefined) return '?'
  if (typeof op !== 'object') return String(op)
  if ('view' in op) return op.view || '?'
  if ('tracker' in op) return op.tracker || '?'
  if ('flag' in op) return `!${op.flag}`
  if ('param' in op) return `$${op.param}`
  if ('hardware' in op) return `hw.${op.hardware}`
  return '?'
}

interface OperandEditorProps {
  operand: FdaOperand
  toolkit: ToolkitRead | null
  onChange: (updated: FdaOperand) => void
}

function OperandEditor({ operand, toolkit, onChange }: OperandEditorProps) {
  const type = getOperandType(operand)
  const key = getOperandKey(operand)

  const setType = (newType: OperandType) => onChange(buildOperand(newType, key))
  const setKey = (val: string) => onChange(buildOperand(type, val))

  const ss: React.CSSProperties = { width: '100%', fontSize: '12px', padding: '4px 7px' }

  const hwOpts = Object.keys(toolkit?.semantic_hardware ?? {})
  const flagOpts = Object.keys(toolkit?.flags ?? {})
  const paramOpts = Object.keys(toolkit?.params_schema ?? {})
  const viewOpts = [...new Set([...hwOpts, ...flagOpts])]

  const allTypes: OperandType[] = toolkit
    ? ['view', 'literal', 'flag', 'param', 'hardware']
    : ['view', 'literal']

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
      <select value={type} onChange={e => setType(e.target.value as OperandType)} style={ss}>
        {allTypes.map(t => <option key={t} value={t}>{t}</option>)}
      </select>

      {type === 'view' && (viewOpts.length > 0 ? (
        <select value={key} onChange={e => setKey(e.target.value)} style={ss}>
          {!viewOpts.includes(key) && key !== '' && <option value={key}>{key}</option>}
          <option value="">— pick —</option>
          {viewOpts.map(k => <option key={k} value={k}>{k}</option>)}
        </select>
      ) : (
        <input type="text" value={key} onChange={e => setKey(e.target.value)} placeholder="view key" style={ss} />
      ))}

      {type === 'flag' && (flagOpts.length > 0 ? (
        <select value={key} onChange={e => setKey(e.target.value)} style={ss}>
          {!flagOpts.includes(key) && key !== '' && <option value={key}>{key}</option>}
          <option value="">— pick —</option>
          {flagOpts.map(k => <option key={k} value={k}>{k}</option>)}
        </select>
      ) : (
        <input type="text" value={key} onChange={e => setKey(e.target.value)} placeholder="flag name" style={ss} />
      ))}

      {type === 'param' && (paramOpts.length > 0 ? (
        <select value={key} onChange={e => setKey(e.target.value)} style={ss}>
          {!paramOpts.includes(key) && key !== '' && <option value={key}>{key}</option>}
          <option value="">— pick —</option>
          {paramOpts.map(k => <option key={k} value={k}>{k}</option>)}
        </select>
      ) : (
        <input type="text" value={key} onChange={e => setKey(e.target.value)} placeholder="param name" style={ss} />
      ))}

      {type === 'hardware' && (hwOpts.length > 0 ? (
        <select value={key} onChange={e => setKey(e.target.value)} style={ss}>
          {!hwOpts.includes(key) && key !== '' && <option value={key}>{key}</option>}
          <option value="">— pick —</option>
          {hwOpts.map(k => <option key={k} value={k}>{k}</option>)}
        </select>
      ) : (
        <input type="text" value={key} onChange={e => setKey(e.target.value)} placeholder="hw key" style={ss} />
      ))}

      {type === 'literal' && (
        <input type="text" value={key} onChange={e => setKey(e.target.value)} placeholder="0" style={ss} />
      )}
    </div>
  )
}

interface Props {
  condition: FdaCondition
  toolkit: ToolkitRead | null
  onChange: (updated: FdaCondition) => void
}

export default function ConditionBuilder({ condition, toolkit, onChange }: Props) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
      <div>
        <div style={{ fontSize: '11px', color: 'var(--muted)', marginBottom: '3px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Left</div>
        <OperandEditor operand={condition.left} toolkit={toolkit} onChange={left => onChange({ ...condition, left })} />
      </div>
      <div>
        <div style={{ fontSize: '11px', color: 'var(--muted)', marginBottom: '3px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Op</div>
        <select
          value={condition.op}
          onChange={e => onChange({ ...condition, op: e.target.value as FdaCondition['op'] })}
          style={{ width: '100%', fontSize: '12px', padding: '4px 7px' }}
        >
          {OPS.map(op => <option key={op} value={op}>{op}</option>)}
        </select>
      </div>
      <div>
        <div style={{ fontSize: '11px', color: 'var(--muted)', marginBottom: '3px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Right</div>
        <OperandEditor operand={condition.right} toolkit={toolkit} onChange={right => onChange({ ...condition, right })} />
      </div>
    </div>
  )
}
