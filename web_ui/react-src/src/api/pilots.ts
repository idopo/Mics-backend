import { apiFetch } from './client'
import type { Pilot } from '../types'

export const getPilots = () => apiFetch<Pilot[]>('/api/pilots')
export const getBackendPilots = () => apiFetch<Pilot[]>('/api/backend/pilots')
export const stopRun = (runId: number) =>
  apiFetch<{ status: string; run_id: number }>(`/api/session-runs/${runId}/stop`, { method: 'POST' })
