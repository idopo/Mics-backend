import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getProtocol } from '../api/protocols'
import { getLeafTasks } from '../api/tasks'

function norm(s: string) { return s.trim().toLowerCase() }

function sanitizeStepTitle(stepName: string, idx: number, taskType: string) {
  const s = stepName.trim().replace(/^step\s*\d+\s*[:\-–]?\s*/i, '').replace(/^\d+\.\s*/, '').trim()
  const label = s || taskType.trim() || 'Unnamed step'
  const clean = taskType && label.toLowerCase() === taskType.toLowerCase() ? taskType : label
  return `Step ${idx + 1}: ${clean}`
}

function getGraduationN(val: unknown): string | null {
  if (val == null) return null
  if (typeof val === 'number' && isFinite(val)) return String(val)
  if (typeof val === 'string' && /^\d+$/.test(val.trim())) return val.trim()
  if (typeof val === 'object' && val !== null) {
    const obj = val as Record<string, unknown>
    const v = (obj.value ?? obj) as Record<string, unknown>
    const n = v?.current_trial ?? v?.n_trials ?? v?.n
    if (n != null) return String(n)
  }
  return null
}

function formatDisplayValue(val: unknown): string {
  if (val === null || val === undefined) return ''
  if (typeof val === 'boolean') return val ? 'true' : 'false'
  if (typeof val === 'number') return String(val)
  if (typeof val === 'string') return val
  if (typeof val === 'object') {
    const obj = val as Record<string, unknown>
    if ('value' in obj) return formatDisplayValue(obj.value)
    const entries = Object.entries(obj).filter(([, v]) => v !== null && v !== undefined)
    if (entries.length === 0) return ''
    if (entries.length <= 4) return entries.map(([k, v]) => `${k}: ${typeof v === 'object' ? JSON.stringify(v) : String(v)}`).join(', ')
    return JSON.stringify(val)
  }
  return String(val)
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
  } catch {
    return iso
  }
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      type="button"
      title={copied ? 'Copied!' : 'Copy full hash'}
      onClick={() => {
        navigator.clipboard.writeText(text).then(() => {
          setCopied(true)
          setTimeout(() => setCopied(false), 1500)
        })
      }}
      style={{
        background: 'none', border: 'none', cursor: 'pointer',
        color: copied ? '#34d399' : 'var(--muted)',
        padding: '0 2px', lineHeight: 1, verticalAlign: 'middle',
        transition: 'color 0.2s ease',
      }}
    >
      {copied ? (
        <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
          <path d="M13.78 4.22a.75.75 0 0 1 0 1.06l-7.25 7.25a.75.75 0 0 1-1.06 0L2.22 9.28a.75.75 0 1 1 1.06-1.06L6 10.94l6.72-6.72a.75.75 0 0 1 1.06 0z"/>
        </svg>
      ) : (
        <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
          <path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z"/>
          <path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z"/>
        </svg>
      )}
    </button>
  )
}

const SKIP_KEYS = new Set(['step_name', 'task_type'])

const DOT = (
  <span
    aria-hidden
    style={{
      color: 'var(--muted)',
      fontSize: '0.65rem',
      padding: '0 10px',
      userSelect: 'none',
      opacity: 0.5,
      lineHeight: 1,
    }}
  >·</span>
)

interface Props {
  protocolId: number
  showFullParams?: boolean
}

export default function ProtocolInfoContent({ protocolId, showFullParams = false }: Props) {
  const { data: protocol } = useQuery({
    queryKey: ['protocol', protocolId],
    queryFn: () => getProtocol(protocolId),
    staleTime: Infinity,
  })
  const { data: tasks } = useQuery({
    queryKey: ['tasks'],
    queryFn: getLeafTasks,
    staleTime: Infinity,
  })
  const tasksByName = useMemo(
    () => new Map((tasks ?? []).map(t => [norm(t.task_name), t])),
    [tasks]
  )

  if (!protocol) {
    return <div className="muted" style={{ padding: '40px 0', textAlign: 'center' }}>Loading…</div>
  }

  const steps = protocol.steps ?? []

  return (
    <div>
      {/* ── Header ── */}
      <div style={{ marginBottom: '32px', paddingBottom: '20px', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <div style={{ fontWeight: 600, fontSize: '1rem', letterSpacing: '0.01em', marginBottom: '6px' }}>
          {protocol.name}
        </div>
        {protocol.created_at && (
          <div className="muted" style={{ fontSize: '0.78rem', letterSpacing: '0.02em' }}>
            {formatDate(protocol.created_at)}
          </div>
        )}
      </div>

      {steps.length === 0 && <div className="muted">No steps defined.</div>}

      {steps.map((step, idx) => {
        const task = tasksByName.get(norm(step.task_type))
        const title = sanitizeStepTitle(step.step_name, idx, step.task_type)
        const hardwareEntries = task?.hardware
          ? Object.entries(task.hardware).filter(([, v]) => Boolean(v))
          : []
        const fileHash = task?.file_hash ?? null
        const stepPilots = task?.pilots ?? []

        const hasPilotOrHw = stepPilots.length > 0 || hardwareEntries.length > 0 || !!task?.base_class
        const hasHash = !!fileHash

        const allParams = Object.entries(step.params ?? {}).filter(([k]) => !SKIP_KEYS.has(norm(k)))
        const gradEntry = allParams.find(([k]) => norm(k) === 'graduation')
        const gradN = gradEntry ? getGraduationN(gradEntry[1]) : null
        const otherParams = allParams.filter(([k]) => norm(k) !== 'graduation')

        return (
          <div
            key={idx}
            className="step-box"
            style={{ marginBottom: '20px', padding: '16px 18px' }}
          >
            {/* ── Step name ── */}
            <div className="step-name" style={{ marginBottom: '12px' }}>{title}</div>

            {/* ── Meta row: [pilots · hw · base_class] · [hash] ── */}
            {(hasPilotOrHw || hasHash) && (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                flexWrap: 'wrap',
                rowGap: '6px',
                marginBottom: (gradN || (showFullParams && otherParams.length > 0)) ? '16px' : 0,
              }}>
                {/* Pilot pills */}
                {stepPilots.map((p, i) => (
                  <span key={p}>
                    {i > 0 && DOT}
                    <span className="meta-pill" style={{ fontSize: '0.74rem' }}>{p}</span>
                  </span>
                ))}

                {/* Hardware pills — grouped tightly, single dot before the group */}
                {hardwareEntries.length > 0 && stepPilots.length > 0 && DOT}
                {hardwareEntries.length > 0 && (
                  <span style={{ display: 'inline-flex', gap: '4px', alignItems: 'center' }}>
                    {hardwareEntries.map(([k]) => (
                      <span key={k} className="meta-pill" style={{
                        fontSize: '0.74rem',
                        background: 'rgba(52,211,153,0.12)',
                        borderColor: 'rgba(52,211,153,0.35)',
                        color: '#34d399',
                      }}>{k}</span>
                    ))}
                  </span>
                )}

                {/* Base class */}
                {task?.base_class && (stepPilots.length > 0 || hardwareEntries.length > 0) && DOT}
                {task?.base_class && (
                  <span className="muted" style={{ fontSize: '0.73rem', fontStyle: 'italic' }}>
                    {task.base_class}
                  </span>
                )}

                {/* Separator before hash */}
                {hasPilotOrHw && hasHash && DOT}

                {/* Hash + copy */}
                {hasHash && (
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '2px' }}>
                    <code style={{ fontSize: '0.72rem', color: 'var(--muted)', fontFamily: 'monospace' }}>
                      {fileHash!.slice(0, 12)}…
                    </code>
                    <CopyButton text={fileHash!} />
                  </span>
                )}
              </div>
            )}

            {/* ── Graduation pill ── */}
            {gradN && (
              <div
                className="graduation-pill"
                style={{ marginBottom: showFullParams && otherParams.length > 0 ? '16px' : 0 }}
              >
                <span className="grad-icon">⟳</span>
                <div style={{ fontWeight: 600, fontSize: '13px' }}>{gradN} trials</div>
              </div>
            )}

            {/* ── Full params (ⓘ modal only) ── */}
            {showFullParams && otherParams.length > 0 && (
              <div className="params-grid" style={{ marginTop: gradN ? 0 : '4px' }}>
                {otherParams.map(([key, val]) => (
                  <div key={key} className="param-field">
                    <label>{key}</label>
                    <input
                      type="text"
                      disabled
                      value={formatDisplayValue(val)}
                      placeholder="—"
                      readOnly
                    />
                  </div>
                ))}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
