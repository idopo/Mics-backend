import { useState, useCallback } from 'react'
import { apiFetch } from '../api/client'

export interface PreflightIssue {
  module_id: number
  module_name: string
  issue: 'missing' | 'incomplete_config' | 'class_mismatch'
  detail: string
  expected_class?: string
  stored_class?: string
  config?: Record<string, unknown>
}

interface HardwareCheckModalProps {
  issues: PreflightIssue[]
  pilotId: number
  onStart: () => void
  onCancel: () => void
}

interface PendingKV {
  key: string
  value: string
}

/** Editable fields for a single hardware module issue. */
function ModuleIssueEditor({
  issue,
  pendingEdits,
  onEdit,
}: {
  issue: PreflightIssue
  pendingEdits: Record<string, unknown>
  onEdit: (moduleId: number, key: string, value: string) => void
}) {
  const [newKey, setNewKey] = useState('')
  const [newValue, setNewValue] = useState('')

  if (issue.issue === 'missing') {
    const kvPairs: PendingKV[] = Object.entries(pendingEdits).map(([k, v]) => ({
      key: k,
      value: String(v),
    }))

    return (
      <div>
        <p style={{ margin: '4px 0 8px', fontSize: '13px', color: 'var(--subtext0)' }}>
          {issue.detail}. Add the hardware parameters below:
        </p>
        {kvPairs.map(({ key }) => (
          <div key={key} style={{ display: 'flex', gap: '8px', marginBottom: '6px' }}>
            <input
              value={key}
              readOnly
              style={{ flex: '0 0 120px', padding: '4px 8px', fontSize: '13px', background: 'var(--surface2)', border: '1px solid var(--overlay0)', borderRadius: '4px', color: 'var(--text)' }}
            />
            <input
              value={String(pendingEdits[key] ?? '')}
              onChange={e => onEdit(issue.module_id, key, e.target.value)}
              placeholder="value"
              style={{ flex: 1, padding: '4px 8px', fontSize: '13px', background: 'var(--surface1)', border: '1px solid var(--overlay0)', borderRadius: '4px', color: 'var(--text)' }}
            />
          </div>
        ))}
        <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
          <input
            value={newKey}
            onChange={e => setNewKey(e.target.value)}
            placeholder="key"
            style={{ flex: '0 0 120px', padding: '4px 8px', fontSize: '13px', background: 'var(--surface1)', border: '1px solid var(--overlay0)', borderRadius: '4px', color: 'var(--text)' }}
          />
          <input
            value={newValue}
            onChange={e => setNewValue(e.target.value)}
            placeholder="value"
            style={{ flex: 1, padding: '4px 8px', fontSize: '13px', background: 'var(--surface1)', border: '1px solid var(--overlay0)', borderRadius: '4px', color: 'var(--text)' }}
          />
          <button
            className="button-secondary"
            onClick={() => {
              if (newKey.trim()) {
                onEdit(issue.module_id, newKey.trim(), newValue)
                setNewKey('')
                setNewValue('')
              }
            }}
            style={{ padding: '4px 12px', fontSize: '13px' }}
          >
            Add
          </button>
        </div>
      </div>
    )
  }

  if (issue.issue === 'incomplete_config') {
    const baseConfig = issue.config ?? {}
    const editableKeys = Object.keys(baseConfig).filter(k => k !== 'class_name')

    return (
      <div>
        <p style={{ margin: '4px 0 8px', fontSize: '13px', color: 'var(--subtext0)' }}>
          {issue.detail}. Fill in the missing values:
        </p>
        {editableKeys.map(key => (
          <div key={key} style={{ display: 'flex', gap: '8px', marginBottom: '6px', alignItems: 'center' }}>
            <span style={{ flex: '0 0 120px', fontSize: '13px', color: 'var(--text)' }}>{key}</span>
            <input
              value={String(pendingEdits[key] ?? baseConfig[key] ?? '')}
              onChange={e => onEdit(issue.module_id, key, e.target.value)}
              style={{ flex: 1, padding: '4px 8px', fontSize: '13px', background: 'var(--surface1)', border: '1px solid var(--overlay0)', borderRadius: '4px', color: 'var(--text)' }}
            />
          </div>
        ))}
      </div>
    )
  }

  if (issue.issue === 'class_mismatch') {
    return (
      <div>
        <p style={{ margin: '4px 0 4px', fontSize: '13px', color: 'var(--subtext0)' }}>
          {issue.detail}
        </p>
        <p style={{ margin: '0 0 8px', fontSize: '12px', color: 'var(--yellow)' }}>
          Expected: <strong>{issue.expected_class}</strong>
        </p>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span style={{ flex: '0 0 80px', fontSize: '13px', color: 'var(--text)' }}>class_name</span>
          <input
            value={String(pendingEdits['class_name'] ?? issue.stored_class ?? '')}
            onChange={e => onEdit(issue.module_id, 'class_name', e.target.value)}
            style={{ flex: 1, padding: '4px 8px', fontSize: '13px', background: 'var(--surface1)', border: '1px solid var(--overlay0)', borderRadius: '4px', color: 'var(--text)' }}
          />
        </div>
      </div>
    )
  }

  return null
}

/** Modal for reviewing and fixing hardware config issues before starting a session. */
export default function HardwareCheckModal({ issues, pilotId, onStart, onCancel }: HardwareCheckModalProps) {
  // pendingEdits: moduleId → {key: value} dict of pending changes
  const [pendingEdits, setPendingEdits] = useState<Record<number, Record<string, unknown>>>(() => {
    const init: Record<number, Record<string, unknown>> = {}
    for (const issue of issues) {
      if (issue.issue === 'class_mismatch') {
        init[issue.module_id] = { ...issue.config }
      } else if (issue.issue === 'incomplete_config') {
        init[issue.module_id] = { ...(issue.config ?? {}) }
      } else {
        init[issue.module_id] = {}
      }
    }
    return init
  })
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')

  const handleEdit = useCallback((moduleId: number, key: string, value: string) => {
    setPendingEdits(prev => ({
      ...prev,
      [moduleId]: { ...(prev[moduleId] ?? {}), [key]: value },
    }))
  }, [])

  const handleStart = async () => {
    setSaving(true)
    setSaveError('')
    try {
      for (const issue of issues) {
        const edits = pendingEdits[issue.module_id] ?? {}
        // Build the config to save: merge edits onto existing config (minus class_name, added by API)
        const baseConfig = issue.config ?? {}
        const configToSave: Record<string, unknown> = { ...baseConfig, ...edits }
        // Remove class_name — the PUT endpoint injects it from the DB record
        delete configToSave['class_name']

        await apiFetch(`/api/pilots/${pilotId}/hardware-config/${issue.module_id}`, {
          method: 'PUT',
          body: JSON.stringify({ config: configToSave }),
        })
      }
      onStart()
    } catch (e: unknown) {
      setSaveError(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-overlay" style={{ alignItems: 'flex-start', paddingTop: '10vh' }}>
      <div className="modal" style={{ width: '560px', maxWidth: '90vw' }}>
        <div className="modal-header">
          <span className="modal-title">Hardware Configuration Required</span>
          <button className="modal-close" onClick={onCancel} disabled={saving}>×</button>
        </div>
        <div className="modal-body" style={{ maxHeight: '60vh', overflowY: 'auto', padding: '16px 20px' }}>
          <p style={{ margin: '0 0 16px', fontSize: '13px', color: 'var(--subtext0)' }}>
            The following hardware modules need configuration before starting:
          </p>
          {issues.map(issue => (
            <div
              key={issue.module_id}
              style={{
                marginBottom: '20px',
                padding: '12px 14px',
                background: 'var(--surface1)',
                borderRadius: '8px',
                border: '1px solid var(--overlay0)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                <strong style={{ fontSize: '14px' }}>{issue.module_name}</strong>
                <span
                  className={`badge status-${issue.issue === 'missing' ? 'error' : 'warning'}`}
                  style={{ fontSize: '11px' }}
                >
                  {issue.issue.replace('_', ' ')}
                </span>
              </div>
              <ModuleIssueEditor
                issue={issue}
                pendingEdits={pendingEdits[issue.module_id] ?? {}}
                onEdit={handleEdit}
              />
            </div>
          ))}
          {saveError && (
            <p style={{ color: 'var(--red)', fontSize: '13px', marginTop: '8px' }}>{saveError}</p>
          )}
        </div>
        <div className="modal-actions ov-actions">
          <button className="button-secondary" onClick={onCancel} disabled={saving}>
            Cancel
          </button>
          <button className="button-primary" onClick={handleStart} disabled={saving}>
            {saving ? 'Saving...' : 'Save & Start'}
          </button>
        </div>
      </div>
    </div>
  )
}
