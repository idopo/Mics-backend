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
      if (json?.detail) message = json.detail
    } catch { /* not JSON */ }
    throw new Error(message)
  }
  return res.json() as Promise<T>
}
