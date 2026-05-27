import React from 'react'
import type { ConditionNode, FdaCondition, ToolkitRead } from '../types'
import { isConditionBranch } from '../types'
import { ConditionRow } from './ConditionBuilder'

const EMPTY_LEAF: FdaCondition = { left: { view: '' }, op: '==', right: 0 }

type Path = number[]

// --- Pure tree mutation helpers ---

function updateNode(tree: ConditionNode, path: Path, updated: ConditionNode): ConditionNode {
  if (path.length === 0) return updated
  if (!isConditionBranch(tree)) return tree  // can't descend into leaf
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
  if (filtered.length === 0) return null       // empty branch → remove
  if (filtered.length === 1) return filtered[0] // single child → collapse branch
  return { ...tree, children: filtered }
}

function addAndSibling(tree: ConditionNode, path: Path): ConditionNode {
  if (path.length === 0) {
    // root node — wrap root + new leaf in AND
    return { op: 'AND', children: [tree, { ...EMPTY_LEAF }] }
  }
  const parentPath = path.slice(0, -1)
  const idx = path[path.length - 1]
  const parent = getNodeAt(tree, parentPath)
  if (parent && isConditionBranch(parent) && parent.op === 'AND') {
    // insert after idx in existing AND-parent
    const newChildren = [...parent.children.slice(0, idx + 1), { ...EMPTY_LEAF }, ...parent.children.slice(idx + 1)]
    return updateNode(tree, parentPath, { ...parent, children: newChildren })
  }
  // parent is OR (or root reached): wrap the target sibling + new leaf in a new AND-branch
  const target = getNodeAt(tree, path)!
  const andBranch: ConditionNode = { op: 'AND', children: [target, { ...EMPTY_LEAF }] }
  return updateNode(tree, path, andBranch)
}

function addOrSibling(tree: ConditionNode, path: Path): ConditionNode {
  if (path.length === 0) {
    // root — wrap root + new leaf in OR
    return { op: 'OR', children: [tree, { ...EMPTY_LEAF }] }
  }
  const parentPath = path.slice(0, -1)
  const idx = path[path.length - 1]
  const parent = getNodeAt(tree, parentPath)
  if (parent && isConditionBranch(parent) && parent.op === 'OR') {
    const newChildren = [...parent.children.slice(0, idx + 1), { ...EMPTY_LEAF }, ...parent.children.slice(idx + 1)]
    return updateNode(tree, parentPath, { ...parent, children: newChildren })
  }
  // No OR-ancestor at this level — wrap entire tree in OR
  return { op: 'OR', children: [tree, { ...EMPTY_LEAF }] }
}

function getNodeAt(tree: ConditionNode, path: Path): ConditionNode | null {
  if (path.length === 0) return tree
  if (!isConditionBranch(tree)) return null
  const [head, ...tail] = path
  if (head >= tree.children.length) return null
  return getNodeAt(tree.children[head], tail)
}

function depthBackground(depth: number): string {
  if (depth === 0) return 'transparent'
  if (depth === 1) return 'rgba(255,255,255,0.03)'
  if (depth === 2) return 'rgba(255,255,255,0.055)'
  return 'rgba(255,255,255,0.08)'
}

// --- Component ---

interface Props {
  tree: ConditionNode | null
  toolkit: ToolkitRead | null
  hwModuleNames?: string[]
  onChange: (tree: ConditionNode | null) => void
}

export function ConditionGroupsEditor({ tree, toolkit, hwModuleNames, onChange }: Props) {

  function renderNode(node: ConditionNode, path: Path, depth: number): React.ReactNode {
    if (isConditionBranch(node)) {
      return (
        <div
          key={path.join('-')}
          style={{ border: '1px solid var(--border)', borderRadius: 4, padding: '6px 8px',
                   marginBottom: 4, background: depthBackground(depth) }}
        >
          {node.children.map((child, i) => (
            <React.Fragment key={i}>
              {i > 0 && (
                <div style={{ fontSize: 10, color: 'var(--accent)', fontWeight: 700,
                              letterSpacing: 1, padding: '2px 0' }}>
                  {node.op}
                </div>
              )}
              {renderNode(child, [...path, i], depth + 1)}
            </React.Fragment>
          ))}
        </div>
      )
    }

    // Leaf node
    const leaf = node
    return (
      <div key={path.join('-')} style={{ marginBottom: 4 }}>
        <ConditionRow
          condition={leaf}
          toolkit={toolkit}
          hwModuleNames={hwModuleNames}
          onChange={updated => onChange(updateNode(tree!, path, updated))}
          onDelete={() => onChange(deleteNode(tree!, path))}
        />
        <div style={{ marginTop: 3 }}>
          <button
            onClick={() => onChange(addAndSibling(tree!, path))}
            style={{ background: 'none', border: 'none', color: 'var(--accent)', cursor: 'pointer',
                     fontSize: 11, padding: '2px 6px', marginRight: 4 }}
          >+AND</button>
          <button
            onClick={() => onChange(addOrSibling(tree!, path))}
            style={{ background: 'none', border: 'none', color: 'var(--accent)', cursor: 'pointer',
                     fontSize: 11, padding: '2px 6px' }}
          >+OR</button>
        </div>
      </div>
    )
  }

  if (tree === null) {
    return (
      <div>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', padding: '2px 0 6px', fontStyle: 'italic' }}>
          unconditional — fires immediately
        </div>
        <button
          onClick={() => onChange({ ...EMPTY_LEAF })}
          style={{ marginTop: 2, fontSize: 11, background: 'none',
                   border: '1px dashed var(--border)', color: 'var(--accent)',
                   cursor: 'pointer', borderRadius: 4, padding: '4px 10px', width: '100%' }}
        >+ Add condition</button>
      </div>
    )
  }

  return <div>{renderNode(tree, [], 0)}</div>
}
