/**
 * Render a FastAPI `detail` as readable text.
 *
 * `detail` is a plain string for HTTPException(str), a list of {loc, msg} for
 * request-schema failures, and `{errors: [...]}` for the FDA hard-validation gate.
 * Passing the object straight to `new Error()` renders "[object Object]", which hides
 * exactly the message the 422 exists to deliver.
 */
function formatDetail(detail: unknown): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map(d => {
        if (typeof d === 'string') return d
        const e = d as { loc?: unknown[]; msg?: string }
        const where = Array.isArray(e.loc) ? e.loc.filter(p => p !== 'body').join('.') : ''
        return where ? `${where}: ${e.msg ?? ''}` : (e.msg ?? JSON.stringify(d))
      })
      .join('\n')
  }
  if (detail && typeof detail === 'object') {
    const errors = (detail as { errors?: unknown }).errors
    if (Array.isArray(errors)) return errors.map(String).join('\n')
    return JSON.stringify(detail)
  }
  return String(detail)
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const defaultHeaders: Record<string, string> =
    init?.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }
  const res = await fetch(path, {
    headers: { ...defaultHeaders, ...(init?.headers ?? {}) },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    let message = text
    try {
      const json = JSON.parse(text)
      if (json?.detail) message = formatDetail(json.detail)
    } catch { /* not JSON */ }
    throw new Error(message)
  }
  return res.json() as Promise<T>
}
