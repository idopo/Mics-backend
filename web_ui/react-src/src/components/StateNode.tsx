import { Handle, Position, type NodeProps } from '@xyflow/react'
import type { FdaState, ToolkitRead } from '../types'

export type StateNodeData = {
  name: string
  state: FdaState
  isInitial: boolean
  toolkit: ToolkitRead | null
}

function isPassthrough(name: string, state: FdaState, toolkit: ToolkitRead | null): boolean {
  if (state.entry_actions && state.entry_actions.length > 0) return false
  if (!toolkit?.states) return false
  return toolkit.states.includes(name)
}

export default function StateNode({ data, selected }: NodeProps) {
  const { name, state, isInitial, toolkit } = data as StateNodeData
  const passthrough = isPassthrough(name, state, toolkit)

  const nodeColor = isInitial ? '#7c3aed' : passthrough ? '#6b7280' : '#2563eb'
  const actionCount = state.entry_actions?.length ?? 0

  return (
    <div
      style={{
        background: '#1e2130',
        border: '1px solid #2d3148',
        borderLeft: `4px solid ${nodeColor}`,
        borderRadius: '8px',
        padding: '10px 14px',
        minWidth: '180px',
        cursor: 'pointer',
        boxShadow: selected
          ? `0 0 0 2px ${nodeColor}, 0 0 16px color-mix(in srgb, ${nodeColor} 40%, transparent)`
          : `0 0 12px color-mix(in srgb, ${nodeColor} 20%, transparent)`,
        color: '#e2e8f0',
        fontFamily: 'monospace',
        fontSize: '13px',
        userSelect: 'none',
      }}
    >
      {!isInitial && <Handle type="target" position={Position.Left} style={{ background: nodeColor, width: 11, height: 11 }} />}

      <div style={{ fontWeight: 600, marginBottom: '4px', letterSpacing: '0.03em' }}>
        {name}
        {isInitial && (
          <span style={{ marginLeft: '6px', fontSize: '10px', color: '#a78bfa', verticalAlign: 'middle' }}>
            INIT
          </span>
        )}
      </div>

      <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
        {passthrough ? (
          <span style={{ fontSize: '11px', color: '#9ca3af' }}>
            {'\u{1F512}'} {'{py}'}
          </span>
        ) : (
          <span style={{ fontSize: '11px', color: '#94a3b8' }}>
            {actionCount} action{actionCount !== 1 ? 's' : ''}
          </span>
        )}
        {state.wait_condition && (
          <span style={{ fontSize: '10px', color: '#60a5fa' }} title="Has wait_condition">
            {'\u23F3'}
          </span>
        )}
      </div>

      <Handle type="source" position={Position.Right} style={{ background: nodeColor, width: 11, height: 11 }} />
    </div>
  )
}
