import { useState, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { listVersions, setHwLibPin, deleteHwLibPin, getHwLibVersionDiff } from '../../api/hardware_libs'
import type { FdaJson, HwLibDiff, HwLibPin, ToolkitRead } from '../../types'

interface Props {
  taskDefId: number
  pin: HwLibPin
  fdaJson: FdaJson | null
  toolkit: ToolkitRead | null
  onClose: () => void
  onSaved: () => void
}

interface ScanRef {
  state_name: string
  action_type: string
  ref: string
  method?: string
}

/** Walk FDA entry_actions to find hardware/timer refs (all hw/timer refs in the FDA). */
function scanFdaForLibRefs(fdaJson: FdaJson): ScanRef[] {
  const refs: ScanRef[] = []

  function walkActions(stateName: string, actions: FdaJson['states'][string]['entry_actions']) {
    if (!actions) return
    for (const action of actions) {
      if (action.type === 'hardware' || action.type === 'timer') {
        // We can't resolve lib filename without module details, so include all hw/timer refs
        // and let caller filter. Here we return all refs for the state.
        if (action.ref) {
          refs.push({ state_name: stateName, action_type: action.type, ref: action.ref, method: action.method })
        }
      }
      if (action.type === 'if') {
        walkActions(stateName, action.then ?? [])
        walkActions(stateName, action.else ?? [])
      }
    }
  }

  for (const [stateName, state] of Object.entries(fdaJson.states ?? {})) {
    walkActions(stateName, state.entry_actions)
  }
  return refs
}

export default function HwLibVersionModal({ taskDefId, pin, fdaJson, onClose, onSaved }: Props) {
  const currentVersionId = pin.pinned_version_id ?? pin.active_version_id
  const [selectedVersionId, setSelectedVersionId] = useState<number | null>(currentVersionId)
  const [diff, setDiff] = useState<HwLibDiff | null>(null)
  const [diffLoading, setDiffLoading] = useState(false)

  const { data: versions = [] } = useQuery({
    queryKey: ['hw-lib-versions', pin.hardware_lib_id],
    queryFn: () => listVersions(pin.hardware_lib_id),
  })

  const setPinMutation = useMutation({
    mutationFn: (versionId: number) => setHwLibPin(taskDefId, pin.hardware_lib_id, versionId),
    onSuccess: onSaved,
  })

  const deletePinMutation = useMutation({
    mutationFn: () => deleteHwLibPin(taskDefId, pin.hardware_lib_id),
    onSuccess: onSaved,
  })

  // Fetch diff when version selection changes
  useEffect(() => {
    if (!selectedVersionId || selectedVersionId === currentVersionId || !currentVersionId) {
      setDiff(null)
      return
    }
    setDiffLoading(true)
    getHwLibVersionDiff(pin.hardware_lib_id, currentVersionId, selectedVersionId)
      .then(d => { setDiff(d); setDiffLoading(false) })
      .catch(() => { setDiff(null); setDiffLoading(false) })
  }, [selectedVersionId, currentVersionId, pin.hardware_lib_id])

  // Determine which FDA refs might be affected by removed/changed methods
  const fdaRefs = fdaJson ? scanFdaForLibRefs(fdaJson) : []

  const removedMethodNames = new Set((diff?.removed_methods ?? []).map(m => m.method_name))
  const changedMethodNames = new Set((diff?.changed_signatures ?? []).map(m => m.method_name))
  const affectedRefs = fdaRefs.filter(r => r.method && (removedMethodNames.has(r.method) || changedMethodNames.has(r.method)))

  const hasBreakageRisk = diff && (diff.removed_methods.length > 0 || diff.changed_signatures.length > 0)
  const isPinned = !!pin.pinned_version_id

  return (
    <div className="modal-overlay" style={{ alignItems: 'flex-start', paddingTop: '10vh' }}>
      <div className="modal" style={{ width: '480px' }}>
        <div className="modal-header">
          <span className="modal-title" style={{ fontFamily: "'IBM Plex Mono', monospace" }}>{pin.lib_filename}</span>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">
          {/* Current status */}
          <div style={{ marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '12px', color: 'var(--muted)' }}>
              {isPinned
                ? `Pinned to v${pin.pinned_version_number}`
                : `Using active version${pin.active_version_number != null ? ` (v${pin.active_version_number})` : ''}`}
            </span>
            {(pin.pinned_version_state ?? pin.active_version_state) && (
              <span className={`badge status-${pin.pinned_version_state ?? pin.active_version_state}`} style={{ fontSize: '10px' }}>
                {pin.pinned_version_state ?? pin.active_version_state}
              </span>
            )}
          </div>

          {/* Version picker */}
          <label style={{ fontSize: '13px', display: 'block', marginBottom: '12px' }}>
            Select version
            <select
              value={selectedVersionId ?? ''}
              onChange={e => setSelectedVersionId(Number(e.target.value))}
              style={{ display: 'block', width: '100%', marginTop: '4px' }}
            >
              {[...versions].sort((a, b) => b.version_number - a.version_number).map(v => (
                <option key={v.id} value={v.id}>
                  v{v.version_number} — {v.state} — {new Date(v.created_at).toLocaleDateString()}
                  {v.id === pin.active_version_id ? ' (active)' : ''}
                  {v.id === pin.pinned_version_id ? ' (pinned)' : ''}
                </option>
              ))}
            </select>
          </label>

          {/* Diff / warning panel */}
          {diffLoading && <p style={{ fontSize: '12px', color: 'var(--muted)' }}>Checking diff…</p>}
          {diff && !diffLoading && hasBreakageRisk && (
            <div className="badge status-error" style={{ display: 'block', marginTop: 8, padding: '8px 10px', lineHeight: 1.5 }}>
              <strong>Potential breakage in this FDA:</strong>
              {affectedRefs.length > 0 ? (
                <ul style={{ margin: '4px 0 0 0', paddingLeft: '16px' }}>
                  {affectedRefs.map((r, i) => (
                    <li key={i} style={{ fontSize: '12px' }}>
                      State "{r.state_name}": {r.ref}.{r.method}
                      {r.method && removedMethodNames.has(r.method) ? ' — removed' : ' — signature changed'}
                    </li>
                  ))}
                </ul>
              ) : (
                <p style={{ margin: '4px 0 0 0', fontSize: '12px' }}>
                  Removed/changed methods are not referenced in this FDA — safe to upgrade.
                </p>
              )}
            </div>
          )}
          {diff && !diffLoading && !hasBreakageRisk && selectedVersionId !== currentVersionId && (
            <p style={{ fontSize: '12px', color: 'var(--green)', marginTop: '8px' }}>No breaking changes detected.</p>
          )}
        </div>

        <div className="modal-actions ov-actions">
          {isPinned && (
            <button
              className="button-secondary"
              onClick={() => deletePinMutation.mutate()}
              disabled={deletePinMutation.isPending}
            >
              {deletePinMutation.isPending ? 'Reverting…' : 'Revert to active'}
            </button>
          )}
          <button className="button-secondary" onClick={onClose}>Cancel</button>
          <button
            className="button-primary"
            disabled={!selectedVersionId || setPinMutation.isPending}
            onClick={() => selectedVersionId && setPinMutation.mutate(selectedVersionId)}
          >
            {setPinMutation.isPending ? 'Saving…' : 'Set Pin'}
          </button>
        </div>
      </div>
    </div>
  )
}
