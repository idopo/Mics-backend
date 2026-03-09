import { apiFetch } from './client'
import type { Subject, SessionSummary } from '../types'

export const getSubjects = () => apiFetch<Subject[]>('/api/subjects')
export const createSubject = (name: string) =>
  apiFetch<Subject>('/api/subjects', {
    method: 'POST',
    body: JSON.stringify({ name }),
  })
export const getSubjectSessions = (subject: string) =>
  apiFetch<SessionSummary[]>(`/api/subjects/${encodeURIComponent(subject)}/sessions`)
