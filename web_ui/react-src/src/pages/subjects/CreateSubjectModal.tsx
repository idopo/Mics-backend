import { useState } from 'react'
import { createPortal } from 'react-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createSubject } from '../../api/subjects'
import { patchSubjectDetail, getResearchers, createResearcher } from '../../api/lab'
import type { ResearcherRead } from '../../types'

interface Props {
  onClose: () => void
}

type Section = 'basic' | 'bio' | 'admin'

export default function CreateSubjectModal({ onClose }: Props) {
  const qc = useQueryClient()

  // Required
  const [name, setName] = useState('')

  // Bio
  const [strain, setStrain] = useState('')
  const [genotype, setGenotype] = useState('')
  const [sex, setSex] = useState('')
  const [dob, setDob] = useState('')
  const [rfid, setRfid] = useState('')
  const [motherName, setMotherName] = useState('')
  const [fatherName, setFatherName] = useState('')

  // Admin
  const [leadResearcherId, setLeadResearcherId] = useState<number | ''>('')
  const [arrivalDate, setArrivalDate] = useState('')
  const [inQuarantine, setInQuarantine] = useState(false)
  const [location, setLocation] = useState('')
  const [holdingConditions, setHoldingConditions] = useState('')
  const [groupType, setGroupType] = useState('')
  const [groupDetails, setGroupDetails] = useState('')
  const [notes, setNotes] = useState('')

  // Researcher quick-add
  const [showResForm, setShowResForm] = useState(false)
  const [newResName, setNewResName] = useState('')
  const [newResEmail, setNewResEmail] = useState('')

  const [section, setSection] = useState<Section>('basic')
  const [error, setError] = useState('')

  const { data: researchers } = useQuery({ queryKey: ['researchers'], queryFn: getResearchers })

  const researcherMutation = useMutation({
    mutationFn: () => createResearcher({ name: newResName.trim(), email: newResEmail.trim() || undefined }),
    onSuccess: (r: ResearcherRead) => {
      qc.invalidateQueries({ queryKey: ['researchers'] })
      setLeadResearcherId(r.id)
      setShowResForm(false)
      setNewResName(''); setNewResEmail('')
    },
  })

  const createMutation = useMutation({
    mutationFn: async () => {
      // Step 1: create subject (name only)
      const subject = await createSubject(name.trim())

      // Step 2: if any extra fields, patch detail
      const patch: Record<string, unknown> = {}
      if (strain) patch.strain = strain
      if (genotype) patch.genotype = genotype
      if (sex) patch.sex = sex
      if (dob) patch.dob = dob
      if (rfid) patch.rfid = parseInt(rfid)
      if (motherName) patch.mother_name = motherName
      if (fatherName) patch.father_name = fatherName
      if (leadResearcherId !== '') patch.lead_researcher_id = leadResearcherId
      if (arrivalDate) patch.arrival_date = arrivalDate
      if (inQuarantine) patch.in_quarantine = true
      if (location) patch.location = location
      if (holdingConditions) patch.holding_conditions = holdingConditions
      if (groupType) patch.group_type = groupType
      if (groupDetails) patch.group_details = groupDetails
      if (notes) patch.notes = notes

      if (Object.keys(patch).length > 0) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        await patchSubjectDetail(subject.id, patch as any)
      }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['subjects'] })
      onClose()
    },
    onError: (e: Error) => setError(e.message),
  })

  const content = (
    <div
      className="modal-overlay"
      style={{ zIndex: 1000 }}
      onMouseDown={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="modal" style={{ width: '640px', maxHeight: '85vh', display: 'flex', flexDirection: 'column' }}>
        <div className="modal-header">
          <span className="modal-title">New Subject</span>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        <div className="modal-tabs">
          {(['basic', 'bio', 'admin'] as Section[]).map(s => (
            <button
              key={s}
              className={`modal-tab${section === s ? ' active' : ''}`}
              onClick={() => setSection(s)}
            >
              {s === 'basic' ? 'Basic' : s === 'bio' ? 'Biology' : 'Admin'}
            </button>
          ))}
        </div>

        <div className="modal-body" style={{ overflowY: 'auto', flex: 1, minHeight: '340px' }}>
          {/* BASIC */}
          {section === 'basic' && (
            <div className="params-grid">
              <div className="param-field" style={{ gridColumn: '1 / -1' }}>
                <label><span className="param-name">Name <span style={{ color: 'var(--red)' }}>*</span></span></label>
                <input
                  type="text"
                  placeholder="e.g. Mouse01"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  autoFocus
                />
              </div>
              <div className="param-field">
                <label><span className="param-name">Strain</span></label>
                <input type="text" placeholder="e.g. C57BL/6" value={strain} onChange={e => setStrain(e.target.value)} />
              </div>
              <div className="param-field">
                <label><span className="param-name">Sex</span></label>
                <select value={sex} onChange={e => setSex(e.target.value)}>
                  <option value="">—</option>
                  <option value="M">Male</option>
                  <option value="F">Female</option>
                </select>
              </div>
              <div className="param-field">
                <label><span className="param-name">Date of Birth</span></label>
                <input type="text" placeholder="YYYY-MM-DD" value={dob} onChange={e => setDob(e.target.value)} />
              </div>
              <div className="param-field">
                <label><span className="param-name">Group Type</span></label>
                <input type="text" placeholder="e.g. control" value={groupType} onChange={e => setGroupType(e.target.value)} />
              </div>
            </div>
          )}

          {/* BIO */}
          {section === 'bio' && (
            <div className="params-grid params-grid-2col">
              <div className="param-field">
                <label><span className="param-name">Genotype</span></label>
                <input type="text" value={genotype} onChange={e => setGenotype(e.target.value)} />
              </div>
              <div className="param-field">
                <label><span className="param-name">RFID</span></label>
                <input type="number" value={rfid} onChange={e => setRfid(e.target.value)} />
              </div>
              <div className="param-field">
                <label><span className="param-name">Mother Name</span></label>
                <input type="text" value={motherName} onChange={e => setMotherName(e.target.value)} />
              </div>
              <div className="param-field">
                <label><span className="param-name">Father Name</span></label>
                <input type="text" value={fatherName} onChange={e => setFatherName(e.target.value)} />
              </div>
            </div>
          )}

          {/* ADMIN */}
          {section === 'admin' && (
            <div className="params-grid params-grid-2col">
              <div className="param-field">
                <label><span className="param-name">Lead Researcher</span></label>
                <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                  <select
                    value={leadResearcherId}
                    onChange={e => setLeadResearcherId(e.target.value ? parseInt(e.target.value) : '')}
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
                    <button className="button-primary" disabled={!newResName.trim() || researcherMutation.isPending} onClick={() => researcherMutation.mutate()}>
                      Add Researcher
                    </button>
                  </div>
                )}
              </div>
              <div className="param-field">
                <label><span className="param-name">Arrival Date</span></label>
                <input type="text" placeholder="YYYY-MM-DD" value={arrivalDate} onChange={e => setArrivalDate(e.target.value)} />
              </div>
              <div className="param-field">
                <label><span className="param-name">Location</span></label>
                <input type="text" value={location} onChange={e => setLocation(e.target.value)} />
              </div>
              <div className="param-field">
                <label><span className="param-name">Holding Conditions</span></label>
                <input type="text" value={holdingConditions} onChange={e => setHoldingConditions(e.target.value)} />
              </div>
              <div className="param-field">
                <label><span className="param-name">Group Details</span></label>
                <input type="text" value={groupDetails} onChange={e => setGroupDetails(e.target.value)} />
              </div>
              <div className="param-field">
                <label><span className="param-name">In Quarantine</span></label>
                <select value={inQuarantine ? 'true' : 'false'} onChange={e => setInQuarantine(e.target.value === 'true')}>
                  <option value="false">No</option>
                  <option value="true">Yes</option>
                </select>
              </div>
              <div className="param-field" style={{ gridColumn: '1 / -1' }}>
                <label><span className="param-name">Notes</span></label>
                <input type="text" value={notes} onChange={e => setNotes(e.target.value)} />
              </div>
            </div>
          )}
        </div>

        <div className="modal-actions ov-actions" style={{ padding: '12px 16px', borderTop: '1px solid var(--surface1)' }}>
          {error && <span style={{ color: 'crimson', fontSize: '13px', flex: 1 }}>{error}</span>}
          <button
            className="button-primary"
            disabled={!name.trim() || createMutation.isPending}
            onClick={() => { setError(''); createMutation.mutate() }}
          >
            {createMutation.isPending ? 'Creating…' : 'Create Subject'}
          </button>
          <button className="button-secondary" onClick={onClose}>Cancel</button>
        </div>
      </div>
    </div>
  )

  return createPortal(content, document.body)
}
