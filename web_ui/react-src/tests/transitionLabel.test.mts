// node:test coverage of transitionLabel.mts — the condition-label TEXT the FDA editor renders
// on every transition edge. These are exact-string assertions on purpose: the point of this
// extraction is to freeze today's output so a later Phase 29 plan cannot silently drift it
// (CANVAS-02). Expected strings were derived by reading condLabel/renderTreeLabel, not by
// running the app.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { condLabel, renderTreeLabel } from '../src/components/transitionLabel.mts'
import type { ConditionNode, FdaTransition } from '../src/types/index.ts'

const leaf = (view: string, right: number): ConditionNode => ({
  left: { view }, op: '==', right,
})

test('leaf condition renders "left op right"', () => {
  const t: FdaTransition = { from: 'A', to: 'B', condition_tree: { left: { view: 'lick' }, op: '==', right: 1 } }
  assert.equal(condLabel(t), 'lick == 1')
})

test('no condition_tree at all renders "(unconditional)"', () => {
  const t: FdaTransition = { from: 'A', to: 'B' }
  assert.equal(condLabel(t), '(unconditional)')
})

test('AND of two leaves joined by " ∧ ", no parens', () => {
  const t: FdaTransition = {
    from: 'A', to: 'B',
    condition_tree: { op: 'AND', children: [leaf('a', 1), leaf('b', 2)] },
  }
  assert.equal(condLabel(t), 'a == 1 ∧ b == 2')
})

test('OR of two leaves joined by " ∨ ", no parens', () => {
  const t: FdaTransition = {
    from: 'A', to: 'B',
    condition_tree: { op: 'OR', children: [leaf('a', 1), leaf('b', 2)] },
  }
  assert.equal(condLabel(t), 'a == 1 ∨ b == 2')
})

test('OR nested inside AND is parenthesised', () => {
  const t: FdaTransition = {
    from: 'A', to: 'B',
    condition_tree: {
      op: 'AND',
      children: [{ op: 'OR', children: [leaf('a', 1), leaf('b', 2)] }, leaf('c', 3)],
    },
  }
  assert.equal(condLabel(t), '(a == 1 ∨ b == 2) ∧ c == 3')
})

test('AND nested inside OR is parenthesised', () => {
  const t: FdaTransition = {
    from: 'A', to: 'B',
    condition_tree: {
      op: 'OR',
      children: [{ op: 'AND', children: [leaf('a', 1), leaf('b', 2)] }, leaf('c', 3)],
    },
  }
  assert.equal(condLabel(t), '(a == 1 ∧ b == 2) ∨ c == 3')
})

test('AND nested inside AND is NOT parenthesised (same-op nesting stays flat)', () => {
  const t: FdaTransition = {
    from: 'A', to: 'B',
    condition_tree: {
      op: 'AND',
      children: [{ op: 'AND', children: [leaf('a', 1), leaf('b', 2)] }, leaf('c', 3)],
    },
  }
  assert.equal(condLabel(t), 'a == 1 ∧ b == 2 ∧ c == 3')
})

test('three-level nest (AND > OR > AND) parenthesises at both switch points', () => {
  const t: FdaTransition = {
    from: 'A', to: 'B',
    condition_tree: {
      op: 'AND',
      children: [
        {
          op: 'OR',
          children: [{ op: 'AND', children: [leaf('a', 1), leaf('b', 2)] }, leaf('c', 3)],
        },
        leaf('d', 4),
      ],
    },
  }
  assert.equal(condLabel(t), '((a == 1 ∧ b == 2) ∨ c == 3) ∧ d == 4')
})

test('null/undefined operands fall through to operandLabel\'s "?"', () => {
  const t: FdaTransition = {
    from: 'A', to: 'B',
    condition_tree: { left: null, op: '==', right: undefined as unknown as number },
  }
  assert.equal(condLabel(t), '? == ?')
})

test('renderTreeLabel is exported directly and behaves identically to condLabel\'s delegate call', () => {
  const node: ConditionNode = { op: 'OR', children: [leaf('a', 1), leaf('b', 2)] }
  assert.equal(renderTreeLabel(node, null), 'a == 1 ∨ b == 2')
})
