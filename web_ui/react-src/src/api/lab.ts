import { apiFetch } from './client'
import type {
  SubjectExtendedRead,
  ResearcherRead,
  IACUCRead,
  WeightRead,
  SurgeryRead,
  ProjectRead,
  ExperimentRead,
  Protocol,
} from '../types'

// Subject detail
export const getSubjectDetail = (id: number) =>
  apiFetch<SubjectExtendedRead>(`/api/subjects/${id}/detail`)

export const patchSubjectDetail = (id: number, data: Partial<SubjectExtendedRead>) =>
  apiFetch<SubjectExtendedRead>(`/api/subjects/${id}/detail`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })

// Weights
export const addWeight = (subjectId: number, data: { measured_at: string; weight_grams: number; notes?: string }) =>
  apiFetch<WeightRead>(`/api/subjects/${subjectId}/weights`, {
    method: 'POST',
    body: JSON.stringify(data),
  })

// Surgeries
export const addSurgery = (subjectId: number, data: { procedure_type: string; performed_at?: string; notes?: string }) =>
  apiFetch<SurgeryRead>(`/api/subjects/${subjectId}/surgeries`, {
    method: 'POST',
    body: JSON.stringify(data),
  })

// Subject ↔ Project links
export const assignSubjectToProject = (subjectId: number, projectId: number) =>
  apiFetch<void>(`/api/subjects/${subjectId}/projects/${projectId}`, { method: 'POST' })

export const removeSubjectFromProject = (subjectId: number, projectId: number) =>
  apiFetch<void>(`/api/subjects/${subjectId}/projects/${projectId}`, { method: 'DELETE' })

// Researchers
export const getResearchers = () => apiFetch<ResearcherRead[]>('/api/researchers')
export const createResearcher = (data: { name: string; email?: string }) =>
  apiFetch<ResearcherRead>('/api/researchers', {
    method: 'POST',
    body: JSON.stringify(data),
  })
export const updateResearcher = (id: number, data: { name?: string; email?: string }) =>
  apiFetch<ResearcherRead>(`/api/researchers/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
export const hideResearcher = (id: number) =>
  apiFetch<ResearcherRead>(`/api/researchers/${id}/hide`, { method: 'PATCH' })

// IACUC
export const getIACUC = () => apiFetch<IACUCRead[]>('/api/iacuc')
export const createIACUC = (data: { number: string; title: string; expires_at?: string }) =>
  apiFetch<IACUCRead>('/api/iacuc', {
    method: 'POST',
    body: JSON.stringify(data),
  })
export const hideIACUC = (id: number) =>
  apiFetch<IACUCRead>(`/api/iacuc/${id}/hide`, { method: 'PATCH' })

// Projects
export const getProjects = () => apiFetch<ProjectRead[]>('/api/projects')
export const getProject = (id: number) => apiFetch<ProjectRead>(`/api/projects/${id}`)
export const createProject = (data: {
  name: string
  description?: string
  iacuc_id?: number
  lead_researcher_id?: number
  notes?: string
}) =>
  apiFetch<ProjectRead>('/api/projects', {
    method: 'POST',
    body: JSON.stringify(data),
  })

// Experiments
export const getExperiments = (projectId?: number) => {
  const qs = projectId != null ? `?project_id=${projectId}` : ''
  return apiFetch<ExperimentRead[]>(`/api/experiments${qs}`)
}
export const getExperiment = (id: number) => apiFetch<ExperimentRead>(`/api/experiments/${id}`)
export const createExperiment = (data: {
  name: string
  project_id: number
  description?: string
  notes?: string
}) =>
  apiFetch<ExperimentRead>('/api/experiments', {
    method: 'POST',
    body: JSON.stringify(data),
  })

export const getExperimentProtocols = (experimentId: number) =>
  apiFetch<Protocol[]>(`/api/experiments/${experimentId}/protocols`)
