import { useState, useMemo } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { getLeafTasks } from '../../api/tasks'
import { createProtocol } from '../../api/protocols'

interface ParamSpec {
  tag?: string
  type?: string
  default?: unknown
}

interface StepDraft {
  id: number
  task_type: string
  paramSpec: Record<string, ParamSpec>
  rawValues: Record<string, string>   // displayed in inputs
  params: Record<string, unknown>     // parsed valid values for save
  invalidKeys: Record<string, boolean>
  graduation_ntrials: string
  collapsed: boolean
}

let _id = 0

function parseByType(raw: string, type: string): { value: unknown } | { invalid: true } {
  const t = type.trim().toLowerCase()
  const s = raw.trim()
  if (t.includes('int')) {
    const n = Number(s)
    if (!Number.isFinite(n) || !Number.isInteger(n)) return { invalid: true }
    return { value: n }
  }
  if (t.includes('float') || t.includes('number') || t.includes('double')) {
    const n = Number(s)
    if (!Number.isFinite(n)) return { invalid: true }
    return { value: n }
  }
  if (t.includes('bool')) {
    if (['true', '1', 'yes', 'y'].includes(s.toLowerCase())) return { value: true }
    if (['false', '0', 'no', 'n'].includes(s.toLowerCase())) return { value: false }
    return { invalid: true }
  }
  if (t.includes('json') || t.includes('dict') || t.includes('list') || t.includes('object')) {
    try { return { value: JSON.parse(s) } } catch { return { invalid: true } }
  }
  return { value: s }
}

export default function ProtocolsCreate() {
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [steps, setSteps] = useState<StepDraft[]>([])
  const [statusMsg, setStatusMsg] = useState('')
  const [statusError, setStatusError] = useState(false)

  const { data: tasks, isLoading } = useQuery({
    queryKey: ['tasks'],
    queryFn: getLeafTasks,
    staleTime: Infinity,
  })

  const tasksByName = useMemo(
    () => new Map((tasks ?? []).map(t => [t.task_name, t])),
    [tasks]
  )

  const mutation = useMutation({
    mutationFn: () => {
      const payload = {
        name: name.trim(),
        description: description.trim() || undefined,
        steps: steps.map((s, idx) => {
          const params: Record<string, unknown> = { ...s.params }
          const n = parseInt(s.graduation_ntrials)
          if (!isNaN(n) && n > 0) {
            params.graduation = { type: 'NTrials', value: { current_trial: n } }
          }
          return {
            order_index: idx,
            task_type: s.task_type,
            step_name: `${idx + 1}. ${s.task_type}`,
            params,
          }
        }),
      }
      return createProtocol(payload)
    },
    onSuccess: (data) => {
      setStatusError(false)
      setStatusMsg(`✅ Saved protocol "${data.name}" (id=${data.id})`)
      setTimeout(() => navigate('/protocols-ui'), 800)
    },
    onError: (e: Error) => { setStatusError(true); setStatusMsg(`❌ Save failed: ${e.message}`) },
  })

  const addStep = (taskName: string) => {
    const task = tasksByName.get(taskName)
    const paramSpec: Record<string, ParamSpec> =
      (task as { default_params?: Record<string, ParamSpec> })?.default_params ?? {}
    setSteps(prev => [...prev, {
      id: ++_id,
      task_type: taskName,
      paramSpec,
      rawValues: {},
      params: {},
      invalidKeys: {},
      graduation_ntrials: '',
      collapsed: prev.length > 0,  // first step open, rest collapsed
    }])
  }

  const removeStep = (idx: number) =>
    setSteps(prev => prev.filter((_, i) => i !== idx))

  const toggleCollapse = (idx: number) =>
    setSteps(prev => prev.map((s, i) => i === idx ? { ...s, collapsed: !s.collapsed } : s))

  const moveStep = (idx: number, dir: -1 | 1) =>
    setSteps(prev => {
      const next = [...prev]
      const swap = idx + dir
      if (swap < 0 || swap >= next.length) return prev
      ;[next[idx], next[swap]] = [next[swap], next[idx]]
      return next
    })

  const handleParamChange = (stepIdx: number, key: string, raw: string) => {
    setSteps(prev => prev.map((s, i) => {
      if (i !== stepIdx) return s
      const rawValues = { ...s.rawValues, [key]: raw }
      const trimmed = raw.trim()
      if (trimmed === '') {
        const { [key]: _removed, ...params } = s.params
        return { ...s, rawValues, params, invalidKeys: { ...s.invalidKeys, [key]: false } }
      }
      const spec = s.paramSpec[key]
      if (spec?.type) {
        const parsed = parseByType(trimmed, spec.type)
        if ('invalid' in parsed) {
          return { ...s, rawValues, invalidKeys: { ...s.invalidKeys, [key]: true } }
        }
        return { ...s, rawValues, params: { ...s.params, [key]: parsed.value }, invalidKeys: { ...s.invalidKeys, [key]: false } }
      }
      return { ...s, rawValues, params: { ...s.params, [key]: trimmed }, invalidKeys: { ...s.invalidKeys, [key]: false } }
    }))
  }

  const handleGraduationChange = (stepIdx: number, val: string) =>
    setSteps(prev => prev.map((s, i) => i === stepIdx ? { ...s, graduation_ntrials: val } : s))

  const handleSave = () => {
    const n = name.trim()
    if (!n) { setStatusError(true); setStatusMsg('Protocol name is required.'); return }
    if (steps.length === 0) { setStatusError(true); setStatusMsg('Add at least one step before saving.'); return }
    setStatusMsg('Saving…'); setStatusError(false)
    mutation.mutate()
  }

  return (
    <div className="container split">
      {/* LEFT: Task palette */}
      <section className="card">
        <h2>Available Tasks</h2>
        <p className="muted">Leaf tasks only (executable)</p>
        {isLoading ? (
          <ul className="scroll-list skeleton-list">
            {[...Array(6)].map((_, i) => <li key={i} className="skeleton-row" />)}
          </ul>
        ) : (
          <ul id="tasks-list" className="scroll-list">
            {tasks?.map((t, idx) => (
              <li
                key={t.task_name}
                className="task-item fade-in-item"
                style={{ animationDelay: `${Math.min(idx * 18, 180)}ms` }}
                onClick={() => addStep(t.task_name)}
              >
                {t.task_name}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* RIGHT: Protocol builder */}
      <section className="card">
        <h2>Protocol</h2>

        <input
          id="protocol-name"
          placeholder="Protocol name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <textarea
          id="protocol-desc"
          placeholder="Description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          style={{ marginTop: '8px', width: '100%', minHeight: '56px', resize: 'vertical' }}
        />

        <h3 style={{ marginTop: '16px' }}>Steps</h3>
        {steps.length === 0 ? (
          <p className="muted">Click a task on the left to add a step.</p>
        ) : (
          <ol id="steps-list" className="scroll-list" style={{ listStyle: 'none', padding: 0 }}>
            {steps.map((step, idx) => (
              <li key={step.id} className="step-card" style={{ marginBottom: '8px' }}>
                {/* Header */}
                <div className="step-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <strong>{idx + 1}. {step.task_type}</strong>
                  <div style={{ display: 'flex', gap: '4px' }}>
                    <button className="icon-btn" type="button" title="Move up" onClick={() => moveStep(idx, -1)} disabled={idx === 0}>↑</button>
                    <button className="icon-btn" type="button" title="Move down" onClick={() => moveStep(idx, 1)} disabled={idx === steps.length - 1}>↓</button>
                    <button className="icon-btn" type="button" onClick={() => toggleCollapse(idx)}>
                      {step.collapsed ? '▸' : '▾'}
                    </button>
                    <button className="icon-btn icon-danger" type="button" onClick={() => removeStep(idx)}>🗑️</button>
                  </div>
                </div>

                {/* Body */}
                {!step.collapsed && (
                  <div className="step-body">
                    {/* Params grid */}
                    <div className="params-grid">
                      {Object.entries(step.paramSpec).map(([key, spec]) => {
                        const rawVal = step.rawValues[key] ?? ''
                        const isInvalid = step.invalidKeys[key]
                        const tag = spec.tag ?? key
                        const typeStr = spec.type ? ` – ${spec.type}` : ''
                        const defVal = spec.default !== undefined && spec.default !== null
                          ? String(spec.default) : ''
                        return (
                          <div key={key} className="param-field">
                            <label title={`${tag}${typeStr}`}>{key}</label>
                            <input
                              type="text"
                              autoComplete="off"
                              placeholder={defVal}
                              value={rawVal}
                              className={isInvalid ? 'is-invalid' : ''}
                              onChange={(e) => handleParamChange(idx, key, e.target.value)}
                            />
                          </div>
                        )
                      })}
                    </div>

                    {/* Graduation */}
                    <div className="graduation-row" style={{ marginTop: '10px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <label>NTrials graduation</label>
                      <input
                        type="number"
                        min={1}
                        placeholder="e.g. 5"
                        value={step.graduation_ntrials}
                        onChange={(e) => handleGraduationChange(idx, e.target.value)}
                        style={{ width: '90px' }}
                      />
                    </div>
                  </div>
                )}
              </li>
            ))}
          </ol>
        )}

        <button
          id="save-protocol-btn"
          type="button"
          className="button-primary"
          style={{ marginTop: '12px' }}
          disabled={mutation.isPending}
          onClick={handleSave}
        >
          {mutation.isPending ? 'Saving…' : 'Save Protocol'}
        </button>
        {statusMsg && (
          <div id="status-line" className="status-line" style={{ marginTop: '8px', color: statusError ? 'crimson' : undefined }}>
            {statusMsg}
          </div>
        )}
      </section>
    </div>
  )
}
