import { useState, useEffect, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  type Node,
  type Edge,
  type Connection,
  type EdgeChange,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import { getTaskDefinition, updateTaskDefinition } from '../../api/task-definitions'
import { getToolkitsByName } from '../../api/toolkits'
import type { FdaJson, FdaTransition, FdaCondition, FdaState, ToolkitRead } from '../../types'
import StateNode from '../../components/StateNode'
import ConditionBuilder, { operandLabel } from '../../components/ConditionBuilder'
import StateBodyPanel from '../../components/StateBodyPanel'
import TriggerAssignmentPanel from '../../components/TriggerAssignmentPanel'

const nodeTypes = { stateNode: StateNode }

const EMPTY_CONDITION: FdaCondition = { left: { view: '' }, op: '==', right: 0 }

// Normalise a stored transition to v2 format (handles legacy from_state/next_state/condition)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function normaliseTransition(t: any): FdaTransition {
  const from: string = t.from ?? t.from_state ?? ''
  const to: string = t.to ?? t.next_state ?? ''
  let conditions: FdaCondition[] = t.conditions ?? []
  if (conditions.length === 0 && t.condition) {
    // convert legacy {view, op, rhs} to {left, op, right}
    const c = t.condition
    if ('left' in c) {
      conditions = [c]
    } else {
      conditions = [{ left: { view: c.view ?? '' }, op: c.op ?? '==', right: c.rhs ?? 0 }]
    }
  }
  return { from, to, conditions, description: t.description }
}

function condLabel(t: FdaTransition): string {
  const cond = t.conditions?.[0]
  if (!cond) return 'new'
  return `${operandLabel(cond.left)} ${cond.op} ${operandLabel(cond.right)}`
}

function normaliseFda(fdaJson: FdaJson): FdaJson {
  return {
    ...fdaJson,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    transitions: (fdaJson.transitions ?? []).map(normaliseTransition),
    trigger_assignments: fdaJson.trigger_assignments ?? [],
  }
}

function fdaToNodes(fdaJson: FdaJson, toolkit: ToolkitRead | null): Node[] {
  return Object.entries(fdaJson.states ?? {}).map(([name, state], i) => ({
    id: name,
    type: 'stateNode',
    position: { x: (i % 4) * 270, y: Math.floor(i / 4) * 170 },
    data: { name, state, isInitial: name === fdaJson.initial_state, toolkit },
  }))
}

function fdaToEdges(fdaJson: FdaJson): Edge[] {
  return fdaJson.transitions.map((t: FdaTransition, i: number) => ({
    id: `e-${i}`,
    source: t.from,
    target: t.to,
    label: condLabel(t),
    data: { transition: t },
    style: { stroke: '#475569' },
    labelStyle: { fill: '#94a3b8', fontSize: 11 },
    labelBgStyle: { fill: '#1e2130' },
  }))
}

export default function TaskEditor() {
  const { id } = useParams<{ id: string }>()
  const numId = Number(id)
  const qc = useQueryClient()

  const { data: taskDef, isLoading } = useQuery({
    queryKey: ['task-definition', numId],
    queryFn: () => getTaskDefinition(numId),
    enabled: !isNaN(numId),
  })

  const { data: toolkits } = useQuery({
    queryKey: ['toolkits-by-name', taskDef?.toolkit_name],
    queryFn: () => getToolkitsByName(taskDef!.toolkit_name!),
    enabled: !!taskDef?.toolkit_name,
    retry: false,
  })

  const toolkit = toolkits?.[0] ?? null
  const hasMultipleVariants = (toolkits?.length ?? 0) > 1

  const [fdaJson, setFdaJson] = useState<FdaJson | null>(null)
  const [selectedState, setSelectedState] = useState<string | null>(null)
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null)
  const [editName, setEditName] = useState('')
  const [savedMsg, setSavedMsg] = useState('')

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])

  useEffect(() => {
    if (taskDef) {
      if (taskDef.fda_json) setFdaJson(normaliseFda(taskDef.fda_json))
      setEditName(taskDef.display_name ?? taskDef.task_name ?? '')
    }
  }, [taskDef])

  // Only sync canvas on initial FDA load or toolkit change — NOT on every edit
  const [canvasInited, setCanvasInited] = useState(false)
  useEffect(() => {
    if (!fdaJson || canvasInited) return
    setNodes(fdaToNodes(fdaJson, toolkit))
    setEdges(fdaToEdges(fdaJson))
    setCanvasInited(true)
  }, [fdaJson, toolkit, canvasInited])

  // Re-sync edges when transitions change (after adding a new edge)
  useEffect(() => {
    if (!fdaJson || !canvasInited) return
    setEdges(fdaToEdges(fdaJson))
  }, [fdaJson?.transitions])

  // Re-sync nodes when state bodies change (so action count updates)
  useEffect(() => {
    if (!fdaJson || !canvasInited) return
    setNodes(prev => prev.map(n => ({
      ...n,
      data: {
        ...n.data,
        state: fdaJson.states[n.id] ?? n.data.state,
        toolkit,
      },
    })))
  }, [fdaJson?.states, toolkit])

  const saveMutation = useMutation({
    mutationFn: () => updateTaskDefinition(numId, {
      display_name: editName.trim() || undefined,
      fda_json: fdaJson ?? undefined,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['task-definition', numId] })
      qc.invalidateQueries({ queryKey: ['task-definitions'] })
      setSavedMsg('Saved ✓')
      setTimeout(() => setSavedMsg(''), 2000)
    },
    onError: (e: Error) => setSavedMsg(`Error: ${e.message}`),
  })

  const handleEdgesChange = useCallback((changes: EdgeChange[]) => {
    onEdgesChange(changes)
    const removedIndices = new Set(
      changes
        .filter(c => c.type === 'remove')
        .map(c => parseInt((c as { id: string }).id.replace('e-', ''), 10))
        .filter(n => !isNaN(n))
    )
    if (removedIndices.size === 0) return
    setFdaJson(prev =>
      prev ? { ...prev, transitions: prev.transitions.filter((_, i) => !removedIndices.has(i)) } : prev
    )
  }, [onEdgesChange])

  const onConnect = useCallback((params: Connection) => {
    if (params.target === fdaJson?.initial_state) return  // initial state cannot be a target
    const tmpId = `e-tmp-${Date.now()}`
    setEdges(eds => addEdge({
      id: tmpId,
      source: params.source!,
      target: params.target!,
      label: 'new',
      style: { stroke: '#475569' },
    }, eds))
    setFdaJson(prev => {
      if (!prev) return prev
      return {
        ...prev,
        transitions: [...prev.transitions, { from: params.source!, to: params.target!, conditions: [] }],
      }
    })
  }, [setEdges])

  const updateTransitionCondition = (edgeId: string, updated: FdaCondition) => {
    if (!fdaJson) return
    const idx = parseInt(edgeId.replace('e-', ''), 10)
    if (isNaN(idx) || idx < 0 || idx >= fdaJson.transitions.length) return
    const newTransitions = fdaJson.transitions.map((t, i) =>
      i === idx ? { ...t, conditions: [updated] } : t
    )
    setFdaJson(prev => prev ? { ...prev, transitions: newTransitions } : prev)
    const label = `${operandLabel(updated.left)} ${updated.op} ${operandLabel(updated.right)}`
    setEdges(eds => eds.map(e => e.id === edgeId ? { ...e, label } : e))
  }

  const updateStateBody = (stateName: string, updated: FdaState) => {
    setFdaJson(prev => prev ? { ...prev, states: { ...prev.states, [stateName]: updated } } : prev)
  }

  const bootstrapFromToolkit = () => {
    if (!toolkit?.states?.length) return
    setFdaJson({
      version: 2,
      initial_state: toolkit.states[0],
      states: Object.fromEntries(toolkit.states.map(s => [s, {}])),
      transitions: [],
      trigger_assignments: [],
    })
    setCanvasInited(false)
  }

  const PANEL = 'var(--panel)'
  const BORDER = 'var(--border)'
  const MUTED = 'var(--muted)'

  // Derive selected transition from edge id
  const selectedTransition = selectedEdgeId && fdaJson
    ? (() => {
        const idx = parseInt(selectedEdgeId.replace('e-', ''), 10)
        return !isNaN(idx) ? fdaJson.transitions[idx] ?? null : null
      })()
    : null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '12px',
        padding: '8px 16px', background: PANEL,
        borderBottom: `1px solid ${BORDER}`, flexShrink: 0,
      }}>
        <Link to="/toolkits-ui" className="button-link" style={{ fontSize: '12px', flexShrink: 0 }}>
          ← Toolkits
        </Link>
        <input
          value={editName}
          onChange={e => setEditName(e.target.value)}
          style={{
            flex: 1, fontFamily: "'IBM Plex Mono', monospace", fontSize: '14px', fontWeight: 600,
            background: 'transparent', border: 'none', borderBottom: `1px solid ${BORDER}`,
            borderRadius: 0, color: 'var(--text)', padding: '2px 0', outline: 'none', minWidth: 0,
          }}
          onFocus={e => (e.target.style.borderBottomColor = 'var(--lavender)')}
          onBlur={e => (e.target.style.borderBottomColor = BORDER)}
          placeholder="Task definition name…"
        />
        {taskDef?.toolkit_name && (
          <span className="badge" style={{ fontSize: '11px', flexShrink: 0 }}>{taskDef.toolkit_name}</span>
        )}
        {savedMsg && (
          <span style={{ fontSize: '12px', color: savedMsg.startsWith('Error') ? 'var(--error)' : 'var(--green)', flexShrink: 0 }}>
            {savedMsg}
          </span>
        )}
        <button
          className="button-primary"
          style={{ fontSize: '12px', padding: '4px 14px', flexShrink: 0 }}
          disabled={saveMutation.isPending || !fdaJson}
          onClick={() => saveMutation.mutate()}
        >
          {saveMutation.isPending ? 'Saving…' : 'Save'}
        </button>
      </div>

      {hasMultipleVariants && (
        <div style={{
          background: 'rgba(234,179,8,0.08)', borderBottom: `1px solid rgba(234,179,8,0.25)`,
          padding: '5px 16px', fontSize: '12px', color: '#ca8a04', flexShrink: 0,
        }}>
          This toolkit has {toolkits!.length} hardware variants. Binding to a specific variant is available in a future update.
        </div>
      )}

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Canvas */}
        <div style={{ flex: 1, background: '#0d1117', position: 'relative' }}>
          {isLoading ? (
            <div style={{ color: MUTED, padding: '2rem', fontSize: '14px' }}>Loading…</div>
          ) : !fdaJson ? (
            <div style={{ color: MUTED, padding: '2rem', fontSize: '14px' }}>
              {toolkit?.states?.length ? (
                <>
                  <div style={{ marginBottom: '12px' }}>No FDA defined yet. Bootstrap from toolkit states?</div>
                  <button className="button-primary" onClick={bootstrapFromToolkit}>
                    Create FDA from toolkit
                  </button>
                </>
              ) : (
                'No FDA JSON stored. Run a session to register the toolkit via HANDSHAKE, then return here.'
              )}
            </div>
          ) : fdaJson.version !== 2 ? (
            <div style={{ color: MUTED, padding: '2rem', fontSize: '14px' }}>
              Legacy v{(fdaJson as { version?: number }).version ?? 1} FDA.{' '}
              {toolkit?.states?.length ? (
                <button className="button-secondary" style={{ marginLeft: '8px', fontSize: '12px' }} onClick={bootstrapFromToolkit}>
                  Replace with v2 from toolkit
                </button>
              ) : 'Visual editor requires v2 format.'}
            </div>
          ) : (
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              onNodesChange={onNodesChange}
              onEdgesChange={handleEdgesChange}
              onConnect={onConnect}
              deleteKeyCode={['Backspace', 'Delete']}
              onNodeClick={(_evt, node) => {
                setSelectedState(node.id)
                setSelectedEdgeId(null)
              }}
              onEdgeClick={(_evt, edge) => {
                setSelectedEdgeId(edge.id)
                setSelectedState(null)
              }}
              onPaneClick={() => {
                setSelectedEdgeId(null)
                setSelectedState(null)
              }}
              fitView
            >
              <Background color="#1e2130" gap={20} />
              <Controls />
              <MiniMap nodeColor={() => '#2563eb'} style={{ background: '#1e2130' }} />
            </ReactFlow>
          )}
        </div>

        {/* Right panel */}
        <div style={{
          width: '300px', flexShrink: 0, background: PANEL,
          borderLeft: `1px solid ${BORDER}`, padding: '14px',
          overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '12px',
        }}>
          {/* Top: state or transition details */}
          {selectedTransition ? (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                <div style={{ fontSize: '11px', color: MUTED, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                  Transition
                </div>
                <button
                  className="button-danger"
                  style={{ fontSize: '10px', padding: '2px 8px' }}
                  onClick={() => {
                    const idx = parseInt(selectedEdgeId!.replace('e-', ''), 10)
                    if (isNaN(idx)) return
                    setFdaJson(prev => prev ? { ...prev, transitions: prev.transitions.filter((_, i) => i !== idx) } : prev)
                    setEdges(eds => eds.filter(e => e.id !== selectedEdgeId))
                    setSelectedEdgeId(null)
                  }}
                >
                  ✕ Remove
                </button>
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text)', marginBottom: '12px', fontFamily: "'IBM Plex Mono', monospace" }}>
                {selectedTransition.from} → {selectedTransition.to}
              </div>
              <div style={{ fontSize: '11px', color: MUTED, marginBottom: '6px', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                Condition
              </div>
              <ConditionBuilder
                condition={selectedTransition.conditions?.[0] ?? EMPTY_CONDITION}
                toolkit={toolkit}
                onChange={updated => updateTransitionCondition(selectedEdgeId!, updated)}
              />
            </div>
          ) : selectedState && fdaJson ? (
            <StateBodyPanel
              stateName={selectedState}
              state={fdaJson.states[selectedState] ?? {}}
              toolkit={toolkit}
              onChange={updated => updateStateBody(selectedState, updated)}
            />
          ) : (
            <div style={{ color: MUTED, fontSize: '13px', textAlign: 'center', lineHeight: 1.6 }}>
              Click a state to edit its actions,<br />or a transition to edit its condition.
            </div>
          )}

          {/* Bottom: trigger assignments always visible */}
          {fdaJson && (
            <>
              <div style={{ borderTop: `1px solid ${BORDER}`, margin: '4px 0' }} />
              <TriggerAssignmentPanel
                assignments={fdaJson.trigger_assignments}
                toolkit={toolkit}
                onChange={updated =>
                  setFdaJson(prev => prev ? { ...prev, trigger_assignments: updated } : prev)
                }
              />
            </>
          )}
        </div>
      </div>
    </div>
  )
}
