// Pure option-assembly + operand-encoding logic behind every view-operand picker
// (ConditionBuilder, ViewActionFields, TriggerAssignmentPanel's action editors).
//
// S1 — the <select> in OperandEditor stays string-valued; this module owns the string <->
// operand mapping. A detector channel is represented in the select only as an opaque
// "@detector/<module>#<channel>" token; viewOperandToOptionValue/optionValueToViewOperand
// convert. optionValueToViewOperand decides by membership in `detectors` (the backend's own
// detector_channels), never by parsing the token string.
//
// S2 — every label is stable-ref-first, preview-second: "MPR121 — channel 2 (-> LICKER2)".
// The parenthetical preview is decoration for the researcher only. Nothing is ever stored
// from it — only `ref` + `channel` are stored (DVK-11). Do not "fix" this by storing the
// resolved key; that is the exact bug DVK-11 exists to prevent.
import type { DetectorChannelGroup, FdaOperand } from '../types/index.ts'

export interface ViewOptionItem {
  value: string
  label: string
  title?: string
}

export interface ViewOptionGroup {
  label: string
  items: ViewOptionItem[]
  warning?: string
}

export interface KeyTemplateSuggestion {
  insert: string
  label: string
  hint: string
  disabled?: boolean
}

/** The opaque select-option token for a detector channel. Never parsed — only compared. */
function _token(moduleName: string, channel: number): string {
  return `@detector/${moduleName}#${channel}`
}

/** "0-3" for a contiguous run, else a comma-separated list. Empty input -> ''. */
function formatChannelRange(channels: number[]): string {
  if (channels.length === 0) return ''
  const sorted = [...channels].sort((a, b) => a - b)
  const isContiguous = sorted.every((c, i) => i === 0 || c === sorted[i - 1] + 1)
  return isContiguous && sorted.length > 1
    ? `${sorted[0]}-${sorted[sorted.length - 1]}`
    : sorted.join(', ')
}

function buildConflictWarning(group: DetectorChannelGroup): string {
  const parts = group.by_pilot.map(p => `${p.pilot_name} has channels ${formatChannelRange(p.channels)}`)
  return `pilots disagree: ${parts.join(', ')}`
}

/** One channel's option: value = opaque token, label = ref-first with an optional preview. */
function buildChannelItem(group: DetectorChannelGroup, channel: number): ViewOptionItem {
  // Preview built from device_names + channel — NOT by searching `keys`, which would be a
  // second key derivation. `keys` is consulted only to decide whether the backend derived
  // anything at all for this group.
  const preview = group.keys.length > 0
    ? group.device_names.map(dn => `${dn}${channel}`).join(' / ')
    : ''
  const label = `${group.module_name} — channel ${channel}${preview ? ` (→ ${preview})` : ''}`
  const title = `stored as {"view_detector": {"ref": "${group.module_name}", "channel": ${channel}}} — the name resolves on the pilot at run time`
  return { value: _token(group.module_name, channel), label, title }
}

/** Drops items whose value was already offered by an earlier group (first occurrence wins). */
function dedupeItems(items: ViewOptionItem[], seen: Set<string>): ViewOptionItem[] {
  const out: ViewOptionItem[] = []
  for (const item of items) {
    if (seen.has(item.value)) continue
    seen.add(item.value)
    out.push(item)
  }
  return out
}

/**
 * Grouped view-operand options: Hardware (the devices) -> Flags & variables -> one group per
 * detector, labelled by device_name (never module_name). Detector channels are always their own
 * group, separate from the "Hardware" group holding the device that produces them (DVK-03), and
 * come last because they are the longest and least-reached-for entries. Empty groups are dropped,
 * so a toolkit with no detectors shows no channel groups at all.
 *
 * Group order is also dedupe precedence (first occurrence of a value wins): hardware still
 * outranks flags. Detector items cannot collide with either — they are opaque "@detector/..."
 * tokens, never plain names — so moving them last changes presentation only.
 */
export function buildViewOptions(
  hwNames: string[],
  flagNames: string[],
  detectors: DetectorChannelGroup[],
): ViewOptionGroup[] {
  const seen = new Set<string>()
  const groups: ViewOptionGroup[] = []

  const hwItems = dedupeItems(hwNames.map(n => ({ value: n, label: n })), seen)
  if (hwItems.length > 0) groups.push({ label: 'Hardware', items: hwItems })

  // DVK-07: detector channels never land here — this group is fed only from toolkit.flags /
  // declared variables, never from `detectors`.
  const flagItems = dedupeItems(flagNames.map(n => ({ value: n, label: n })), seen)
  if (flagItems.length > 0) groups.push({ label: 'Flags & variables', items: flagItems })

  const sortedDetectors = [...detectors].sort((a, b) => a.module_name.localeCompare(b.module_name))
  for (const group of sortedDetectors) {
    const label = group.device_names.length > 0
      ? `${group.device_names.join(' / ')} channels`
      : `${group.module_name} channels`
    const items = dedupeItems(group.channels.map(ch => buildChannelItem(group, ch)), seen)
    if (items.length === 0) continue
    const entry: ViewOptionGroup = { label, items }
    if (group.conflict) entry.warning = buildConflictWarning(group)
    groups.push(entry)
  }

  return groups
}

/** The select's string value for a stored operand. '' when the operand is not a view operand. */
export function viewOperandToOptionValue(op: FdaOperand): string {
  if (op !== null && typeof op === 'object') {
    if ('view' in op) return op.view
    if ('tracker' in op) return op.tracker
    if ('view_detector' in op) return _token(op.view_detector.ref, op.view_detector.channel)
  }
  return ''
}

/**
 * The operand a selected option value means. A token that matches an offered
 * (module_name, channel) pair becomes a view_detector operand; anything else — including a
 * literal that merely looks like a channel key, or an out-of-range channel token — passes
 * through unchanged as a plain view operand, so nothing is invented (DVK-05/DVK-11).
 */
export function optionValueToViewOperand(value: string, detectors: DetectorChannelGroup[]): FdaOperand {
  for (const group of detectors) {
    for (const channel of group.channels) {
      if (_token(group.module_name, channel) === value) {
        return { view_detector: { ref: group.module_name, channel } }
      }
    }
  }
  return { view: value }
}

/** Is `value` offered anywhere in `groups`? Drives the DVK-05 unknown flag. */
export function isKnownViewOption(value: string, groups: ViewOptionGroup[]): boolean {
  if (value === '') return false
  return groups.some(g => g.items.some(item => item.value === value))
}

/** Compact label for an edge/summary: "MPR121 ch2". Used by operandLabel. */
export function detectorOperandLabel(ref: string, channel: number): string {
  return `${ref} ch${channel}`
}

/** DVK-04: what the key_template field offers instead of free typing. */
export function buildKeyTemplateSuggestions(
  detectors: DetectorChannelGroup[],
  variableNames: string[],
  sourceRef: string | null,
): KeyTemplateSuggestion[] {
  const suggestions: KeyTemplateSuggestion[] = [{
    insert: '{device_name}',
    label: '{device_name}',
    hint: sourceRef
      ? "resolves on the pilot at run time from the action's source device"
      : 'pick a source device first — {device_name} has nothing to resolve against',
    ...(sourceRef ? {} : { disabled: true }),
  }]

  for (const name of variableNames) {
    suggestions.push({
      insert: `{${name}}`,
      label: `{${name}}`,
      hint: `current value of the ${name} variable`,
    })
  }

  for (const group of detectors) {
    for (const key of group.keys) {
      suggestions.push({ insert: key, label: key, hint: 'pilot-specific — prefer {device_name}' })
    }
  }

  return suggestions
}
