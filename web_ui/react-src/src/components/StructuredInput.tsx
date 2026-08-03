import { useState, useRef, useEffect } from 'react'
import { parseStructuredArg } from './computeArgs.mts'

interface Props {
  value: unknown
  onChange: (updated: unknown) => void
  style?: React.CSSProperties
}

/**
 * Editor for a list/dict argument (`random_choice(options: list)`).
 *
 * Exists because a structured arg used to fall through to a plain text input, so typing
 * ["left","right"] stored the STRING '["left", "right"]' and the Pi ran random.choice() over
 * its characters — no error, silent garbage. Here the researcher's raw text stays local and
 * only the PARSED list/dict is committed, so a stringified list cannot be saved at all.
 * Unparseable input is reported and nothing is written, rather than quietly storing text.
 */
export default function StructuredInput({ value, onChange, style }: Props) {
  const render = (v: unknown): string => {
    if (v === null || v === undefined) return ''
    if (typeof v === 'string') return v          // legacy stringified value — show it to be fixed
    return JSON.stringify(v)
  }

  const [draft, setDraft] = useState<string>(() => render(value))
  const [error, setError] = useState<string | null>(null)
  const committed = useRef<unknown>(value)

  useEffect(() => {
    if (JSON.stringify(value) !== JSON.stringify(committed.current)) {
      setDraft(render(value))
      committed.current = value
    }
  }, [value])

  const handle = (raw: string) => {
    setDraft(raw)
    const parsed = parseStructuredArg(raw)
    if (!parsed.ok) {
      setError(parsed.error ?? 'Not a valid list')
      return                                      // never commit a raw string
    }
    setError(null)
    committed.current = parsed.value
    onChange(parsed.value)
  }

  const legacyString = typeof value === 'string'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
      <input
        type="text"
        value={draft}
        onChange={e => handle(e.target.value)}
        placeholder='["left", "right"]'
        style={{ ...style, borderColor: error || legacyString ? '#ef4444' : undefined }}
      />
      {error && <span style={{ fontSize: '10px', color: '#ef4444' }}>{error}</span>}
      {!error && legacyString && (
        <span style={{ fontSize: '10px', color: '#ef4444' }}>
          Saved as text, not a list — the Pi would pick one character. Re-enter to fix.
        </span>
      )}
      {!error && !legacyString && (
        <span style={{ fontSize: '10px', color: 'var(--muted)' }}>
          {Array.isArray(value) ? `${value.length} item${value.length === 1 ? '' : 's'}` : 'list'}
        </span>
      )}
    </div>
  )
}
