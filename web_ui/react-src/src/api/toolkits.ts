import { apiFetch } from './client'
import type { BackendToolkitCreatePayload, LockedStatesResponse, ToolkitRead } from '../types'

export const getToolkits = () =>
  apiFetch<ToolkitRead[]>('/api/toolkits')

export const getToolkitsByName = (name: string) =>
  apiFetch<ToolkitRead[]>(`/api/toolkits/by-name/${encodeURIComponent(name)}`)

export const getLockedStates = () =>
  apiFetch<LockedStatesResponse>('/api/locked-states')

export const createBackendToolkit = (payload: BackendToolkitCreatePayload): Promise<ToolkitRead> =>
  apiFetch('/api/toolkits', { method: 'POST', body: JSON.stringify(payload) })
