import { apiFetch } from './client'
import type { SessionSummary, SessionDetail, StartOptions, RunWithProgress, Overrides } from '../types'

export const getSessions = () => apiFetch<SessionSummary[]>('/api/sessions')

export const getSessionDetail = (sessionId: number) =>
  apiFetch<SessionDetail>(`/api/sessions/${sessionId}`)

export const getStartOptions = (sessionId: number, pilotId: number) =>
  apiFetch<StartOptions>(`/api/sessions/${sessionId}/pilots/${pilotId}/start-options`)

export const getLatestRun = (sessionId: number, pilotId: number) =>
  apiFetch<RunWithProgress>(`/api/sessions/${sessionId}/pilots/${pilotId}/latest-run`)

export const getLatestRunsBulk = (pilotId: number, sessionIds: number[]) =>
  apiFetch<Record<string, RunWithProgress | null>>(
    `/api/sessions/pilots/${pilotId}/latest-runs`,
    { method: 'POST', body: JSON.stringify({ session_ids: sessionIds }) }
  )

export const startSessionOnPilot = (
  sessionId: number,
  pilotId: number,
  mode?: string,
  overrides?: Overrides
) =>
  apiFetch<{ status: string; run_id: number }>(`/api/sessions/${sessionId}/start-on-pilot`, {
    method: 'POST',
    body: JSON.stringify({ pilot_id: pilotId, mode, overrides }),
  })
