import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  listHardwareModules,
  getHardwareModuleMethods,
  listPilotHardwareConfig,
  upsertPilotHardwareConfig,
} from '../../api/hardware_modules'
import { apiFetch } from '../../api/client'
import type { AstMethodArg } from '../../types'

function inputType(annotation: string | null): string {
  if (annotation === 'int' || annotation === 'float') return 'number'
  if (annotation === 'bool') return 'checkbox'
  return 'text'
}

function inputStep(annotation: string | null): string | undefined {
  if (annotation === 'float') return '0.01'
  if (annotation === 'int') return '1'
  return undefined
}

interface RowState {
  editing: boolean
  values: Record<string, string>
  extra: string  // JSON string for kwargs not in __init__ signature
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
  const [rowState, setRowState] = useState<Record<number, RowState>>({})
  const [saveError, setSaveError] = useState<Record<number, string>>({})

  const { data: modules = [], isLoading: loadingModules } = useQuery({
    queryKey: ['hardware-modules'],
    queryFn: listHardwareModules,
  })

  const { data: configs = [] } = useQuery({
    queryKey: ['pilot-hardware-config', pid],
    queryFn: () => listPilotHardwareConfig(pid),
    enabled: pid > 0,
  })

  const configByModuleId = Object.fromEntries(configs.map(c => [c.hardware_module_id, c]))

  const saveMutation = useMutation({
    mutationFn: ({ moduleId, config }: { moduleId: number; config: Record<string, unknown> }) =>
      upsertPilotHardwareConfig(pid, moduleId, config),
    onSuccess: (_data, { moduleId }) => {
      qc.invalidateQueries({ queryKey: ['pilot-hardware-config', pid] })
      setRowState(s => ({ ...s, [moduleId]: { ...s[moduleId], editing: false } }))
      setSaveError(e => ({ ...e, [moduleId]: '' }))
    },
    onError: (err: Error, { moduleId }) => {
      setSaveError(e => ({ ...e, [moduleId]: err.message }))
    },
  })

  function getInitArgs(moduleId: number): AstMethodArg[] {
    const key = ['hw-module-methods', moduleId]
    const cached = qc.getQueryData<{ methods: { name: string; args: AstMethodArg[] }[] }>(key)
    return cached?.methods.find(m => m.name === '__init__')?.args.filter(a => a.name !== 'self') ?? []
  }

  function getOrLoadArgs(moduleId: number): AstMethodArg[] {
    const args = getInitArgs(moduleId)
    if (args.length === 0) {
      qc.fetchQuery({
        queryKey: ['hw-module-methods', moduleId],
        queryFn: () => getHardwareModuleMethods(moduleId),
      }).catch(() => {})
    }
    return args
  }

  function startEdit(moduleId: number) {
    const args = getInitArgs(moduleId)
    const existing = configByModuleId[moduleId]?.config ?? {}
    const knownKeys = new Set(args.map(a => a.name))
    const values: Record<string, string> = {}
    for (const arg of args) {
      values[arg.name] = String(existing[arg.name] ?? arg.default ?? '')
    }
    const extraEntries = Object.entries(existing).filter(([k]) => !knownKeys.has(k))
    const extra = extraEntries.length > 0 ? JSON.stringify(Object.fromEntries(extraEntries), null, 2) : ''
    setRowState(s => ({ ...s, [moduleId]: { editing: true, values, extra } }))
  }

  function saveRow(moduleId: number) {
    const args = getInitArgs(moduleId)
    const values = rowState[moduleId]?.values ?? {}
    const extra = rowState[moduleId]?.extra ?? ''
    const config: Record<string, unknown> = {}
    for (const arg of args) {
      const raw = values[arg.name] ?? ''
      if (arg.annotation === 'int') config[arg.name] = parseInt(raw) || 0
      else if (arg.annotation === 'float') config[arg.name] = parseFloat(raw) || 0
      else if (arg.annotation === 'bool') config[arg.name] = raw === 'true' || raw === '1'
      else config[arg.name] = raw
    }
    if (extra.trim()) {
      try {
        Object.assign(config, JSON.parse(extra))
      } catch {
        setSaveError(e => ({ ...e, [moduleId]: 'Extra fields: invalid JSON' }))
        return
      }
    }
    saveMutation.mutate({ moduleId, config })
  }

  if (loadingModules || !pid) return <div className="container"><p>Loading…</p></div>

  return (
    <div className="container">
      <h2 style={{ marginBottom: '1rem' }}>Hardware Config — {pilotName}</h2>
      <div className="card">
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              <th style={{ textAlign: 'left', padding: '0.5rem', width: '180px' }}>Module</th>
              <th style={{ textAlign: 'left', padding: '0.5rem' }}>Config Fields</th>
              <th style={{ textAlign: 'right', padding: '0.5rem', width: '120px' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {modules.map(m => {
              const args = getOrLoadArgs(m.id)
              const row = rowState[m.id]
              const existing = configByModuleId[m.id]?.config ?? {}
              const isEditing = row?.editing ?? false

              return (
                <tr key={m.id} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '0.6rem 0.5rem', verticalAlign: 'top' }}>
                    <strong>{m.name}</strong>
                    <br />
                    <span className="badge status-running">{m.class_name}</span>
                  </td>
                  <td style={{ padding: '0.6rem 0.5rem' }}>
                    {args.length === 0 && <span style={{ color: 'var(--text-muted)' }}>loading…</span>}
                    <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                      {args.map(arg => {
                        const itype = inputType(arg.annotation)
                        const displayVal = isEditing
                          ? undefined
                          : String(existing[arg.name] ?? arg.default ?? '—')
                        return (
                          <div key={arg.name} style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                            <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                              {arg.name}{arg.annotation ? ` (${arg.annotation})` : ''}
                            </label>
                            {isEditing ? (
                              itype === 'checkbox' ? (
                                <input
                                  type="checkbox"
                                  checked={row.values[arg.name] === 'true'}
                                  onChange={e => setRowState(s => ({
                                    ...s,
                                    [m.id]: { ...s[m.id], values: { ...s[m.id].values, [arg.name]: e.target.checked ? 'true' : 'false' } },
                                  }))}
                                />
                              ) : (
                                <input
                                  type={itype}
                                  step={inputStep(arg.annotation)}
                                  value={row.values[arg.name] ?? ''}
                                  onChange={e => setRowState(s => ({
                                    ...s,
                                    [m.id]: { ...s[m.id], values: { ...s[m.id].values, [arg.name]: e.target.value } },
                                  }))}
                                  style={{ width: '80px' }}
                                />
                              )
                            ) : (
                              <span>{displayVal}</span>
                            )}
                          </div>
                        )
                      })}
                    </div>
                    {isEditing && (
                      <div style={{ marginTop: '0.75rem' }}>
                        <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: '2px' }}>
                          extra kwargs (JSON) — for trigger, pull, init_hardware_state, etc.
                        </label>
                        <textarea
                          rows={3}
                          value={row?.extra ?? ''}
                          placeholder={'{\n  "trigger": "U",\n  "pull": ""\n}'}
                          onChange={e => setRowState(s => ({ ...s, [m.id]: { ...s[m.id], extra: e.target.value } }))}
                          style={{ width: '100%', fontFamily: 'monospace', fontSize: '0.8rem', resize: 'vertical', boxSizing: 'border-box' }}
                        />
                      </div>
                    )}
                    {!isEditing && (() => {
                      const args = getInitArgs(m.id)
                      const existing = configByModuleId[m.id]?.config ?? {}
                      const knownKeys = new Set(args.map(a => a.name))
                      const extraEntries = Object.entries(existing).filter(([k]) => !knownKeys.has(k))
                      return extraEntries.length > 0 ? (
                        <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          {extraEntries.map(([k, v]) => (
                            <span key={k} style={{ marginRight: '0.75rem' }}><strong>{k}</strong>: {String(v)}</span>
                          ))}
                        </div>
                      ) : null
                    })()}
                    {saveError[m.id] && (
                      <span className="badge status-error" style={{ marginTop: '0.25rem' }}>{saveError[m.id]}</span>
                    )}
                  </td>
                  <td style={{ padding: '0.6rem 0.5rem', textAlign: 'right', verticalAlign: 'top' }}>
                    {isEditing ? (
                      <div style={{ display: 'flex', gap: '0.4rem', justifyContent: 'flex-end' }}>
                        <button className="button-primary" onClick={() => saveRow(m.id)}>Save</button>
                        <button className="button-secondary" onClick={() => setRowState(s => ({ ...s, [m.id]: { ...s[m.id], editing: false, extra: '' } }))}>Cancel</button>
                      </div>
                    ) : (
                      <button className="button-secondary" onClick={() => startEdit(m.id)}>Edit</button>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
