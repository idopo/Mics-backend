import { useState, useRef, useEffect } from 'react'
import { commitDraft } from './numericDraft.mts'

interface Props {
  value: unknown
  onChange: (updated: number | string) => void
  /** Keep a non-numeric draft as a string — condition literals may hold "idle". */
  allowText?: boolean
  placeholder?: string
  style?: React.CSSProperties
}

/**
 * Numeric input that lets a decimal actually be typed.
 *
 * The researcher's raw text is local state; only the parsed value goes to `onChange`. Re-syncing
 * from `value` is gated on the parent having changed it to something this input did not commit
 * (switching op, undo) — otherwise typing "0." would be echoed back as "0" and eat the point.
 * See numericDraft.mts for the commit rule and its tests.
 */
export default function NumericInput({ value, onChange, allowText = false, placeholder, style }: Props) {
  const [draft, setDraft] = useState<string>(() => (value === null || value === undefined ? '' : String(value)))
  const committed = useRef<unknown>(value)

  useEffect(() => {
    // Compare stringified: a caller may store the number 0.5 and hand back the string "0.5"
    // (ConditionBuilder does exactly this). A strict !== would see every keystroke as an
    // external change and reset the draft — reintroducing the bug this component exists to fix.
    const incoming = value === null || value === undefined ? '' : String(value)
    if (incoming !== String(committed.current ?? '')) {
      setDraft(incoming)
      committed.current = value
    }
  }, [value])

  const handle = (raw: string) => {
    setDraft(raw)
    const next = commitDraft(raw, { allowText })
    committed.current = next
    onChange(next)
  }

  return (
    <input
      type="text"
      inputMode="decimal"
      value={draft}
      onChange={e => handle(e.target.value)}
      placeholder={placeholder}
      style={style}
    />
  )
}
