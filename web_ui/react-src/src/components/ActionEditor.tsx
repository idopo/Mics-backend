import { useEffect } from 'react'
import type { FdaAction, ToolkitRead, HardwareModule, DetectorChannelGroup } from '../types'
import ArgInput from './ArgInput'
import IfActionEditor from './IfActionEditor'
import HardwareActionFields from './HardwareActionFields'
import ViewActionFields from './ViewActionFields'
import OutputCapture from './OutputCapture'

// ── Action type metadata ────────────────────────────────────────────────────

const TYPE_COLORS: Record<string, string> = {
  hardware: '#3b82f6',
  trial:    '#0ea5e9',   // sky blue — distinct from flag amber
  flag:     '#f59e0b',
  method:   '#a78bfa',
  if:       '#22c55e',
  special:  '#94a3b8',
  view:     '#ec4899',
}

const TYPE_LABELS: Record<string, string> = {
  hardware: 'HARDWARE',
  trial:    'TRIAL CTR',
  flag:     'FLAG',
  method:   'METHOD',
  if:       'IF',
  special:  'SPECIAL',
  view:     'VIEW',
}

// ── Tracker method tables ────────────────────────────────────────────────────

export interface TrackerMethod {
  name: string
  hasArg: boolean
  description: string
}

const TRACKER_METHODS: Record<string, TrackerMethod[]> = {
  Counter_Tracker: [
    { name: 'increment', hasArg: false, description: 'Add 1 to this counter' },
    { name: 'decrement', hasArg: false, description: 'Subtract 1 from this counter' },
    { name: 'reset',     hasArg: false, description: 'Reset to its starting value' },
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

function getTrackerMethods(trackerType: string): TrackerMethod[] {
  return TRACKER_METHODS[trackerType] ?? TRACKER_METHODS['Tracker']
}

function defaultArgForTrackerType(trackerType: string): unknown {
  return trackerType === 'Boolean_Tracker' ? false : 0
}

/** Shared with HardwareActionFields — exported to avoid duplicating the predicate. */
export function isTimerModule(mod: HardwareModule): boolean {
  return mod.lib_filename === 'timer.py'
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
  onChange: (updated: FdaAction) => void
}

// ── Component ────────────────────────────────────────────────────────────────

export default function ActionEditor({ action, toolkit, hwModules, taskDefId, versionStamp, variableNames, detectorChannels, allowTriggerContext, onChange }: Props) {
  const isBackendAuthored = toolkit?.is_backend_authored ?? false

  const flagKeys = Object.keys(toolkit?.flags ?? {})
  // Split flags: trial counter flags vs regular flags
  const trialFlagKeys  = flagKeys.filter(k => toolkit?.flags?.[k]?.tracker_type === 'Trial_Tracker')
  const regularFlagKeys = flagKeys.filter(k => toolkit?.flags?.[k]?.tracker_type !== 'Trial_Tracker')
  const callableMethods = toolkit?.callable_methods ?? []

  const toolkitModules = hwModules.filter(m => toolkit?.hardware_module_ids?.includes(m.id))

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
      const trackerType = toolkit?.flags?.[firstFlag]?.tracker_type ?? 'Counter_Tracker'
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
    } else {
      onChange({ type: t as FdaAction['type'], ref: '', args: [] })
    }
  }

  function handleFlagChange(flagName: string) {
    const trackerType = toolkit?.flags?.[flagName]?.tracker_type ?? 'Counter_Tracker'
    const firstMethodDef = getTrackerMethods(trackerType)[0]
    const firstMethod = firstMethodDef?.name ?? 'increment'
    const args = firstMethodDef?.hasArg ? [defaultArgForTrackerType(trackerType)] : []
    update({ ref: flagName, method: firstMethod, args })
  }

  // Current flag method meta (for regular flags)
  const flagTrackerType = action.type === 'flag'
    ? (toolkit?.flags?.[action.ref ?? '']?.tracker_type ?? 'Counter_Tracker')
    : 'Counter_Tracker'
  const flagMethodDefs = getTrackerMethods(flagTrackerType)
  const currentFlagMethodDef = flagMethodDefs.find(m => m.name === action.method)
  const flagMethodNeedsArg = currentFlagMethodDef?.hasArg ?? false

  // Auto-initialize args for flag actions loaded from DB where args is empty but method needs one.
  // The display default in ArgInput is only cosmetic; args stays [] unless we write it here.
  useEffect(() => {
    if (action.type !== 'flag' || uiType !== 'flag') return
    if (!flagMethodNeedsArg || (action.args ?? []).length > 0) return
    update({ args: [defaultArgForTrackerType(flagTrackerType)] })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [action.method, action.ref, flagMethodNeedsArg])

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
          <option value="view">view</option>
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

      {/* ── Trial counter action ─────────────────────────────────────────── */}
      {action.type === 'flag' && uiType === 'trial' && (
        <>
          <div>
            <label style={labelStyle} title="Which Trial_Tracker flag to update? increment dispatches INC_TRIAL_COUNTER to the orchestrator.">
              Trial counter ⓘ
            </label>
            {trialFlagKeys.length === 1 ? (
              <div style={{ fontSize: '12px', fontFamily: 'monospace', color: 'var(--text)' }}>
                {trialFlagKeys[0]}
              </div>
            ) : trialFlagKeys.length > 1 ? (
              <select value={action.ref || trialFlagKeys[0]} onChange={e => update({ ref: e.target.value, method: 'increment', args: [] })} style={{ width: '100%' }}>
                {trialFlagKeys.map(k => <option key={k} value={k}>{k}</option>)}
              </select>
            ) : (
              <input type="text" value={action.ref ?? ''} onChange={e => update({ ref: e.target.value })} placeholder="trial flag name" style={{ width: '100%' }} />
            )}
          </div>
          <div>
            <label style={labelStyle}>Operation</label>
            <select value={action.method ?? 'increment'} onChange={e => update({ method: e.target.value, args: [] })} style={{ width: '100%' }}>
              {TRACKER_METHODS['Trial_Tracker'].map(m => (
                <option key={m.name} value={m.name} title={m.description}>{m.name}</option>
              ))}
            </select>
          </div>
          {action.method === 'set' && (
            <div>
              <label style={labelStyle}>Value</label>
              <ArgInput
                value={(action.args ?? [])[0] ?? 0}
                toolkit={toolkit}
                annotation="int"
                variableNames={variableNames}
                allowTriggerContext={allowTriggerContext}
                onChange={v => update({ args: [v] })}
              />
            </div>
          )}
        </>
      )}

      {/* ── Flag action (Counter / Boolean / base Tracker — not Trial) ────── */}
      {action.type === 'flag' && uiType === 'flag' && (
        <>
          <div>
            <label style={labelStyle} title="Which counter, boolean, or value tracker to update?">Flag ⓘ</label>
            {regularFlagKeys.length > 0 ? (
              <select value={action.ref ?? ''} onChange={e => handleFlagChange(e.target.value)} style={{ width: '100%' }}>
                {!regularFlagKeys.includes(action.ref ?? '') && <option value={action.ref ?? ''}>{action.ref ?? '—'}</option>}
                {regularFlagKeys.map(k => (
                  <option key={k} value={k}>{k} ({toolkit?.flags?.[k]?.tracker_type ?? 'Tracker'})</option>
                ))}
              </select>
            ) : (
              <input type="text" value={action.ref ?? ''} onChange={e => update({ ref: e.target.value })} style={{ width: '100%' }} />
            )}
          </div>
          <div>
            <label style={labelStyle} title={currentFlagMethodDef?.description ?? ''}>Operation ⓘ</label>
            <select
              value={action.method ?? flagMethodDefs[0]?.name ?? ''}
              onChange={e => {
                const newMethodDef = flagMethodDefs.find(m => m.name === e.target.value)
                const args = newMethodDef?.hasArg ? [defaultArgForTrackerType(flagTrackerType)] : []
                update({ method: e.target.value, args })
              }}
              style={{ width: '100%' }}
            >
              {flagMethodDefs.map(m => <option key={m.name} value={m.name} title={m.description}>{m.name}</option>)}
            </select>
          </div>
          {flagMethodNeedsArg && (
            <div>
              <label style={labelStyle}>Value</label>
              <ArgInput
                value={(action.args ?? [])[0] ?? (flagTrackerType === 'Boolean_Tracker' ? false : 0)}
                toolkit={toolkit}
                annotation={flagTrackerType === 'Boolean_Tracker' ? 'bool' : null}
                variableNames={variableNames}
                allowTriggerContext={allowTriggerContext}
                onChange={v => update({ args: [v] })}
              />
            </div>
          )}
        </>
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
