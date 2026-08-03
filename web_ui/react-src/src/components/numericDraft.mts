/**
 * The commit rule shared by every numeric input in the FDA editor.
 *
 * A controlled input that does `onChange(Number(e.target.value))` and renders that number back
 * cannot accept a decimal: "0." parses to 0, the input re-renders as "0", and the point is gone.
 * Splitting the two concerns fixes it — `commitDraft` says what to STORE, `isDraftInProgress`
 * says when the component must keep showing the researcher's raw text instead of the stored
 * value. Pure functions in .mts so `npm run test:unit` can cover them without a DOM.
 */

/** A draft the researcher is still mid-way through typing — never re-render the input from it. */
export function isDraftInProgress(draft: string): boolean {
  return draft === '' || draft === '-' || draft === '.' || draft === '-.' || /[.eE][+-]?$/.test(draft)
}

export interface CommitOptions {
  /** Keep a non-numeric draft as a string (condition literals may hold "idle"). */
  allowText: boolean
}

/** The value to store for a raw input draft. */
export function commitDraft(draft: string, { allowText }: CommitOptions): number | string {
  if (draft === '') return 0
  const n = Number(draft)
  if (!Number.isNaN(n)) return n
  return allowText ? draft : 0
}
