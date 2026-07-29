/**
 * Sets or deletes `key` in a JSON config string. Deleting (value === undefined) removes the key
 * entirely rather than writing 0/null, so an absent first_channel and an explicit
 * first_channel: 0 both round-trip distinctly.
 */
export function setJsonKey(json: string, key: string, value: number | undefined): string {
  try {
    const parsed = JSON.parse(json) as Record<string, unknown>
    if (value === undefined) {
      delete parsed[key]
    } else {
      parsed[key] = value
    }
    return JSON.stringify(parsed, null, 2)
  } catch {
    return json
  }
}

function parseConfig(json: string): Record<string, unknown> {
  try {
    return JSON.parse(json) as Record<string, unknown>
  } catch {
    return {}
  }
}

/**
 * Cosmetic preview only — authority for this derivation is api/detector_keys.py::derive_view_keys
 * (first_channel default 0, range(first_channel, first_channel + num_detectors)). This preview
 * shows the PILOT's resolved key names; a task definition instead stores a channel index (DVK-11)
 * — the two are deliberately different, and this preview must never become a third derivation
 * anything else depends on.
 */
function deriveKeysPreview(config: Record<string, unknown>): string[] {
  const deviceName = typeof config.device_name === 'string' ? config.device_name : ''
  const numDetectors = Number(config.num_detectors)
  if (!deviceName || !Number.isFinite(numDetectors) || numDetectors <= 0) return []
  const rawFirst = config.first_channel
  const firstChannel = rawFirst === undefined || rawFirst === null ? 0 : Number(rawFirst)
  if (!Number.isFinite(firstChannel) || firstChannel < 0) return []
  const keys: string[] = []
  for (let i = firstChannel; i < firstChannel + numDetectors; i++) keys.push(`${deviceName}${i}`)
  return keys
}

interface DetectorChannelFieldsProps {
  json: string
  onChange: (json: string) => void
}

/** Detector-module config affordance (DVK-09) — declares first_channel above the raw JSON textarea. */
export default function DetectorChannelFields({ json, onChange }: DetectorChannelFieldsProps): JSX.Element {
  const config = parseConfig(json)
  const deviceName = typeof config.device_name === 'string' && config.device_name ? config.device_name : 'DEVICE'
  const rawFirst = config.first_channel
  const firstChannelValue = rawFirst === undefined || rawFirst === null ? '' : String(rawFirst)
  const keys = deriveKeysPreview(config)

  function handleFirstChannelChange(value: string): void {
    if (value.trim() === '') {
      onChange(setJsonKey(json, 'first_channel', undefined))
      return
    }
    const n = Number(value)
    if (Number.isFinite(n)) onChange(setJsonKey(json, 'first_channel', n))
  }

  return (
    <div
      style={{
        marginBottom: '0.75rem',
        padding: '0.6rem 0.75rem',
        background: 'var(--surface2)',
        borderRadius: '4px',
        border: '1px solid var(--overlay0)',
      }}
    >
      <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--subtext0)', marginBottom: '4px' }}>
        Detector channels
      </label>
      <p style={{ margin: '0 0 8px', fontSize: '0.78rem', color: 'var(--subtext0)' }}>
        <code>first_channel</code> (default 0) plus <code>num_detectors</code> decide which
        trackers exist: <code>{deviceName}{'{first}'}</code> … <code>{deviceName}{'{first + n - 1}'}</code>.
        A tracker's name is its raw hardware channel index, so a detector wired to channels 1-4
        needs <code>first_channel: 1</code>. Leaving it out means channels start at 0, exactly as
        before.
      </p>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
        <span style={{ fontSize: '0.8rem', color: 'var(--text)' }}>first_channel</span>
        <input
          type="number"
          min={0}
          value={firstChannelValue}
          onChange={e => handleFirstChannelChange(e.target.value)}
          placeholder="0"
          style={{ padding: '4px 8px', fontSize: '0.85rem', width: '80px' }}
        />
      </div>
      {keys.length > 0 ? (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
          {keys.map(k => (
            <span key={k} className="meta-pill" style={{ fontSize: '12px' }}>{k}</span>
          ))}
        </div>
      ) : (
        <span style={{ fontSize: '0.78rem', color: 'var(--overlay1)' }}>
          set device_name and num_detectors to preview keys
        </span>
      )}
    </div>
  )
}
