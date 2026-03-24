import type { FdaAction, FdaCondition, ToolkitRead } from '../types'
import ConditionBuilder from './ConditionBuilder'
import ActionEditor from './ActionEditor'

interface Props {
  action: FdaAction // action.type === 'if'
  toolkit: ToolkitRead | null
  onChange: (updated: FdaAction) => void
}

const EMPTY_CONDITION: FdaCondition = { left: { view: '' }, op: '==', right: 0 }
const DEFAULT_ACTION: FdaAction = { type: 'hardware', ref: '', method: 'set', args: [1] }

const branchLabel: React.CSSProperties = {
  fontSize: '11px',
  color: 'var(--muted)',
  fontWeight: 600,
  letterSpacing: '0.06em',
  textTransform: 'uppercase' as const,
  marginBottom: '6px',
  display: 'block',
}

export default function IfActionEditor({ action, toolkit, onChange }: Props) {
  const thenActions: FdaAction[] = action.then ?? []
  const elseActions: FdaAction[] | undefined = action.else

  const updateCondition = (updated: FdaCondition) =>
    onChange({ ...action, condition: updated })

  const updateThen = (i: number, updated: FdaAction) =>
    onChange({ ...action, then: thenActions.map((a, idx) => (idx === i ? updated : a)) })

  const removeThen = (i: number) =>
    onChange({ ...action, then: thenActions.filter((_, idx) => idx !== i) })

  const addThen = () =>
    onChange({ ...action, then: [...thenActions, { ...DEFAULT_ACTION }] })

  const updateElse = (i: number, updated: FdaAction) =>
    onChange({
      ...action,
      else: (elseActions ?? []).map((a, idx) => (idx === i ? updated : a)),
    })

  const removeElse = (i: number) =>
    onChange({
      ...action,
      else: (elseActions ?? []).filter((_, idx) => idx !== i),
    })

  const addElse = () =>
    onChange({ ...action, else: [...(elseActions ?? []), { ...DEFAULT_ACTION }] })

  const removeElseBranch = () => {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { else: _removed, ...rest } = action
    onChange(rest as FdaAction)
  }

  return (
    <div
      style={{
        borderLeft: '2px solid var(--lavender)',
        paddingLeft: '10px',
        marginTop: '4px',
        display: 'flex',
        flexDirection: 'column',
        gap: '0',
      }}
    >
      {/* Condition */}
      <span style={branchLabel}>Condition</span>
      <ConditionBuilder
        condition={action.condition ?? EMPTY_CONDITION}
        toolkit={toolkit}
        onChange={updateCondition}
      />

      {/* Then branch */}
      <div style={{ marginTop: '10px' }}>
        <span style={branchLabel}>Then</span>
        {thenActions.length === 0 ? (
          <p style={{ fontSize: '12px', color: 'var(--muted)', marginBottom: '6px' }}>
            No actions.
          </p>
        ) : (
          <div
            style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '6px' }}
          >
            {thenActions.map((a, i) => (
              <div key={i}>
                <ActionEditor
                  action={a}
                  toolkit={toolkit}
                  onChange={upd => updateThen(i, upd)}
                />
                <button
                  className="button-danger"
                  style={{ fontSize: '10px', padding: '1px 6px', marginTop: '3px' }}
                  onClick={() => removeThen(i)}
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        )}
        <button
          className="button-secondary"
          style={{ fontSize: '11px', width: '100%' }}
          onClick={addThen}
        >
          + Add then action
        </button>
      </div>

      {/* Else branch */}
      <div style={{ marginTop: '10px' }}>
        {elseActions === undefined ? (
          <button
            className="button-link"
            style={{ fontSize: '11px', color: 'var(--muted)' }}
            onClick={() => onChange({ ...action, else: [] })}
          >
            + Add else branch
          </button>
        ) : (
          <>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: '6px',
              }}
            >
              <span style={branchLabel}>Else</span>
              <button
                className="button-link"
                style={{ fontSize: '10px', color: 'var(--error)' }}
                onClick={removeElseBranch}
              >
                Remove else
              </button>
            </div>
            {elseActions.length === 0 ? (
              <p style={{ fontSize: '12px', color: 'var(--muted)', marginBottom: '6px' }}>
                No actions.
              </p>
            ) : (
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '6px',
                  marginBottom: '6px',
                }}
              >
                {elseActions.map((a, i) => (
                  <div key={i}>
                    <ActionEditor
                      action={a}
                      toolkit={toolkit}
                      onChange={upd => updateElse(i, upd)}
                    />
                    <button
                      className="button-danger"
                      style={{ fontSize: '10px', padding: '1px 6px', marginTop: '3px' }}
                      onClick={() => removeElse(i)}
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            )}
            <button
              className="button-secondary"
              style={{ fontSize: '11px', width: '100%' }}
              onClick={addElse}
            >
              + Add else action
            </button>
          </>
        )}
      </div>
    </div>
  )
}
