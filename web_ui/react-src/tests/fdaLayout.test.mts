// node:test coverage of fdaLayout.mts — the BFS-ranked layered auto-layout (CANVAS-07/08) that
// replaces TaskEditor.tsx's index-grid node placement, plus (later in this file) the
// "place one new node without disturbing anything already positioned" rule and the
// unreachable-states grid block (CANVAS-14).
//
// Same layout rules as internalVariables.test.mts — outside tsconfig's include, .mts for ESM.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { columnRanks, layeredLayout } from '../src/components/fdaLayout.mts'
import type { LayoutInput, XY } from '../src/components/fdaLayout.mts'

function coordSet(positions: Record<string, XY>): Set<string> {
  return new Set(Object.values(positions).map(p => `${p.x},${p.y}`))
}

// ---------------------------------------------------------------------------
// Task 1: layeredLayout — BFS ranking, sibling spread, unreachable trailing column
// ---------------------------------------------------------------------------

test('linear chain: three distinct x values, strictly increasing in BFS order', () => {
  const input: LayoutInput = {
    states: ['IDLE', 'CUE', 'REWARD'],
    transitions: [{ from: 'IDLE', to: 'CUE' }, { from: 'CUE', to: 'REWARD' }],
    initialState: 'IDLE',
  }
  const result = layeredLayout(input)
  assert.ok(result.IDLE.x < result.CUE.x)
  assert.ok(result.CUE.x < result.REWARD.x)
})

test('two states at the same depth: same x, distinct y', () => {
  const input: LayoutInput = {
    states: ['IDLE', 'A', 'B'],
    transitions: [{ from: 'IDLE', to: 'A' }, { from: 'IDLE', to: 'B' }],
    initialState: 'IDLE',
  }
  const result = layeredLayout(input)
  assert.equal(result.A.x, result.B.x)
  assert.notEqual(result.A.y, result.B.y)
})

test('diamond: END sits one column right of A and B, not duplicated', () => {
  const input: LayoutInput = {
    states: ['IDLE', 'A', 'B', 'END'],
    transitions: [
      { from: 'IDLE', to: 'A' },
      { from: 'IDLE', to: 'B' },
      { from: 'A', to: 'END' },
      { from: 'B', to: 'END' },
    ],
    initialState: 'IDLE',
  }
  const result = layeredLayout(input)
  assert.equal(Object.keys(result).length, 4)
  assert.equal(result.END.x, result.A.x + COLUMN_SPACING())
  assert.equal(result.END.x, result.B.x + COLUMN_SPACING())
})

test('a cycle does not hang and places both states', () => {
  const input: LayoutInput = {
    states: ['A', 'B'],
    transitions: [{ from: 'A', to: 'B' }, { from: 'B', to: 'A' }],
    initialState: 'A',
  }
  const result = layeredLayout(input)
  assert.equal(Object.keys(result).length, 2)
})

test('unreachable state is placed, never dropped, in a trailing column', () => {
  const input: LayoutInput = {
    states: ['IDLE', 'ORPHAN'],
    transitions: [{ from: 'IDLE', to: 'IDLE' }],
    initialState: 'IDLE',
  }
  const result = layeredLayout(input)
  assert.equal(Object.keys(result).length, 2)
  assert.ok(result.ORPHAN.x > result.IDLE.x)
})

test('two unreachable states get the same trailing x and distinct y', () => {
  const input: LayoutInput = {
    states: ['IDLE', 'A', 'B'],
    transitions: [{ from: 'IDLE', to: 'IDLE' }],
    initialState: 'IDLE',
  }
  const result = layeredLayout(input)
  assert.equal(result.A.x, result.B.x)
  assert.notEqual(result.A.y, result.B.y)
})

test('no two states share a coordinate, across every case above', () => {
  const cases: LayoutInput[] = [
    { states: ['IDLE', 'CUE', 'REWARD'], transitions: [{ from: 'IDLE', to: 'CUE' }, { from: 'CUE', to: 'REWARD' }], initialState: 'IDLE' },
    { states: ['IDLE', 'A', 'B'], transitions: [{ from: 'IDLE', to: 'A' }, { from: 'IDLE', to: 'B' }], initialState: 'IDLE' },
    { states: ['IDLE', 'A', 'B', 'END'], transitions: [{ from: 'IDLE', to: 'A' }, { from: 'IDLE', to: 'B' }, { from: 'A', to: 'END' }, { from: 'B', to: 'END' }], initialState: 'IDLE' },
    { states: ['A', 'B'], transitions: [{ from: 'A', to: 'B' }, { from: 'B', to: 'A' }], initialState: 'A' },
    { states: ['IDLE', 'ORPHAN'], transitions: [{ from: 'IDLE', to: 'IDLE' }], initialState: 'IDLE' },
    { states: ['IDLE', 'A', 'B'], transitions: [{ from: 'IDLE', to: 'IDLE' }], initialState: 'IDLE' },
  ]
  for (const input of cases) {
    const result = layeredLayout(input)
    assert.equal(coordSet(result).size, input.states.length)
  }
})

test('empty states returns {} without throwing', () => {
  assert.deepEqual(layeredLayout({ states: [], transitions: [], initialState: '' }), {})
})

test('a single state returns one entry without throwing', () => {
  const result = layeredLayout({ states: ['ONLY'], transitions: [], initialState: 'ONLY' })
  assert.equal(Object.keys(result).length, 1)
})

test("initialState '' places every state, all in the trailing column (no root => all unreachable)", () => {
  const input: LayoutInput = { states: ['A', 'B', 'C'], transitions: [{ from: 'A', to: 'B' }], initialState: '' }
  const result = layeredLayout(input)
  assert.equal(Object.keys(result).length, 3)
  assert.equal(result.A.x, result.B.x)
  assert.equal(result.B.x, result.C.x)
  assert.equal(coordSet(result).size, 3)
})

test('initialState naming a state absent from states does not throw and places everything', () => {
  const input: LayoutInput = { states: ['X', 'Y'], transitions: [], initialState: 'Z' }
  const result = layeredLayout(input)
  assert.equal(Object.keys(result).length, 2)
})

test('self-transitions do not affect ranking or create a phantom column', () => {
  const input: LayoutInput = { states: ['A'], transitions: [{ from: 'A', to: 'A' }], initialState: 'A' }
  assert.deepEqual(columnRanks(input), { A: 0 })
  const result = layeredLayout(input)
  assert.equal(Object.keys(result).length, 1)
})

test('columnRanks on the definition-186 topology pins the exact map plan 29-02 depends on', () => {
  const input: LayoutInput = {
    states: ['init', 'trial_onset', 'play_led', 'rand'],
    transitions: [
      { from: 'init', to: 'trial_onset' },
      { from: 'trial_onset', to: 'play_led' },
      { from: 'play_led', to: 'rand' },
      { from: 'rand', to: 'trial_onset' },
      { from: 'rand', to: 'play_led' },
    ],
    initialState: 'init',
  }
  assert.deepEqual(columnRanks(input), { init: 0, trial_onset: 1, play_led: 2, rand: 3 })
})

test('columnRanks omits unreachable states entirely (absent key, not -1)', () => {
  const input: LayoutInput = { states: ['IDLE', 'ORPHAN'], transitions: [], initialState: 'IDLE' }
  const ranks = columnRanks(input)
  assert.equal('ORPHAN' in ranks, false)
})

test("layeredLayout's column for every reachable state equals its columnRanks value", () => {
  const input: LayoutInput = {
    states: ['init', 'trial_onset', 'play_led', 'rand', 'ORPHAN'],
    transitions: [
      { from: 'init', to: 'trial_onset' },
      { from: 'trial_onset', to: 'play_led' },
      { from: 'play_led', to: 'rand' },
      { from: 'rand', to: 'trial_onset' },
    ],
    initialState: 'init',
  }
  const ranks = columnRanks(input)
  const layout = layeredLayout(input)
  const spacing = layout.trial_onset.x - layout.init.x // COLUMN_SPACING, derived rather than hardcoded twice
  for (const state of Object.keys(ranks)) {
    assert.equal(layout[state].x, ranks[state] * spacing)
  }
})

// Reads COLUMN_SPACING indirectly via two known-adjacent layout x values, so this test file never
// hardcodes the constant and cannot drift from the module if it is retuned later.
function COLUMN_SPACING(): number {
  const probe = layeredLayout({ states: ['A', 'B'], transitions: [{ from: 'A', to: 'B' }], initialState: 'A' })
  return probe.B.x - probe.A.x
}
