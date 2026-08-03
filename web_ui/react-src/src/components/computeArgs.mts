/**
 * Building a compute action's `args` array.
 *
 * Writing an index straight into a copy of the stored array (`newArgs[1] = v` on an empty
 * array) creates a SPARSE array, which JSON-serializes as [null, 1]. The Pi then calls
 * random_float(None, 1) and dies with a TypeError at run time — long after the editor said
 * the action was fine. Args are therefore always rebuilt dense, one slot per declared
 * parameter, before the edited index is written.
 */

export interface AstArg {
  name: string
  annotation?: string | null
  default?: unknown
}

/** The value an untouched parameter should hold. */
function defaultFor(arg: AstArg): unknown {
  if (arg.default !== undefined && arg.default !== null) {
    // ast_metadata stores defaults as source text ("0.5", "True"), not typed values.
    const raw = String(arg.default)
    const base = (arg.annotation ?? '').replace(/Optional\[|\]/g, '').trim()
    if (base === 'int' || base === 'float') {
      const n = Number(raw)
      return Number.isNaN(n) ? raw : n
    }
    if (base === 'bool') return raw === 'True' || raw === 'true'
    return raw
  }
  const base = (arg.annotation ?? '').replace(/Optional\[|\]/g, '').trim()
  if (base === 'int' || base === 'float') return 0
  if (base === 'bool') return false
  return ''
}

/**
 * A dense args array for `argList`, carrying over any existing values, with `index` set to
 * `value`. Extra trailing values from a previous op are dropped.
 */
export function withArgAt(
  argList: AstArg[],
  existing: unknown[] | undefined,
  index: number,
  value: unknown,
): unknown[] {
  const args = argList.map((arg, i) => {
    const current = existing?.[i]
    return current === undefined || current === null ? defaultFor(arg) : current
  })
  if (index >= 0 && index < args.length) args[index] = value
  return args
}
