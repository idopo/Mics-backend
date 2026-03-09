import { useEffect, useRef, useState, useCallback } from 'react'

export function useWebSocket<T = unknown>(url: string, enabled = true) {
  const [lastMessage, setLastMessage] = useState<T | null>(null)
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mountedRef = useRef(true)

  const connect = useCallback(() => {
    if (!mountedRef.current || !enabled) return
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${proto}//${window.location.host}${url}`)
    wsRef.current = ws

    ws.onopen = () => {
      if (!mountedRef.current) { ws.close(); return }
      setConnected(true)
    }
    ws.onmessage = (ev) => {
      if (!mountedRef.current) return
      try {
        setLastMessage(JSON.parse(ev.data) as T)
      } catch {
        // ignore parse errors
      }
    }
    ws.onclose = () => {
      if (!mountedRef.current) return
      setConnected(false)
      retryRef.current = setTimeout(connect, 2000)
    }
    ws.onerror = () => {
      ws.close()
    }
  }, [url, enabled])

  useEffect(() => {
    mountedRef.current = true
    if (enabled) connect()
    return () => {
      mountedRef.current = false
      if (retryRef.current) clearTimeout(retryRef.current)
      wsRef.current?.close()
    }
  }, [connect, enabled])

  return { lastMessage, connected }
}
