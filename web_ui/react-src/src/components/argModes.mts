// Pure ArgInput mode logic — extracted so the trigger-context escape and (Task 3) the view/
// legacy-flag escape are assertions instead of click-throughs.
import type { ToolkitRead } from '../types/index.ts'
import { isStructuredAnnotation } from './computeArgs.mts'

export type ArgMode = 'literal' | 'param' | 'view' | 'flag' | 'trigger'

export type LiteralInputKind = 'number' | 'bool' | 'text' | 'structured'

/** Handles both array [{name}] and dict {name:{}} shapes for params_schema. */
export function getParamKeys(toolkit: ToolkitRead | null | undefined): string[] {
  const schema = toolkit?.params_schema
  if (!schema) return []
  if (Array.isArray(schema)) return schema.map((p: { name: string }) => p.name)
  return Object.keys(schema)
}

export function annotationToInputKind(ann: string | null | undefined): LiteralInputKind {
  if (!ann) return 'text'
  // list/dict get a parsing editor — a plain text input silently stored '["a","b"]' as a
  // string and the Pi ran random.choice() over its characters.
  if (isStructuredAnnotation(ann)) return 'structured'
  const base = ann.replace(/Optional\[|\]/g, '').trim()
  if (base === 'bool') return 'bool'
  if (base === 'int' || base === 'float') return 'number'
  return 'text'
}

export function detectMode(value: unknown): ArgMode {
  if (value !== null && typeof value === 'object') {
    if ('param' in (value as object)) return 'param'
    if ('view' in (value as object)) return 'view'
    if ('flag' in (value as object)) return 'flag'
    if ('trigger' in (value as object)) return 'trigger'
  }
  return 'literal'
}

// ── Colors for mode pills ───────────────────────────────────────────────────
export const MODE_COLORS: Record<ArgMode, string> = {
  literal: '#6b7280',
  param: '#22c55e',
  // 'view' reuses the view ACTION's pink from ActionEditor's TYPE_COLORS — same concept, same colour.
  view: '#ec4899',
  flag: '#f59e0b',
  trigger: '#38bdf8',
}

export const MODE_LABELS: Record<ArgMode, string> = {
  literal: '# Literal',
  param: '$ Param',
  view: '~ View',
  flag: '! Flag (legacy)',
  trigger: '@ Trigger',
}

export const MODE_TOOLTIPS: Record<ArgMode, string> = {
  literal: 'A fixed value baked into the FDA. Does not change between runs.',
  param: 'Resolved from a protocol parameter at runtime. Set in the protocol step config.',
  view: 'Read a value from the live view at run time — toolkit flags, declared variables, and hardware state. The read namespace.',
  flag: 'Legacy read form, kept so this saved argument round-trips. Switch to View — it reads the same value.',
  trigger: 'The level or timestamp of the hardware event that fired this trigger. Only available inside a trigger action list.',
}

/** 'flag' is escape-only — never in the base list, only appended by visibleArgModes when the
 *  stored value is already a flag operand. */
export const ALL_MODES: ArgMode[] = ['literal', 'param', 'view', 'trigger']

/** Defensive: if the stored value is already a trigger (or flag) operand, keep offering that
 *  pill even when this editor wasn't opted into it — never silently corrupt the stored value. */
export function visibleArgModes(mode: ArgMode, allowTriggerContext: boolean): ArgMode[] {
  const base = allowTriggerContext || mode === 'trigger' ? ALL_MODES : ALL_MODES.filter(m => m !== 'trigger')
  return mode === 'flag' ? [...base, 'flag'] : base
}
