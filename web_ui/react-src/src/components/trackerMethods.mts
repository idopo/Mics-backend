// Tracker method tables behind ActionEditor's flag/trial-counter write pickers, extracted so
// CMP-22's variable-as-write-target resolution is tested rather than click-through-verified.

export interface TrackerMethod {
  name: string
  hasArg: boolean
  description: string
}

export const TRACKER_METHODS: Record<string, TrackerMethod[]> = {
  // decrement/reset removed 2026-08-05 (CMP-22): neither exists on any Tracker.py class —
  // picking one saved cleanly and raised AttributeError on the rig. Zero of 153 task
  // definitions used either at the time of removal (verified against the dev DB).
  Counter_Tracker: [
    { name: 'increment', hasArg: false, description: 'Add 1 to this counter' },
    { name: 'set',       hasArg: true,  description: 'Set to an exact value' },
  ],
  Boolean_Tracker: [
    { name: 'set',    hasArg: true,  description: 'Set to an exact value' },
    { name: 'toggle', hasArg: false, description: 'Flip between true and false' },
  ],
  Trial_Tracker: [
    { name: 'increment', hasArg: false, description: 'Increment trial count (dispatches INC_TRIAL_COUNTER to orchestrator)' },
    { name: 'set',       hasArg: true,  description: 'Set trial count to an exact value' },
  ],
  Tracker: [
    { name: 'increment', hasArg: false, description: 'Add 1 to this tracker' },
    { name: 'set',       hasArg: true,  description: 'Set to any value' },
  ],
}

export function getTrackerMethods(trackerType: string): TrackerMethod[] {
  return TRACKER_METHODS[trackerType] ?? TRACKER_METHODS['Tracker']
}

export function defaultArgForTrackerType(trackerType: string): unknown {
  return trackerType === 'Boolean_Tracker' ? false : 0
}

/** The tracker method set a flag-action `ref` resolves to. A declared variable is a plain
 *  Tracker (increment/set) — the historical `?? 'Counter_Tracker'` default is wrong for it. */
export function trackerTypeForRef(
  ref: string,
  flags: Record<string, { tracker_type?: string }> | null | undefined,
  variableNames: readonly string[] = [],
): string {
  const declared = flags?.[ref]?.tracker_type
  if (declared) return declared
  if (variableNames.includes(ref)) return 'Tracker'
  return 'Counter_Tracker'
}
