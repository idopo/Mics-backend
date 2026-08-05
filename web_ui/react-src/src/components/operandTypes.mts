// Pure operand type/key/build logic behind ConditionBuilder's OperandEditor — extracted so the
// legacy-operand escape (retiring `flag`/`hardware` from fresh reads while keeping stored
// operands round-trippable) is an assertion, not a click-through. See 23-CONTEXT.md
// "Operand-namespace consistency" for the governing rule: write by name, read through `view`.
import type { DetectorChannelGroup, FdaOperand } from '../types/index.ts'
import {
  viewOperandToOptionValue,
  optionValueToViewOperand,
  detectorOperandLabel,
} from './detectorOptions.mts'

export type OperandType = 'view' | 'literal' | 'param' | 'flag' | 'hardware'

/** Legacy read forms kept ONLY so a stored operand round-trips — never offered as a fresh
 *  choice. `flag` is redundant with `view` (same Tracker, both dicts); `hardware` is broken
 *  (`_build_condition_operand` reads `.value`, which `Hardware` does not define). */
export const LEGACY_OPERAND_TYPES: ReadonlySet<OperandType> = new Set(['flag', 'hardware'])

export function getOperandType(op: FdaOperand): OperandType {
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

export function getOperandKey(op: FdaOperand): string {
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
export function resolveDetectorDisplayName(
  detector: { ref: string; channel: number },
  detectors: DetectorChannelGroup[],
): string {
  const group = detectors.find(g => g.module_name === detector.ref)
  if (!group) return ''
  const idx = group.channels.indexOf(detector.channel)
  return idx >= 0 ? (group.keys[idx] ?? '') : ''
}

export function buildOperand(type: OperandType, value: string, detectorChannels: DetectorChannelGroup[]): FdaOperand {
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

/** The type list a slot offers. `stored` is the type of the operand ALREADY in that slot —
 *  a legacy type is offered only to let it round-trip, never as a fresh choice. */
export function visibleOperandTypes(stored: OperandType, hasToolkit: boolean): OperandType[] {
  const base: OperandType[] = hasToolkit ? ['view', 'literal', 'param'] : ['view', 'literal']
  return LEGACY_OPERAND_TYPES.has(stored) ? [...base, stored] : base
}
