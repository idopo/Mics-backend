import type { FdaAction, ToolkitRead, HardwareModule, DetectorChannelGroup } from '../types'
import ArgInput from './ArgInput'
import IfActionEditor from './IfActionEditor'
import HardwareActionFields from './HardwareActionFields'
import ViewActionFields from './ViewActionFields'
import ComputeActionFields from './ComputeActionFields'
import FlagActionFields from './FlagActionFields'
import OutputCapture from './OutputCapture'
import { getTrackerMethods, defaultArgForTrackerType, trackerTypeForRef } from './trackerMethods.mts'

// ── Action type metadata ────────────────────────────────────────────────────

const TYPE_COLORS: Record<string, string> = {
  hardware: '#3b82f6',
  trial:    '#0ea5e9',   // sky blue — distinct from flag amber
  flag:     '#f59e0b',
  method:   '#a78bfa',
  if:       '#22c55e',
  special:  '#94a3b8',
  view:     '#ec4899',
  compute:  '#8b5cf6',   // distinct from method's #a78bfa
}

const TYPE_LABELS: Record<string, string> = {
  hardware: 'HARDWARE',
  trial:    'TRIAL CTR',
  flag:     'FLAG',
  method:   'METHOD',
  if:       'IF',
  special:  'SPECIAL',
  view:     'VIEW',
  compute:  'COMPUTE',
}

/** Shared with HardwareActionFields — exported to avoid duplicating the predicate. */
export function isTimerModule(mod: HardwareModule): boolean {
  return mod.lib_filename === 'timer.py'
}

/** Shared with ComputeActionFields — exported to avoid duplicating the predicate. */
export function isComputeModule(mod: HardwareModule): boolean {
  return mod.lib_kind === 'compute'
}

// ── Style helpers ────────────────────────────────────────────────────────────
// labelStyle is exported for HardwareActionFields — a static style const never varies
// per render, so exporting it is cleaner than threading it through every prop chain.

export const labelStyle: React.CSSProperties = {
  fontSize: '11px',
  color: 'var(--muted)',
  display: 'block',
  marginBottom: '2px',
}

function cardStyle(type: string): React.CSSProperties {
  const color = TYPE_COLORS[type] ?? '#94a3b8'
  const rgb = hexToRgb(color)
  return {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    padding: '8px',
    background: rgb ? `rgba(${rgb}, 0.06)` : 'rgba(255,255,255,0.03)',
    borderRadius: '6px',
    border: `1px solid ${rgb ? `rgba(${rgb}, 0.25)` : 'var(--border)'}`,
    borderLeft: `3px solid ${color}`,
  }
}

function hexToRgb(hex: string): string | null {
  const m = /^#([0-9a-f]{6})$/i.exec(hex)
  if (!m) return null
  const n = parseInt(m[1], 16)
  return `${(n >> 16) & 0xff}, ${(n >> 8) & 0xff}, ${n & 0xff}`
}

function typeChipStyle(type: string): React.CSSProperties {
  const color = TYPE_COLORS[type] ?? '#94a3b8'
  return {
    display: 'inline-block',
    padding: '1px 6px',
    borderRadius: '3px',
    fontSize: '9px',
    fontWeight: 700,
    fontFamily: "'IBM Plex Mono', monospace",
    letterSpacing: '0.08em',
    background: `${color}22`,
    color,
    border: `1px solid ${color}44`,
  }
}

// ── Props ────────────────────────────────────────────────────────────────────

interface Props {
  action: FdaAction
  toolkit: ToolkitRead | null
  hwModules: HardwareModule[]
  taskDefId?: number
  versionStamp?: string
  /** Declared FdaJson.variables names — valid `output` targets and key_template tokens. */
  variableNames?: string[]
  detectorChannels?: DetectorChannelGroup[]
  /** True only when this editor is inside a trigger's action list. */
  allowTriggerContext?: boolean
  /** Declares a new name into FdaJson.variables — threaded from TaskEditor for compute's
   *  auto-declare-on-type behaviour (CMP-13). */
  onDeclareVariable?: (name: string) => void
  onChange: (updated: FdaAction) => void
}

// ── Component ────────────────────────────────────────────────────────────────

export default function ActionEditor({ action, toolkit, hwModules, taskDefId, versionStamp, variableNames, detectorChannels, allowTriggerContext, onDeclareVariable, onChange }: Props) {
  const isBackendAuthored = toolkit?.is_backend_authored ?? false

  const flagKeys = Object.keys(toolkit?.flags ?? {})
  // Split flags: trial counter flags vs regular flags
  const trialFlagKeys  = flagKeys.filter(k => toolkit?.flags?.[k]?.tracker_type === 'Trial_Tracker')
  // CMP-22: declared variables are a valid flag-write ref too — same self.flags namespace on
  // the Pi, resolved through the 'Tracker' method set via trackerTypeForRef, never the
  // Counter_Tracker default.
  const regularFlagKeys = [...new Set([
    ...flagKeys.filter(k => toolkit?.flags?.[k]?.tracker_type !== 'Trial_Tracker'),
    ...(variableNames ?? []),
  ])]
  const callableMethods = toolkit?.callable_methods ?? []

  const toolkitModules = hwModules.filter(m => toolkit?.hardware_module_ids?.includes(m.id))
  const firstComputeModule = toolkitModules.filter(isComputeModule)[0]

  const update = (patch: Partial<FdaAction>) => onChange({ ...action, ...patch })

  // ── Normalise stored FDA types for display ───────────────────────────────
  // type:timer in FDA → show as hardware (timer is a hw module sub-type)
  // type:flag with Trial_Tracker ref → show as trial
  function effectiveUiType(): string {
    if (action.type === 'timer') return 'hardware'
    if (action.type === 'flag' && trialFlagKeys.includes(action.ref ?? '')) return 'trial'
    return action.type
  }
  const uiType = effectiveUiType()

  // ── Type change handler ──────────────────────────────────────────────────

  function handleTypeChange(t: string) {
    if (t === 'hardware') {
      const firstMod = isBackendAuthored ? (toolkitModules[0]?.name ?? '') : (Object.keys(toolkit?.semantic_hardware ?? {})[0] ?? '')
      const isTimer = toolkitModules[0] ? isTimerModule(toolkitModules[0]) : false
      onChange({ type: isTimer ? 'timer' : 'hardware', ref: firstMod, method: isTimer ? 'start' : '', args: [] })
    } else if (t === 'trial') {
      onChange({ type: 'flag', ref: trialFlagKeys[0] ?? '', method: 'increment', args: [] })
    } else if (t === 'flag') {
      const firstFlag = regularFlagKeys[0] ?? ''
      const trackerType = trackerTypeForRef(firstFlag, toolkit?.flags, variableNames ?? [])
      const firstMethodDef = getTrackerMethods(trackerType)[0]
      const firstMethod = firstMethodDef?.name ?? 'increment'
      const args = firstMethodDef?.hasArg ? [defaultArgForTrackerType(trackerType)] : []
      onChange({ type: 'flag', ref: firstFlag, method: firstMethod, args })
    } else if (t === 'if') {
      onChange({ type: 'if', condition: undefined, then: [], else: undefined })
    } else if (t === 'method') {
      onChange({ type: 'method', ref: callableMethods[0] ?? '', args: [] })
    } else if (t === 'view') {
      // A brand-new action object (no spread of the previous type's fields) — switching
      // AWAY from view naturally drops key_template/value/kwargs the same way every other
      // branch here drops the previous type's ref/method/args.
      onChange({ type: 'view', key_template: '', value: null, kwargs: {} })
    } else if (t === 'compute') {
      // A brand-new action object (no spread of the previous type's fields) — same
      // precedent as the view branch above.
      onChange({ type: 'compute', ref: firstComputeModule?.name ?? '', method: '', args: [], output: '' })
    } else {
      onChange({ type: t as FdaAction['type'], ref: '', args: [] })
    }
  }

  // ── Legacy special action ────────────────────────────────────────────────
  if (action.type === 'special') {
    return (
      <div style={{ ...cardStyle('special'), flexDirection: 'row', alignItems: 'center', gap: '8px' }}>
        <span style={typeChipStyle('special')}>LEGACY</span>
        <span style={{ fontSize: '11px', color: '#f59e0b' }}>
          Legacy special action: {action.action} — replace with a Trial_Tracker flag increment.
        </span>
      </div>
    )
  }

  return (
    <div style={cardStyle(uiType)}>
      {/* Header: colored chip + type selector */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span style={typeChipStyle(uiType)} title="What kind of action executes when this state is entered?">
          {TYPE_LABELS[uiType] ?? uiType.toUpperCase()}
        </span>
        <select
          value={uiType}
          onChange={e => handleTypeChange(e.target.value)}
          style={{ fontSize: '11px', flex: 1 }}
          title="What kind of action executes when this state is entered?"
        >
          <option value="hardware">hardware</option>
          <option value="trial">trial counter</option>
          <option value="flag">flag</option>
          {/* Compute is out of scope for trigger assignments this phase (deferred, 2026-08-03) —
              hidden there so an already-set value stays readable but the option can't be picked. */}
          {(!allowTriggerContext || action.type === 'compute') && (
            <option value="compute">compute</option>
          )}
          {/* View is not a user-facing state-body action: the view is the *read* surface,
              written indirectly by hardware/flag actions and by the detector-read macro under a
              trigger. Offered only inside trigger actions (where detect-change lives), plus
              whenever an already-stored view action needs to stay readable/editable. */}
          {(allowTriggerContext || action.type === 'view') && (
            <option value="view">view</option>
          )}
          <option value="method">method</option>
          <option value="if">if</option>
        </select>
      </div>

      {/* ── Hardware action (includes timer modules) ─────────────────────── */}
      {(action.type === 'hardware' || action.type === 'timer') && (
        <HardwareActionFields
          action={action}
          toolkit={toolkit}
          hwModules={hwModules}
          taskDefId={taskDefId}
          versionStamp={versionStamp}
          allowTriggerContext={allowTriggerContext}
          variableNames={variableNames}
          onChange={update}
        />
      )}

      {/* ── Trial counter / flag write action ──────────────────────────────── */}
      {action.type === 'flag' && (uiType === 'trial' || uiType === 'flag') && (
        <FlagActionFields
          action={action}
          uiType={uiType}
          toolkit={toolkit}
          trialFlagKeys={trialFlagKeys}
          regularFlagKeys={regularFlagKeys}
          variableNames={variableNames}
          allowTriggerContext={allowTriggerContext}
          onChange={update}
        />
      )}

      {/* ── View action ──────────────────────────────────────────────────── */}
      {action.type === 'view' && (
        <ViewActionFields
          action={action}
          toolkit={toolkit}
          variableNames={variableNames}
          detectorChannels={detectorChannels}
          allowTriggerContext={allowTriggerContext}
          onChange={update}
        />
      )}

      {/* ── Compute action ───────────────────────────────────────────────── */}
      {action.type === 'compute' && (
        <ComputeActionFields
          action={action}
          toolkit={toolkit}
          hwModules={hwModules}
          taskDefId={taskDefId}
          versionStamp={versionStamp}
          variableNames={variableNames}
          onDeclareVariable={onDeclareVariable}
          onChange={update}
        />
      )}

      {/* ── Method action ────────────────────────────────────────────────── */}
      {action.type === 'method' && (
        <>
          <div>
            <label style={labelStyle}>Method name</label>
            {callableMethods.length > 0 ? (
              <select value={action.ref ?? ''} onChange={e => update({ ref: e.target.value })} style={{ width: '100%' }}>
                {!callableMethods.includes(action.ref ?? '') && <option value={action.ref ?? ''}>{action.ref ?? '—'}</option>}
                {callableMethods.map(k => <option key={k} value={k}>{k}</option>)}
              </select>
            ) : (
              <input type="text" value={action.ref ?? ''} onChange={e => update({ ref: e.target.value })} placeholder="method name" style={{ width: '100%' }} />
            )}
          </div>
          {(action.args ?? []).map((arg, i) => (
            <div key={i}>
              <label style={labelStyle}>Arg {i + 1}</label>
              <ArgInput
                value={arg}
                toolkit={toolkit}
                annotation={null}
                variableNames={variableNames}
                allowTriggerContext={allowTriggerContext}
                onChange={v => {
                  const newArgs = [...(action.args ?? [])]
                  newArgs[i] = v
                  update({ args: newArgs })
                }}
              />
            </div>
          ))}
        </>
      )}

      {/* ── Output capture (hardware/timer/method actions only) ───────────── */}
      {(action.type === 'hardware' || action.type === 'timer' || action.type === 'method') && (
        <OutputCapture action={action} variableNames={variableNames} onChange={update} />
      )}

      {/* ── If action ─────────────────────────────────────────────────────── */}
      {action.type === 'if' && (
        <IfActionEditor
          action={action}
          toolkit={toolkit}
          hwModules={hwModules}
          taskDefId={taskDefId}
          versionStamp={versionStamp}
          variableNames={variableNames}
          detectorChannels={detectorChannels}
          allowTriggerContext={allowTriggerContext}
          onChange={onChange}
        />
      )}
    </div>
  )
}
