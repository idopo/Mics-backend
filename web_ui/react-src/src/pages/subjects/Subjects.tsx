import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getSubjects } from '../../api/subjects'
import CreateSubjectModal from './CreateSubjectModal'
import SubjectDetailModal from './SubjectDetailModal'

export default function Subjects() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [detailId, setDetailId] = useState<number | null>(null)

  const { data: subjects, isLoading } = useQuery({ queryKey: ['subjects'], queryFn: getSubjects })

  const filtered = useMemo(() => {
    if (!search.trim()) return subjects ?? []
    const q = search.trim().toLowerCase()
    return (subjects ?? []).filter(s => s.name.toLowerCase().includes(q))
  }, [subjects, search])

  return (
    <div className="container">
      <section className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h2 style={{ margin: 0 }}>Subjects</h2>
          <button className="button-primary" onClick={() => setShowCreate(true)}>
            + New Subject
          </button>
        </div>

        <div style={{ marginBottom: '0.75rem' }}>
          <input
            type="text"
            placeholder="Search subjects…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{ width: '100%' }}
          />
        </div>

        {isLoading ? (
          <div className="skeleton-list">
            {[...Array(8)].map((_, i) => <div key={i} className="skeleton-row" />)}
          </div>
        ) : filtered.length === 0 ? (
          <p className="muted">{search ? 'No matches.' : 'No subjects yet — create one above.'}</p>
        ) : (
          <ul id="subjects-list" style={{ maxHeight: 'calc(100vh - 260px)', overflowY: 'auto', margin: 0 }}>
            {filtered.map((s, idx) => {
              const subtitle = [s.strain, s.sex, s.group_type].filter(Boolean).join(' · ')
              return (
                <li
                  key={s.id}
                  className="subject-item fade-in-item"
                  style={{ animationDelay: `${Math.min(idx * 14, 180)}ms`, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
                  onClick={() => navigate(`/subjects/${s.name}/sessions-ui`)}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 500 }}>{s.name}</div>
                    {subtitle && (
                      <div style={{ fontSize: '12px', color: 'var(--subtext0)', marginTop: '1px' }}>
                        {subtitle}
                      </div>
                    )}
                  </div>
                  <button
                    title="View details"
                    style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '16px', padding: '4px 8px', color: 'var(--subtext0)', flexShrink: 0, lineHeight: 1, opacity: 0.7 }}
                    onClick={e => { e.stopPropagation(); setDetailId(s.id) }}
                  >
                    ⓘ
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </section>

      {showCreate && (
        <CreateSubjectModal
          onClose={() => { setShowCreate(false); qc.invalidateQueries({ queryKey: ['subjects'] }) }}
        />
      )}

      {detailId != null && (
        <SubjectDetailModal subjectId={detailId} onClose={() => setDetailId(null)} />
      )}
    </div>
  )
}
