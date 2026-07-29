import type { FdaCondition, FdaOperand, ToolkitRead, DetectorChannelGroup } from '../types'
import { getParamKeys } from './ArgInput'
import {
  buildViewOptions,
  isKnownViewOption,
  viewOperandToOptionValue,
  optionValueToViewOperand,
  detectorOperandLabel,
} from './detectorOptions.mts'

const OPS = ['==', '!=', '>=', '<=', '>', '<'] as const
type OperandType = 'view' | 'literal' | 'param' | 'flag' | 'hardware'

function getOperandType(op: FdaOperand): OperandType {
  if (op === null || typeof op !== 'object') return 'literal'
  if ('view' in op || 'tracker' in op) return 'view'
  // A detector channel IS a view operand as far as the UI is concerned — it does not become a
  // sixth OperandType, or the type <select> grows an entry the researcher has to understand.
  if ('view_detector' in op) return 'view'
  if ('flag' in op) return 'flag'
  if ('param' in op) return 'param'
  if ('hardware' in op) return 'hardware'
  return 'literal'
}

function getOperandKey(op: FdaOperand): string {
  if (op === null || typeof op !== 'object') return String(op ?? '')
  if (getOperandType(op) === 'view') return viewOperandToOptionValue(op)
  if ('flag' in op) return op.flag
  if ('param' in op) return op.param
  if ('hardware' in op) return op.hardware
  return ''
}

// S3: switching a detector-channel operand's TYPE away from `view` must not carry its opaque
// select token ("@detector/MPR121#2") into another operand type — that would save nonsense like
// {"flag": "@detector/MPR121#2"} and 422 on an undeclared flag. Resolve the display name instead.
function resolveDetectorDisplayName(
  detector: { ref: string; channel: number },
  detectors: DetectorChannelGroup[],
): string {
  const group = detectors.find(g => g.module_name === detector.ref)
  if (!group) return ''
  const idx = group.channels.indexOf(detector.channel)
  return idx >= 0 ? (group.keys[idx] ?? '') : ''
}

function buildOperand(type: OperandType, value: string, detectorChannels: DetectorChannelGroup[]): FdaOperand {
  if (type === 'literal') {
    const n = Number(value)
    return value === '' ? 0 : !isNaN(n) ? n : value
  }
  if (type === 'flag') return { flag: value }
  if (type === 'param') return { param: value }
  if (type === 'hardware') return { hardware: value }
  return optionValueToViewOperand(value, detectorChannels)
}

export function operandLabel(op: FdaOperand): string {
  if (op === null || op === undefined) return '?'
  if (typeof op !== 'object') return String(op)
  if ('view' in op) return op.view || '?'
  if ('tracker' in op) return op.tracker || '?'
  if ('view_detector' in op) return detectorOperandLabel(op.view_detector.ref, op.view_detector.channel)
  if ('flag' in op) return `!${op.flag}`
  if ('param' in op) return `$${op.param}`
  if ('hardware' in op) return `hw.${op.hardware}`
  return '?'
}

interface OperandEditorProps {
  operand: FdaOperand
  toolkit: ToolkitRead | null
  hwModuleNames?: string[]
  /** Declared FdaJson.variables names — one namespace with toolkit.flags (both live in
   *  self.flags on the Pi), so they join the same flag/view option lists rather than a
   *  separate operand type. */
  variableNames?: string[]
  /** Advisory, pilot-agnostic detector channels from toolkit.detector_channels (plan 03). */
  detectorChannels?: DetectorChannelGroup[]
  onChange: (updated: FdaOperand) => void
}

function OperandEditor({ operand, toolkit, hwModuleNames, variableNames, detectorChannels, onChange }: OperandEditorProps) {
  const type = getOperandType(operand)
  const key = getOperandKey(operand)
  const detectors = detectorChannels ?? []

  const setType = (newType: OperandType) => {
    const displayKey = (operand !== null && typeof operand === 'object' && 'view_detector' in operand)
      ? resolveDetectorDisplayName(operand.view_detector, detectors)
      : key
    onChange(buildOperand(newType, displayKey, detectors))
  }
  const setKey = (val: string) => onChange(buildOperand(type, val, detectors))

  const ss: React.CSSProperties = { width: '100%', fontSize: '12px', padding: '4px 7px' }

  const hwOpts = [...Object.keys(toolkit?.semantic_hardware ?? {}), ...(hwModuleNames ?? [])]
  // DVK-07: flagOpts is fed only from toolkit.flags + declared variables — detector channels
  // are never added here, so the flag picker can never offer {"flag": "LICKER1"}.
  const flagOpts = [...new Set([...Object.keys(toolkit?.flags ?? {}), ...(variableNames ?? [])])]
  const paramOpts = getParamKeys(toolkit)
  const viewGroups = buildViewOptions(hwOpts, flagOpts, detectors)

  const allTypes: OperandType[] = toolkit
    ? ['view', 'literal', 'flag', 'param', 'hardware']
    : ['view', 'literal']

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
      <select value={type} onChange={e => setType(e.target.value as OperandType)} style={ss}>
        {allTypes.map(t => <option key={t} value={t}>{t}</option>)}
      </select>

      {type === 'view' && (viewGroups.length > 0 ? (
        <>
          <select value={key} onChange={e => setKey(e.target.value)} style={ss}>
            {/* Keep-current-value escape (S6): a stored key the backend cannot model — a
                Python-only tracker, an ExternalHardware signal, a hand-authored definition —
                must survive a round trip instead of being silently rewritten to "" on save.
                Flagged as unknown, not hidden. There is no legacy detector key to migrate here
                (25-CONTEXT S6): the editor could never emit one before this plan. */}
            {!isKnownViewOption(key, viewGroups) && key !== '' && (
              <option value={key}>{key} (unknown)</option>
            )}
            <option value="">— pick —</option>
            {viewGroups.map(group => (
              <optgroup key={group.label} label={group.label}>
                {group.items.map(item => (
                  <option key={item.value} value={item.value} title={item.title}>{item.label}</option>
                ))}
              </optgroup>
            ))}
          </select>
          {viewGroups.filter(g => g.warning).map(g => (
            <p key={g.label} style={{ fontSize: '10px', color: 'var(--muted)', margin: 0 }}>{g.warning}</p>
          ))}
        </>
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

export interface ConditionBuilderProps {
  condition: FdaCondition
  toolkit: ToolkitRead | null
  hwModuleNames?: string[]
  variableNames?: string[]
  detectorChannels?: DetectorChannelGroup[]
  onChange: (updated: FdaCondition) => void
}

export interface ConditionRowProps {
  condition: FdaCondition
  toolkit: ToolkitRead | null
  hwModuleNames?: string[]
  variableNames?: string[]
  detectorChannels?: DetectorChannelGroup[]
  onChange: (c: FdaCondition) => void
  onDelete?: () => void
}

export function ConditionRow({
  condition, toolkit, hwModuleNames, variableNames, detectorChannels, onChange, onDelete
}: ConditionRowProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
      <div>
        <div style={{ fontSize: '11px', color: 'var(--muted)', marginBottom: '3px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Left</div>
        <OperandEditor operand={condition.left} toolkit={toolkit} hwModuleNames={hwModuleNames} variableNames={variableNames} detectorChannels={detectorChannels} onChange={left => onChange({ ...condition, left })} />
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
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: '11px', color: 'var(--muted)', marginBottom: '3px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Right</div>
          <OperandEditor operand={condition.right} toolkit={toolkit} hwModuleNames={hwModuleNames} variableNames={variableNames} detectorChannels={detectorChannels} onChange={right => onChange({ ...condition, right })} />
        </div>
        {onDelete && (
          <button
            onClick={onDelete}
            style={{ marginTop: 20, fontSize: 11, color: 'var(--text-muted)',
                     background: 'none', border: 'none', cursor: 'pointer', padding: '0 4px' }}
            title="Remove condition"
          >×</button>
        )}
      </div>
    </div>
  )
}

export default function ConditionBuilder(props: ConditionBuilderProps) {
  return <ConditionRow {...props} />
}
