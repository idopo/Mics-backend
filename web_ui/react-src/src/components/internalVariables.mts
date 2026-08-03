/**
 * Which FDA variables are under-the-hood machinery, not researcher-authored slots.
 *
 * A detector trigger (TOUCH_INT -> MPR121.detect_change) writes pin_number/level via `output`
 * purely so its own key_template and `if` can read them back. Offering those in the variable
 * list invites renaming or branching on a value the mechanism owns, which silently breaks the
 * trigger. The rule (user decision, 2026-08-03): written ONLY by a trigger action = internal.
 * The moment a state body writes it too, the researcher has taken ownership and it stays
 * visible — hiding it then would strand work they can see in the canvas.
 *
 * Hiding is presentation only. The names stay in FdaJson.variables and the backend/Pi keep
 * resolving them exactly as before; nothing here changes what is stored or dispatched.
 */

interface OutputBearing {
  output?: unknown
  then?: unknown[]
  else?: unknown[]
}

function collectOutputs(actions: unknown[] | undefined, into: Set<string>): void {
  for (const raw of actions ?? []) {
    if (!raw || typeof raw !== 'object') continue
    const action = raw as OutputBearing
    const out = action.output
    if (typeof out === 'string' && out) into.add(out)
    else if (Array.isArray(out)) out.forEach(o => { if (typeof o === 'string' && o) into.add(o) })
    // `if` actions nest real actions that may carry their own output
    collectOutputs(action.then, into)
    collectOutputs(action.else, into)
  }
}

interface FdaLike {
  states?: Record<string, { entry_actions?: unknown[] }>
  trigger_assignments?: { actions?: unknown[] }[]
}

/** Names written by a trigger action and by no state body. */
export function internalVariableNames(fda: FdaLike | null | undefined): Set<string> {
  if (!fda) return new Set()

  const triggerWritten = new Set<string>()
  for (const assignment of fda.trigger_assignments ?? []) {
    collectOutputs(assignment?.actions, triggerWritten)
  }
  if (!triggerWritten.size) return new Set()

  const stateWritten = new Set<string>()
  for (const state of Object.values(fda.states ?? {})) {
    collectOutputs(state?.entry_actions, stateWritten)
  }

  return new Set([...triggerWritten].filter(name => !stateWritten.has(name)))
}
