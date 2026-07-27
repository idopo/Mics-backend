import type { FdaAction, FdaVariable, ToolkitRead } from '../types'

interface Props {
  actions: FdaAction[]
  toolkit: ToolkitRead | null
  variables: Record<string, FdaVariable>
  onChange: (actions: FdaAction[], variables: Record<string, FdaVariable>) => void
}

/** The two names a hardware `detect_change` call captures — always these two, in this order. */
const CAPTURE_NAMES = ['pin_number', 'level'] as const

function buildActions(ref: string): FdaAction[] {
  return [
    { type: 'hardware', ref, method: 'detect_change', args: [], output: ['pin_number', 'level'] },
    {
      type: 'if',
      condition: { left: { flag: 'pin_number' }, op: '!=', right: null },
      then: [
        { type: 'view', key_template: '{device_name}{pin_number}', source_ref: ref, value: { flag: 'level' } },
      ],
    },
  ]
}

/** Capture names this affordance cannot safely auto-declare — each already names a toolkit
 *  flag, and fda_validation.validate_variables hard-422s a variable/flag name collision. */
export function detectorCaptureCollisions(toolkit: ToolkitRead | null): string[] {
  return CAPTURE_NAMES.filter(name => name in (toolkit?.flags ?? {}))
}

/** Build the canonical action list plus the variables patch that declares its capture slots,
 *  in one call — actions and variables must be emitted together, since a debounced save
 *  landing between "actions reference pin_number" and "pin_number is declared" is a 422. */
export function buildDetectorWrite(
  ref: string,
  variables: Record<string, FdaVariable>,
): { actions: FdaAction[]; variables: Record<string, FdaVariable> } {
  const nextVariables = { ...variables }
  for (const name of CAPTURE_NAMES) {
    if (!(name in nextVariables)) nextVariables[name] = {}
  }
  return { actions: buildActions(ref), variables: nextVariables }
}

/**
 * Returns the detector ref when `actions` is structurally exactly the canonical detector-write
 * shape (24-CONTEXT.md <canonical_payload>) — compared field by field, never by serialised JSON
 * equality — else null. A hand-edited list that no longer matches degrades to the raw editor;
 * that is graceful degradation (R4), not a bug to paper over.
 */
export function matchesDetectorWrite(actions: FdaAction[]): string | null {
  if (actions.length !== 2) return null
  const [hw, ifAction] = actions
  if (hw.type !== 'hardware' || hw.method !== 'detect_change' || !hw.ref) return null
  const output = hw.output
  if (!Array.isArray(output) || output[0] !== 'pin_number' || output[1] !== 'level') return null

  if (ifAction.type !== 'if') return null
  const then = ifAction.then ?? []
  if (then.length !== 1) return null
  const view = then[0]
  if (view.type !== 'view' || view.source_ref !== hw.ref || view.key_template !== '{device_name}{pin_number}') {
    return null
  }
  return hw.ref
}

/**
 * The constrained one-pick detector write (TRIGA-17): the researcher picks the device and
 * NOTHING else. The target key and the written value both derive from that call's own return —
 * reading electrode 2 and writing LICKER0 is structurally impossible from this affordance. No
 * key_template box, no operand wiring, no value field, no pin field.
 *
 * A UI macro over the general vocabulary: `onChange` emits ordinary FDA JSON through the same
 * `actions` list a hand-built trigger uses. Nothing new reaches the Pi.
 */
export default function DetectorWriteWidget({ actions, toolkit, variables, onChange }: Props): JSX.Element | null {
  const detectorRefs = toolkit?.detector_refs ?? []
  if (detectorRefs.length === 0) return null

  const collisions = detectorCaptureCollisions(toolkit)
  const currentRef = matchesDetectorWrite(actions) ?? detectorRefs[0]

  const label = (
    <label style={{ fontSize: '11px', color: 'var(--muted)', display: 'block', marginBottom: '4px' }}>
      Read detector
    </label>
  )

  if (collisions.length > 0) {
    return (
      <div style={{
        padding: '8px', background: 'rgba(239,68,68,0.06)',
        border: '1px solid rgba(239,68,68,0.3)', borderRadius: '6px',
      }}>
        {label}
        <p style={{ fontSize: '11px', color: '#ef4444', margin: 0 }}>
          Can't auto-declare {collisions.join(', ')} — already used as toolkit flag name{collisions.length > 1 ? 's' : ''}.
          Use the raw action editor instead.
        </p>
      </div>
    )
  }

  const setDevice = (ref: string): void => {
    const built = buildDetectorWrite(ref, variables)
    onChange(built.actions, built.variables)
  }

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', gap: '6px', padding: '8px',
      background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)', borderRadius: '6px',
    }}>
      {label}
      <select
        value={currentRef}
        onChange={e => setDevice(e.target.value)}
        style={{ width: '100%', fontFamily: "'IBM Plex Mono', monospace", fontSize: '12px' }}
      >
        {detectorRefs.map(ref => <option key={ref} value={ref}>{ref}</option>)}
      </select>
      <p style={{ fontSize: '10px', color: 'var(--muted)', margin: 0 }}>
        → on each interrupt, writes the tracker for whichever electrode changed, timestamped by
        the trigger. Both the electrode and its level come from the device&apos;s own reply. The
        tracker names are the device&apos;s <code>device_name</code> + index, resolved on the
        pilot at run time — not <code>{currentRef}</code>, which is the module name.
      </p>
    </div>
  )
}
