import React, { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  listHardwareModules,
  listPilotHardwareConfig,
  upsertPilotHardwareConfig,
  deletePilotHardwareConfig,
  getHardwareModuleMethods,
} from '../../api/hardware_modules'
import { apiFetch } from '../../api/client'
import DetectorChannelFields from './DetectorChannelFields'
import type { PilotHardwareConfigRow, HardwareModule, AstMethodArg } from '../../types'

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

function syncNameInJson(json: string, name: string): string {
  try {
    const parsed = JSON.parse(json) as Record<string, unknown>
    parsed['name'] = name
    return JSON.stringify(parsed, null, 2)
  } catch {
    return json
  }
}

function ParamsSummary({ config }: { config: Record<string, unknown> }): JSX.Element {
  const skip = new Set(['type', 'name', 'group', 'class_name'])
  const entries = Object.entries(config).filter(([k]) => !skip.has(k))
  const shown = entries.slice(0, 4)
  return (
    <span style={{ fontSize: '0.82rem', color: 'var(--subtext0)' }}>
      {shown.map(([k, v]) => (
        <span key={k} style={{ marginRight: '0.6rem' }}>
          <strong>{k}</strong>: {String(v)}
        </span>
      ))}
      {entries.length > 4 && (
        <span style={{ color: 'var(--overlay1)' }}>+{entries.length - 4} more</span>
      )}
    </span>
  )
}

export default function PilotHardwareConfig(): JSX.Element {
  const { pilotName } = useParams<{ pilotName: string }>()
  const qc = useQueryClient()

  const { data: pilotRecord } = useQuery({
    queryKey: ['pilot-by-name', pilotName],
    queryFn: () => apiFetch<{ id: number; name: string }>(`/api/pilots/by-name/${pilotName}`),
    enabled: !!pilotName,
  })
  const pid = pilotRecord?.id ?? 0

  const [editingRow, setEditingRow] = useState<string | null>(null)
  const [editName, setEditName] = useState('')
  const [editJson, setEditJson] = useState('')
  const [editError, setEditError] = useState('')
  const [editSaving, setEditSaving] = useState(false)

  const [addName, setAddName] = useState('')
  const [addJson, setAddJson] = useState('{}')
  const [addError, setAddError] = useState('')
  const [addSaving, setAddSaving] = useState(false)
  const [selectedModuleId, setSelectedModuleId] = useState<string>('')
  const [templateLoading, setTemplateLoading] = useState(false)

  const { data: configs = [], isLoading: loadingConfigs } = useQuery({
    queryKey: ['pilot-hardware-config', pid],
    queryFn: () => listPilotHardwareConfig(pid),
    enabled: pid > 0,
  })

  const { data: modules = [] } = useQuery({
    queryKey: ['hardware-modules'],
    queryFn: listHardwareModules,
  })

  // Resolved by name, not by id — a pilot_hardware_config row carries no module_id (it's
  // free-form, see Phase 17). Both entry points share the same query key so picking a module in
  // the add flow does not trigger a second network fetch for the edit flow's own resolution.
  const editingModule = modules.find(m => m.name === editName)
  const { data: editModuleMethods } = useQuery({
    queryKey: ['hardware-module-methods', editingModule?.id],
    queryFn: () => getHardwareModuleMethods(editingModule!.id),
    enabled: editingRow !== null && !!editingModule,
  })
  const editIsDetector = editModuleMethods?.is_detector ?? false

  const addModule = modules.find(m => String(m.id) === selectedModuleId)
  const { data: addModuleMethods } = useQuery({
    queryKey: ['hardware-module-methods', addModule?.id],
    queryFn: () => getHardwareModuleMethods(addModule!.id),
    enabled: !!addModule,
  })
  const addIsDetector = addModuleMethods?.is_detector ?? false

  const deleteMutation = useMutation({
    mutationFn: (name: string) => deletePilotHardwareConfig(pid, name),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['pilot-hardware-config', pid] }),
  })

  function startEdit(row: PilotHardwareConfigRow): void {
    setEditingRow(row.name)
    setEditName(row.name)
    setEditJson(JSON.stringify(row.config, null, 2))
    setEditError('')
  }

  function cancelEdit(): void {
    setEditingRow(null)
    setEditName('')
    setEditJson('')
    setEditError('')
  }

  function handleEditNameChange(name: string): void {
    setEditName(name)
    setEditJson(prev => syncNameInJson(prev, name))
  }

  async function saveEdit(): Promise<void> {
    const trimmed = editName.trim()
    if (!trimmed) { setEditError('Name is required'); return }
    let parsed: Record<string, unknown>
    try { parsed = JSON.parse(editJson) } catch { setEditError('Invalid JSON'); return }

    setEditSaving(true)
    try {
      await upsertPilotHardwareConfig(pid, trimmed, parsed)
      if (editingRow && trimmed !== editingRow) {
        await deletePilotHardwareConfig(pid, editingRow)
      }
      qc.invalidateQueries({ queryKey: ['pilot-hardware-config', pid] })
      cancelEdit()
    } catch (e: unknown) {
      setEditError(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setEditSaving(false)
    }
  }

  async function handleModulePick(moduleId: string): Promise<void> {
    setSelectedModuleId(moduleId)
    if (!moduleId) { setAddJson('{}'); return }
    const mod = modules.find(m => String(m.id) === moduleId)
    if (!mod) return
    setTemplateLoading(true)
    try {
      const methods = await qc.fetchQuery({
        queryKey: ['hardware-module-methods', mod.id],
        queryFn: () => getHardwareModuleMethods(mod.id),
      })
      const initArgs = methods.methods.find(m => m.name === '__init__')?.args ?? []
      setAddJson(buildTemplate(mod, initArgs, addName))
    } catch {
      setAddJson(buildTemplate(mod, [], addName))
    } finally {
      setTemplateLoading(false)
    }
  }

  function handleAddNameChange(name: string): void {
    setAddName(name)
    setAddJson(prev => syncNameInJson(prev, name))
  }

  async function submitAdd(): Promise<void> {
    const trimmed = addName.trim()
    if (!trimmed) { setAddError('Name is required'); return }
    let parsed: Record<string, unknown>
    try { parsed = JSON.parse(addJson) } catch { setAddError('Invalid JSON'); return }

    setAddSaving(true)
    try {
      await upsertPilotHardwareConfig(pid, trimmed, parsed)
      qc.invalidateQueries({ queryKey: ['pilot-hardware-config', pid] })
      setAddName('')
      setAddJson('{}')
      setSelectedModuleId('')
      setAddError('')
    } catch (e: unknown) {
      setAddError(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setAddSaving(false)
    }
  }

  if (!pid) return <div className="container"><p>Loading…</p></div>

  return (
    <div className="container">
      <h2 style={{ marginBottom: '1rem' }}>Hardware Config — {pilotName}</h2>

      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              <th style={{ textAlign: 'left', padding: '0.5rem', width: '180px' }}>Name</th>
              <th style={{ textAlign: 'left', padding: '0.5rem', width: '170px' }}>Type</th>
              <th style={{ textAlign: 'left', padding: '0.5rem' }}>Params</th>
              <th style={{ textAlign: 'right', padding: '0.5rem', width: '130px' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loadingConfigs && (
              <tr><td colSpan={4} style={{ padding: '1rem', color: 'var(--subtext0)' }}>Loading…</td></tr>
            )}
            {!loadingConfigs && configs.length === 0 && (
              <tr><td colSpan={4} style={{ padding: '1rem', color: 'var(--subtext0)' }}>No entries yet — use Add Entry below.</td></tr>
            )}
            {configs.map(row => (
              <React.Fragment key={row.name}>
                <tr style={{ borderBottom: editingRow === row.name ? 'none' : '1px solid var(--border)' }}>
                  <td style={{ padding: '0.6rem 0.5rem', verticalAlign: 'top' }}>
                    <strong>{row.name}</strong>
                  </td>
                  <td style={{ padding: '0.6rem 0.5rem', verticalAlign: 'top' }}>
                    {(row.config.type ?? row.config.class_name) ? (
                      <span className="badge status-running">
                        {String(row.config.type ?? row.config.class_name)}
                      </span>
                    ) : (
                      <span style={{ color: 'var(--overlay1)', fontSize: '0.8rem' }}>—</span>
                    )}
                  </td>
                  <td style={{ padding: '0.6rem 0.5rem', verticalAlign: 'top' }}>
                    {editingRow !== row.name && <ParamsSummary config={row.config} />}
                  </td>
                  <td style={{ padding: '0.6rem 0.5rem', textAlign: 'right', verticalAlign: 'top' }}>
                    {editingRow === row.name ? (
                      <div style={{ display: 'flex', gap: '0.4rem', justifyContent: 'flex-end' }}>
                        <button className="button-primary" onClick={saveEdit} disabled={editSaving}>Save</button>
                        <button className="button-secondary" onClick={cancelEdit}>Cancel</button>
                      </div>
                    ) : (
                      <div style={{ display: 'flex', gap: '0.4rem', justifyContent: 'flex-end' }}>
                        <button className="button-secondary" onClick={() => startEdit(row)}>Edit</button>
                        <button
                          className="button-danger"
                          onClick={() => deleteMutation.mutate(row.name)}
                          disabled={deleteMutation.isPending}
                        >Delete</button>
                      </div>
                    )}
                  </td>
                </tr>
                {editingRow === row.name && (
                  <tr style={{ borderBottom: '1px solid var(--border)', background: 'var(--surface1)' }}>
                    <td colSpan={4} style={{ padding: '0.75rem' }}>
                      <div style={{ marginBottom: '0.5rem' }}>
                        <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--subtext0)', marginBottom: '2px' }}>
                          Name
                        </label>
                        <input
                          type="text"
                          value={editName}
                          onChange={e => handleEditNameChange(e.target.value)}
                          style={{ padding: '5px 8px', fontSize: '0.875rem', width: '220px' }}
                        />
                        {editName.trim() && editName.trim() !== editingRow && (
                          <span style={{ marginLeft: '0.5rem', fontSize: '0.8rem', color: 'var(--yellow)' }}>
                            rename: {editingRow} → {editName.trim()}
                          </span>
                        )}
                      </div>
                      {editIsDetector && (
                        <DetectorChannelFields json={editJson} onChange={setEditJson} />
                      )}
                      <textarea
                        rows={8}
                        value={editJson}
                        onChange={e => setEditJson(e.target.value)}
                        style={TEXTAREA_STYLE}
                      />
                      {editError && (
                        <span className="badge status-error" style={{ marginTop: '4px', display: 'inline-block' }}>
                          {editError}
                        </span>
                      )}
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0, marginBottom: '0.75rem', fontSize: '1rem' }}>Add Entry</h3>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '0.75rem', alignItems: 'flex-end' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--subtext0)', marginBottom: '2px' }}>Name</label>
            <input
              type="text"
              value={addName}
              onChange={e => handleAddNameChange(e.target.value)}
              placeholder="e.g. LED1"
              style={{ padding: '5px 8px', fontSize: '0.875rem', width: '180px' }}
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
        {addIsDetector && (
          <DetectorChannelFields json={addJson} onChange={setAddJson} />
        )}
        <div style={{ marginBottom: '0.75rem' }}>
          <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--subtext0)', marginBottom: '2px' }}>Config JSON</label>
          <textarea
            rows={8}
            value={addJson}
            onChange={e => setAddJson(e.target.value)}
            style={TEXTAREA_STYLE}
          />
        </div>
        {addError && (
          <p style={{ color: 'var(--red)', fontSize: '0.85rem', margin: '0 0 0.5rem' }}>{addError}</p>
        )}
        <button className="button-primary" onClick={submitAdd} disabled={addSaving || templateLoading}>
          Add
        </button>
      </div>
    </div>
  )
}
