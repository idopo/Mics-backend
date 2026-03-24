import type { FdaState, FdaAction, ToolkitRead } from '../types'
import ActionEditor from './ActionEditor'
import { operandLabel } from './ConditionBuilder'

const DEFAULT_ACTION: FdaAction = { type: 'hardware', ref: '', method: 'set', args: [1] }

interface Props {
  stateName: string
  state: FdaState
  toolkit: ToolkitRead | null
  onChange: (updated: FdaState) => void
}

export default function StateBodyPanel({ stateName, state, toolkit, onChange }: Props) {
  const isPassthrough = !state.entry_actions?.length && (toolkit?.states?.includes(stateName) ?? false)
  const actions = state.entry_actions ?? []

  const updateAction = (i: number, updated: FdaAction) =>
    onChange({ ...state, entry_actions: actions.map((a, idx) => idx === i ? updated : a) })

  const removeAction = (i: number) =>
    onChange({ ...state, entry_actions: actions.filter((_, idx) => idx !== i) })

  const addAction = () =>
    onChange({ ...state, entry_actions: [...actions, { ...DEFAULT_ACTION }] })

  return (
    <div>
      <div style={{ fontSize: '12px', color: 'var(--muted)', marginBottom: '8px', fontWeight: 500 }}>
        STATE BODY
      </div>
      <div style={{ fontSize: '13px', fontWeight: 600, fontFamily: 'monospace', marginBottom: '12px', color: 'var(--text)' }}>
        {stateName}
        {isPassthrough && (
          <span style={{ marginLeft: '8px', fontSize: '11px', color: '#9ca3af', fontFamily: 'sans-serif', fontWeight: 400 }}>
            locked passthrough
          </span>
        )}
      </div>

      {isPassthrough ? (
        <p style={{ fontSize: '12px', color: 'var(--muted)', margin: 0 }}>
          This state delegates to the Python method of the same name. Add an entry_action to override.
        </p>
      ) : (
        <>
          {actions.length === 0 ? (
            <p style={{ fontSize: '12px', color: 'var(--muted)', marginBottom: '12px' }}>
              No entry actions. Add one below.
            </p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '12px' }}>
              {actions.map((action, i) => (
                <div key={i}>
                  <ActionEditor action={action} toolkit={toolkit} onChange={updated => updateAction(i, updated)} />
                  <button
                    className="button-danger"
                    style={{ fontSize: '11px', padding: '2px 6px', marginTop: '4px' }}
                    onClick={() => removeAction(i)}
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
          )}
          <button className="button-secondary" style={{ fontSize: '12px', width: '100%' }} onClick={addAction}>
            + Add action
          </button>
        </>
      )}

      {state.wait_condition && (
        <div style={{ marginTop: '16px', padding: '8px', background: 'rgba(0,0,0,0.2)', borderRadius: '6px', border: '1px solid var(--border)' }}>
          <div style={{ fontSize: '11px', color: 'var(--muted)', marginBottom: '4px' }}>wait_condition (read-only)</div>
          <code style={{ fontSize: '12px', color: '#60a5fa' }}>
            {operandLabel(state.wait_condition.left)} {state.wait_condition.op} {operandLabel(state.wait_condition.right)}
          </code>
        </div>
      )}

      {state.return_data && state.return_data.length > 0 && (
        <div className="param-field" style={{ marginTop: '12px' }}>
          <span className="param-name">return_data</span>
          <span className="meta-pill">{state.return_data.map(String).join(', ')}</span>
        </div>
      )}
    </div>
  )
}
