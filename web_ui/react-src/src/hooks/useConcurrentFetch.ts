import { useRef } from 'react'

type Fn<T> = () => Promise<T>

interface QueueItem<T> {
  fn: Fn<T>
  resolve: (v: T) => void
  reject: (e: unknown) => void
}

export function useConcurrentFetch(max = 4) {
  const activeRef = useRef(0)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const queueRef = useRef<QueueItem<any>[]>([])

  const runNext = () => {
    if (activeRef.current >= max || queueRef.current.length === 0) return
    activeRef.current++
    const { fn, resolve, reject } = queueRef.current.shift()!
    Promise.resolve()
      .then(fn)
      .then(resolve, reject)
      .finally(() => {
        activeRef.current--
        runNext()
      })
  }

  const limit = <T>(fn: Fn<T>): Promise<T> =>
    new Promise<T>((resolve, reject) => {
      queueRef.current.push({ fn, resolve, reject })
      runNext()
    })

  return { limit }
}
