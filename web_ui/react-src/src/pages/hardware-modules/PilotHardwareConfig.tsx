import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  listHardwareModules,
  listPilotHardwareConfig,
  upsertPilotHardwareConfig,
  deletePilotHardwareConfig,
} from '../../api/hardware_modules'
import { apiFetch } from '../../api/client'
import type { PilotHardwareConfigRow, HardwareModule } from '../../types'

const TEXTAREA_STYLE: React.CSSProperties = {
  width: '100%',
  fontFamily: 'monospace',
  fontSize: 13,
  resize: 'vertical',
  boxSizing: 'border-box',
}

function ParamsSummary({ config }: { config: Record<string, unknown> }) {
  const entries = Object.entries(config).filter(([k]) => k !== 'class_name')
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

function buildDefaultConfig(module: HardwareModule): string {
  return JSON.stringify({ class_name: module.class_name }, null, 2)
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

  // Table edit state: row name → raw JSON string being edited
  const [editingRow, setEditingRow] = useState<string | null>(null)
  const [editJson, setEditJson] = useState('')
  const [editError, setEditError] = useState('')

  // Add Entry form state
  const [addName, setAddName] = useState('')
  const [addJson, setAddJson] = useState('{}')
  const [addError, setAddError] = useState('')
  const [selectedModuleId, setSelectedModuleId] = useState<string>('')

  const { data: configs = [], isLoading: loadingConfigs } = useQuery({
    queryKey: ['pilot-hardware-config', pid],
    queryFn: () => listPilotHardwareConfig(pid),
    enabled: pid > 0,
  })

  const { data: modules = [] } = useQuery({
    queryKey: ['hardware-modules'],
    queryFn: listHardwareModules,
  })

  const upsertMutation = useMutation({
    mutationFn: ({ name, config }: { name: string; config: Record<string, unknown> }) =>
      upsertPilotHardwareConfig(pid, name, config),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['pilot-hardware-config', pid] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (name: string) => deletePilotHardwareConfig(pid, name),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['pilot-hardware-config', pid] })
    },
  })

  function startEdit(row: PilotHardwareConfigRow) {
    setEditingRow(row.name)
    setEditJson(JSON.stringify(row.config, null, 2))
    setEditError('')
  }

  function cancelEdit() {
    setEditingRow(null)
    setEditJson('')
    setEditError('')
  }

  function saveEdit(name: string) {
    let parsed: Record<string, unknown>
    try {
      parsed = JSON.parse(editJson)
    } catch {
      setEditError('Invalid JSON')
      return
    }
    upsertMutation.mutate(
      { name, config: parsed },
      {
        onSuccess: () => {
          setEditingRow(null)
          setEditJson('')
          setEditError('')
        },
        onError: (e: Error) => setEditError(e.message),
      },
    )
  }

  function handleModulePick(moduleId: string) {
    setSelectedModuleId(moduleId)
    if (!moduleId) {
      setAddJson('{}')
      return
    }
    const mod = modules.find(m => String(m.id) === moduleId)
    if (mod) {
      if (!addName) setAddName(mod.name)
      setAddJson(buildDefaultConfig(mod))
    }
  }

  function submitAdd() {
    if (!addName.trim()) {
      setAddError('Name is required')
      return
    }
    let parsed: Record<string, unknown>
    try {
      parsed = JSON.parse(addJson)
    } catch {
      setAddError('Invalid JSON')
      return
    }
    upsertMutation.mutate(
      { name: addName.trim(), config: parsed },
      {
        onSuccess: () => {
          setAddName('')
          setAddJson('{}')
          setSelectedModuleId('')
          setAddError('')
        },
        onError: (e: Error) => setAddError(e.message),
      },
    )
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
              <th style={{ textAlign: 'left', padding: '0.5rem', width: '150px' }}>Class</th>
              <th style={{ textAlign: 'left', padding: '0.5rem' }}>Params</th>
              <th style={{ textAlign: 'right', padding: '0.5rem', width: '130px' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loadingConfigs && (
              <tr>
                <td colSpan={4} style={{ padding: '1rem', color: 'var(--subtext0)' }}>Loading…</td>
              </tr>
            )}
            {!loadingConfigs && configs.length === 0 && (
              <tr>
                <td colSpan={4} style={{ padding: '1rem', color: 'var(--subtext0)' }}>No entries yet — use Add Entry below.</td>
              </tr>
            )}
            {configs.map(row => (
              <tr key={row.name} style={{ borderBottom: '1px solid var(--border)' }}>
                <td style={{ padding: '0.6rem 0.5rem', verticalAlign: 'top' }}>
                  <strong>{row.name}</strong>
                </td>
                <td style={{ padding: '0.6rem 0.5rem', verticalAlign: 'top' }}>
                  {row.config.class_name ? (
                    <span className="badge status-running">{String(row.config.class_name)}</span>
                  ) : (
                    <span style={{ color: 'var(--overlay1)', fontSize: '0.8rem' }}>—</span>
                  )}
                </td>
                <td style={{ padding: '0.6rem 0.5rem', verticalAlign: 'top' }}>
                  {editingRow === row.name ? (
                    <div>
                      <textarea
                        rows={6}
                        value={editJson}
                        onChange={e => setEditJson(e.target.value)}
                        style={TEXTAREA_STYLE}
                      />
                      {editError && (
                        <span className="badge status-error" style={{ marginTop: '4px', display: 'inline-block' }}>
                          {editError}
                        </span>
                      )}
                    </div>
                  ) : (
                    <ParamsSummary config={row.config} />
                  )}
                </td>
                <td style={{ padding: '0.6rem 0.5rem', textAlign: 'right', verticalAlign: 'top' }}>
                  {editingRow === row.name ? (
                    <div style={{ display: 'flex', gap: '0.4rem', justifyContent: 'flex-end' }}>
                      <button
                        className="button-primary"
                        onClick={() => saveEdit(row.name)}
                        disabled={upsertMutation.isPending}
                      >
                        Save
                      </button>
                      <button className="button-secondary" onClick={cancelEdit}>
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <div style={{ display: 'flex', gap: '0.4rem', justifyContent: 'flex-end' }}>
                      <button className="button-secondary" onClick={() => startEdit(row)}>
                        Edit
                      </button>
                      <button
                        className="button-danger"
                        onClick={() => deleteMutation.mutate(row.name)}
                        disabled={deleteMutation.isPending}
                      >
                        Delete
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0, marginBottom: '0.75rem', fontSize: '1rem' }}>Add Entry</h3>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '0.75rem', alignItems: 'flex-end' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--subtext0)', marginBottom: '2px' }}>
              Name
            </label>
            <input
              type="text"
              value={addName}
              onChange={e => setAddName(e.target.value)}
              placeholder="e.g. Left_LED"
              style={{ padding: '5px 8px', fontSize: '0.875rem', width: '180px' }}
            />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--subtext0)', marginBottom: '2px' }}>
              Pre-fill from module (optional)
            </label>
            <select
              value={selectedModuleId}
              onChange={e => handleModulePick(e.target.value)}
              style={{ padding: '5px 8px', fontSize: '0.875rem' }}
            >
              <option value="">— none —</option>
              {modules.map(m => (
                <option key={m.id} value={String(m.id)}>
                  {m.name} ({m.class_name})
                </option>
              ))}
            </select>
          </div>
        </div>
        <div style={{ marginBottom: '0.75rem' }}>
          <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--subtext0)', marginBottom: '2px' }}>
            Config JSON
          </label>
          <textarea
            rows={6}
            value={addJson}
            onChange={e => setAddJson(e.target.value)}
            style={TEXTAREA_STYLE}
          />
        </div>
        {addError && (
          <p style={{ color: 'var(--red)', fontSize: '0.85rem', margin: '0 0 0.5rem' }}>{addError}</p>
        )}
        <button
          className="button-primary"
          onClick={submitAdd}
          disabled={upsertMutation.isPending}
        >
          Add
        </button>
      </div>
    </div>
  )
}
