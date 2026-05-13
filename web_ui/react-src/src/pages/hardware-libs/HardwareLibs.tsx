import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listHardwareLibs, uploadHardwareLib } from '../../api/hardware_libs'
import type { HardwareLib, LibState } from '../../types'

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function stateClass(state: LibState | null): string {
  if (state === 'stable') return 'badge status-completed'
  if (state === 'beta') return 'badge status-running'
  return 'badge status-error'
}

function UploadForm({ onDone }: { onDone: (id: number) => void }): JSX.Element {
  const qc = useQueryClient()
  const [name, setName] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  const mutation = useMutation({
    mutationFn: () => uploadHardwareLib(name.trim(), file!),
    onSuccess: (lib) => {
      qc.invalidateQueries({ queryKey: ['hardware-libs'] })
      setName(''); setFile(null); setError('')
      if (fileRef.current) fileRef.current.value = ''
      onDone(lib.id)
    },
    onError: (e: Error) => setError(e.message),
  })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
      <input
        type="text"
        placeholder="Library name (e.g. GPIO Driver) *"
        value={name}
        onChange={e => { setName(e.target.value); setError('') }}
      />
      <input
        ref={fileRef}
        type="file"
        accept=".py"
        onChange={e => { setFile(e.target.files?.[0] ?? null); setError('') }}
      />
      {error && <span className="badge status-error" style={{ alignSelf: 'flex-start' }}>{error}</span>}
      <button
        className="button-primary"
        style={{ alignSelf: 'flex-start' }}
        disabled={!file || !name.trim() || mutation.isPending}
        onClick={() => mutation.mutate()}
      >
        {mutation.isPending ? 'Uploading…' : 'Upload'}
      </button>
    </div>
  )
}

export default function HardwareLibs(): JSX.Element {
  const navigate = useNavigate()
  const { data: libs, isLoading } = useQuery<HardwareLib[]>({
    queryKey: ['hardware-libs'],
    queryFn: listHardwareLibs,
  })
  const [showUpload, setShowUpload] = useState(false)

  return (
    <div className="container">
      <section className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h2 style={{ margin: 0 }}>Hardware Libraries</h2>
          <button
            className="button-primary"
            style={{ width: '28px', height: '28px', padding: 0, fontSize: '18px', lineHeight: '1', borderRadius: '6px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
            title="Upload new library"
            onClick={() => setShowUpload(v => !v)}
          >
            {showUpload ? '✕' : '+'}
          </button>
        </div>

        {showUpload && (
          <div style={{ background: 'var(--surface1)', padding: '1rem', borderRadius: '8px', marginBottom: '1rem' }}>
            <UploadForm onDone={(id) => { setShowUpload(false); navigate(`/hardware-libs/${id}`) }} />
          </div>
        )}

        {isLoading ? (
          <p className="muted">Loading…</p>
        ) : (libs ?? []).length === 0 ? (
          <p className="muted">No hardware libraries yet. Upload one above.</p>
        ) : (
          <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
            {(libs ?? []).map(lib => (
              <li
                key={lib.id}
                onClick={() => navigate(`/hardware-libs/${lib.id}`)}
                style={{ padding: '10px 0', borderBottom: '1px solid var(--surface1)', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
              >
                <div>
                  <div style={{ fontWeight: 500, fontSize: '14px' }}>{lib.name}</div>
                  <div style={{ fontSize: '12px', color: 'var(--subtext0)', marginTop: '2px', fontFamily: 'monospace' }}>{lib.filename}</div>
                  <div style={{ fontSize: '11px', color: 'var(--subtext0)', marginTop: '2px' }}>{formatDate(lib.created_at)}</div>
                </div>
                <span className={stateClass(lib.active_state)}>{lib.active_state ?? 'none'}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
