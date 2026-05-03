import { apiFetch } from './client'
import type { HardwareLib, HardwareLibVersion, HwLibPin, HwLibDiff } from '../types'

export async function listHardwareLibs(): Promise<HardwareLib[]> {
  return apiFetch('/api/hardware-libs')
}

export async function getHardwareLib(id: number): Promise<HardwareLib> {
  return apiFetch(`/api/hardware-libs/${id}`)
}

export async function uploadHardwareLib(name: string, file: File): Promise<HardwareLib> {
  const fd = new FormData()
  fd.append('name', name)
  fd.append('file', file)
  return apiFetch('/api/hardware-libs', { method: 'POST', body: fd })
}

export async function updateHardwareLibSource(id: number, source_code: string): Promise<HardwareLib> {
  return apiFetch(`/api/hardware-libs/${id}`, {
    method: 'PUT',
    body: JSON.stringify({ source_code }),
  })
}

export async function listVersions(id: number, state?: string): Promise<HardwareLibVersion[]> {
  const q = state ? `?state=${encodeURIComponent(state)}` : ''
  return apiFetch(`/api/hardware-libs/${id}/versions${q}`)
}

export async function markStable(id: number): Promise<HardwareLib> {
  return apiFetch(`/api/hardware-libs/${id}/mark-stable`, { method: 'PATCH' })
}

export async function rollback(id: number, version_id: number): Promise<HardwareLib> {
  return apiFetch(`/api/hardware-libs/${id}/rollback`, {
    method: 'POST',
    body: JSON.stringify({ version_id }),
  })
}

export async function getHwLibPins(taskDefId: number): Promise<HwLibPin[]> {
  return apiFetch(`/api/task-definitions/${taskDefId}/hw-lib-pins`)
}

export async function setHwLibPin(taskDefId: number, libId: number, versionId: number): Promise<void> {
  return apiFetch(`/api/task-definitions/${taskDefId}/hw-lib-pins/${libId}`, {
    method: 'PUT',
    body: JSON.stringify({ pinned_version_id: versionId }),
  })
}

export async function deleteHwLibPin(taskDefId: number, libId: number): Promise<void> {
  return apiFetch(`/api/task-definitions/${taskDefId}/hw-lib-pins/${libId}`, { method: 'DELETE' })
}

export async function getHwLibVersionDiff(libId: number, fromVersionId: number, toVersionId: number): Promise<HwLibDiff> {
  return apiFetch(`/api/hardware-libs/${libId}/versions/diff?from=${fromVersionId}&to=${toVersionId}`)
}
