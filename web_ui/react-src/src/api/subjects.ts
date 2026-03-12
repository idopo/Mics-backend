import { apiFetch } from './client'
import type { Subject, SubjectProtocolRunItem } from '../types'

export const getSubjects = () => apiFetch<Subject[]>('/api/subjects')
export const createSubject = (name: string) =>
  apiFetch<Subject>('/api/subjects', {
    method: 'POST',
    body: JSON.stringify({ name }),
  })
export const getSubjectSessions = (subject: string) =>
  apiFetch<SubjectProtocolRunItem[]>(`/api/subjects/${encodeURIComponent(subject)}/runs`)
