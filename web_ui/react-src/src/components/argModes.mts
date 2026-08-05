// Pure ArgInput mode logic — extracted so the trigger-context escape and (Task 3) the view/
// legacy-flag escape are assertions instead of click-throughs.
import type { ToolkitRead } from '../types/index.ts'
import { isStructuredAnnotation } from './computeArgs.mts'

export type ArgMode = 'literal' | 'param' | 'flag' | 'trigger'

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
    if ('flag' in (value as object)) return 'flag'
    if ('trigger' in (value as object)) return 'trigger'
  }
  return 'literal'
}

// ── Colors for mode pills ───────────────────────────────────────────────────
export const MODE_COLORS: Record<ArgMode, string> = {
  literal: '#6b7280',
  param: '#22c55e',
  flag: '#f59e0b',
  trigger: '#38bdf8',
}

export const MODE_LABELS: Record<ArgMode, string> = {
  literal: '# Literal',
  param: '$ Param',
  flag: '! Flag',
  trigger: '@ Trigger',
}

export const MODE_TOOLTIPS: Record<ArgMode, string> = {
  literal: 'A fixed value baked into the FDA. Does not change between runs.',
  param: 'Resolved from a protocol parameter at runtime. Set in the protocol step config.',
  flag: "Resolved from a flag's current value at runtime. Changes during the session.",
  trigger: 'The level or timestamp of the hardware event that fired this trigger. Only available inside a trigger action list.',
}

export const ALL_MODES: ArgMode[] = ['literal', 'param', 'flag', 'trigger']

/** Today's rule, lifted out of ArgInput.tsx:82. Task 3 adds the flag legacy escape. */
export function visibleArgModes(mode: ArgMode, allowTriggerContext: boolean): ArgMode[] {
  return allowTriggerContext || mode === 'trigger' ? ALL_MODES : ALL_MODES.filter(m => m !== 'trigger')
}
