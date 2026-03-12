import { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getSubjectDetail, patchSubjectDetail,
  addWeight, addSurgery,
  assignSubjectToProject, removeSubjectFromProject,
  getProjects, getResearchers, createResearcher,
} from '../../api/lab'
import type { SubjectExtendedRead, ResearcherRead, ProjectRead } from '../../types'

type Tab = 'bio' | 'admin' | 'weights' | 'surgeries' | 'projects'

interface Props {
  subjectId: number
  onClose: () => void
}

function Field({ label, value }: { label: string; value?: string | number | boolean | null }) {
  return (
    <div className="param-field">
      <label><span className="param-name">{label}</span></label>
      <div style={{ fontSize: '13px', color: 'var(--text)', padding: '2px 0' }}>
        {value == null || value === '' ? <span className="muted">—</span> : String(value)}
      </div>
    </div>
  )
}

export default function SubjectDetailModal({ subjectId, onClose }: Props) {
  const qc = useQueryClient()
  const [tab, setTab] = useState<Tab>('bio')
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<Partial<SubjectExtendedRead>>({})

  // Weight form
  const [wDate, setWDate] = useState('')
  const [wGrams, setWGrams] = useState('')
  const [wNotes, setWNotes] = useState('')

  // Surgery form
  const [sType, setSType] = useState('')
  const [sDate, setSDate] = useState('')
  const [sNotes, setSNotes] = useState('')

  // Researcher form
  const [newResName, setNewResName] = useState('')
  const [newResEmail, setNewResEmail] = useState('')
  const [showResForm, setShowResForm] = useState(false)

  const { data: subject, isLoading } = useQuery({
    queryKey: ['subject-detail', subjectId],
    queryFn: () => getSubjectDetail(subjectId),
  })

  const { data: allProjects } = useQuery({ queryKey: ['projects'], queryFn: getProjects })
  const { data: researchers } = useQuery({ queryKey: ['researchers'], queryFn: getResearchers })

  useEffect(() => {
    if (subject && editing) {
      setDraft({
        strain: subject.strain ?? '',
        genotype: subject.genotype ?? '',
        mother_name: subject.mother_name ?? '',
        father_name: subject.father_name ?? '',
        dob: subject.dob ?? '',
        sex: subject.sex ?? '',
        rfid: subject.rfid ?? undefined,
        lead_researcher_id: subject.lead_researcher_id ?? undefined,
        arrival_date: subject.arrival_date ?? '',
        in_quarantine: subject.in_quarantine ?? false,
        location: subject.location ?? '',
        holding_conditions: subject.holding_conditions ?? '',
        group_type: subject.group_type ?? '',
        group_details: subject.group_details ?? '',
        notes: subject.notes ?? '',
      })
    }
  }, [editing, subject])

  const patchMutation = useMutation({
    mutationFn: (data: Partial<SubjectExtendedRead>) => patchSubjectDetail(subjectId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['subject-detail', subjectId] })
      qc.invalidateQueries({ queryKey: ['subjects'] })
      setEditing(false)
    },
  })

  const weightMutation = useMutation({
    mutationFn: () => addWeight(subjectId, { measured_at: wDate, weight_grams: parseFloat(wGrams), notes: wNotes || undefined }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['subject-detail', subjectId] })
      setWDate(''); setWGrams(''); setWNotes('')
    },
  })

  const surgeryMutation = useMutation({
    mutationFn: () => addSurgery(subjectId, { procedure_type: sType, performed_at: sDate || undefined, notes: sNotes || undefined }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['subject-detail', subjectId] })
      setSType(''); setSDate(''); setSNotes('')
    },
  })

  const assignProjectMutation = useMutation({
    mutationFn: (projectId: number) => assignSubjectToProject(subjectId, projectId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['subject-detail', subjectId] }),
  })

  const removeProjectMutation = useMutation({
    mutationFn: (projectId: number) => removeSubjectFromProject(subjectId, projectId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['subject-detail', subjectId] }),
  })

  const researcherMutation = useMutation({
    mutationFn: () => createResearcher({ name: newResName.trim(), email: newResEmail.trim() || undefined }),
    onSuccess: (r: ResearcherRead) => {
      qc.invalidateQueries({ queryKey: ['researchers'] })
      setDraft(d => ({ ...d, lead_researcher_id: r.id }))
      setShowResForm(false)
      setNewResName(''); setNewResEmail('')
    },
  })

  const assignedProjectIds = new Set((subject?.projects ?? []).map(p => p.id))
  const availableProjects = (allProjects ?? []).filter(p => !assignedProjectIds.has(p.id))
  const researcherName = (id?: number | null) =>
    researchers?.find(r => r.id === id)?.name ?? (id ? `#${id}` : '—')

  const set = (k: keyof SubjectExtendedRead, v: unknown) => setDraft(d => ({ ...d, [k]: v }))

  const content = (
    <div
      className="modal-overlay"
      style={{ zIndex: 1000, alignItems: 'flex-start', paddingTop: '10vh' }}
      onMouseDown={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="modal" style={{ width: '560px', maxHeight: '75vh', display: 'flex', flexDirection: 'column' }}>
        <div className="modal-header">
          <span className="modal-title">Subject Detail</span>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        <div className="modal-tabs">
          {(['bio', 'admin', 'weights', 'surgeries', 'projects'] as Tab[]).map(t => (
            <button key={t} className={`modal-tab${tab === t ? ' active' : ''}`} onClick={() => { setTab(t); setEditing(false) }}>
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>

        <div className="modal-body" style={{ overflowY: 'auto', flex: 1 }}>
          {isLoading && <p className="muted">Loading…</p>}

          {!isLoading && subject && (
            <>
              {/* BIO TAB */}
              {tab === 'bio' && (
                <div>
                  {!editing ? (
                    <>
                      <div className="params-grid params-grid-2col">
                        <Field label="Strain" value={subject.strain} />
                        <Field label="Genotype" value={subject.genotype} />
                        <Field label="Sex" value={subject.sex} />
                        <Field label="DOB" value={subject.dob} />
                        <Field label="RFID" value={subject.rfid} />
                        <Field label="Mother" value={subject.mother_name} />
                        <Field label="Father" value={subject.father_name} />
                      </div>
                      <button className="button-secondary" style={{ marginTop: '1rem' }} onClick={() => setEditing(true)}>Edit</button>
                    </>
                  ) : (
                    <>
                      <div className="params-grid params-grid-2col">
                        {([['strain', 'Strain'], ['genotype', 'Genotype'], ['sex', 'Sex'], ['dob', 'DOB (YYYY-MM-DD)'], ['mother_name', 'Mother'], ['father_name', 'Father']] as [keyof SubjectExtendedRead, string][]).map(([k, lbl]) => (
                          <div key={k} className="param-field">
                            <label><span className="param-name">{lbl}</span></label>
                            <input type="text" value={(draft[k] as string) ?? ''} onChange={e => set(k, e.target.value)} />
                          </div>
                        ))}
                        <div className="param-field">
                          <label><span className="param-name">RFID</span></label>
                          <input type="number" value={draft.rfid ?? ''} onChange={e => set('rfid', e.target.value ? parseInt(e.target.value) : null)} />
                        </div>
                      </div>
                      <div className="modal-actions ov-actions" style={{ marginTop: '1rem' }}>
                        <button className="button-primary" disabled={patchMutation.isPending} onClick={() => patchMutation.mutate(draft)}>Save</button>
                        <button className="button-secondary" onClick={() => setEditing(false)}>Cancel</button>
                      </div>
                    </>
                  )}
                </div>
              )}

              {/* ADMIN TAB */}
              {tab === 'admin' && (
                <div>
                  {!editing ? (
                    <>
                      <div className="params-grid params-grid-2col">
                        <Field label="Lead Researcher" value={researcherName(subject.lead_researcher_id)} />
                        <Field label="Arrival Date" value={subject.arrival_date} />
                        <Field label="In Quarantine" value={subject.in_quarantine ? 'Yes' : 'No'} />
                        <Field label="Location" value={subject.location} />
                        <Field label="Holding Conditions" value={subject.holding_conditions} />
                        <Field label="Group Type" value={subject.group_type} />
                        <Field label="Group Details" value={subject.group_details} />
                        <Field label="Notes" value={subject.notes} />
                      </div>
                      <button className="button-secondary" style={{ marginTop: '1rem' }} onClick={() => setEditing(true)}>Edit</button>
                    </>
                  ) : (
                    <>
                      <div className="params-grid params-grid-2col">
                        <div className="param-field">
                          <label><span className="param-name">Lead Researcher</span></label>
                          <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                            <select
                              value={draft.lead_researcher_id ?? ''}
                              onChange={e => set('lead_researcher_id', e.target.value ? parseInt(e.target.value) : null)}
                              style={{ flex: 1 }}
                            >
                              <option value="">None</option>
                              {(researchers ?? []).map(r => (
                                <option key={r.id} value={r.id}>{r.name}</option>
                              ))}
                            </select>
                            <button className="button-link" type="button" onClick={() => setShowResForm(v => !v)}>+</button>
                          </div>
                          {showResForm && (
                            <div style={{ marginTop: '6px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                              <input type="text" placeholder="Name" value={newResName} onChange={e => setNewResName(e.target.value)} />
                              <input type="email" placeholder="Email (optional)" value={newResEmail} onChange={e => setNewResEmail(e.target.value)} />
                              <button className="button-primary" disabled={!newResName.trim() || researcherMutation.isPending} onClick={() => researcherMutation.mutate()}>Add</button>
                            </div>
                          )}
                        </div>
                        <div className="param-field">
                          <label><span className="param-name">Arrival Date</span></label>
                          <input type="text" placeholder="YYYY-MM-DD" value={draft.arrival_date ?? ''} onChange={e => set('arrival_date', e.target.value)} />
                        </div>
                        <div className="param-field">
                          <label><span className="param-name">In Quarantine</span></label>
                          <select value={draft.in_quarantine ? 'true' : 'false'} onChange={e => set('in_quarantine', e.target.value === 'true')}>
                            <option value="false">No</option>
                            <option value="true">Yes</option>
                          </select>
                        </div>
                        {(['location', 'holding_conditions', 'group_type', 'group_details', 'notes'] as const).map(k => (
                          <div key={k} className="param-field">
                            <label><span className="param-name">{k.replace(/_/g, ' ')}</span></label>
                            <input type="text" value={(draft[k] as string) ?? ''} onChange={e => set(k, e.target.value)} />
                          </div>
                        ))}
                      </div>
                      <div className="modal-actions ov-actions" style={{ marginTop: '1rem' }}>
                        <button className="button-primary" disabled={patchMutation.isPending} onClick={() => patchMutation.mutate(draft)}>Save</button>
                        <button className="button-secondary" onClick={() => setEditing(false)}>Cancel</button>
                      </div>
                    </>
                  )}
                </div>
              )}

              {/* WEIGHTS TAB */}
              {tab === 'weights' && (
                <div>
                  {subject.weights.length === 0 ? (
                    <p className="muted">No weight measurements.</p>
                  ) : (
                    <table style={{ width: '100%', fontSize: '13px', borderCollapse: 'collapse', marginBottom: '1rem' }}>
                      <thead>
                        <tr style={{ color: 'var(--subtext0)', textAlign: 'left' }}>
                          <th style={{ padding: '4px 8px' }}>Date</th>
                          <th style={{ padding: '4px 8px' }}>Weight (g)</th>
                          <th style={{ padding: '4px 8px' }}>Notes</th>
                        </tr>
                      </thead>
                      <tbody>
                        {subject.weights.map(w => (
                          <tr key={w.id} style={{ borderTop: '1px solid var(--surface1)' }}>
                            <td style={{ padding: '4px 8px' }}>{w.measured_at}</td>
                            <td style={{ padding: '4px 8px' }}>{w.weight_grams}</td>
                            <td style={{ padding: '4px 8px', color: 'var(--subtext0)' }}>{w.notes ?? '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'flex-end' }}>
                    <div className="param-field" style={{ flex: '1 1 120px' }}>
                      <label><span className="param-name">Date</span></label>
                      <input type="text" placeholder="YYYY-MM-DD" value={wDate} onChange={e => setWDate(e.target.value)} />
                    </div>
                    <div className="param-field" style={{ flex: '1 1 100px' }}>
                      <label><span className="param-name">Weight (g)</span></label>
                      <input type="number" step="0.1" placeholder="23.5" value={wGrams} onChange={e => setWGrams(e.target.value)} />
                    </div>
                    <div className="param-field" style={{ flex: '2 1 160px' }}>
                      <label><span className="param-name">Notes</span></label>
                      <input type="text" value={wNotes} onChange={e => setWNotes(e.target.value)} />
                    </div>
                    <button
                      className="button-primary"
                      disabled={!wDate || !wGrams || weightMutation.isPending}
                      onClick={() => weightMutation.mutate()}
                    >
                      Add
                    </button>
                  </div>
                </div>
              )}

              {/* SURGERIES TAB */}
              {tab === 'surgeries' && (
                <div>
                  {subject.surgeries.length === 0 ? (
                    <p className="muted">No surgeries recorded.</p>
                  ) : (
                    <table style={{ width: '100%', fontSize: '13px', borderCollapse: 'collapse', marginBottom: '1rem' }}>
                      <thead>
                        <tr style={{ color: 'var(--subtext0)', textAlign: 'left' }}>
                          <th style={{ padding: '4px 8px' }}>Procedure</th>
                          <th style={{ padding: '4px 8px' }}>Date</th>
                          <th style={{ padding: '4px 8px' }}>Notes</th>
                        </tr>
                      </thead>
                      <tbody>
                        {subject.surgeries.map(s => (
                          <tr key={s.id} style={{ borderTop: '1px solid var(--surface1)' }}>
                            <td style={{ padding: '4px 8px' }}>{s.procedure_type}</td>
                            <td style={{ padding: '4px 8px' }}>{s.performed_at ?? '—'}</td>
                            <td style={{ padding: '4px 8px', color: 'var(--subtext0)' }}>{s.notes ?? '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'flex-end' }}>
                    <div className="param-field" style={{ flex: '2 1 180px' }}>
                      <label><span className="param-name">Procedure type</span></label>
                      <input type="text" placeholder="e.g. Cannulation" value={sType} onChange={e => setSType(e.target.value)} />
                    </div>
                    <div className="param-field" style={{ flex: '1 1 120px' }}>
                      <label><span className="param-name">Date</span></label>
                      <input type="text" placeholder="YYYY-MM-DD" value={sDate} onChange={e => setSDate(e.target.value)} />
                    </div>
                    <div className="param-field" style={{ flex: '2 1 160px' }}>
                      <label><span className="param-name">Notes</span></label>
                      <input type="text" value={sNotes} onChange={e => setSNotes(e.target.value)} />
                    </div>
                    <button
                      className="button-primary"
                      disabled={!sType || surgeryMutation.isPending}
                      onClick={() => surgeryMutation.mutate()}
                    >
                      Add
                    </button>
                  </div>
                </div>
              )}

              {/* PROJECTS TAB */}
              {tab === 'projects' && (
                <div>
                  <div style={{ marginBottom: '1rem' }}>
                    <div style={{ fontSize: '12px', color: 'var(--subtext0)', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Assigned Projects</div>
                    {subject.projects.length === 0 ? (
                      <p className="muted">Not assigned to any projects.</p>
                    ) : (
                      subject.projects.map((p: ProjectRead) => (
                        <div key={p.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0', borderBottom: '1px solid var(--surface1)' }}>
                          <span style={{ fontSize: '13px' }}>{p.name}</span>
                          <button
                            className="button-danger"
                            style={{ fontSize: '11px', padding: '2px 8px' }}
                            disabled={removeProjectMutation.isPending}
                            onClick={() => removeProjectMutation.mutate(p.id)}
                          >
                            Remove
                          </button>
                        </div>
                      ))
                    )}
                  </div>
                  {availableProjects.length > 0 && (
                    <div>
                      <div style={{ fontSize: '12px', color: 'var(--subtext0)', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Add to Project</div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        {availableProjects.map((p: ProjectRead) => (
                          <div key={p.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ fontSize: '13px', color: 'var(--subtext1)' }}>{p.name}</span>
                            <button
                              className="button-secondary"
                              style={{ fontSize: '11px', padding: '2px 8px' }}
                              disabled={assignProjectMutation.isPending}
                              onClick={() => assignProjectMutation.mutate(p.id)}
                            >
                              Add
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )

  return createPortal(content, document.body)
}
