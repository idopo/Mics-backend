import { apiFetch } from './client'
import type { TaskDef } from '../types'

export const getLeafTasks = () => apiFetch<TaskDef[]>('/api/tasks/leaf')
