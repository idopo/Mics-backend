import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listHardwareLibs, uploadHardwareLib } from '../../api/hardware_libs'
import type { HardwareLib, LibState, LibKind } from '../../types'

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function stateClass(state: LibState | null): string {
  if (state === 'stable') return 'badge status-completed'
  if (state === 'beta') return 'badge status-running'
  return 'badge status-error'
}

// Selected/unselected treatment mirrors stateClass's badge + status-* composition above.
function chipClass(selected: boolean): string {
  return selected ? 'badge status-completed' : 'badge'
}

function parseDeclaredImports(raw: string): string[] {
  return raw.split(',').map(s => s.trim()).filter(Boolean)
}

function UploadForm({ onDone }: { onDone: (id: number) => void }): JSX.Element {
  const qc = useQueryClient()
  const [name, setName] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [kind, setKind] = useState<LibKind>('hardware')
  const [declaredImportsRaw, setDeclaredImportsRaw] = useState('')
  const [error, setError] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  const mutation = useMutation({
    mutationFn: () => uploadHardwareLib(name.trim(), file!, kind, parseDeclaredImports(declaredImportsRaw)),
    onSuccess: (lib) => {
      qc.invalidateQueries({ queryKey: ['hardware-libs'] })
      setName(''); setFile(null); setKind('hardware'); setDeclaredImportsRaw(''); setError('')
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
      <select value={kind} onChange={e => { setKind(e.target.value as LibKind); setError('') }}>
        <option value="hardware">Hardware</option>
        <option value="compute">Compute</option>
      </select>
      {kind === 'compute' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          <input
            type="text"
            placeholder="random, math"
            value={declaredImportsRaw}
            onChange={e => { setDeclaredImportsRaw(e.target.value); setError('') }}
          />
          <span className="muted" style={{ fontSize: '11px' }}>
            Comma-separated stdlib imports only, for now. Third-party packages need per-Pi package
            management (deferred).
          </span>
        </div>
      )}
      {error && <span className="badge status-error" style={{ alignSelf: 'flex-start', whiteSpace: 'pre-wrap' }}>{error}</span>}
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
  const [kindFilter, setKindFilter] = useState<LibKind | 'all'>('all')

  const allLibs = libs ?? []
  const counts = {
    all: allLibs.length,
    hardware: allLibs.filter(l => l.kind === 'hardware').length,
    compute: allLibs.filter(l => l.kind === 'compute').length,
  }
  const filteredLibs = allLibs.filter(l => kindFilter === 'all' || l.kind === kindFilter)

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

        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
          {(['all', 'hardware', 'compute'] as const).map(k => (
            <button
              key={k}
              className={chipClass(kindFilter === k)}
              style={{ cursor: 'pointer', textTransform: 'capitalize' }}
              onClick={() => setKindFilter(k)}
            >
              {k} ({counts[k]})
            </button>
          ))}
        </div>

        {showUpload && (
          <div style={{ background: 'var(--surface1)', padding: '1rem', borderRadius: '8px', marginBottom: '1rem' }}>
            <UploadForm onDone={(id) => { setShowUpload(false); navigate(`/hardware-libs/${id}`) }} />
          </div>
        )}

        {isLoading ? (
          <p className="muted">Loading…</p>
        ) : filteredLibs.length === 0 ? (
          <p className="muted">
            {allLibs.length === 0 ? 'No hardware libraries yet. Upload one above.' : `No ${kindFilter} libraries.`}
          </p>
        ) : (
          <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
            {filteredLibs.map(lib => (
              <li
                key={lib.id}
                onClick={() => navigate(`/hardware-libs/${lib.id}`)}
                style={{ padding: '10px 0', borderBottom: '1px solid var(--surface1)', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
              >
                <div>
                  <div style={{ fontWeight: 500, fontSize: '14px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    {lib.name}
                    {lib.kind === 'compute' && <span className="meta-pill">compute</span>}
                  </div>
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
