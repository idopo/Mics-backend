import type { FdaAction, ToolkitRead } from '../types'
import ArgInput from './ArgInput'
import { labelStyle } from './ActionEditor'

interface Props {
  action: FdaAction
  toolkit: ToolkitRead | null
  /** Declared FdaJson.variables names — valid key_template tokens and value/flag options. */
  variableNames?: string[]
  /** True only when this editor is inside a trigger's action list. */
  allowTriggerContext?: boolean
  onChange: (patch: Partial<FdaAction>) => void
}

/**
 * Form for `type: 'view'` actions — writes a view.view[key] Tracker (e.g. a detector
 * channel created by check_for_detectors). Deliberately renders NO pi_timestamp control:
 * the Pi injects it from the trigger tick silently (2026-07-27 decision, 24-CONTEXT.md).
 */
export default function ViewActionFields({ action, toolkit, variableNames, allowTriggerContext, onChange }: Props) {
  const names = variableNames ?? []
  const kwargsEntries = Object.entries(action.kwargs ?? {})

  const appendToken = (name: string) => {
    const current = action.key_template ?? ''
    onChange({ key_template: `${current}{${name}}` })
  }

  return (
    <>
      <div>
        <label
          style={labelStyle}
          title="The view.view key to write. Prefer {device_name}{pin_number} over a literal name — a hardcoded prefix only works on pilots that happen to use it."
        >
          Target key ⓘ
        </label>
        <input
          type="text"
          value={action.key_template ?? ''}
          onChange={e => onChange({ key_template: e.target.value })}
          placeholder="{device_name}{pin_number}"
          style={{ width: '100%', fontFamily: "'IBM Plex Mono', monospace" }}
        />
        <p style={{ fontSize: '10px', color: 'var(--muted)', margin: '4px 0 0' }}>
          {'{name}'} tokens are replaced with the current value of that variable.{' '}
          {'{device_name}'} resolves at run time from the action&apos;s source device, so the
          definition stays pilot-agnostic — prefer it over typing a literal prefix.
        </p>
        {names.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '6px' }}>
            {names.map(name => (
              <button
                key={name}
                className="meta-pill"
                style={{ cursor: 'pointer', border: 'none' }}
                onClick={() => appendToken(name)}
                title={`Append {${name}} to the target key`}
              >
                {`{${name}}`}
              </button>
            ))}
          </div>
        )}
      </div>

      <div>
        <label style={labelStyle} title="The value to write into the target key.">Value ⓘ</label>
        <ArgInput
          value={action.value}
          toolkit={toolkit}
          annotation={null}
          variableNames={names}
          allowTriggerContext={allowTriggerContext}
          onChange={v => onChange({ value: v })}
        />
      </div>

      {kwargsEntries.length > 0 && (
        <div>
          <label style={labelStyle} title="Extra keyword args passed through to Tracker.set unchanged.">
            Passthrough kwargs (read-only) ⓘ
          </label>
          {kwargsEntries.map(([key, val]) => (
            <div className="param-field" key={key}>
              <span className="param-name">{key}</span>
              <span className="meta-pill">{JSON.stringify(val)}</span>
            </div>
          ))}
        </div>
      )}
    </>
  )
}
