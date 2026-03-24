import type { FdaTriggerAssignment, ToolkitRead } from '../types'

interface Props {
  assignments: FdaTriggerAssignment[]
  toolkit: ToolkitRead | null
  onChange: (updated: FdaTriggerAssignment[]) => void
}

const HANDLERS: FdaTriggerAssignment['handler'][] = [
  'touch_detector',
  'digital_input',
  'default',
  'log_only',
]

const sectionLabel: React.CSSProperties = {
  fontSize: '11px',
  color: 'var(--muted)',
  fontWeight: 600,
  letterSpacing: '0.08em',
  textTransform: 'uppercase',
  marginBottom: '10px',
}

const fieldLabel: React.CSSProperties = {
  fontSize: '11px',
  color: 'var(--muted)',
  display: 'block',
  marginBottom: '3px',
}

export default function TriggerAssignmentPanel({ assignments, toolkit, onChange }: Props) {
  const hwKeys = Object.keys(toolkit?.semantic_hardware ?? {})

  const update = (i: number, patch: Partial<FdaTriggerAssignment>) =>
    onChange(assignments.map((a, idx) => (idx === i ? { ...a, ...patch } : a)))

  const updateConfig = (i: number, patch: Partial<NonNullable<FdaTriggerAssignment['config']>>) =>
    onChange(
      assignments.map((a, idx) =>
        idx === i ? { ...a, config: { ...a.config, ...patch } } : a,
      ),
    )

  const remove = (i: number) => onChange(assignments.filter((_, idx) => idx !== i))

  const add = () => onChange([...assignments, { trigger_name: '', handler: 'touch_detector' }])

  return (
    <div>
      <div style={sectionLabel}>Trigger Assignments</div>

      {assignments.length === 0 ? (
        <p style={{ fontSize: '12px', color: 'var(--muted)', marginBottom: '12px' }}>
          No trigger assignments configured.
        </p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '12px' }}>
          {assignments.map((a, i) => (
            <div
              key={i}
              style={{
                padding: '10px',
                background: 'rgba(255,255,255,0.02)',
                borderRadius: '6px',
                border: '1px solid var(--border)',
                display: 'flex',
                flexDirection: 'column',
                gap: '6px',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: '2px',
                }}
              >
                <label style={fieldLabel}>Trigger name</label>
                <button
                  className="button-danger"
                  style={{ fontSize: '10px', padding: '1px 6px', lineHeight: 1.4 }}
                  onClick={() => remove(i)}
                >
                  ✕
                </button>
              </div>
              <input
                type="text"
                value={a.trigger_name}
                onChange={e => update(i, { trigger_name: e.target.value })}
                placeholder="e.g. TOUCH_INT"
                style={{
                  width: '100%',
                  fontFamily: "'IBM Plex Mono', monospace",
                  fontSize: '12px',
                }}
              />

              <label style={fieldLabel}>Handler</label>
              <select
                value={a.handler}
                onChange={e =>
                  update(i, { handler: e.target.value as FdaTriggerAssignment['handler'] })
                }
                style={{ width: '100%' }}
              >
                {HANDLERS.map(h => (
                  <option key={h} value={h}>
                    {h}
                  </option>
                ))}
              </select>

              {a.handler === 'touch_detector' && (
                <>
                  <label style={fieldLabel}>Hardware ref</label>
                  {hwKeys.length > 0 ? (
                    <select
                      value={a.config?.hardware_ref ?? ''}
                      onChange={e =>
                        updateConfig(i, { hardware_ref: e.target.value || undefined })
                      }
                      style={{ width: '100%' }}
                    >
                      <option value="">— hardware ref —</option>
                      {hwKeys.map(k => (
                        <option key={k} value={k}>
                          {k}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type="text"
                      value={a.config?.hardware_ref ?? ''}
                      onChange={e =>
                        updateConfig(i, { hardware_ref: e.target.value || undefined })
                      }
                      placeholder="hardware key"
                      style={{ width: '100%' }}
                    />
                  )}
                </>
              )}
            </div>
          ))}
        </div>
      )}

      <button
        className="button-secondary"
        style={{ fontSize: '12px', width: '100%' }}
        onClick={add}
      >
        + Add trigger
      </button>
    </div>
  )
}
