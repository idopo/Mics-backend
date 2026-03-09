import { apiFetch } from './client'
import type { Protocol } from '../types'

export const getProtocols = () => apiFetch<Protocol[]>('/api/protocols')
export const getProtocol = (id: number) => apiFetch<Protocol>(`/api/protocols/${id}`)
export const createProtocol = (payload: { name: string; description?: string; steps: Array<{ task_type: string; params?: Record<string, unknown> }> }) =>
  apiFetch<Protocol>('/api/protocols', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
export const assignProtocol = (protocolId: number, subjects: string[]) =>
  apiFetch<{ status: string; session: { session_id: number } }>('/api/assign-protocol', {
    method: 'POST',
    body: JSON.stringify({ protocol_id: protocolId, subjects }),
  })
