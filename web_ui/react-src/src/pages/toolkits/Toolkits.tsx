import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { getToolkits } from '../../api/toolkits'
import { getTaskDefinitions, createTaskDefinition } from '../../api/task-definitions'
import type { ToolkitRead, TaskDefinitionFull } from '../../types'

function deduplicateToolkits(toolkits: ToolkitRead[]): ToolkitRead[] {
  const map = new Map<string, ToolkitRead>()
  for (const tk of toolkits) {
    const existing = map.get(tk.name)
    if (!existing || tk.updated_at > existing.updated_at) {
      map.set(tk.name, tk)
    }
  }
  return Array.from(map.values())
}

function emptySkeletonFor(toolkit: ToolkitRead): Record<string, unknown> {
  return {
    version: 2,
    initial_state: toolkit.states?.[0] ?? '',
    states: Object.fromEntries((toolkit.states ?? []).map(s => [s, {}])),
    transitions: [],
    trigger_assignments: [],
  }
}

function MetaChips({ label, items }: { label: string; items: string[] }) {
  if (items.length === 0) return (
    <div style={{ display: 'flex', gap: '6px', alignItems: 'baseline' }}>
      <span style={{ fontSize: '11px', color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em', minWidth: '80px', flexShrink: 0 }}>{label}</span>
      <span style={{ fontSize: '12px', color: 'var(--muted)', fontStyle: 'italic' }}>—</span>
    </div>
  )
  return (
    <div style={{ display: 'flex', gap: '6px', alignItems: 'baseline', flexWrap: 'wrap' }}>
      <span style={{ fontSize: '11px', color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em', minWidth: '80px', flexShrink: 0 }}>{label}</span>
      <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
        {items.map(item => (
          <span key={item} style={{
            fontSize: '11px',
            fontFamily: "'IBM Plex Mono', monospace",
            padding: '1px 6px',
            borderRadius: '3px',
            background: 'rgba(255,255,255,0.04)',
            border: '1px solid var(--border)',
            color: 'var(--text)',
            letterSpacing: '0.02em',
          }}>
            {item}
          </span>
        ))}
      </div>
    </div>
  )
}

function DefinitionRow({ def, onClick }: { def: TaskDefinitionFull; onClick: () => void }) {
  const name = def.display_name || def.task_name
  const date = new Date(def.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
  return (
    <li
      onClick={onClick}
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '7px 10px',
        borderRadius: '5px',
        cursor: 'pointer',
        border: '1px solid transparent',
        transition: 'background 0.1s, border-color 0.1s',
      }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLLIElement).style.background = 'rgba(129,140,248,0.08)'
        ;(e.currentTarget as HTMLLIElement).style.borderColor = 'rgba(129,140,248,0.2)'
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLLIElement).style.background = 'transparent'
        ;(e.currentTarget as HTMLLIElement).style.borderColor = 'transparent'
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
        <span style={{
          width: '6px', height: '6px', borderRadius: '50%',
          background: 'var(--lavender)', flexShrink: 0,
          boxShadow: '0 0 6px rgba(129,140,248,0.5)',
        }} />
        <span style={{ fontSize: '13px', fontWeight: 500, color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {name}
        </span>
      </div>
      <span className="meta-date" style={{ flexShrink: 0, marginLeft: '12px' }}>{date}</span>
    </li>
  )
}

function ToolkitCard({
  toolkit,
  definitions,
  onNewDefinition,
  onOpenDefinition,
  creating,
}: {
  toolkit: ToolkitRead
  definitions: TaskDefinitionFull[]
  onNewDefinition: (toolkit: ToolkitRead) => void
  onOpenDefinition: (id: number) => void
  creating: boolean
}) {
  const hwKeys = Object.keys(toolkit.semantic_hardware ?? {})
  const flagKeys = Object.keys(toolkit.flags ?? {})
  const paramKeys = Object.keys(toolkit.params_schema ?? {})
  const stateNames = toolkit.states ?? []

  return (
    <div className="card fade-in-item" style={{
      borderLeft: '3px solid rgba(129,140,248,0.5)',
      display: 'flex',
      flexDirection: 'column',
      gap: '0',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
            <h2 style={{
              margin: 0,
              fontFamily: "'IBM Plex Mono', monospace",
              fontSize: '1rem',
              fontWeight: 600,
              color: 'var(--text)',
              letterSpacing: '0.01em',
            }}>
              {toolkit.name}
            </h2>
            {definitions.length > 0 && (
              <span className="badge" style={{ fontSize: '11px', color: 'var(--lavender)', borderColor: 'rgba(129,140,248,0.3)' }}>
                {definitions.length} {definitions.length === 1 ? 'definition' : 'definitions'}
              </span>
            )}
          </div>
          {toolkit.pilot_origins.length > 0 && (
            <div style={{ display: 'flex', gap: '4px', marginTop: '5px', flexWrap: 'wrap' }}>
              {toolkit.pilot_origins.map(p => (
                <span key={p} className="meta-pill" style={{ fontSize: '11px' }}>{p}</span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Metadata grid */}
      <div style={{
        background: 'rgba(0,0,0,0.2)',
        borderRadius: '6px',
        padding: '10px 12px',
        display: 'flex',
        flexDirection: 'column',
        gap: '6px',
        marginBottom: '12px',
        border: '1px solid var(--border)',
      }}>
        <MetaChips label="States" items={stateNames} />
        <MetaChips label="Hardware" items={hwKeys} />
        <MetaChips label="Flags" items={flagKeys} />
        <MetaChips label="Params" items={paramKeys} />
      </div>

      {/* Definitions section */}
      <div style={{ marginBottom: '12px' }}>
        <div style={{
          fontSize: '11px',
          color: 'var(--muted)',
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
          marginBottom: '6px',
          paddingLeft: '2px',
        }}>
          Task Definitions
        </div>
        {definitions.length === 0 ? (
          <p className="muted" style={{ margin: '4px 0 0 2px', fontSize: '12px', fontStyle: 'italic' }}>
            No definitions yet — create one below.
          </p>
        ) : (
          <ul style={{ margin: 0, padding: 0 }}>
            {definitions.map(def => (
              <DefinitionRow
                key={def.id}
                def={def}
                onClick={() => onOpenDefinition(def.id)}
              />
            ))}
          </ul>
        )}
      </div>

      {/* Action */}
      <button
        className="button-primary"
        style={{ alignSelf: 'flex-start', fontSize: '13px' }}
        disabled={creating}
        onClick={() => onNewDefinition(toolkit)}
      >
        {creating ? 'Creating…' : '+ New Task Definition'}
      </button>
    </div>
  )
}

export default function Toolkits() {
  const navigate = useNavigate()
  const qc = useQueryClient()

  const { data: toolkits, isLoading: loadingToolkits, isError: errorToolkits } = useQuery({
    queryKey: ['toolkits'],
    queryFn: getToolkits,
  })

  const { data: taskDefs } = useQuery({
    queryKey: ['task-definitions'],
    queryFn: getTaskDefinitions,
  })

  const createMutation = useMutation({
    mutationFn: createTaskDefinition,
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ['task-definitions'] })
      qc.invalidateQueries({ queryKey: ['toolkits'] })
      navigate(`/task-editor/${result.id}`)
    },
    onError: (e: Error) => alert(`Failed to create task definition: ${e.message}`),
  })

  const handleNewDefinition = (toolkit: ToolkitRead) => {
    createMutation.mutate({
      display_name: toolkit.name + ' FDA',
      toolkit_name: toolkit.name,
      fda_json: emptySkeletonFor(toolkit),
    })
  }

  const toolkitCards = deduplicateToolkits(toolkits ?? [])

  return (
    <div className="container" style={{ paddingTop: '1rem' }}>
      {/* Page header */}
      <div style={{ marginBottom: '1.5rem' }}>
        <h1 style={{
          margin: 0,
          fontSize: '1.4rem',
          fontWeight: 700,
          fontFamily: "'IBM Plex Sans', sans-serif",
          color: 'var(--text)',
        }}>
          Toolkits
        </h1>
        <p className="muted" style={{ marginTop: '4px', fontSize: '13px' }}>
          Toolkits are registered automatically when a pilot runs a task. Create a task definition from a toolkit to configure its state machine.
        </p>
      </div>

      {loadingToolkits ? (
        <p className="muted">Loading toolkits…</p>
      ) : errorToolkits ? (
        <p className="error">Failed to load toolkits.</p>
      ) : toolkitCards.length === 0 ? (
        <div className="card" style={{ borderLeft: '3px solid var(--border)' }}>
          <p className="muted" style={{ margin: 0 }}>
            No toolkits registered yet. Run a session on a pilot — the HANDSHAKE message will register its toolkit here automatically.
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {toolkitCards.map(toolkit => {
            const defs = (taskDefs ?? []).filter(d => d.toolkit_name === toolkit.name && d.fda_json !== null)
            return (
              <ToolkitCard
                key={toolkit.name}
                toolkit={toolkit}
                definitions={defs}
                onNewDefinition={handleNewDefinition}
                onOpenDefinition={id => navigate(`/task-editor/${id}`)}
                creating={createMutation.isPending}
              />
            )
          })}
        </div>
      )}
    </div>
  )
}
