import { useEffect } from 'react'
import type { FdaAction, ToolkitRead } from '../types'
import ArgInput from './ArgInput'
import { labelStyle } from './ActionEditor'
import { TRACKER_METHODS, getTrackerMethods, defaultArgForTrackerType, trackerTypeForRef } from './trackerMethods.mts'

interface Props {
  action: FdaAction
  uiType: string
  toolkit: ToolkitRead | null
  trialFlagKeys: string[]
  /** toolkit.flags (minus Trial_Tracker) union declared FdaJson.variables — CMP-22. */
  regularFlagKeys: string[]
  variableNames?: string[]
  allowTriggerContext?: boolean
  onChange: (patch: Partial<FdaAction>) => void
}

/** Trial-counter and regular-flag write actions — extracted out of ActionEditor for its
 *  file-size budget. Renders when `action.type === 'flag'` (uiType is 'trial' or 'flag'). */
export default function FlagActionFields({
  action, uiType, toolkit, trialFlagKeys, regularFlagKeys, variableNames, allowTriggerContext, onChange: update,
}: Props) {
  function handleFlagChange(flagName: string) {
    const trackerType = trackerTypeForRef(flagName, toolkit?.flags, variableNames ?? [])
    const firstMethodDef = getTrackerMethods(trackerType)[0]
    const firstMethod = firstMethodDef?.name ?? 'increment'
    const args = firstMethodDef?.hasArg ? [defaultArgForTrackerType(trackerType)] : []
    update({ ref: flagName, method: firstMethod, args })
  }

  // Current flag method meta (for regular flags)
  const flagTrackerType = action.type === 'flag'
    ? trackerTypeForRef(action.ref ?? '', toolkit?.flags, variableNames ?? [])
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

  return (
    <>
      {/* ── Trial counter action ─────────────────────────────────────────── */}
      {uiType === 'trial' && (
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
      {uiType === 'flag' && (
        <>
          <div>
            <label style={labelStyle} title="Which counter, boolean, or value tracker to update?">Flag ⓘ</label>
            {regularFlagKeys.length > 0 ? (
              <select value={action.ref ?? ''} onChange={e => handleFlagChange(e.target.value)} style={{ width: '100%' }}>
                {!regularFlagKeys.includes(action.ref ?? '') && <option value={action.ref ?? ''}>{action.ref ?? '—'}</option>}
                {regularFlagKeys.map(k => {
                  const tt = trackerTypeForRef(k, toolkit?.flags, variableNames ?? [])
                  const isVar = !(toolkit?.flags && k in toolkit.flags)
                  return <option key={k} value={k}>{k} ({tt}){isVar ? ' — variable' : ''}</option>
                })}
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
    </>
  )
}
