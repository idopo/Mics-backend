// node:test coverage of fdaLayout.mts — the BFS-ranked layered auto-layout (CANVAS-07/08) that
// replaces TaskEditor.tsx's index-grid node placement, plus (later in this file) the
// "place one new node without disturbing anything already positioned" rule and the
// unreachable-states grid block (CANVAS-14).
//
// Same layout rules as internalVariables.test.mts — outside tsconfig's include, .mts for ESM.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { columnRanks, layeredLayout, placeNewState, resolvePositions } from '../src/components/fdaLayout.mts'
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

test("initialState '' places every state — no root => all unreachable, packed into the orphan block (Task 3 bounds its shape)", () => {
  const input: LayoutInput = { states: ['A', 'B', 'C'], transitions: [{ from: 'A', to: 'B' }], initialState: '' }
  const result = layeredLayout(input)
  assert.equal(Object.keys(result).length, 3)
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

function ROW_SPACING(): number {
  const probe = layeredLayout({ states: ['A', 'B', 'C'], transitions: [{ from: 'C', to: 'A' }, { from: 'C', to: 'B' }], initialState: 'C' })
  return probe.B.y - probe.A.y
}

// ---------------------------------------------------------------------------
// Task 2: placeNewState and resolvePositions — never disturb what is already positioned
// ---------------------------------------------------------------------------

test('placeNewState({}) returns some position without throwing', () => {
  const pos = placeNewState({})
  assert.equal(typeof pos.x, 'number')
  assert.equal(typeof pos.y, 'number')
})

test('placeNewState collides with nothing in taken, with a minimum separation', () => {
  const taken: Record<string, XY> = { A: { x: 0, y: 0 }, B: { x: 320, y: 0 }, C: { x: 0, y: 180 } }
  const pos = placeNewState(taken)
  const colSpacing = COLUMN_SPACING()
  const rowSpacing = ROW_SPACING()
  for (const existing of Object.values(taken)) {
    const withinX = Math.abs(existing.x - pos.x) < colSpacing / 2
    const withinY = Math.abs(existing.y - pos.y) < rowSpacing / 2
    assert.equal(withinX && withinY, false)
  }
})

test('placeNewState never mutates or returns its taken argument (CANVAS-08 regression)', () => {
  const taken: Record<string, XY> = { A: { x: 0, y: 0 }, B: { x: 320, y: 180 } }
  const snapshot = structuredClone(taken)
  placeNewState(taken)
  assert.deepEqual(taken, snapshot)
})

test('two states added in a row do not stack: second call returns a different position', () => {
  const first = placeNewState({})
  const second = placeNewState({ a: first })
  assert.notDeepEqual(second, first)
})

test('resolvePositions(input, null) deep-equals layeredLayout(input)', () => {
  const input: LayoutInput = { states: ['A', 'B'], transitions: [{ from: 'A', to: 'B' }], initialState: 'A' }
  assert.deepEqual(resolvePositions(input, null), layeredLayout(input))
})

test('resolvePositions(input, {}) deep-equals layeredLayout(input) — empty stored is "nothing stored"', () => {
  const input: LayoutInput = { states: ['A', 'B'], transitions: [{ from: 'A', to: 'B' }], initialState: 'A' }
  assert.deepEqual(resolvePositions(input, {}), layeredLayout(input))
})

test('resolvePositions(input, fullStoredMap) returns each stored position deep-equal, no extra keys', () => {
  const input: LayoutInput = { states: ['A', 'B'], transitions: [{ from: 'A', to: 'B' }], initialState: 'A' }
  const stored: Record<string, XY> = { A: { x: 5, y: 5 }, B: { x: 500, y: -50 } }
  const result = resolvePositions(input, stored)
  assert.deepEqual(result.A, stored.A)
  assert.deepEqual(result.B, stored.B)
  assert.deepEqual(Object.keys(result).sort(), ['A', 'B'])
})

test('partial stored map: stored states come back byte-identical, missing one is added without colliding', () => {
  const input: LayoutInput = { states: ['A', 'B', 'C'], transitions: [], initialState: '' }
  const stored: Record<string, XY> = { A: { x: 12, y: 34 }, B: { x: 999, y: -1 } }
  const result = resolvePositions(input, stored)
  assert.deepEqual(result.A, stored.A)
  assert.deepEqual(result.B, stored.B)
  assert.ok('C' in result)
  assert.notDeepEqual(result.C, result.A)
  assert.notDeepEqual(result.C, result.B)
})

test('a stored entry for a state that no longer exists is dropped (a deleted state must not resurrect)', () => {
  const input: LayoutInput = { states: ['A'], transitions: [], initialState: 'A' }
  const stored: Record<string, XY> = { A: { x: 1, y: 2 }, GONE: { x: 3, y: 4 } }
  const result = resolvePositions(input, stored)
  assert.deepEqual(Object.keys(result), ['A'])
})

test('non-finite or non-numeric stored coordinates are ignored, not propagated', () => {
  const input: LayoutInput = { states: ['A', 'B'], transitions: [], initialState: 'A' }
  const stored = { A: { x: NaN, y: Infinity }, B: { x: 'nope' as unknown as number, y: 5 } }
  const result = resolvePositions(input, stored)
  assert.equal(Number.isFinite(result.A.x), true)
  assert.equal(Number.isFinite(result.A.y), true)
  assert.equal(Number.isFinite(result.B.x), true)
})

// ---------------------------------------------------------------------------
// Task 3: pack unreachable states into a bounded grid block (CANVAS-14)
// ---------------------------------------------------------------------------

// Definition 172 ("bbb FDA"), verified against the live DB 2026-08-05: 14 states, only 3 wired
// into any transition. The other 11 are toolkit states the sync effect appended, never wired up.
const orphanNames = [
  'off_led2', 'setTImer', 'play_led2', 'play_leds', 'inbar_state', 'trial_onset',
  'number_is_above', 'number_is_below', 'state_end_trial', 'state_release_water', 'state_wait_for_lick',
]
const def172: LayoutInput = {
  states: ['prepare_session', 'new_trial_onset', 'sadsd', ...orphanNames],
  transitions: [
    { from: 'prepare_session', to: 'new_trial_onset' },
    { from: 'new_trial_onset', to: 'sadsd' },
    { from: 'sadsd', to: 'new_trial_onset' },
  ],
  initialState: 'prepare_session',
}

test('definition 172: all 14 states placed (CANVAS-07 never-drop guarantee survives)', () => {
  const result = layeredLayout(def172)
  assert.equal(Object.keys(result).length, 14)
})

test('definition 172: the 11 orphans form a block, at least 2 distinct x values', () => {
  const result = layeredLayout(def172)
  const orphanXs = new Set(orphanNames.map(name => result[name].x))
  assert.ok(orphanXs.size >= 2)
})

test('definition 172: bounded height — no orphan column holds more than the literal bound of 4', () => {
  const result = layeredLayout(def172)
  const byColumn = new Map<number, number>()
  for (const name of orphanNames) {
    const { x } = result[name]
    byColumn.set(x, (byColumn.get(x) ?? 0) + 1)
  }
  assert.ok(Math.max(...byColumn.values()) <= 4)
})

test('definition 172: every orphan sits strictly right of every connected state', () => {
  const result = layeredLayout(def172)
  const connectedXs = ['prepare_session', 'new_trial_onset', 'sadsd'].map(name => result[name].x)
  const maxConnectedX = Math.max(...connectedXs)
  for (const name of orphanNames) assert.ok(result[name].x > maxConnectedX)
})

test('definition 172: all 14 coordinates distinct', () => {
  const result = layeredLayout(def172)
  assert.equal(coordSet(result).size, 14)
})

test("aspect scales with the connected graph: a 5-row-tall connected part keeps ≤5 orphans per orphan column, not ceil(sqrt(6))=3", () => {
  const input: LayoutInput = {
    states: ['ROOT', 'R1', 'R2', 'R3', 'R4', 'R5', 'O1', 'O2', 'O3', 'O4', 'O5', 'O6'],
    transitions: ['R1', 'R2', 'R3', 'R4', 'R5'].map(to => ({ from: 'ROOT', to })),
    initialState: 'ROOT',
  }
  const result = layeredLayout(input)
  const orphans = ['O1', 'O2', 'O3', 'O4', 'O5', 'O6']
  const byColumn = new Map<number, number>()
  for (const name of orphans) byColumn.set(result[name].x, (byColumn.get(result[name].x) ?? 0) + 1)
  assert.ok(Math.max(...byColumn.values()) <= 5)
  assert.ok([...byColumn.values()].some(count => count > 3))
})

test('0 orphans: identical to a fully connected graph (no block artefacts)', () => {
  const input: LayoutInput = { states: ['A', 'B'], transitions: [{ from: 'A', to: 'B' }], initialState: 'A' }
  const result = layeredLayout(input)
  assert.equal(Object.keys(result).length, 2)
  assert.notEqual(result.A.x, result.B.x)
})

test('1 orphan: a single node, no wrapping artefacts', () => {
  const input: LayoutInput = { states: ['A', 'ORPHAN'], transitions: [], initialState: 'A' }
  const result = layeredLayout(input)
  assert.equal(Object.keys(result).length, 2)
})

test('orphans referencing each other (an isolated cycle) still land in the block, both placed', () => {
  const input: LayoutInput = {
    states: ['IDLE', 'X', 'Y'],
    transitions: [{ from: 'IDLE', to: 'IDLE' }, { from: 'X', to: 'Y' }, { from: 'Y', to: 'X' }],
    initialState: 'IDLE',
  }
  const result = layeredLayout(input)
  assert.equal(Object.keys(result).length, 3)
  assert.ok(result.X.x > result.IDLE.x)
  assert.ok(result.Y.x > result.IDLE.x)
})

test('placeNewState works around the definition-172 block: collides with nothing, including orphan slots', () => {
  const layout = layeredLayout(def172)
  const pos = placeNewState(layout)
  const colSpacing = COLUMN_SPACING()
  const rowSpacing = ROW_SPACING()
  for (const existing of Object.values(layout)) {
    const withinX = Math.abs(existing.x - pos.x) < colSpacing / 2
    const withinY = Math.abs(existing.y - pos.y) < rowSpacing / 2
    assert.equal(withinX && withinY, false)
  }
})

test("initialState '': the whole graph is one bounded block, not a 14-tall column", () => {
  const input: LayoutInput = { states: def172.states, transitions: def172.transitions, initialState: '' }
  const result = layeredLayout(input)
  assert.equal(Object.keys(result).length, 14)
  const xs = new Set(Object.values(result).map(p => p.x))
  assert.ok(xs.size >= 2)
  const byColumn = new Map<number, number>()
  for (const p of Object.values(result)) byColumn.set(p.x, (byColumn.get(p.x) ?? 0) + 1)
  assert.ok(Math.max(...byColumn.values()) < 14)
})
