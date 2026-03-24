import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { getTaskDefinitions } from '../../api/task-definitions'
import { getToolkits } from '../../api/toolkits'
import type { TaskDefinitionFull, ToolkitRead } from '../../types'

// ── Design tokens ─────────────────────────────────────────────────────────────
const TOOLKIT_COLORS = [
  '#818cf8', // lavender
  '#34d399', // green
  '#38bdf8', // sky
  '#fb923c', // orange
  '#a78bfa', // violet
  '#f472b6', // pink
  '#facc15', // yellow
]

function toolkitColor(name: string): string {
  let h = 0
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0
  return TOOLKIT_COLORS[h % TOOLKIT_COLORS.length]
}

function buildVariantNames(toolkits: ToolkitRead[]): Set<string> {
  const counts: Record<string, number> = {}
  for (const t of toolkits) counts[t.name] = (counts[t.name] ?? 0) + 1
  return new Set(Object.entries(counts).filter(([, n]) => n >= 2).map(([k]) => k))
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric',
  })
}

// Group by task_name, keep highest id per group as the representative row
function dedupeTaskDefs(defs: TaskDefinitionFull[]): Array<{ def: TaskDefinitionFull; revisions: number }> {
  const groups = new Map<string, TaskDefinitionFull[]>()
  for (const d of defs) {
    const g = groups.get(d.task_name) ?? []
    g.push(d)
    groups.set(d.task_name, g)
  }
  return Array.from(groups.values()).map(g => ({
    def: g.reduce((best, d) => (d.id > best.id ? d : best)),
    revisions: g.length,
  }))
}

// ── Styles ────────────────────────────────────────────────────────────────────
const CSS = `
  .tdreg-shell {
    padding: 0;
  }

  .tdreg-header {
    display: flex;
    align-items: baseline;
    gap: 14px;
    margin-bottom: 24px;
  }

  .tdreg-title {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--muted);
  }

  .tdreg-count {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    font-weight: 500;
    color: var(--lavender);
    background: rgba(129,140,248,0.08);
    border: 1px solid rgba(129,140,248,0.18);
    border-radius: 3px;
    padding: 1px 7px;
    letter-spacing: 0.06em;
  }

  .tdreg-col-headers {
    display: grid;
    grid-template-columns: 1fr 160px 110px;
    gap: 0 12px;
    padding: 0 0 6px 16px;
    margin-bottom: 4px;
    border-bottom: 1px solid var(--border);
  }

  .tdreg-col-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--muted);
    opacity: 0.6;
  }
  .tdreg-col-label:last-child {
    text-align: right;
  }

  .tdreg-list {
    list-style: none;
    padding: 0;
    margin: 0;
  }

  .tdreg-row {
    position: relative;
    display: grid;
    grid-template-columns: 1fr 160px 110px;
    gap: 0 12px;
    align-items: center;
    padding: 11px 0 11px 16px;
    border-bottom: 1px solid var(--border);
    cursor: pointer;
    transition: background 0.12s ease;
    animation: tdreg-fadein 0.25s ease both;
  }

  .tdreg-row::before {
    content: '';
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 3px;
    border-radius: 0 2px 2px 0;
    background: var(--tdreg-accent, var(--border));
    opacity: 0.4;
    transition: opacity 0.12s ease, width 0.12s ease;
  }

  .tdreg-row:hover {
    background: rgba(255,255,255,0.025);
  }

  .tdreg-row:hover::before {
    opacity: 1;
    width: 4px;
  }

  .tdreg-name {
    font-family: 'IBM Plex Sans', system-ui, sans-serif;
    font-size: 13px;
    font-weight: 500;
    color: var(--text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .tdreg-task-id {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    color: var(--muted);
    margin-top: 3px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .tdreg-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
    align-items: center;
  }

  .tdreg-badge-toolkit {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 9.5px;
    font-weight: 500;
    letter-spacing: 0.04em;
    padding: 2px 7px;
    border-radius: 3px;
    border: 1px solid;
    white-space: nowrap;
  }

  .tdreg-badge-variant {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 0.06em;
    padding: 2px 6px;
    border-radius: 3px;
    background: rgba(251,191,36,0.08);
    color: #f59e0b;
    border: 1px solid rgba(251,191,36,0.22);
    white-space: nowrap;
  }

  .tdreg-badge-revisions {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 0.06em;
    padding: 2px 6px;
    border-radius: 3px;
    background: rgba(148,163,184,0.08);
    color: var(--muted);
    border: 1px solid rgba(148,163,184,0.2);
    white-space: nowrap;
  }

  .tdreg-date {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    color: var(--muted);
    text-align: right;
    opacity: 0.7;
  }

  .tdreg-empty {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px;
    color: var(--muted);
    padding: 32px 0;
    text-align: center;
    letter-spacing: 0.06em;
    opacity: 0.5;
  }

  .tdreg-skeleton-row {
    display: grid;
    grid-template-columns: 1fr 160px 110px;
    gap: 0 12px;
    align-items: center;
    padding: 11px 0 11px 16px;
    border-bottom: 1px solid var(--border);
  }

  .tdreg-skel {
    height: 10px;
    border-radius: 3px;
    background: var(--border);
    animation: tdreg-pulse 1.4s ease-in-out infinite;
  }

  @keyframes tdreg-fadein {
    from { opacity: 0; transform: translateY(4px); }
    to   { opacity: 1; transform: translateY(0);   }
  }

  @keyframes tdreg-pulse {
    0%, 100% { opacity: 0.4; }
    50%       { opacity: 0.8; }
  }
`

// ── Component ─────────────────────────────────────────────────────────────────
export default function TaskDefinitions() {
  const navigate = useNavigate()

  const { data: taskDefs, isLoading } = useQuery({
    queryKey: ['task-definitions'],
    queryFn: getTaskDefinitions,
  })

  const { data: toolkits } = useQuery({
    queryKey: ['toolkits'],
    queryFn: getToolkits,
  })

  const variantNames = toolkits ? buildVariantNames(toolkits) : new Set<string>()
  const withFda = taskDefs ? taskDefs.filter(d => d.fda_json !== null) : []
  const deduped = dedupeTaskDefs(withFda)
  const count = deduped.length

  return (
    <div className="container">
      <style>{CSS}</style>

      <section className="card tdreg-shell">
        <div className="tdreg-header">
          <span className="tdreg-title">Task Definitions</span>
          {!isLoading && <span className="tdreg-count">{count}</span>}
        </div>

        <div className="tdreg-col-headers">
          <span className="tdreg-col-label">Name</span>
          <span className="tdreg-col-label">Toolkit</span>
          <span className="tdreg-col-label">Created</span>
        </div>

        {isLoading ? (
          <ul className="tdreg-list">
            {[0.25, 0.15, 0.2].map((d, i) => (
              <li key={i} className="tdreg-skeleton-row" style={{ animationDelay: `${d}s` }}>
                <div className="tdreg-skel" style={{ width: '55%' }} />
                <div className="tdreg-skel" style={{ width: '70%' }} />
                <div className="tdreg-skel" style={{ width: '80%', marginLeft: 'auto' }} />
              </li>
            ))}
          </ul>
        ) : count === 0 ? (
          <div className="tdreg-empty">— no task definitions registered —</div>
        ) : (
          <ul className="tdreg-list">
            {deduped.map(({ def, revisions }, idx) => {
              const color = def.toolkit_name ? toolkitColor(def.toolkit_name) : 'var(--border)'
              return (
                <li
                  key={def.id}
                  className="tdreg-row"
                  style={{
                    ['--tdreg-accent' as string]: color,
                    animationDelay: `${idx * 0.04}s`,
                  }}
                  onClick={() => navigate(`/task-editor/${def.id}`)}
                >
                  {/* Name column */}
                  <div>
                    <div className="tdreg-name">{def.display_name ?? def.task_name}</div>
                    {def.display_name && (
                      <div className="tdreg-task-id">{def.task_name}</div>
                    )}
                  </div>

                  {/* Toolkit column */}
                  <div className="tdreg-badges">
                    {def.toolkit_name && (
                      <span
                        className="tdreg-badge-toolkit"
                        style={{
                          color,
                          borderColor: `${color}33`,
                          background: `${color}0d`,
                        }}
                      >
                        {def.toolkit_name}
                      </span>
                    )}
                    {def.toolkit_name && variantNames.has(def.toolkit_name) && (
                      <span className="tdreg-badge-variant" title="Multiple hardware variants exist for this toolkit">
                        2+ var
                      </span>
                    )}
                    {revisions > 1 && (
                      <span className="tdreg-badge-revisions" title={`${revisions} revisions stored`}>
                        {revisions} rev
                      </span>
                    )}
                  </div>

                  {/* Date column */}
                  <div className="tdreg-date">{formatDate(def.created_at)}</div>
                </li>
              )
            })}
          </ul>
        )}
      </section>
    </div>
  )
}
