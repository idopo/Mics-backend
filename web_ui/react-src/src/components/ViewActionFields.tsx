import type { FdaAction, ToolkitRead, DetectorChannelGroup } from '../types'
import ArgInput from './ArgInput'
import { labelStyle } from './ActionEditor'
import { buildKeyTemplateSuggestions } from './detectorOptions.mts'

interface Props {
  action: FdaAction
  toolkit: ToolkitRead | null
  /** Declared FdaJson.variables names — valid key_template tokens and value/flag options. */
  variableNames?: string[]
  detectorChannels?: DetectorChannelGroup[]
  /** True only when this editor is inside a trigger's action list. */
  allowTriggerContext?: boolean
  onChange: (patch: Partial<FdaAction>) => void
}

/**
 * Form for `type: 'view'` actions — writes a view.view[key] Tracker (e.g. a detector
 * channel created by check_for_detectors). Deliberately renders NO pi_timestamp control:
 * the Pi injects it from the trigger tick silently (2026-07-27 decision, 24-CONTEXT.md).
 *
 * DVK-04, not DVK-11: this field is untouched by the detector-reference redesign (25-CONTEXT
 * D5). It stays free text with pickable completions — a state body may legitimately write one
 * fixed channel, so a literal per-pilot key is still offered here, with a hint that it hardcodes
 * a pilot. Do not convert this input to a select; DVK-05 requires the free-text escape.
 */
export default function ViewActionFields({ action, toolkit, variableNames, detectorChannels, allowTriggerContext, onChange }: Props) {
  const names = variableNames ?? []
  const kwargsEntries = Object.entries(action.kwargs ?? {})
  const suggestions = buildKeyTemplateSuggestions(detectorChannels ?? [], names, action.source_ref ?? null)

  const appendSuggestion = (insert: string) => {
    const current = action.key_template ?? ''
    onChange({ key_template: `${current}${insert}` })
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
        {suggestions.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '6px' }}>
            {suggestions.map(s => (
              <button
                key={s.insert}
                className="meta-pill"
                disabled={s.disabled}
                style={{ cursor: s.disabled ? 'default' : 'pointer', border: 'none', opacity: s.disabled ? 0.5 : 1 }}
                onClick={() => appendSuggestion(s.insert)}
                title={s.hint}
              >
                {s.label}
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
