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

/** Bare annotation, stripped of Optional[...] wrapping. */
function baseAnnotation(annotation: string | null | undefined): string {
  return (annotation ?? '').replace(/Optional\[|\]/g, '').trim()
}

/**
 * Does this parameter take a structured value (a list/dict) rather than a scalar?
 *
 * `random_choice(options: list)` is the case that matters: it used to fall through to a plain
 * text input, so typing ["left","right"] stored the STRING '["left", "right"]'. random.choice()
 * on a string returns a single CHARACTER — no crash, silent garbage on the rig.
 */
export function isStructuredAnnotation(annotation: string | null | undefined): boolean {
  const base = baseAnnotation(annotation).toLowerCase()
  return base === 'list' || base === 'dict' || base === 'tuple' || base.startsWith('list[') || base.startsWith('dict[')
}

export interface ParseResult {
  ok: boolean
  value?: unknown
  error?: string
}

/**
 * Parse what a researcher typed into a real list/dict.
 *
 * Accepts JSON, Python-style single quotes, and a bare comma-separated list — researchers type
 * all three, and quietly storing the raw string is what caused the bug this exists to prevent.
 */
export function parseStructuredArg(raw: string): ParseResult {
  const text = raw.trim()
  if (!text) return { ok: true, value: [] }

  try {
    return { ok: true, value: JSON.parse(text) }
  } catch {
    // not JSON — fall through
  }

  // Python-style single quotes: ['left', 'right']
  if (/^[[{]/.test(text)) {
    try {
      return { ok: true, value: JSON.parse(text.replace(/'/g, '"')) }
    } catch {
      return { ok: false, error: 'Not a valid list — use ["a", "b"] or a, b' }
    }
  }

  // Bare comma-separated: left, right  /  1, 2.5
  const parts = text.split(',').map(p => p.trim()).filter(p => p !== '')
  if (!parts.length) return { ok: false, error: 'Not a valid list — use ["a", "b"] or a, b' }
  return {
    ok: true,
    value: parts.map(p => {
      const n = Number(p)
      return p !== '' && !Number.isNaN(n) ? n : p.replace(/^['"]|['"]$/g, '')
    }),
  }
}

/** The value an untouched parameter should hold. */
function defaultFor(arg: AstArg): unknown {
  if (isStructuredAnnotation(arg.annotation) && arg.default === undefined) {
    return baseAnnotation(arg.annotation).toLowerCase().startsWith('dict') ? {} : []
  }
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
