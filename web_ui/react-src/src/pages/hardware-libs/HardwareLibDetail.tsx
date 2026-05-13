import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import CodeMirror from '@uiw/react-codemirror'
import { python } from '@codemirror/lang-python'
import { oneDark } from '@codemirror/theme-one-dark'
import {
  getHardwareLib,
  updateHardwareLibSource,
  listVersions,
  markStable,
  rollback,
} from '../../api/hardware_libs'
import type { HardwareLib, HardwareLibVersion, LibState } from '../../types'

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function stateClass(state: LibState | null): string {
  if (state === 'stable') return 'badge status-completed'
  if (state === 'beta') return 'badge status-running'
  return 'badge status-error'
}

export default function HardwareLibDetail(): JSX.Element {
  const { id } = useParams<{ id: string }>()
  const libId = Number(id)
  const navigate = useNavigate()
  const qc = useQueryClient()

  const { data: lib, isLoading } = useQuery<HardwareLib>({
    queryKey: ['hardware-libs', libId],
    queryFn: () => getHardwareLib(libId),
    enabled: !!libId,
  })
  const { data: versions } = useQuery<HardwareLibVersion[]>({
    queryKey: ['hardware-libs', libId, 'versions'],
    queryFn: () => listVersions(libId),
    enabled: !!libId,
  })

  const [selectedVersionId, setSelectedVersionId] = useState<number | null>(null)
  const [editMode, setEditMode] = useState(false)
  const [draft, setDraft] = useState('')
  const [saveError, setSaveError] = useState('')

  // Select active version by default when data loads
  useEffect(() => {
    if (lib?.active_version_id && selectedVersionId === null) {
      setSelectedVersionId(lib.active_version_id)
    }
  }, [lib?.active_version_id, selectedVersionId])

  // Exit edit mode when switching versions
  useEffect(() => {
    setEditMode(false)
    setSaveError('')
  }, [selectedVersionId])

  // Keep draft in sync with selected version source
  const selectedVersion = (versions ?? []).find(v => v.id === selectedVersionId) ?? null

  useEffect(() => {
    if (selectedVersion?.source_code != null) setDraft(selectedVersion.source_code)
  }, [selectedVersion?.source_code, selectedVersionId])

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['hardware-libs'] })
    qc.invalidateQueries({ queryKey: ['hardware-libs', libId] })
    qc.invalidateQueries({ queryKey: ['hardware-libs', libId, 'versions'] })
  }

  const saveMutation = useMutation({
    mutationFn: () => updateHardwareLibSource(libId, draft),
    onSuccess: (updated) => {
      invalidate()
      setEditMode(false)
      setSaveError('')
      setSelectedVersionId(updated.active_version_id)
    },
    onError: (e: Error) => setSaveError(e.message),
  })

  const stableMutation = useMutation({
    mutationFn: () => markStable(libId),
    onSuccess: invalidate,
  })

  const rollbackMutation = useMutation({
    mutationFn: (versionId: number) => rollback(libId, versionId),
    onSuccess: (updated) => {
      invalidate()
      setSelectedVersionId(updated.active_version_id)
    },
  })

  if (isLoading) return (
    <div style={{ display: 'flex', justifyContent: 'center', paddingTop: '4rem', color: 'var(--subtext0)' }}>
      Loading…
    </div>
  )
  if (!lib) return (
    <div style={{ display: 'flex', justifyContent: 'center', paddingTop: '4rem', color: 'var(--subtext0)' }}>
      Library not found.
    </div>
  )

  const isActiveSelected = selectedVersionId === lib.active_version_id

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 48px)', overflow: 'hidden' }}>

      {/* Top bar */}
      <div style={{
        flexShrink: 0,
        borderBottom: '1px solid var(--surface1)',
        padding: '0.65rem 1.25rem',
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        background: 'var(--base)',
      }}>
        <button
          className="button-secondary"
          style={{ fontSize: '12px', padding: '3px 10px' }}
          onClick={() => navigate('/hardware-libs-ui')}
        >
          ← Back
        </button>

        <span style={{ fontWeight: 600, fontSize: '15px' }}>{lib.name}</span>
        <span style={{ fontSize: '12px', color: 'var(--subtext0)', fontFamily: 'monospace' }}>{lib.filename}</span>
        <span className={stateClass(lib.active_state)}>{lib.active_state ?? 'none'}</span>

        <div style={{ marginLeft: 'auto', display: 'flex', gap: '8px', alignItems: 'center' }}>
          {saveError && (
            <span className="badge status-error" style={{ fontSize: '11px' }}>{saveError}</span>
          )}
          {editMode ? (
            <>
              <button
                className="button-primary"
                style={{ fontSize: '12px', padding: '4px 12px' }}
                disabled={saveMutation.isPending}
                onClick={() => saveMutation.mutate()}
              >
                {saveMutation.isPending ? 'Saving…' : 'Save new version'}
              </button>
              <button
                className="button-secondary"
                style={{ fontSize: '12px', padding: '4px 12px' }}
                onClick={() => { setEditMode(false); setSaveError(''); if (selectedVersion) setDraft(selectedVersion.source_code ?? '') }}
              >
                Cancel
              </button>
            </>
          ) : (
            <>
              {selectedVersion?.state === 'beta' && isActiveSelected && (
                <button
                  className="button-primary"
                  style={{ fontSize: '12px', padding: '4px 12px' }}
                  disabled={stableMutation.isPending}
                  onClick={() => stableMutation.mutate()}
                >
                  {stableMutation.isPending ? '…' : 'Mark Stable'}
                </button>
              )}
              {!isActiveSelected && selectedVersion && (
                <button
                  className="button-secondary"
                  style={{ fontSize: '12px', padding: '4px 12px' }}
                  disabled={rollbackMutation.isPending}
                  onClick={() => rollbackMutation.mutate(selectedVersion.id)}
                >
                  {rollbackMutation.isPending ? '…' : 'Restore this version'}
                </button>
              )}
              {isActiveSelected && (
                <button
                  className="button-secondary"
                  style={{ fontSize: '12px', padding: '4px 12px' }}
                  onClick={() => setEditMode(true)}
                >
                  Edit
                </button>
              )}
            </>
          )}
        </div>
      </div>

      {/* Split body */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>

        {/* Left: versions list */}
        <div style={{
          width: '200px',
          flexShrink: 0,
          borderRight: '1px solid var(--surface1)',
          overflowY: 'auto',
          padding: '0.5rem 0',
        }}>
          <div style={{ fontSize: '10px', color: 'var(--subtext0)', textTransform: 'uppercase', letterSpacing: '0.06em', padding: '4px 12px 8px' }}>
            Versions
          </div>
          {(versions ?? []).map(v => {
            const isActive = v.id === lib.active_version_id
            const isSelected = v.id === selectedVersionId
            return (
              <button
                key={v.id}
                onClick={() => setSelectedVersionId(v.id)}
                style={{
                  width: '100%',
                  textAlign: 'left',
                  padding: '8px 12px',
                  border: 'none',
                  cursor: 'pointer',
                  background: isSelected ? 'var(--surface1)' : 'transparent',
                  borderLeft: isSelected ? '2px solid var(--blue, #89b4fa)' : '2px solid transparent',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '3px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text)' }}>v{v.version_number}</span>
                  {isActive && <span style={{ fontSize: '10px', color: 'var(--subtext0)' }}>active</span>}
                </div>
                <span className={stateClass(v.state)} style={{ fontSize: '10px', alignSelf: 'flex-start' }}>{v.state}</span>
                <span style={{ fontSize: '11px', color: 'var(--subtext0)' }}>{formatDate(v.created_at)}</span>
              </button>
            )
          })}
        </div>

        {/* Right: code panel */}
        <div style={{ flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
          {selectedVersion ? (
            <>
              {selectedVersion.validation_error && (
                <div className="badge status-error" style={{ display: 'block', margin: '0.75rem 1rem', whiteSpace: 'pre-wrap', fontSize: '12px' }}>
                  {selectedVersion.validation_error}
                </div>
              )}
              <div style={{ flex: 1 }}>
                <CodeMirror
                  value={editMode ? draft : (selectedVersion.source_code ?? '')}
                  extensions={[python()]}
                  theme={oneDark}
                  editable={editMode}
                  onChange={(val) => setDraft(val)}
                  style={{ fontSize: '13px', minHeight: '100%' }}
                />
              </div>
            </>
          ) : (
            <div style={{ color: 'var(--subtext0)', padding: '2rem', fontSize: '13px' }}>
              Select a version to view its source.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
