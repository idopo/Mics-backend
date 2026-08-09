import { useState, useCallback, useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../api/client'
import { listHardwareModules, getHardwareModuleMethods } from '../api/hardware_modules'
import type { HardwareModule, AstMethodArg } from '../types'
import ComputeIssueDetail from './ComputeIssueDetail'

/** `device_held` only — the pilot currently holding the lease (api/device_lease.py's
 * `device_held_issue` shape, pinned in 18-08-SUMMARY.md). */
export interface DeviceLeaseHolder {
  host: string
  pilot_id: number
  pilot_name: string | null
  session_id: number | null
  run_id: number | null
  subject_key: string | null
  acquired_at: string
}

// Issue kinds and their shape-specific fields are authored in
// api/routers/toolkit_dispatch.py::PREFLIGHT_ISSUE_KINDS — mirror it, do not invent fields.
export interface PreflightIssue {
  module_id: number | null
  module_name: string
  issue: 'missing' | 'incomplete_config' | 'class_mismatch' | 'fda_ref_unresolved' | 'view_key_unresolved'
       | 'variable_never_written' | 'lib_version_unresolved' | 'compute_lib_import_failed'
       | 'state_wait_unsatisfiable' | 'device_held' | 'extlink_config_invalid'
  detail: string
  expected_class?: string
  stored_class?: string
  config?: Record<string, unknown>
  existing_configs?: Array<{ name: string; config: Record<string, unknown> }>
  /** view_key_unresolved only — where in the FDA JSON the offending operand/key_template lives. */
  location?: string
  /** view_key_unresolved only — the offending literal key, or the key `detector` would resolve to. */
  key?: string
  /** view_key_unresolved only — this pilot's real view keys, scoped per the issue (module or pilot-wide). */
  available_keys?: string[]
  /** view_key_unresolved, detector-channel shape only (DVK-11) — the stored operand, a channel not a key. */
  detector?: { ref: string; channel: number }
  /** view_key_unresolved, detector-channel shape only — this pilot's real channels for `detector.ref`. */
  available_channels?: number[]
  /** variable_never_written only — the variable name nothing writes. */
  variable?: string
  /** lib_version_unresolved / compute_lib_import_failed only — the lib source filename. */
  lib_filename?: string
  /** lib_version_unresolved only — why no version could be resolved (e.g. "none"). */
  reason?: string
  /** compute_lib_import_failed only — the import error message. */
  error?: string
  /** device_held only — the normalized host another pilot's lease is holding. */
  host?: string
  /** device_held only — who holds the lease. */
  holder?: DeviceLeaseHolder
}

/**
 * None of these names a `pilot_hardware_config` row — a variable-analysis result, a
 * lib-resolution failure, a held device lease, and an invalid extlink config field all live
 * elsewhere (task definition, Hardware Libraries page, the lease table, the pilot hardware
 * config page respectively). Shared by `handleStart` and the `pendingEdits` initialiser so a
 * PUT is never issued for them — doing so would overwrite a good config with `{}` or hit an
 * empty path segment (the bug plan 25-05 fixed for `view_key_unresolved`; `device_held` names a
 * lease, not a config row, and `extlink_config_invalid` requires an edit on the hardware-config
 * page, not this modal — same trap, same fix).
 */
const NON_CONFIG_ISSUES = new Set<PreflightIssue['issue']>([
  'view_key_unresolved',
  'variable_never_written',
  'lib_version_unresolved',
  'compute_lib_import_failed',
  'state_wait_unsatisfiable',
  'device_held',
  'extlink_config_invalid',
])

interface HardwareCheckModalProps {
  issues: PreflightIssue[]
  pilotId: number
  onStart: () => void
  onCancel: () => void
}

const INPUT_STYLE: React.CSSProperties = {
  flex: 1,
  padding: '4px 8px',
  fontSize: '13px',
  background: 'var(--surface1)',
  border: '1px solid var(--overlay0)',
  borderRadius: '4px',
  color: 'var(--text)',
}

const TEXTAREA_STYLE: React.CSSProperties = {
  width: '100%',
  fontFamily: 'monospace',
  fontSize: 13,
  resize: 'vertical',
  boxSizing: 'border-box',
}

function libTypePrefix(filename: string | null): string {
  return filename ? filename.replace(/\.py$/i, '') : ''
}

function parseDefault(s: string): unknown {
  if (s === 'True') return true
  if (s === 'False') return false
  if (s === 'None') return null
  const n = Number(s)
  if (s.trim() !== '' && !isNaN(n)) return n
  if ((s.startsWith("'") && s.endsWith("'")) || (s.startsWith('"') && s.endsWith('"'))) {
    return s.slice(1, -1)
  }
  return s
}

function buildTemplate(mod: HardwareModule, initArgs: AstMethodArg[], name: string): string {
  const prefix = libTypePrefix(mod.lib_filename)
  const type = prefix ? `${prefix}.${mod.class_name}` : mod.class_name
  const obj: Record<string, unknown> = { type, name, group: '' }
  for (const arg of initArgs) {
    if (arg.name === 'self') continue
    obj[arg.name] = arg.default !== undefined ? parseDefault(arg.default) : null
  }
  return JSON.stringify(obj, null, 2)
}

/**
 * Editor for missing / fda_ref_unresolved issues.
 * Two modes: copy an existing config (dropdown → confirmation) or add manually (Name + Class + JSON textarea).
 */
function MissingModuleEditor({
  issue,
  onReplaceEdits,
}: {
  issue: PreflightIssue
  onReplaceEdits: (moduleName: string, config: Record<string, unknown>) => void
}): JSX.Element {
  const [copySource, setCopySource] = useState('')
  const [addJson, setAddJson] = useState('{}')
  const [jsonError, setJsonError] = useState('')
  const [selectedModuleId, setSelectedModuleId] = useState('')
  const [templateLoading, setTemplateLoading] = useState(false)

  const { data: modules = [] } = useQuery<HardwareModule[]>({
    queryKey: ['hardware-modules'],
    queryFn: listHardwareModules,
  })

  const existingConfigs = issue.existing_configs ?? []
  const autoSeeded = useRef(false)

  useEffect(() => {
    if (autoSeeded.current || !issue.expected_class || modules.length === 0) return
    const mod = modules.find(m => m.class_name === issue.expected_class)
    if (!mod) return
    autoSeeded.current = true
    void handleModulePick(String(mod.id))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modules])

  function handleCopyPick(name: string): void {
    setCopySource(name)
    if (!name) return
    const src = existingConfigs.find(c => c.name === name)
    if (src) onReplaceEdits(issue.module_name, { ...src.config, name: issue.module_name })
  }

  async function handleModulePick(moduleId: string): Promise<void> {
    setSelectedModuleId(moduleId)
    if (!moduleId) { setAddJson('{}'); return }
    const mod = modules.find(m => String(m.id) === moduleId)
    if (!mod) return
    setTemplateLoading(true)
    try {
      const methods = await getHardwareModuleMethods(mod.id)
      const initArgs = methods.methods.find(m => m.name === '__init__')?.args ?? []
      const json = buildTemplate(mod, initArgs, issue.module_name)
      setAddJson(json)
      setJsonError('')
      onReplaceEdits(issue.module_name, JSON.parse(json) as Record<string, unknown>)
    } finally {
      setTemplateLoading(false)
    }
  }

  function handleJsonChange(value: string): void {
    setAddJson(value)
    try {
      onReplaceEdits(issue.module_name, JSON.parse(value) as Record<string, unknown>)
      setJsonError('')
    } catch {
      setJsonError('Invalid JSON')
    }
  }

  if (copySource) {
    return (
      <div>
        <p style={{ margin: '4px 0 10px', fontSize: '13px', color: 'var(--subtext0)' }}>{issue.detail}</p>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 10px', background: 'var(--surface2)', borderRadius: '4px', border: '1px solid var(--overlay0)' }}>
          <span style={{ fontSize: '13px', flex: 1 }}>
            Copy <strong>{copySource}</strong> → rename to <strong>{issue.module_name}</strong>
          </span>
          <button
            className="button-secondary"
            style={{ padding: '2px 10px', fontSize: '12px' }}
            onClick={() => setCopySource('')}
          >
            Clear
          </button>
        </div>
      </div>
    )
  }

  return (
    <div>
      <p style={{ margin: '4px 0 10px', fontSize: '13px', color: 'var(--subtext0)' }}>{issue.detail}</p>
      {existingConfigs.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
          <span style={{ fontSize: '12px', color: 'var(--subtext0)', whiteSpace: 'nowrap' }}>Copy from:</span>
          <select
            style={{ flex: 1, padding: '4px 8px', fontSize: '13px', background: 'var(--surface1)', border: '1px solid var(--overlay0)', borderRadius: '4px', color: 'var(--text)' }}
            value=""
            onChange={e => handleCopyPick(e.target.value)}
          >
            <option value="">— pick existing config —</option>
            {existingConfigs.map(c => (
              <option key={c.name} value={c.name}>{c.name}</option>
            ))}
          </select>
        </div>
      )}
      <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '0.75rem', alignItems: 'flex-end' }}>
        <div>
          <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--subtext0)', marginBottom: '2px' }}>Name</label>
          <input
            type="text"
            value={issue.module_name}
            readOnly
            style={{ padding: '5px 8px', fontSize: '0.875rem', width: '160px', background: 'var(--surface2)', border: '1px solid var(--overlay0)', borderRadius: '4px', color: 'var(--text)' }}
          />
        </div>
        <div>
          <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--subtext0)', marginBottom: '2px' }}>Class</label>
          <select
            value={selectedModuleId}
            onChange={e => handleModulePick(e.target.value)}
            style={{ padding: '5px 8px', fontSize: '0.875rem' }}
            disabled={templateLoading}
          >
            <option value="">— select class —</option>
            {modules.map(m => (
              <option key={m.id} value={String(m.id)}>
                {libTypePrefix(m.lib_filename)}.{m.class_name}
              </option>
            ))}
          </select>
          {templateLoading && (
            <span style={{ marginLeft: '0.5rem', fontSize: '0.8rem', color: 'var(--subtext0)' }}>Loading…</span>
          )}
        </div>
      </div>
      <div>
        <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--subtext0)', marginBottom: '2px' }}>Config JSON</label>
        <textarea
          rows={6}
          value={addJson}
          onChange={e => handleJsonChange(e.target.value)}
          style={TEXTAREA_STYLE}
        />
        {jsonError && <span style={{ fontSize: '12px', color: 'var(--red)' }}>{jsonError}</span>}
      </div>
    </div>
  )
}

/**
 * Read-only detail for a `view_key_unresolved` issue (DVK-06/DVK-11) — both shapes.
 * There is nothing to edit here: the fix is either in the task definition (change the
 * channel/key) or in the pilot's hardware config (`first_channel`/`num_detectors`), neither of
 * which belongs in this modal.
 */
function ViewKeyIssueDetail({ issue }: { issue: PreflightIssue }): JSX.Element {
  const availableKeys = issue.available_keys ?? []
  return (
    <div>
      {issue.detector ? (
        <>
          <p style={{ margin: '0 0 4px', fontSize: '14px', fontFamily: 'monospace' }}>
            {issue.detector.ref} — channel {issue.detector.channel}
          </p>
          {issue.key && (
            <p style={{ margin: '0 0 8px', fontSize: '12px', fontFamily: 'monospace', color: 'var(--subtext0)' }}>
              would resolve to {issue.key}
            </p>
          )}
        </>
      ) : (
        issue.key && (
          <p style={{ margin: '0 0 8px', fontSize: '14px', fontFamily: 'monospace' }}>{issue.key}</p>
        )
      )}
      <p style={{ margin: '4px 0 8px', fontSize: '13px', color: 'var(--subtext0)' }}>{issue.detail}</p>
      {issue.location && (
        <p style={{ margin: '0 0 8px', fontSize: '12px', fontFamily: 'monospace', color: 'var(--overlay1)' }}>
          {issue.location}
        </p>
      )}
      {availableKeys.length > 0 ? (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '8px' }}>
          {availableKeys.map(k => (
            <span key={k} className="meta-pill" style={{ fontSize: '12px' }}>{k}</span>
          ))}
        </div>
      ) : (
        <p style={{ margin: '0 0 8px', fontSize: '12px', color: 'var(--subtext0)' }}>
          this pilot has no detector channels configured
        </p>
      )}
      <p style={{ margin: 0, fontSize: '12px', color: 'var(--subtext0)' }}>
        {issue.detector
          ? "Pick a channel this pilot has in the task editor, or set this pilot's first_channel / num_detectors on the hardware-config page."
          : "Fix the key in the task editor, or set this pilot's first_channel / num_detectors on the hardware-config page."}
      </p>
    </div>
  )
}

/** Renders `acquired_at` as "Xm"/"Xh Ym" elapsed, or the raw timestamp if unparsable. */
function formatHeldSince(acquiredAt: string): string {
  const acquiredMs = Date.parse(acquiredAt)
  if (isNaN(acquiredMs)) return acquiredAt
  const elapsedMin = Math.max(0, Math.round((Date.now() - acquiredMs) / 60000))
  if (elapsedMin < 60) return `${elapsedMin}m`
  return `${Math.floor(elapsedMin / 60)}h ${elapsedMin % 60}m`
}

/**
 * Read-only detail for a `device_held` issue (EXTLINK-16/17), modelled on `ViewKeyIssueDetail`.
 * Nothing to edit here: the fix is either waiting for the holding run to finish or a manual
 * force-release (`DELETE /api/device-leases/{host}`), neither of which is a config PUT. Leads
 * with the host, then names the holding pilot/subject/run and how long it has been held — the
 * whole justification for the issue naming the holder is "that run on pilot 2 is still going",
 * actionable without a terminal.
 */
function DeviceHeldIssueDetail({ issue }: { issue: PreflightIssue }): JSX.Element {
  const holder = issue.holder
  const host = issue.host ?? holder?.host
  return (
    <div>
      {host && (
        <p style={{ margin: '0 0 4px', fontSize: '14px', fontFamily: 'monospace' }}>{host}</p>
      )}
      <p style={{ margin: '4px 0 8px', fontSize: '13px', color: 'var(--subtext0)' }}>
        {holder
          ? `Held by pilot '${holder.pilot_name ?? 'unknown'}' (subject ${holder.subject_key ?? '?'}, run ${holder.run_id ?? '?'}), for ${formatHeldSince(holder.acquired_at)}.`
          : issue.detail}
      </p>
    </div>
  )
}

function ModuleIssueEditor({
  issue,
  pendingEdits,
  onEdit,
  onReplaceEdits,
}: {
  issue: PreflightIssue
  pendingEdits: Record<string, unknown>
  onEdit: (moduleName: string, key: string, value: string) => void
  onReplaceEdits: (moduleName: string, config: Record<string, unknown>) => void
}): JSX.Element | null {
  if (issue.issue === 'view_key_unresolved') {
    return <ViewKeyIssueDetail issue={issue} />
  }

  if (issue.issue === 'device_held') {
    return <DeviceHeldIssueDetail issue={issue} />
  }

  if (issue.issue === 'extlink_config_invalid') {
    return (
      <p style={{ margin: 0, fontSize: '13px', color: 'var(--subtext0)' }}>{issue.detail}</p>
    )
  }

  if (
    issue.issue === 'variable_never_written' ||
    issue.issue === 'lib_version_unresolved' ||
    issue.issue === 'compute_lib_import_failed' ||
    issue.issue === 'state_wait_unsatisfiable'
  ) {
    return <ComputeIssueDetail issue={issue} />
  }

  if (issue.issue === 'missing' || issue.issue === 'fda_ref_unresolved') {
    return <MissingModuleEditor issue={issue} onReplaceEdits={onReplaceEdits} />
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
              onChange={e => onEdit(issue.module_name, key, e.target.value)}
              style={INPUT_STYLE}
            />
          </div>
        ))}
      </div>
    )
  }

  if (issue.issue === 'class_mismatch') {
    return (
      <div>
        <p style={{ margin: '4px 0 4px', fontSize: '13px', color: 'var(--subtext0)' }}>{issue.detail}</p>
        <p style={{ margin: '0 0 8px', fontSize: '12px', color: 'var(--yellow)' }}>
          Expected: <strong>{issue.expected_class}</strong>
        </p>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span style={{ flex: '0 0 80px', fontSize: '13px', color: 'var(--text)' }}>class_name</span>
          <input
            value={String(pendingEdits['class_name'] ?? issue.stored_class ?? '')}
            onChange={e => onEdit(issue.module_name, 'class_name', e.target.value)}
            style={INPUT_STYLE}
          />
        </div>
      </div>
    )
  }

  return null
}

/** Modal for reviewing and fixing hardware config issues before starting a session. */
export default function HardwareCheckModal({ issues, pilotId, onStart, onCancel }: HardwareCheckModalProps): JSX.Element {
  const [pendingEdits, setPendingEdits] = useState<Record<string, Record<string, unknown>>>(() => {
    const init: Record<string, Record<string, unknown>> = {}
    for (const issue of issues) {
      // Names no config row to write — see NON_CONFIG_ISSUES.
      if (NON_CONFIG_ISSUES.has(issue.issue)) continue
      if (issue.issue === 'class_mismatch') {
        init[issue.module_name] = { ...issue.config }
      } else if (issue.issue === 'incomplete_config') {
        init[issue.module_name] = { ...(issue.config ?? {}) }
      } else {
        init[issue.module_name] = {}
      }
    }
    return init
  })
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')

  const handleEdit = useCallback((moduleName: string, key: string, value: string) => {
    setPendingEdits(prev => ({
      ...prev,
      [moduleName]: { ...(prev[moduleName] ?? {}), [key]: value },
    }))
  }, [])

  const handleReplaceEdits = useCallback((moduleName: string, config: Record<string, unknown>) => {
    setPendingEdits(prev => ({ ...prev, [moduleName]: config }))
  }, [])

  const handleStart = async (): Promise<void> => {
    setSaving(true)
    setSaveError('')
    try {
      for (const issue of issues) {
        // Names no config row to write — see NON_CONFIG_ISSUES.
        if (NON_CONFIG_ISSUES.has(issue.issue)) continue
        const edits = pendingEdits[issue.module_name] ?? {}
        const baseConfig = issue.config ?? {}
        const configToSave: Record<string, unknown> =
          issue.issue === 'missing' || issue.issue === 'fda_ref_unresolved'
            ? edits
            : { ...baseConfig, ...edits }

        await apiFetch(`/api/pilots/${pilotId}/hardware-config/${encodeURIComponent(issue.module_name)}`, {
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
          {issues.map((issue, i) => (
            <div
              key={`${issue.issue}:${issue.module_name}:${issue.location ?? i}`}
              style={{
                marginBottom: '20px',
                padding: '12px 14px',
                background: 'var(--surface1)',
                borderRadius: '8px',
                border: '1px solid var(--overlay0)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                <strong style={{ fontSize: '14px' }}>{issue.module_name || 'View key'}</strong>
                <span
                  className={`badge status-${issue.issue === 'missing' || issue.issue === 'fda_ref_unresolved' ? 'error' : 'warning'}`}
                  style={{ fontSize: '11px' }}
                >
                  {issue.issue.replace(/_/g, ' ')}
                </span>
              </div>
              <ModuleIssueEditor
                issue={issue}
                pendingEdits={pendingEdits[issue.module_name] ?? {}}
                onEdit={handleEdit}
                onReplaceEdits={handleReplaceEdits}
              />
            </div>
          ))}
          {saveError && (
            <p style={{ color: 'var(--red)', fontSize: '13px', marginTop: '8px' }}>{saveError}</p>
          )}
        </div>
        <div className="modal-actions ov-actions">
          <button className="button-secondary" onClick={onCancel} disabled={saving}>Cancel</button>
          <button className="button-primary" onClick={handleStart} disabled={saving}>
            {saving ? 'Saving...' : 'Save & Start'}
          </button>
        </div>
      </div>
    </div>
  )
}
