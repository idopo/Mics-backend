import { useCallback, useEffect, useRef, useState } from 'react'
import { useMutation } from '@tanstack/react-query'

import { updateTaskDefinition } from '../../api/task-definitions'
import type { XY } from '../../components/fdaLayout.mts'

const DEBOUNCE_MS = 600
const SAVED_MSG_TTL_MS = 1500

/**
 * Debounced `ui_layout` persistence for the FDA canvas, deliberately separate from the FDA
 * autosave (see TaskEditor.tsx's `saveMutation`/`autoSaveTimerRef`). A drag must never touch
 * the FDA state — routing layout through that path would re-arm the FDA autosave and could hold
 * a position PUT behind an incomplete trigger or half-built action (CANVAS-10).
 */
export interface LayoutPersistence {
  /** Current known positions. Ref-backed: reading it never re-renders. */
  current: () => Record<string, XY>
  /** Record the hydrated positions at canvas init. Does NOT write to the server. */
  seed: (positions: Record<string, XY>) => void
  /** Merge dragged/placed positions and schedule a debounced PUT. */
  record: (entries: ReadonlyArray<{ id: string; position: XY }>) => void
  /** Replace the whole map and PUT immediately (used by 'Restore default layout'). */
  replaceAll: (next: Record<string, XY>) => void
  /** Status string for the header. Empty when idle. */
  layoutMsg: string
}

/** A ref, not state — a drag records into `positionsRef` without re-rendering the editor. */
export function useLayoutPersistence(taskDefId: number): LayoutPersistence {
  const positionsRef = useRef<Record<string, XY>>({})
  const [layoutMsg, setLayoutMsg] = useState('')
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const clearMsgTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const mutation = useMutation({
    mutationFn: (nodes: Record<string, XY>) => updateTaskDefinition(taskDefId, { ui_layout: { nodes } }),
    onSuccess: () => {
      setLayoutMsg('Layout saved ✓')
      if (clearMsgTimerRef.current) clearTimeout(clearMsgTimerRef.current)
      clearMsgTimerRef.current = setTimeout(() => setLayoutMsg(''), SAVED_MSG_TTL_MS)
    },
    onError: (e: Error) => setLayoutMsg(`Layout not saved: ${e.message}`),
  })

  useEffect(() => () => {
    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current)
    if (clearMsgTimerRef.current) clearTimeout(clearMsgTimerRef.current)
  }, [])

  const seed = useCallback((positions: Record<string, XY>): void => {
    positionsRef.current = { ...positions }
  }, [])

  const record = useCallback((entries: ReadonlyArray<{ id: string; position: XY }>): void => {
    for (const { id, position } of entries) positionsRef.current[id] = position
    setLayoutMsg('Layout…')
    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current)
    debounceTimerRef.current = setTimeout(() => mutation.mutate(positionsRef.current), DEBOUNCE_MS)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const replaceAll = useCallback((next: Record<string, XY>): void => {
    positionsRef.current = { ...next }
    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current)
    mutation.mutate(positionsRef.current)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const current = useCallback((): Record<string, XY> => positionsRef.current, [])

  return { current, seed, record, replaceAll, layoutMsg }
}
