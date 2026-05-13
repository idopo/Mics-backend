import { apiFetch } from './client'
import type { HardwareModule, HardwareModuleMethods, PilotHardwareConfigRow } from '../types'

export async function listHardwareModules(): Promise<HardwareModule[]> {
  return apiFetch('/api/hardware-modules')
}

export async function getHardwareModule(id: number): Promise<HardwareModule> {
  return apiFetch(`/api/hardware-modules/${id}`)
}

export interface CreateHardwareModuleBody {
  name: string
  hardware_lib_id: number
  class_name: string
  display_name?: string
  description?: string
}

export async function createHardwareModule(body: CreateHardwareModuleBody): Promise<HardwareModule> {
  return apiFetch('/api/hardware-modules', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function updateHardwareModule(id: number, body: Partial<CreateHardwareModuleBody>): Promise<HardwareModule> {
  return apiFetch(`/api/hardware-modules/${id}`, {
    method: 'PUT',
    body: JSON.stringify(body),
  })
}

export async function deleteHardwareModule(id: number): Promise<void> {
  return apiFetch(`/api/hardware-modules/${id}`, { method: 'DELETE' })
}

export async function getHardwareModuleMethods(id: number): Promise<HardwareModuleMethods> {
  return apiFetch(`/api/hardware-modules/${id}/methods`)
}

export async function listPilotHardwareConfig(pilotId: number): Promise<PilotHardwareConfigRow[]> {
  return apiFetch(`/api/pilots/${pilotId}/hardware-config`)
}

export async function upsertPilotHardwareConfig(
  pilotId: number,
  moduleId: number,
  config: Record<string, unknown>,
): Promise<PilotHardwareConfigRow> {
  return apiFetch(`/api/pilots/${pilotId}/hardware-config/${moduleId}`, {
    method: 'PUT',
    body: JSON.stringify({ config }),
  })
}

export async function deletePilotHardwareConfig(pilotId: number, moduleId: number): Promise<void> {
  return apiFetch(`/api/pilots/${pilotId}/hardware-config/${moduleId}`, { method: 'DELETE' })
}
