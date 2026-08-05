// node:test coverage of fdaNormalise.mts — the legacy FDA migration paths a stored task
// definition still exercises today (condition_groups DNF, flat conditions[], from_state/
// next_state, handler-bearing trigger assignments). None of these had a test before this
// extraction; they are pinned here so a later refactor can't silently break a stored row.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  normaliseFda,
  normaliseTransition,
  normaliseTriggerAssignment,
  parseStateWarnings,
} from '../src/components/fdaNormalise.mts'
import type { FdaCondition, FdaJson, FdaTriggerAssignment } from '../src/types/index.ts'

const c1: FdaCondition = { left: { view: 'a' }, op: '==', right: 1 }
const c2: FdaCondition = { left: { view: 'b' }, op: '==', right: 2 }
const c3: FdaCondition = { left: { view: 'c' }, op: '==', right: 3 }

test('normaliseTransition: condition_tree already present is returned unchanged', () => {
  const tree = { left: { view: 'x' }, op: '==' as const, right: 1 }
  const result = normaliseTransition({ from: 'A', to: 'B', condition_tree: tree, description: 'd' })
  assert.deepEqual(result, { from: 'A', to: 'B', condition_tree: tree, description: 'd' })
})

test('normaliseTransition: legacy from_state/next_state map to from/to', () => {
  const result = normaliseTransition({ from_state: 'A', next_state: 'B' })
  assert.equal(result.from, 'A')
  assert.equal(result.to, 'B')
  assert.equal(result.condition_tree, undefined)
})

test('normaliseTransition: condition_groups with ONE group of ONE condition is a bare leaf', () => {
  const result = normaliseTransition({ from: 'A', to: 'B', condition_groups: [{ conditions: [c1] }] })
  assert.deepEqual(result.condition_tree, c1)
})

test('normaliseTransition: condition_groups with ONE group of TWO conditions is a single AND', () => {
  const result = normaliseTransition({ from: 'A', to: 'B', condition_groups: [{ conditions: [c1, c2] }] })
  assert.deepEqual(result.condition_tree, { op: 'AND', children: [c1, c2] })
})

test('normaliseTransition: condition_groups with TWO groups is OR-of-AND', () => {
  const result = normaliseTransition({
    from: 'A', to: 'B',
    condition_groups: [{ conditions: [c1] }, { conditions: [c2, c3] }],
  })
  assert.deepEqual(result.condition_tree, {
    op: 'OR',
    children: [c1, { op: 'AND', children: [c2, c3] }],
  })
})

test('normaliseTransition: a group with zero conditions is filtered out', () => {
  const result = normaliseTransition({
    from: 'A', to: 'B',
    condition_groups: [{ conditions: [] }, { conditions: [c1] }],
  })
  assert.deepEqual(result.condition_tree, c1)
})

test('normaliseTransition: condition_groups: [] falls through to the legacy path', () => {
  const result = normaliseTransition({ from: 'A', to: 'B', condition_groups: [] })
  assert.equal(result.condition_tree, undefined)
})

test('normaliseTransition: legacy flat conditions[] becomes a single AND', () => {
  const result = normaliseTransition({ from: 'A', to: 'B', conditions: [c1, c2] })
  assert.deepEqual(result.condition_tree, { op: 'AND', children: [c1, c2] })
})

test('normaliseTransition: legacy singular condition {view,op,rhs} becomes a leaf', () => {
  const result = normaliseTransition({ from: 'A', to: 'B', condition: { view: 'x', op: '>', rhs: 3 } })
  assert.deepEqual(result.condition_tree, { left: { view: 'x' }, op: '>', right: 3 })
})

test('normaliseTransition: legacy singular condition that already has left is used directly', () => {
  const leaf = { left: { view: 'y' }, op: '==', right: 5 }
  const result = normaliseTransition({ from: 'A', to: 'B', condition: leaf })
  assert.deepEqual(result.condition_tree, leaf)
})

test('normaliseTransition: no conditions at all yields undefined condition_tree', () => {
  const result = normaliseTransition({ from: 'A', to: 'B' })
  assert.equal(result.condition_tree, undefined)
})

test('normaliseTriggerAssignment: drops handler and config, defaults missing actions to []', () => {
  const input = {
    trigger_name: 'TOUCH_INT',
    handler: 'digital_input',
    config: { hardware_ref: 'MPR121' },
  } as unknown as FdaTriggerAssignment
  const result = normaliseTriggerAssignment(input)
  assert.deepEqual(result, { trigger_name: 'TOUCH_INT', actions: [] })
})

test('normaliseFda: defaults transitions, trigger_assignments, and variables when absent', () => {
  const input = { version: 2, initial_state: 'A', states: {} } as unknown as FdaJson
  const result = normaliseFda(input)
  assert.deepEqual(result.transitions, [])
  assert.deepEqual(result.trigger_assignments, [])
  assert.deepEqual(result.variables, {})
})

test('parseStateWarnings(null) is {}', () => {
  assert.deepEqual(parseStateWarnings(null), {})
})

test('parseStateWarnings: a single "State \'CUE\': msg" line', () => {
  assert.deepEqual(parseStateWarnings("State 'CUE': msg"), { CUE: 'msg' })
})

test('parseStateWarnings: two lines for the same state are joined with \\n', () => {
  const message = "State 'CUE': first\nState 'CUE': second"
  assert.deepEqual(parseStateWarnings(message), { CUE: 'first\nsecond' })
})

test('parseStateWarnings: a non-matching line is ignored', () => {
  const message = "not a state warning\nState 'CUE': msg"
  assert.deepEqual(parseStateWarnings(message), { CUE: 'msg' })
})
