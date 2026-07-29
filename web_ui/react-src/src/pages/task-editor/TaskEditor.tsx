import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
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
import { getHwLibVersions } from '../../api/hardware_libs'
import { getHardwareModule } from '../../api/hardware_modules'
import type { FdaJson, FdaTransition, FdaCondition, FdaOperand, FdaState, ToolkitRead, HardwareModule, ConditionGroup, ConditionNode, FdaTriggerAssignment } from '../../types'
import { isConditionBranch } from '../../types'
import StateNode from '../../components/StateNode'
import { operandLabel } from '../../components/ConditionBuilder'
import { ConditionGroupsEditor } from '../../components/ConditionGroupsEditor'
import StateBodyPanel from '../../components/StateBodyPanel'
import TriggerAssignmentPanel, { isCompleteTrigger } from '../../components/TriggerAssignmentPanel'
import VariablesPanel from '../../components/VariablesPanel'
import HwLibVersionModal from './HwLibVersionModal'

const nodeTypes = { stateNode: StateNode }

// Normalise a stored transition to v2 format (handles legacy from_state/next_state/condition)
function normaliseTransition(t: Record<string, unknown>): FdaTransition {
  const from: string = (t.from ?? t.from_state ?? '') as string
  const to: string   = (t.to   ?? t.next_state  ?? '') as string

  // Already has condition_tree — use as-is (canonical Phase 16+ format)
  if (t.condition_tree !== undefined) {
    return { from, to, condition_tree: t.condition_tree as ConditionNode, description: t.description as string | undefined }
  }

  // Migrate condition_groups (DNF) → OR-of-AND tree
  const groups = t.condition_groups as ConditionGroup[] | undefined
  if (groups && groups.length > 0) {
    // Build OR-of-AND tree
    const andNodes = groups
      .filter(g => g.conditions.length > 0)
      .map(g =>
        g.conditions.length === 1
          ? g.conditions[0]
          : ({ op: 'AND' as const, children: g.conditions })
      )
    const tree: ConditionNode | null =
      andNodes.length === 0 ? null :
      andNodes.length === 1 ? andNodes[0] :
      { op: 'OR', children: andNodes }
    return { from, to, condition_tree: tree ?? undefined, description: t.description as string | undefined }
  }

  // Migrate legacy conditions[] → single AND-leaf (or null if empty)
  let legacyConditions: FdaCondition[] = (t.conditions ?? []) as FdaCondition[]
  if (legacyConditions.length === 0 && t.condition) {
    const c = t.condition as Record<string, unknown>
    if ('left' in c) {
      legacyConditions = [c as unknown as FdaCondition]
    } else {
      legacyConditions = [{ left: { view: (c.view ?? '') as string }, op: (c.op ?? '==') as FdaCondition['op'], right: (c.rhs ?? 0) as FdaOperand }]
    }
  }
  const tree: ConditionNode | undefined =
    legacyConditions.length === 0 ? undefined :
    legacyConditions.length === 1 ? legacyConditions[0] :
    { op: 'AND', children: legacyConditions }

  return { from, to, condition_tree: tree, description: t.description as string | undefined }
}

function condLabel(t: FdaTransition): string {
  const tree = t.condition_tree
  if (!tree) return '(unconditional)'
  return renderTreeLabel(tree, null)
}

function renderTreeLabel(node: ConditionNode, parentOp: 'AND' | 'OR' | null): string {
  if (!isConditionBranch(node)) {
    // Leaf: render as "left op right"
    return `${operandLabel(node.left)} ${node.op} ${operandLabel(node.right)}`
  }
  const childLabels = node.children.map(c => renderTreeLabel(c, node.op))
  const sep = node.op === 'AND' ? ' ∧ ' : ' ∨ '
  const joined = childLabels.join(sep)
  // Add parens when this node's op has lower precedence than parent's op
  // OR inside AND needs parens: (A ∨ B) ∧ C
  const needsParens = parentOp !== null && (
    (node.op === 'OR' && parentOp === 'AND') ||
    (node.op === 'AND' && parentOp === 'OR')
  )
  return needsParens ? `(${joined})` : joined
}


function normaliseFda(fdaJson: FdaJson): FdaJson {
  return {
    ...fdaJson,
    transitions: (fdaJson.transitions ?? []).map(t => normaliseTransition(t as unknown as Record<string, unknown>)),
    trigger_assignments: (fdaJson.trigger_assignments ?? []).map(normaliseTriggerAssignment),
    variables: fdaJson.variables ?? {},
  }
}

/**
 * Heal a trigger assignment saved before the handler enum was removed.
 *
 * Legacy rows (e.g. task definitions 181 and 185) carry `handler` and no `actions`
 * at all, so rendering `a.actions.length` throws and the whole editor fails to mount.
 * `actions` is required in the current schema, so default it and drop the dead keys.
 */
function normaliseTriggerAssignment(a: FdaTriggerAssignment): FdaTriggerAssignment {
  const { handler: _handler, config: _config, ...rest } =
    a as FdaTriggerAssignment & { handler?: unknown; config?: unknown }
  return {
    ...rest,
    trigger_name: rest.trigger_name ?? '',
    actions: Array.isArray(rest.actions) ? rest.actions : [],
  }
}

function parseStateWarnings(validationMessage: string | null | undefined): Record<string, string> {
  if (!validationMessage) return {}
  const result: Record<string, string> = {}
  for (const line of validationMessage.split('\n')) {
    const m = line.match(/^State '([^']+)': (.+)$/)
    if (m) {
      result[m[1]] = result[m[1]] ? `${result[m[1]]}\n${m[2]}` : m[2]
    }
  }
  return result
}

function fdaToNodes(fdaJson: FdaJson, toolkit: ToolkitRead | null, stateWarnings: Record<string, string>): Node[] {
  return Object.entries(fdaJson.states ?? {}).map(([name, state], i) => ({
    id: name,
    type: 'stateNode',
    position: { x: (i % 4) * 270, y: Math.floor(i / 4) * 170 },
    data: { name, state, isInitial: name === fdaJson.initial_state, toolkit, warning: stateWarnings[name] },
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

  const { data: hwLibVersions = [], refetch: refetchPins } = useQuery({
    queryKey: ['hw-lib-versions', taskDef?.id],
    queryFn: () => getHwLibVersions(taskDef!.id),
    enabled: !!taskDef?.id && !!toolkit,
  })

  // Changes whenever the user saves a different version — used as a cache-bust key in ActionEditor
  const versionStamp = hwLibVersions.map(e => `${e.hardware_lib_id}:${e.selected_version_id ?? 'none'}`).join(',')

  const hwModuleIds: number[] = toolkit?.hardware_module_ids ?? []
  const { data: hwModules = [] } = useQuery<HardwareModule[]>({
    queryKey: ['hw-modules-for-toolkit', hwModuleIds],
    queryFn: () => Promise.all(hwModuleIds.map(id => getHardwareModule(id))),
    enabled: hwModuleIds.length > 0,
  })
  const hwModuleNames = hwModules.map(m => m.name)

  const [fdaJson, setFdaJson] = useState<FdaJson | null>(null)
  const variableNames = Object.keys(fdaJson?.variables ?? {})
  const detectorChannels = toolkit?.detector_channels ?? []
  const [selectedState, setSelectedState] = useState<string | null>(null)
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null)
  const [editName, setEditName] = useState('')
  const [savedMsg, setSavedMsg] = useState('')
  const [hwLibsOpen, setHwLibsOpen] = useState(false)
  const [addingState, setAddingState] = useState(false)
  const [newStateName, setNewStateName] = useState('')
  const [ctxMenu, setCtxMenu] = useState<{ nodeId: string; x: number; y: number } | null>(null)
  const [condModalOpen, setCondModalOpen] = useState(false)
  const [condModalTree, setCondModalTree] = useState<ConditionNode | null>(null)

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])

  const stateWarnings = useMemo(
    () => taskDef?.validation_status === 'broken' ? parseStateWarnings(taskDef.validation_message) : {},
    [taskDef?.validation_status, taskDef?.validation_message],
  )

  // Seed the editor from the server ONCE per task definition. React Query refetches on
  // window focus and after every save; re-seeding on each refetch would overwrite whatever
  // the user is midway through building — a half-built trigger assignment (which correctly
  // does not autosave) vanished on the next refocus. After seeding, local state is
  // authoritative until the id changes.
  const seededIdRef = useRef<number | null>(null)
  useEffect(() => {
    if (!taskDef) return
    setEditName(taskDef.display_name ?? taskDef.task_name ?? '')
    if (seededIdRef.current === numId) return
    if (taskDef.fda_json) {
      seededIdRef.current = numId
      setFdaJson(normaliseFda(taskDef.fda_json))
    }
  }, [taskDef, numId])

  // Only sync canvas on initial FDA load or toolkit change — NOT on every edit
  const [canvasInited, setCanvasInited] = useState(false)
  useEffect(() => {
    if (!fdaJson || canvasInited) return
    setNodes(fdaToNodes(fdaJson, toolkit, stateWarnings))
    setEdges(fdaToEdges(fdaJson))
    setCanvasInited(true)
  }, [fdaJson, toolkit, canvasInited])

  // Sync warning badges when validation status changes (e.g. after save)
  useEffect(() => {
    if (!canvasInited) return
    setNodes(prev => prev.map(n => ({ ...n, data: { ...n.data, warning: stateWarnings[n.id] } })))
  }, [stateWarnings, canvasInited])

  // Re-sync edges when transitions change (after adding a new edge)
  useEffect(() => {
    if (!fdaJson || !canvasInited) return
    setEdges(fdaToEdges(fdaJson))
  }, [fdaJson?.transitions])

  // Re-sync nodes when state bodies change (so action count updates).
  // Also add any toolkit states missing from the current node set (e.g. new states added to toolkit after FDA was created).
  useEffect(() => {
    if (!fdaJson || !canvasInited) return
    setNodes(prev => {
      const updated = prev.map(n => ({
        ...n,
        data: {
          ...n.data,
          state: fdaJson.states[n.id] ?? n.data.state,
          toolkit,
          warning: stateWarnings[n.id],
        },
      }))
      if (!toolkit?.states) return updated
      const existingIds = new Set(prev.map(n => n.id))
      const missing = toolkit.states.filter(s => !existingIds.has(s))
      if (missing.length === 0) return updated
      // Patch fdaJson.states so missing states get included on save
      setFdaJson(f => f ? {
        ...f,
        states: { ...f.states, ...Object.fromEntries(missing.map(s => [s, {}])) },
      } : f)
      const offset = prev.length
      missing.forEach((s, i) => {
        updated.push({
          id: s,
          type: 'stateNode',
          position: { x: ((offset + i) % 4) * 270, y: Math.floor((offset + i) / 4) * 170 },
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          data: { name: s, state: {} as any, isInitial: false, toolkit } as any,
        })
      })
      return updated
    })
  }, [fdaJson?.states, toolkit, stateWarnings])

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

  // Debounced auto-save: triggers 1500ms after fdaJson changes (only after initial canvas load)
  const autoSaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => {
    if (!fdaJson || !canvasInited) return
    if (autoSaveTimerRef.current) clearTimeout(autoSaveTimerRef.current)
    // Never PUT while a trigger assignment is half-built. The backend rejects it with a
    // 422, and filtering it out of the payload instead would DELETE an already-saved
    // incomplete assignment on the next autosave. Hold the whole save until it's finished
    // or removed — nothing invalid is sent, and nothing existing is silently dropped.
    const incomplete = (fdaJson.trigger_assignments ?? []).filter(a => !isCompleteTrigger(a))
    if (incomplete.length) {
      setSavedMsg(`Not saved — finish or remove trigger '${incomplete[0].trigger_name || '(unnamed)'}'`)
      return
    }
    setSavedMsg('Unsaved…')
    autoSaveTimerRef.current = setTimeout(() => saveMutation.mutate(), 1500)
    return () => {
      if (autoSaveTimerRef.current) clearTimeout(autoSaveTimerRef.current)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fdaJson])

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
        transitions: [...prev.transitions, { from: params.source!, to: params.target! }],
      }
    })
  }, [setEdges])

  const updateTransitionTree = (edgeId: string, tree: ConditionNode | null) => {
    if (!fdaJson) return
    const idx = parseInt(edgeId.replace('e-', ''), 10)
    if (isNaN(idx) || idx < 0 || idx >= fdaJson.transitions.length) return
    const newTransitions = fdaJson.transitions.map((t, i) =>
      i === idx ? { ...t, condition_tree: tree ?? undefined, condition_groups: undefined } : t
    )
    setFdaJson(prev => prev ? { ...prev, transitions: newTransitions } : prev)
    const label = condLabel({ ...fdaJson.transitions[idx], condition_tree: tree ?? undefined })
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
      variables: {},
    })
    setCanvasInited(false)
  }

  const addState = () => {
    const name = newStateName.trim()
    if (!name || !fdaJson) return
    if (fdaJson.states[name]) { setNewStateName(''); setAddingState(false); return }
    const existingCount = Object.keys(fdaJson.states).length
    const isFirst = existingCount === 0 || !fdaJson.initial_state
    setFdaJson(prev => {
      if (!prev) return prev
      return {
        ...prev,
        states: { ...prev.states, [name]: {} },
        initial_state: isFirst ? name : prev.initial_state,
      }
    })
    setNodes(prev => [
      ...prev.map(n => isFirst ? { ...n, data: { ...n.data, isInitial: false } } : n),
      {
        id: name,
        type: 'stateNode',
        position: { x: (existingCount % 4) * 270, y: Math.floor(existingCount / 4) * 170 },
        data: { name, state: {}, isInitial: isFirst, toolkit },
      },
    ])
    setNewStateName('')
    setAddingState(false)
    setSelectedState(name)
  }

  const setInitialState = (stateName: string) => {
    setFdaJson(prev => prev ? { ...prev, initial_state: stateName } : prev)
    setNodes(prev => prev.map(n => ({
      ...n,
      data: { ...n.data, isInitial: n.id === stateName },
    })))
  }

  const deleteState = (stateName: string) => {
    setFdaJson(prev => {
      if (!prev) return prev
      const { [stateName]: _dropped, ...remainingStates } = prev.states
      return {
        ...prev,
        states: remainingStates,
        initial_state: prev.initial_state === stateName ? '' : prev.initial_state,
        transitions: prev.transitions.filter(t => t.from !== stateName && t.to !== stateName),
      }
    })
    setNodes(prev => prev.filter(n => n.id !== stateName))
    setEdges(prev => prev.filter(e => e.source !== stateName && e.target !== stateName))
    if (selectedState === stateName) setSelectedState(null)
  }

  const PANEL = 'var(--panel)'
  const BORDER = 'var(--border)'
  const MUTED = 'var(--muted)'

  const hasStates = Object.keys(fdaJson?.states ?? {}).length > 0
  const missingInitial = hasStates && !fdaJson?.initial_state

  const handleSave = () => {
    if (missingInitial) return
    saveMutation.mutate()
  }

  // Derive selected transition from edge id
  const selectedTransition = selectedEdgeId && fdaJson
    ? (() => {
        const idx = parseInt(selectedEdgeId.replace('e-', ''), 10)
        return !isNaN(idx) ? fdaJson.transitions[idx] ?? null : null
      })()
    : null

  function openCondModal() {
    setCondModalTree(selectedTransition?.condition_tree ?? null)
    setCondModalOpen(true)
  }

  function saveCondModal() {
    if (selectedEdgeId) updateTransitionTree(selectedEdgeId, condModalTree)
    setCondModalOpen(false)
  }

  function conditionSummary(tree: ConditionNode | null): string {
    if (tree === null) return 'unconditional'
    if (!isConditionBranch(tree)) return '1 condition'
    function countLeaves(n: ConditionNode): number {
      if (!isConditionBranch(n)) return 1
      return n.children.reduce((s, c) => s + countLeaves(c), 0)
    }
    const n = countLeaves(tree)
    return `${n} condition${n !== 1 ? 's' : ''} (${tree.op})`
  }

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
        {taskDef?.toolkit_name && hwLibVersions.length > 0 && (
          <button
            onClick={() => setHwLibsOpen(true)}
            title={`Hardware libraries — ${taskDef.toolkit_name}`}
            style={{
              background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer',
              fontSize: '17px', padding: '2px 4px', flexShrink: 0, lineHeight: 1,
            }}
            onMouseEnter={e => (e.currentTarget.style.color = 'var(--text)')}
            onMouseLeave={e => (e.currentTarget.style.color = 'var(--muted)')}
          >
            ⚙
          </button>
        )}
        {savedMsg && (
          <span style={{ fontSize: '12px', color: savedMsg.startsWith('Error') ? 'var(--error)' : 'var(--green)', flexShrink: 0 }}>
            {savedMsg}
          </span>
        )}
        {missingInitial && (
          <span style={{ color: '#f87171', fontSize: 12, marginRight: 8, flexShrink: 0 }}>
            No initial state set — right-click a state to set one
          </span>
        )}
        <button
          className="button-primary"
          style={{ fontSize: '12px', padding: '4px 14px', flexShrink: 0 }}
          disabled={saveMutation.isPending || !fdaJson || missingInitial}
          onClick={handleSave}
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
        <div style={{ flex: 1, background: '#0d1117', position: 'relative', display: 'flex', flexDirection: 'column' }}>
          {fdaJson && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: '8px',
              padding: '6px 12px', background: 'rgba(255,255,255,0.03)',
              borderBottom: `1px solid ${BORDER}`, flexShrink: 0,
            }}>
              {addingState ? (
                <>
                  <input
                    autoFocus
                    value={newStateName}
                    onChange={e => setNewStateName(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter') addState(); if (e.key === 'Escape') { setAddingState(false); setNewStateName('') } }}
                    placeholder="State name…"
                    style={{
                      fontFamily: "'IBM Plex Mono', monospace", fontSize: '12px',
                      background: 'var(--input-bg)', border: `1px solid ${BORDER}`,
                      borderRadius: '4px', color: 'var(--text)', padding: '3px 8px', width: '180px',
                    }}
                  />
                  <button className="button-primary" style={{ fontSize: '11px', padding: '3px 10px' }} onClick={addState}>Add</button>
                  <button className="button-secondary" style={{ fontSize: '11px', padding: '3px 10px' }} onClick={() => { setAddingState(false); setNewStateName('') }}>Cancel</button>
                </>
              ) : (
                <button
                  className="button-secondary"
                  style={{ fontSize: '11px', padding: '3px 10px' }}
                  onClick={() => setAddingState(true)}
                  title="Add a new custom state to the FDA"
                >
                  + Add State
                </button>
              )}
            </div>
          )}
          <div style={{ flex: 1, position: 'relative' }}>
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
            <>
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
                setCtxMenu(null)
              }}
              onNodeContextMenu={(e, node) => {
                e.preventDefault()
                setCtxMenu({ nodeId: node.id, x: e.clientX, y: e.clientY })
              }}
              fitView
            >
              <Background color="#1e2130" gap={20} />
              <Controls />
              <MiniMap nodeColor={() => '#2563eb'} style={{ background: '#1e2130' }} />
            </ReactFlow>
            {ctxMenu && (
              <div
                style={{
                  position: 'fixed', top: ctxMenu.y, left: ctxMenu.x,
                  background: 'var(--panel)', border: '1px solid var(--border)',
                  borderRadius: 6, padding: '4px 0', zIndex: 1000,
                  boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
                }}
                onMouseLeave={() => setCtxMenu(null)}
              >
                <button
                  style={{
                    display: 'block', width: '100%', padding: '6px 14px',
                    background: 'none', border: 'none', color: 'var(--text)',
                    cursor: 'pointer', textAlign: 'left', fontSize: 13,
                  }}
                  onClick={() => { setInitialState(ctxMenu.nodeId); setCtxMenu(null) }}
                >
                  Set as Initial State
                </button>
                <button
                  style={{
                    display: 'block', width: '100%', padding: '6px 14px',
                    background: 'none', border: 'none', color: '#f87171',
                    cursor: 'pointer', textAlign: 'left', fontSize: 13,
                  }}
                  onClick={() => { deleteState(ctxMenu.nodeId); setCtxMenu(null) }}
                >
                  Delete State
                </button>
              </div>
            )}
            </>
          )}
          </div>
        </div>

        {/* Right panel */}
        <div style={{
          width: '380px', flexShrink: 0, background: PANEL,
          borderLeft: `1px solid ${BORDER}`, padding: '14px',
          overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '12px',
        }}>
          {hwLibsOpen && (
            <HwLibVersionModal
              taskDefId={numId}
              pins={hwLibVersions}
              onClose={() => setHwLibsOpen(false)}
              onSaved={() => {
                qc.invalidateQueries({ queryKey: ['task-definition', numId] })
                refetchPins()
                setHwLibsOpen(false)
              }}
            />
          )}
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
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                <div style={{ fontSize: '11px', color: MUTED, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                  Conditions
                </div>
                <button
                  className="button-secondary"
                  style={{ fontSize: '10px', padding: '2px 10px' }}
                  onClick={openCondModal}
                >
                  Edit →
                </button>
              </div>
              <div style={{
                fontSize: '11px',
                fontStyle: selectedTransition.condition_tree ? 'normal' : 'italic',
                color: selectedTransition.condition_tree ? 'var(--text)' : MUTED,
              }}>
                {conditionSummary(selectedTransition.condition_tree ?? null)}
              </div>
            </div>
          ) : selectedState && fdaJson ? (
            <StateBodyPanel
              stateName={selectedState}
              state={fdaJson.states[selectedState] ?? {}}
              toolkit={toolkit}
              hwModules={hwModules}
              taskDefId={numId}
              versionStamp={versionStamp}
              variableNames={variableNames}
              detectorChannels={detectorChannels}
              onChange={updated => updateStateBody(selectedState, updated)}
            />
          ) : (
            <div style={{ color: MUTED, fontSize: '13px', textAlign: 'center', lineHeight: 1.6 }}>
              Click a state to edit its actions,<br />or a transition to edit its condition.
            </div>
          )}

          {/* Bottom: variables + trigger assignments always visible */}
          {fdaJson && (
            <>
              <div style={{ borderTop: `1px solid ${BORDER}`, margin: '4px 0' }} />
              <VariablesPanel
                variables={fdaJson.variables ?? {}}
                toolkit={toolkit}
                onChange={updated => setFdaJson(prev => prev ? { ...prev, variables: updated } : prev)}
              />
              <div style={{ borderTop: `1px solid ${BORDER}`, margin: '4px 0' }} />
              <TriggerAssignmentPanel
                assignments={fdaJson.trigger_assignments}
                toolkit={toolkit}
                hwModules={hwModules}
                taskDefId={numId}
                versionStamp={versionStamp}
                variableNames={variableNames}
                detectorChannels={detectorChannels}
                variables={fdaJson.variables ?? {}}
                onVariablesChange={updated =>
                  setFdaJson(prev => prev ? { ...prev, variables: updated } : prev)
                }
                onChange={updated =>
                  setFdaJson(prev => prev ? { ...prev, trigger_assignments: updated } : prev)
                }
              />
            </>
          )}
        </div>
      </div>

      {/* Condition editor modal */}
      {condModalOpen && selectedTransition && (
        <div className="modal-overlay" style={{ alignItems: 'flex-start', paddingTop: '8vh' }}>
          <div className="modal" style={{ width: '700px', maxHeight: '80vh', display: 'flex', flexDirection: 'column' }}>
            <div className="modal-header">
              <span className="modal-title" style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: '13px' }}>
                Conditions: {selectedTransition.from} → {selectedTransition.to}
              </span>
              <button className="modal-close" onClick={() => setCondModalOpen(false)}>✕</button>
            </div>

            <div className="modal-body" style={{ overflowY: 'auto', flex: 1, padding: '16px 20px' }}>
              <ConditionGroupsEditor
                tree={condModalTree}
                toolkit={toolkit}
                hwModuleNames={hwModuleNames}
                variableNames={variableNames}
                detectorChannels={detectorChannels}
                onChange={setCondModalTree}
              />
            </div>

            <div style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '12px 20px', borderTop: `1px solid ${BORDER}`, flexShrink: 0,
            }}>
              <button
                className="button-secondary"
                style={{ fontSize: '11px', color: MUTED }}
                onClick={() => setCondModalTree(null)}
              >
                Clear (unconditional)
              </button>
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="button-secondary" onClick={() => setCondModalOpen(false)}>Cancel</button>
                <button className="button-primary" onClick={saveCondModal}>Save</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
