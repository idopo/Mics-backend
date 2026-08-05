// Condition-label rendering for FDA transition edges, extracted verbatim from TaskEditor.tsx.
//
// This text is frozen by contract: Phase 29 is free to change WHERE a label is placed, but
// never what it says. See tests/transitionLabel.test.mts for the byte-identical assertions
// this extraction exists to protect.
import type { ConditionNode, FdaTransition } from '../types/index.ts'
import { isConditionBranch } from '../types/index.ts'
import { operandLabel } from './operandTypes.mts'

export function condLabel(t: FdaTransition): string {
  const tree = t.condition_tree
  if (!tree) return '(unconditional)'
  return renderTreeLabel(tree, null)
}

export function renderTreeLabel(node: ConditionNode, parentOp: 'AND' | 'OR' | null): string {
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
