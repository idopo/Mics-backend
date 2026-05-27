import { useState } from 'react'
import { useQueries } from '@tanstack/react-query'
import { listVersions, setHwLibVersion } from '../../api/hardware_libs'
import type { HwLibVersionEntry } from '../../types'

interface Props {
  taskDefId: number
  pins: HwLibVersionEntry[]
  onClose: () => void
  onSaved: () => void
}

export default function HwLibVersionModal({ taskDefId, pins, onClose, onSaved }: Props) {
  const [selections, setSelections] = useState<Record<number, number>>(
    () => Object.fromEntries(
      pins
        .filter(e => (e.selected_version_id ?? e.active_version_id) != null)
        .map(e => [e.hardware_lib_id, (e.selected_version_id ?? e.active_version_id) as number])
    )
  )
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const versionsQueries = useQueries({
    queries: pins.map(e => ({
      queryKey: ['hw-lib-versions-list', e.hardware_lib_id],
      queryFn: () => listVersions(e.hardware_lib_id),
    })),
  })

  const hasChanges = pins.some(e => selections[e.hardware_lib_id] !== e.selected_version_id)

  async function handleSave() {
    setSaving(true)
    setError(null)
    try {
      await Promise.all(
        pins.map(e => {
          const sel = selections[e.hardware_lib_id]
          if (!sel || sel === e.selected_version_id) return Promise.resolve()
          return setHwLibVersion(taskDefId, e.hardware_lib_id, sel)
        })
      )
      onSaved()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Save failed')
      setSaving(false)
    }
  }

  return (
    <div className="modal-overlay" style={{ alignItems: 'flex-start', paddingTop: '10vh' }}>
      <div className="modal" style={{ width: '460px' }}>
        <div className="modal-header">
          <span className="modal-title">Hardware Library Versions</span>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        <div className="modal-body" style={{ padding: '0' }}>
          {pins.map((entry, i) => {
            const versions = versionsQueries[i].data ?? []
            const sel = selections[entry.hardware_lib_id]

            return (
              <div
                key={entry.hardware_lib_id}
                style={{ padding: '12px 20px', borderBottom: '1px solid var(--border)' }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                  <span style={{
                    fontFamily: "'IBM Plex Mono', monospace",
                    fontSize: '12px',
                    color: 'var(--text)',
                    flex: 1,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}>
                    {entry.lib_filename}
                  </span>
                </div>

                <select
                  value={sel ?? ''}
                  onChange={e => setSelections(s => ({
                    ...s,
                    [entry.hardware_lib_id]: Number(e.target.value),
                  }))}
                  style={{
                    width: '100%',
                    fontSize: '12px',
                    background: '#12141a',
                    color: 'var(--text)',
                    border: '1px solid var(--border)',
                    borderRadius: '4px',
                    padding: '5px 8px',
                    cursor: 'pointer',
                  }}
                >
                  {[...versions]
                    .sort((a, b) => b.version_number - a.version_number)
                    .map(v => (
                      <option key={v.id} value={v.id}>
                        v{v.version_number} — {v.state}
                      </option>
                    ))}
                </select>
              </div>
            )
          })}

          {error && (
            <p style={{ color: 'var(--error)', fontSize: '12px', margin: '12px 20px' }}>{error}</p>
          )}
        </div>

        <div style={{
          display: 'flex', justifyContent: 'flex-end', gap: '8px',
          padding: '12px 20px', borderTop: '1px solid var(--border)',
        }}>
          <button className="button-secondary" onClick={onClose}>Cancel</button>
          <button
            className="button-primary"
            disabled={!hasChanges || saving}
            onClick={handleSave}
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}
