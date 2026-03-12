export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
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
