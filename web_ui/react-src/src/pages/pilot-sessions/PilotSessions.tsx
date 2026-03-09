import { useState, useMemo, useRef, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getBackendPilots } from '../../api/pilots'
import { getSessions, getLatestRunsBulk, startSessionOnPilot } from '../../api/sessions'
import { stopRun } from '../../api/pilots'
import { getSubjects } from '../../api/subjects'
import { useConcurrentFetch } from '../../hooks/useConcurrentFetch'
import { useWebSocket } from '../../hooks/useWebSocket'
import SessionCard from './SessionCard'
import type { PilotLive, Overrides } from '../../types'

function norm(s: string) { return s.trim().toLowerCase() }

export default function PilotSessions() {
  const { pilot } = useParams<{ pilot: string }>()
  const qc = useQueryClient()
  const [filterText, setFilterText] = useState('')
  const [filterSubjects, setFilterSubjects] = useState<string[]>([])
  const [showTypeahead, setShowTypeahead] = useState(false)
  const [typeaheadIdx, setTypeaheadIdx] = useState(-1)
  const filterWrapRef = useRef<HTMLDivElement>(null)
  const { limit } = useConcurrentFetch(4)
  const [statusMsg, setStatusMsg] = useState('')

  const { lastMessage } = useWebSocket<Record<string, PilotLive>>('/ws/pilots')
  const pilotLive = lastMessage?.[pilot ?? ''] ?? null

  const { data: pilots } = useQuery({ queryKey: ['backend-pilots'], queryFn: getBackendPilots })
  const pilotObj = pilots?.find((p) => p.name === pilot)
  const pilotId = pilotObj?.id ?? null

  const { data: sessions, isLoading } = useQuery({ queryKey: ['sessions'], queryFn: getSessions })
  const { data: subjects } = useQuery({ queryKey: ['subjects'], queryFn: getSubjects })

  const subjectNames = useMemo(() =>
    (subjects ?? []).map(s => s.name).sort((a, b) => a.localeCompare(b)),
    [subjects]
  )

  const sessionIds = useMemo(() => sessions?.map((s) => s.session_id) ?? [], [sessions])

  const { data: latestRuns } = useQuery({
    queryKey: ['latest-runs', pilotId, sessionIds],
    queryFn: () => getLatestRunsBulk(pilotId!, sessionIds),
    enabled: !!pilotId && sessionIds.length > 0,
    refetchInterval: 5000,
  })

  // WebSocket is authoritative for current active run
  const activeRunId = pilotLive?.active_run?.id ?? null
  const activeSessionId = useMemo(() => {
    if (pilotLive?.active_run?.session_id) return pilotLive.active_run.session_id
    if (!latestRuns) return null
    for (const [sid, entry] of Object.entries(latestRuns)) {
      // API returns uppercase status ('RUNNING') — compare case-insensitively
      if (entry?.run?.status && entry.run.status.toLowerCase() === 'running') return Number(sid)
    }
    return null
  }, [pilotLive, latestRuns])

  const refetchLatestRuns = () => qc.invalidateQueries({ queryKey: ['latest-runs'] })

  const startMutation = useMutation({
    mutationFn: ({ sessionId, pId, mode, overrides }: { sessionId: number; pId: number; mode: string; overrides: Overrides | null }) =>
      startSessionOnPilot(sessionId, pId, mode, overrides ?? undefined),
    onSuccess: (data) => { setStatusMsg(`Started run #${data.run_id}`); refetchLatestRuns() },
    onError: (e: Error) => setStatusMsg(`Error: ${e.message}`),
  })

  const stopMutation = useMutation({
    mutationFn: (runId: number) => stopRun(runId),
    onSuccess: () => { setStatusMsg('Run stopped.'); refetchLatestRuns() },
    onError: (e: Error) => setStatusMsg(`Stop error: ${e.message}`),
  })

  const handleStart = (sessionId: number, pId: number, mode: string, overrides: Overrides | null) => {
    startMutation.mutate({ sessionId, pId, mode, overrides })
  }

  // SessionCard already provides activeRunId ?? run?.id — just fire it
  const handleStop = (runId: number) => { stopMutation.mutate(runId) }

  // Typeahead candidates: subject names matching filter text, not already added
  const typeaheadMatches = useMemo(() => {
    if (!filterText.trim()) return []
    const q = norm(filterText)
    return subjectNames.filter(n => norm(n).includes(q) && !filterSubjects.includes(n))
  }, [filterText, subjectNames, filterSubjects])

  const addChip = (name: string) => {
    const canonical = subjectNames.find(n => norm(n) === norm(name)) ?? name.trim()
    if (!canonical || filterSubjects.includes(canonical)) return
    setFilterSubjects(prev => [...prev, canonical])
    setFilterText('')
    setTypeaheadIdx(-1)
    setShowTypeahead(false)
  }

  const removeChip = (name: string) => setFilterSubjects(prev => prev.filter(x => x !== name))

  const clearFilter = () => {
    setFilterText('')
    setFilterSubjects([])
    setTypeaheadIdx(-1)
    setShowTypeahead(false)
  }

  // Close typeahead on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (!filterWrapRef.current?.contains(e.target as Node)) setShowTypeahead(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const isOffline = pilotLive !== null && !pilotLive.connected

  return (
    <div className="container">
      <section className="card">
        <h2>Pilot: {pilot}</h2>

        <div className="filter-bar">
          <div className="chips" id="subject-chips">
            {filterSubjects.map(name => (
              <span key={name} className="chip">
                {name} <button aria-label="Remove" onClick={() => removeChip(name)}>✕</button>
              </span>
            ))}
          </div>
          <div className="filter-input-wrap" ref={filterWrapRef}>
            <input
              id="subject-filter"
              type="text"
              placeholder="Filter by subject…"
              autoComplete="off"
              value={filterText}
              onChange={(e) => { setFilterText(e.target.value); setShowTypeahead(true); setTypeaheadIdx(-1) }}
              onFocus={() => { if (filterText) setShowTypeahead(true) }}
              onKeyDown={(e) => {
                if (e.key === 'ArrowDown' && typeaheadMatches.length) {
                  e.preventDefault()
                  setTypeaheadIdx(i => (i + 1) % typeaheadMatches.length)
                } else if (e.key === 'ArrowUp' && typeaheadMatches.length) {
                  e.preventDefault()
                  setTypeaheadIdx(i => (i - 1 + typeaheadMatches.length) % typeaheadMatches.length)
                } else if (e.key === 'Enter') {
                  e.preventDefault()
                  if (typeaheadIdx >= 0 && typeaheadMatches[typeaheadIdx]) addChip(typeaheadMatches[typeaheadIdx])
                  else if (filterText.trim()) addChip(filterText.trim())
                } else if (e.key === 'Escape') {
                  setShowTypeahead(false)
                }
              }}
            />
            {(filterText || filterSubjects.length > 0) && (
              <button className="input-clear is-visible" type="button" aria-label="Clear filter" onClick={clearFilter}>✕</button>
            )}
            {showTypeahead && typeaheadMatches.length > 0 && (
              <div className="typeahead" id="subject-typeahead">
                <ul>
                  {typeaheadMatches.map((m, i) => (
                    <li
                      key={m}
                      className={`typeahead-item${i === typeaheadIdx ? ' active' : ''}`}
                      onMouseDown={(e) => { e.preventDefault(); addChip(m) }}
                    >
                      {m}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>

        {statusMsg && <div className="status-line">{statusMsg}</div>}
        {isOffline && <p className="muted">Pilot is offline.</p>}

        {isLoading ? (
          <ul className="sessions-scroll">
            {[...Array(6)].map((_, i) => (
              <li key={i} className="session-card is-loading">
                <div className="session-skel">
                  <div className="session-skel-line w70" />
                  <div className="session-skel-line w40" />
                  <div className="session-skel-line w55" />
                </div>
              </li>
            ))}
          </ul>
        ) : sessions?.length === 0 ? (
          <p className="muted">No sessions available.</p>
        ) : (
          <ul id="sessions" className="sessions-scroll">
            {sessions?.map((session) => (
              <SessionCard
                key={session.session_id}
                sessionId={session.session_id}
                latestRun={latestRuns?.[String(session.session_id)]}
                pilotId={pilotId ?? 0}
                activeRunId={activeRunId}
                activeSessionId={activeSessionId}
                filterSubjects={filterSubjects}
                onStart={handleStart}
                onStop={handleStop}
                limit={limit}
              />
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
