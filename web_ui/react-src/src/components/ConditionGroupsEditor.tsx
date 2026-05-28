import React from 'react'
import type { ConditionNode, FdaCondition, ToolkitRead } from '../types'
import { isConditionBranch } from '../types'
import { ConditionRow } from './ConditionBuilder'

const EMPTY_LEAF: FdaCondition = { left: { view: '' }, op: '==', right: 0 }

// Use app palette: lavender for AND, green for OR — both at low opacity to stay subtle
const AND_BORDER = 'rgba(129,140,248,0.4)'
const OR_BORDER  = 'rgba(52,211,153,0.38)'
const AND_PILL_BG   = 'rgba(129,140,248,0.08)'
const OR_PILL_BG    = 'rgba(52,211,153,0.07)'
const AND_PILL_TEXT = 'rgba(129,140,248,0.8)'
const OR_PILL_TEXT  = 'rgba(52,211,153,0.8)'

type Path = number[]

function updateNode(tree: ConditionNode, path: Path, updated: ConditionNode): ConditionNode {
  if (path.length === 0) return updated
  if (!isConditionBranch(tree)) return tree
  const [head, ...tail] = path
  return { ...tree, children: tree.children.map((child, i) => i === head ? updateNode(child, tail, updated) : child) }
}

function deleteNode(tree: ConditionNode, path: Path): ConditionNode | null {
  if (path.length === 0) return null
  if (!isConditionBranch(tree)) return tree
  const [head, ...tail] = path
  let newChildren: (ConditionNode | null)[]
  if (tail.length === 0) {
    newChildren = tree.children.filter((_, i) => i !== head)
  } else {
    newChildren = tree.children.map((child, i) => i === head ? deleteNode(child, tail) : child)
  }
  const filtered = newChildren.filter((c): c is ConditionNode => c !== null)
  if (filtered.length === 0) return null
  if (filtered.length === 1) return filtered[0]
  return { ...tree, children: filtered }
}

function addAndSibling(tree: ConditionNode, path: Path): ConditionNode {
  if (path.length === 0) {
    return { op: 'AND', children: [tree, { ...EMPTY_LEAF }] }
  }
  const parentPath = path.slice(0, -1)
  const idx = path[path.length - 1]
  const parent = getNodeAt(tree, parentPath)
  if (parent && isConditionBranch(parent) && parent.op === 'AND') {
    const newChildren = [...parent.children.slice(0, idx + 1), { ...EMPTY_LEAF }, ...parent.children.slice(idx + 1)]
    return updateNode(tree, parentPath, { ...parent, children: newChildren })
  }
  const target = getNodeAt(tree, path)!
  const andBranch: ConditionNode = { op: 'AND', children: [target, { ...EMPTY_LEAF }] }
  return updateNode(tree, path, andBranch)
}

function addOrSibling(tree: ConditionNode, path: Path): ConditionNode {
  if (path.length === 0) {
    return { op: 'OR', children: [tree, { ...EMPTY_LEAF }] }
  }
  const parentPath = path.slice(0, -1)
  const idx = path[path.length - 1]
  const parent = getNodeAt(tree, parentPath)
  if (parent && isConditionBranch(parent) && parent.op === 'OR') {
    // Parent is already OR → insert as sibling
    const newChildren = [...parent.children.slice(0, idx + 1), { ...EMPTY_LEAF }, ...parent.children.slice(idx + 1)]
    return updateNode(tree, parentPath, { ...parent, children: newChildren })
  }
  // Parent is AND (or root) → wrap just this leaf in a new OR group, nested in place
  const target = getNodeAt(tree, path)!
  return updateNode(tree, path, { op: 'OR', children: [target, { ...EMPTY_LEAF }] })
}

function getNodeAt(tree: ConditionNode, path: Path): ConditionNode | null {
  if (path.length === 0) return tree
  if (!isConditionBranch(tree)) return null
  const [head, ...tail] = path
  if (head >= tree.children.length) return null
  return getNodeAt(tree.children[head], tail)
}

interface Props {
  tree: ConditionNode | null
  toolkit: ToolkitRead | null
  hwModuleNames?: string[]
  onChange: (tree: ConditionNode | null) => void
}

export function ConditionGroupsEditor({ tree, toolkit, hwModuleNames, onChange }: Props) {

  function renderNode(node: ConditionNode, path: Path): React.ReactNode {
    if (isConditionBranch(node)) {
      const border   = node.op === 'AND' ? AND_BORDER   : OR_BORDER
      const pillBg   = node.op === 'AND' ? AND_PILL_BG   : OR_PILL_BG
      const pillText = node.op === 'AND' ? AND_PILL_TEXT : OR_PILL_TEXT

      return (
        <div
          key={path.join('-')}
          style={{ borderLeft: `2px solid ${border}`, paddingLeft: 12, marginBottom: 8 }}
        >
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
            <span style={{
              background: pillBg,
              color: pillText,
              border: `1px solid ${border}`,
              borderRadius: 3,
              padding: '1px 7px',
              fontSize: 10,
              fontWeight: 600,
              letterSpacing: '0.09em',
              textTransform: 'uppercase',
            }}>
              {node.op}
            </span>
            {path.length > 0 && (
              <button
                onClick={() => onChange(deleteNode(tree!, path))}
                onMouseEnter={e => (e.currentTarget.style.color = 'var(--error)')}
                onMouseLeave={e => (e.currentTarget.style.color = 'var(--muted)')}
                style={{
                  marginLeft: 'auto', background: 'none', border: 'none',
                  color: 'var(--muted)', cursor: 'pointer', fontSize: 11, padding: '1px 4px',
                }}
                title="Remove group"
              >
                ✕ Remove group
              </button>
            )}
          </div>

          {node.children.map((child, i) => (
            <React.Fragment key={i}>
              {renderNode(child, [...path, i])}
            </React.Fragment>
          ))}
        </div>
      )
    }

    const leaf = node
    return (
      <div
        key={path.join('-')}
        style={{
          background: 'rgba(255,255,255,0.025)',
          border: '1px solid var(--border)',
          borderRadius: 4,
          marginBottom: 8,
        }}
      >
        <div style={{ padding: '10px 10px 6px', display: 'flex', gap: 8, alignItems: 'flex-start' }}>
          <div style={{ flex: 1 }}>
            <ConditionRow
              condition={leaf}
              toolkit={toolkit}
              hwModuleNames={hwModuleNames}
              onChange={updated => onChange(updateNode(tree!, path, updated))}
            />
          </div>
          <button
            onClick={() => onChange(deleteNode(tree!, path))}
            onMouseEnter={e => (e.currentTarget.style.color = 'var(--error)')}
            onMouseLeave={e => (e.currentTarget.style.color = 'var(--muted)')}
            style={{
              background: 'none', border: 'none',
              color: 'var(--muted)', cursor: 'pointer',
              fontSize: 14, padding: '2px 4px', flexShrink: 0,
            }}
            title="Remove condition"
          >
            ✕
          </button>
        </div>

        <div style={{
          padding: '5px 10px 8px', display: 'flex', gap: 4,
          borderTop: '1px solid var(--border)',
        }}>
          <button
            onClick={() => onChange(addAndSibling(tree!, path))}
            onMouseEnter={e => (e.currentTarget.style.background = AND_PILL_BG)}
            onMouseLeave={e => (e.currentTarget.style.background = 'none')}
            style={{
              background: 'none', border: `1px solid ${AND_BORDER}`, color: AND_PILL_TEXT,
              cursor: 'pointer', fontSize: 10, padding: '2px 8px', borderRadius: 3,
              fontWeight: 600, letterSpacing: '0.06em',
            }}
          >+ AND</button>
          <button
            onClick={() => onChange(addOrSibling(tree!, path))}
            onMouseEnter={e => (e.currentTarget.style.background = OR_PILL_BG)}
            onMouseLeave={e => (e.currentTarget.style.background = 'none')}
            style={{
              background: 'none', border: `1px solid ${OR_BORDER}`, color: OR_PILL_TEXT,
              cursor: 'pointer', fontSize: 10, padding: '2px 8px', borderRadius: 3,
              fontWeight: 600, letterSpacing: '0.06em',
            }}
          >+ OR</button>
        </div>
      </div>
    )
  }

  if (tree === null) {
    return (
      <div>
        <div style={{ fontSize: 12, color: 'var(--muted)', padding: '2px 0 10px', fontStyle: 'italic' }}>
          No condition — transition fires immediately.
        </div>
        <button
          onClick={() => onChange({ ...EMPTY_LEAF })}
          style={{
            width: '100%', background: 'none',
            border: '1px dashed var(--border)', color: 'var(--lavender)',
            cursor: 'pointer', borderRadius: 4, padding: '8px 14px', fontSize: 12,
          }}
        >
          + Add condition
        </button>
      </div>
    )
  }

  return <div>{renderNode(tree, [])}</div>
}
