import { apiFetch } from './client'
import type { ToolkitRead } from '../types'

export const getToolkits = () =>
  apiFetch<ToolkitRead[]>('/api/toolkits')

export const getToolkitsByName = (name: string) =>
  apiFetch<ToolkitRead[]>(`/api/toolkits/by-name/${encodeURIComponent(name)}`)
