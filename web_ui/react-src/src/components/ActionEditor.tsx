import type { FdaAction, ToolkitRead } from '../types'
import ArgInput from './ArgInput'
import IfActionEditor from './IfActionEditor'

const HW_METHODS = ['set', 'toggle']
const FLAG_METHODS = ['set', 'increment', 'reset']
const SPECIAL_ACTIONS = ['INC_TRIAL_COUNTER']

interface Props {
  action: FdaAction
  toolkit: ToolkitRead | null
  onChange: (updated: FdaAction) => void
}

const labelStyle: React.CSSProperties = {
  fontSize: '11px',
  color: 'var(--muted)',
  display: 'block',
  marginBottom: '2px',
}

export default function ActionEditor({ action, toolkit, onChange }: Props) {
  const hwKeys = Object.keys(toolkit?.semantic_hardware ?? {})
  const flagKeys = Object.keys(toolkit?.flags ?? {})
  const methodKeys = toolkit?.callable_methods ?? []

  const update = (patch: Partial<FdaAction>) => onChange({ ...action, ...patch })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', padding: '8px', background: 'rgba(255,255,255,0.03)', borderRadius: '6px', border: '1px solid var(--border)' }}>
      <div>
        <label style={labelStyle}>Type</label>
        <select
          value={action.type}
          onChange={e => {
            const t = e.target.value as FdaAction['type']
            if (t === 'hardware') onChange({ type: t, ref: hwKeys[0] ?? '', method: 'set', args: [1] })
            else if (t === 'flag') onChange({ type: t, ref: flagKeys[0] ?? '', method: 'set', args: [1] })
            else if (t === 'timer') onChange({ type: t, duration: 500 })
            else if (t === 'special') onChange({ type: t, action: 'INC_TRIAL_COUNTER' })
            else if (t === 'if') onChange({ type: t, condition: undefined, then: [], else: undefined })
            else onChange({ type: t, ref: methodKeys[0] ?? '', args: [] })
          }}
          style={{ width: '100%' }}
        >
          <option value="hardware">hardware</option>
          <option value="flag">flag</option>
          <option value="timer">timer</option>
          <option value="special">special</option>
          <option value="method">method</option>
          <option value="if">if</option>
        </select>
      </div>

      {action.type === 'hardware' && (
        <>
          <div>
            <label style={labelStyle}>Hardware ref</label>
            {hwKeys.length > 0 ? (
              <select value={action.ref ?? ''} onChange={e => update({ ref: e.target.value })} style={{ width: '100%' }}>
                {!hwKeys.includes(action.ref ?? '') && <option value={action.ref ?? ''}>{action.ref ?? '—'}</option>}
                {hwKeys.map(k => <option key={k} value={k}>{k}</option>)}
              </select>
            ) : (
              <input type="text" value={action.ref ?? ''} onChange={e => update({ ref: e.target.value })} style={{ width: '100%' }} />
            )}
          </div>
          <div>
            <label style={labelStyle}>Method</label>
            <select value={action.method ?? 'set'} onChange={e => update({ method: e.target.value })} style={{ width: '100%' }}>
              {HW_METHODS.map(m => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
          <div>
            <label style={labelStyle}>Arg</label>
            <ArgInput value={action.args?.[0] ?? 1} toolkit={toolkit} onChange={v => update({ args: [v] })} />
          </div>
        </>
      )}

      {action.type === 'flag' && (
        <>
          <div>
            <label style={labelStyle}>Flag ref</label>
            {flagKeys.length > 0 ? (
              <select value={action.ref ?? ''} onChange={e => update({ ref: e.target.value })} style={{ width: '100%' }}>
                {!flagKeys.includes(action.ref ?? '') && <option value={action.ref ?? ''}>{action.ref ?? '—'}</option>}
                {flagKeys.map(k => <option key={k} value={k}>{k}</option>)}
              </select>
            ) : (
              <input type="text" value={action.ref ?? ''} onChange={e => update({ ref: e.target.value })} style={{ width: '100%' }} />
            )}
          </div>
          <div>
            <label style={labelStyle}>Method</label>
            <select value={action.method ?? 'set'} onChange={e => update({ method: e.target.value })} style={{ width: '100%' }}>
              {FLAG_METHODS.map(m => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
          <div>
            <label style={labelStyle}>Value</label>
            <ArgInput value={action.args?.[0] ?? 1} toolkit={toolkit} onChange={v => update({ args: [v] })} />
          </div>
        </>
      )}

      {action.type === 'timer' && (
        <div>
          <label style={labelStyle}>Duration (ms)</label>
          <ArgInput value={action.duration ?? 500} toolkit={toolkit} onChange={v => update({ duration: v })} />
        </div>
      )}

      {action.type === 'special' && (
        <div>
          <label style={labelStyle}>Action</label>
          <select value={action.action ?? 'INC_TRIAL_COUNTER'} onChange={e => update({ action: e.target.value })} style={{ width: '100%' }}>
            {SPECIAL_ACTIONS.map(a => <option key={a} value={a}>{a}</option>)}
          </select>
        </div>
      )}

      {action.type === 'if' && (
        <IfActionEditor action={action} toolkit={toolkit} onChange={onChange} />
      )}

      {action.type === 'method' && (
        <>
          <div>
            <label style={labelStyle}>Callable method</label>
            {methodKeys.length > 0 ? (
              <select value={action.ref ?? ''} onChange={e => update({ ref: e.target.value })} style={{ width: '100%' }}>
                {!methodKeys.includes(action.ref ?? '') && <option value={action.ref ?? ''}>{action.ref ?? '—'}</option>}
                {methodKeys.map(k => <option key={k} value={k}>{k}</option>)}
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
    </div>
  )
}
