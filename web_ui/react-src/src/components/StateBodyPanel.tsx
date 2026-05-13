import type { FdaState, FdaAction, ToolkitRead, HardwareModule } from '../types'
import ActionEditor from './ActionEditor'
import { operandLabel } from './ConditionBuilder'

// ── Action type color chips ──────────────────────────────────────────────────

const TYPE_COLORS: Record<string, string> = {
  hardware: '#3b82f6',
  flag: '#f59e0b',
  timer: '#14b8a6',
  method: '#a78bfa',
  if: '#22c55e',
  special: '#94a3b8',
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
    flexShrink: 0,
  }
}

function actionSummary(action: FdaAction): string {
  if (action.type === 'hardware') return action.ref ? `${action.ref}.${action.method ?? ''}` : 'hardware'
  if (action.type === 'flag') return action.ref ? `${action.ref}.${action.method ?? ''}` : 'flag'
  if (action.type === 'timer') return action.ref ? `${action.ref}.${action.method ?? ''}` : 'timer'
  if (action.type === 'method') return action.ref ?? 'method'
  if (action.type === 'if') return 'if (…)'
  if (action.type === 'special') return `special: ${action.action ?? ''}`
  return action.type
}

interface Props {
  stateName: string
  state: FdaState
  toolkit: ToolkitRead | null
  hwModules: HardwareModule[]
  onChange: (updated: FdaState) => void
}

export default function StateBodyPanel({ stateName, state, toolkit, hwModules, onChange }: Props) {
  const isPassthrough = !state.entry_actions?.length && (toolkit?.states?.includes(stateName) ?? false)
  const actions = state.entry_actions ?? []

  const updateAction = (i: number, updated: FdaAction) =>
    onChange({ ...state, entry_actions: actions.map((a, idx) => idx === i ? updated : a) })

  const removeAction = (i: number) =>
    onChange({ ...state, entry_actions: actions.filter((_, idx) => idx !== i) })

  const addAction = () => {
    const toolkitModules = hwModules.filter(m => toolkit?.hardware_module_ids?.includes(m.id))
    const firstMod = toolkit?.is_backend_authored ? toolkitModules[0] : undefined
    const isTimer = firstMod?.lib_filename === 'timer.py'
    const initial: FdaAction = firstMod
      ? { type: isTimer ? 'timer' : 'hardware', ref: firstMod.name, method: '', args: [] }
      : { type: 'hardware', ref: '', method: '', args: [] }
    onChange({ ...state, entry_actions: [...actions, initial] })
  }

  const moveAction = (i: number, direction: 'up' | 'down') => {
    const j = direction === 'up' ? i - 1 : i + 1
    if (j < 0 || j >= actions.length) return
    const next = [...actions]
    ;[next[i], next[j]] = [next[j], next[i]]
    onChange({ ...state, entry_actions: next })
  }

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
                  {/* Row header: type chip + summary + reorder buttons */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                    <span style={typeChipStyle(action.type)}>{action.type.toUpperCase()}</span>
                    <span style={{ fontSize: '11px', color: 'var(--muted)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {actionSummary(action)}
                    </span>
                    <button
                      onClick={() => moveAction(i, 'up')}
                      disabled={i === 0}
                      title="Move action up"
                      style={{ background: 'none', border: 'none', cursor: i === 0 ? 'default' : 'pointer', color: i === 0 ? 'var(--border)' : 'var(--muted)', padding: '0 2px', fontSize: '12px' }}
                    >
                      ▲
                    </button>
                    <button
                      onClick={() => moveAction(i, 'down')}
                      disabled={i === actions.length - 1}
                      title="Move action down"
                      style={{ background: 'none', border: 'none', cursor: i === actions.length - 1 ? 'default' : 'pointer', color: i === actions.length - 1 ? 'var(--border)' : 'var(--muted)', padding: '0 2px', fontSize: '12px' }}
                    >
                      ▼
                    </button>
                  </div>
                  <ActionEditor
                    action={action}
                    toolkit={toolkit}
                    hwModules={hwModules}
                    onChange={updated => updateAction(i, updated)}
                  />
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
