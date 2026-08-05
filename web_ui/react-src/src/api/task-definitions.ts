import { apiFetch } from './client'
import type { TaskDefinitionFull, FdaJson, UiLayout, VariableUsageResponse } from '../types'

export const getTaskDefinitions = () =>
  apiFetch<TaskDefinitionFull[]>('/api/task-definitions')

export const getTaskDefinition = (id: number) =>
  apiFetch<TaskDefinitionFull>(`/api/task-definitions/${id}`)

export const updateTaskDefinition = (
  id: number,
  payload: { display_name?: string; fda_json?: FdaJson; ui_layout?: UiLayout }
) =>
  apiFetch<{ status: string; id: number }>(`/api/task-definitions/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })

export const createTaskDefinition = (payload: {
  display_name: string
  toolkit_name: string
  fda_json: Record<string, unknown>
}) =>
  apiFetch<{ id: number; task_name: string }>('/api/task-definitions', {
    method: 'POST',
    body: JSON.stringify(payload),
  })

/** Per-variable writers/readers for the FDA editor's read-only inspector (plan 23-07). */
export const getVariableUsage = (taskDefId: number) =>
  apiFetch<VariableUsageResponse>(`/api/task-definitions/${taskDefId}/variable-usage`)
