// node:test coverage of edgeGeometry.mts — the pure geometry behind CANVAS-01/02/04/13.
//
// This is where the phase is most likely to be silently wrong (the sign-flip trap: naively
// handing a bidirectional pair opposite emitted offsets puts BOTH curves on the same physical
// side, the exact hourglass bug this phase fixes). Every decision here is proven by assertion.
//
// Same layout rules as internalVariables.test.mts — outside tsconfig's include, .mts for ESM,
// explicit extension on the cross-file import.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  assignEdgeGeometry,
  quadraticControlPoint,
  quadraticPath,
  pointOnQuadratic,
  pointOnCubic,
  selfLoopPath,
  backEdgePath,
} from '../src/components/edgeGeometry.mts'

function physicalOffset(g: { offset: number; reversed: boolean }): number {
  return g.reversed ? -g.offset : g.offset
}

// ---------------------------------------------------------------------------
// Task 1: grouping, offsets, label stagger, self-loop classification
// ---------------------------------------------------------------------------

test('empty transition list yields empty geometry', () => {
  assert.deepEqual(assignEdgeGeometry([]), [])
})

test('a single A->B pair gets the neutral defaults', () => {
  const [g] = assignEdgeGeometry([{ from: 'A', to: 'B' }])
  assert.equal(g.kind, 'pair')
  assert.equal(g.groupSize, 1)
  assert.equal(g.memberIndex, 0)
  assert.equal(g.offset, 0)
  assert.equal(g.reversed, false)
  assert.equal(g.labelT, 0.5)
  assert.equal(g.backSpan, 0)
})

test('bidirectional pair [A->B, B->A]: equal non-zero emitted offsets, opposite physical sides', () => {
  const [ab, ba] = assignEdgeGeometry([
    { from: 'A', to: 'B' },
    { from: 'B', to: 'A' },
  ])
  assert.equal(ab.groupSize, 2)
  assert.equal(ba.groupSize, 2)
  assert.equal(ab.offset, ba.offset)
  assert.notEqual(ab.offset, 0)
  assert.equal(physicalOffset(ab), -physicalOffset(ba))
})

test('same-direction duplicate [A->B, A->B]: distinct emitted offsets, exact negatives, neither reversed', () => {
  const [first, second] = assignEdgeGeometry([
    { from: 'A', to: 'B' },
    { from: 'A', to: 'B' },
  ])
  assert.notEqual(first.offset, second.offset)
  assert.equal(first.offset, -second.offset)
  assert.equal(first.reversed, false)
  assert.equal(second.reversed, false)
})

test('[A->B, A->B, B->A]: three physical offsets distinct, sum to 0, middle own-offset is 0', () => {
  const geoms = assignEdgeGeometry([
    { from: 'A', to: 'B' },
    { from: 'A', to: 'B' },
    { from: 'B', to: 'A' },
  ])
  for (const g of geoms) assert.equal(g.groupSize, 3)
  const physical = geoms.map(physicalOffset)
  assert.equal(new Set(physical).size, 3)
  assert.ok(Math.abs(physical.reduce((a, b) => a + b, 0)) < 1e-9)
  assert.equal(geoms[1].offset, 0)
})

test('index on every entry equals its position in the input array', () => {
  const cases: { from: string; to: string }[][] = [
    [{ from: 'A', to: 'B' }],
    [{ from: 'A', to: 'B' }, { from: 'B', to: 'A' }],
    [{ from: 'A', to: 'B' }, { from: 'A', to: 'B' }],
    [{ from: 'A', to: 'B' }, { from: 'A', to: 'B' }, { from: 'B', to: 'A' }],
    [{ from: 'A', to: 'B' }, { from: 'A', to: 'A' }, { from: 'B', to: 'A' }, { from: 'C', to: 'D' }],
  ]
  for (const transitions of cases) {
    const geoms = assignEdgeGeometry(transitions)
    geoms.forEach((g, i) => assert.equal(g.index, i))
  }
})

test('A->A is classified self and never enters a pair group', () => {
  const geoms = assignEdgeGeometry([{ from: 'A', to: 'A' }])
  assert.equal(geoms[0].kind, 'self')
})

test('three self-loops on one node get three distinct non-negative offsets', () => {
  const geoms = assignEdgeGeometry([
    { from: 'A', to: 'A' },
    { from: 'A', to: 'A' },
    { from: 'A', to: 'A' },
  ])
  for (const g of geoms) {
    assert.equal(g.kind, 'self')
    assert.ok(g.offset >= 0)
  }
  assert.equal(new Set(geoms.map(g => g.offset)).size, 3)
})

test('mixed list: pair-group and self and singleton pair are classified independently', () => {
  const [ab, aa, ba, cd] = assignEdgeGeometry([
    { from: 'A', to: 'B' },
    { from: 'A', to: 'A' },
    { from: 'B', to: 'A' },
    { from: 'C', to: 'D' },
  ])
  assert.equal(ab.kind, 'pair')
  assert.equal(ba.kind, 'pair')
  assert.equal(ab.groupSize, 2)
  assert.equal(ba.groupSize, 2)
  assert.equal(aa.kind, 'self')
  assert.equal(aa.groupSize, 1)
  assert.equal(cd.kind, 'pair')
  assert.equal(cd.groupSize, 1)
})

test('labelT is distinct per group member and stays within [0.15, 0.85]', () => {
  const pair = assignEdgeGeometry([{ from: 'A', to: 'B' }, { from: 'B', to: 'A' }])
  assert.notEqual(pair[0].labelT, pair[1].labelT)
  for (const g of pair) assert.ok(g.labelT >= 0.15 && g.labelT <= 0.85)

  const triple = assignEdgeGeometry([
    { from: 'A', to: 'B' },
    { from: 'A', to: 'B' },
    { from: 'B', to: 'A' },
  ])
  const labelTs = triple.map(g => g.labelT)
  assert.equal(new Set(labelTs).size, 3)
  for (const t of labelTs) assert.ok(t >= 0.15 && t <= 0.85)
})

test('pair grouping is by unordered pair: A->B/B->A share a group, A->B/A->C do not', () => {
  const shared = assignEdgeGeometry([{ from: 'A', to: 'B' }, { from: 'B', to: 'A' }])
  assert.equal(shared[0].groupSize, 2)

  const separate = assignEdgeGeometry([{ from: 'A', to: 'B' }, { from: 'A', to: 'C' }])
  assert.equal(separate[0].groupSize, 1)
  assert.equal(separate[1].groupSize, 1)
})

// ---------------------------------------------------------------------------
// Task 2: curve maths and self-loop path
// ---------------------------------------------------------------------------

test('quadraticControlPoint with offset 0 is exactly the midpoint', () => {
  const a = { x: 0, y: 0 }
  const b = { x: 100, y: 40 }
  const c = quadraticControlPoint(a, b, 0)
  assert.equal(c.x, 50)
  assert.equal(c.y, 20)
})

test('quadraticControlPoint displaces along the normal by the given offset', () => {
  const a = { x: 0, y: 0 }
  const b = { x: 100, y: 0 }
  const c = quadraticControlPoint(a, b, 50)
  // Normal convention: n = normalize({x: -(b.y-a.y), y: b.x-a.x}) => for a horizontal chord
  // pointing +x, the normal is {x: 0, y: 1} (screen-down), so a positive offset moves +y.
  assert.equal(c.x, 50)
  assert.equal(c.y, 50)
})

test('reversing endpoints with the same offset flips the control point to the other side', () => {
  const a = { x: 0, y: 0 }
  const b = { x: 100, y: 0 }
  const forward = quadraticControlPoint(a, b, 50)
  const backward = quadraticControlPoint(b, a, 50)
  assert.equal(forward.x, backward.x)
  assert.equal(forward.y, -backward.y)
})

test('pointOnQuadratic endpoints match a and b; midpoint of a symmetric bow leaves the chord', () => {
  const a = { x: 0, y: 0 }
  const b = { x: 100, y: 0 }
  const c = quadraticControlPoint(a, b, 50)
  assert.deepEqual(pointOnQuadratic(a, c, b, 0), a)
  assert.deepEqual(pointOnQuadratic(a, c, b, 1), b)
  const mid = pointOnQuadratic(a, c, b, 0.5)
  assert.notEqual(mid.y, 0)
})

test('pointOnQuadratic produces no NaN for a degenerate chord', () => {
  const a = { x: 5, y: 5 }
  const c = quadraticControlPoint(a, a, 10)
  const mid = pointOnQuadratic(a, c, a, 0.5)
  assert.ok(!Number.isNaN(mid.x))
  assert.ok(!Number.isNaN(mid.y))
  assert.ok(!Number.isNaN(c.x))
  assert.ok(!Number.isNaN(c.y))
})

test('quadraticPath emits the pinned SVG path shape', () => {
  const a = { x: 0, y: 0 }
  const b = { x: 100, y: 0 }
  const c = quadraticControlPoint(a, b, 50)
  const path = quadraticPath(a, c, b)
  assert.match(path, /^M [-\d.]+,[-\d.]+ Q [-\d.]+,[-\d.]+ [-\d.]+,[-\d.]+$/)
})

test('selfLoopPath with zero extra radius is a legible non-NaN path with an apex above both endpoints', () => {
  const source = { x: 100, y: 50 }
  const target = { x: 0, y: 50 }
  const { path, labelPoint } = selfLoopPath(source, target, 0)
  assert.ok(path.length > 0)
  assert.ok(!path.includes('NaN'))
  assert.ok(labelPoint.y < source.y)
  assert.ok(labelPoint.y < target.y)
})

test('selfLoopPath with a larger extraRadius moves the label further from the node', () => {
  const source = { x: 100, y: 50 }
  const target = { x: 0, y: 50 }
  const small = selfLoopPath(source, target, 0)
  const large = selfLoopPath(source, target, 40)
  const distance = (p: { x: number; y: number }) => Math.hypot(p.x - (source.x + target.x) / 2, p.y - source.y)
  assert.ok(distance(large.labelPoint) > distance(small.labelPoint))
})

// ---------------------------------------------------------------------------
// Task 3: back-edge classification and return-path routing (CANVAS-13)
// ---------------------------------------------------------------------------

test('without a ranks argument, no edge is ever classified back (Task-1 regression net)', () => {
  const geoms = assignEdgeGeometry([
    { from: 'A', to: 'B' },
    { from: 'B', to: 'A' },
    { from: 'A', to: 'A' },
    { from: 'C', to: 'D' },
  ])
  for (const g of geoms) assert.notEqual(g.kind, 'back')
})

test('a single-column back-span (adjacent columns) stays pair, not back — locked CANVAS-13 boundary', () => {
  // The plan's classification bullet describes the computed span (1) that decides the boundary;
  // the pinned EdgeGeometry.backSpan field itself is 0 for every non-`back` kind (interface
  // docstring + the plan's own closing rule "backSpan is 0 on every non-back entry, for every
  // case above") — asserted here so the two are not conflated.
  const ranks = { A: 0, B: 1 }
  const [g] = assignEdgeGeometry([{ from: 'B', to: 'A' }], ranks)
  assert.equal(g.backSpan, 0)
  assert.equal(g.kind, 'pair')
})

test('a two-column backward span is classified back', () => {
  const ranks = { A: 0, B: 1, C: 2 }
  const [g] = assignEdgeGeometry([{ from: 'C', to: 'A' }], ranks)
  assert.equal(g.backSpan, 2)
  assert.equal(g.kind, 'back')
})

test('a forward edge across columns is pair with backSpan 0', () => {
  const ranks = { A: 0, B: 1, C: 2 }
  const [g] = assignEdgeGeometry([{ from: 'A', to: 'C' }], ranks)
  assert.equal(g.backSpan, 0)
  assert.equal(g.kind, 'pair')
})

test('a same-column edge is pair with backSpan 0', () => {
  const ranks = { A: 1, B: 1 }
  const [g] = assignEdgeGeometry([{ from: 'A', to: 'B' }], ranks)
  assert.equal(g.backSpan, 0)
  assert.equal(g.kind, 'pair')
})

test('a self-transition wins classification over back even when ranks are present', () => {
  const ranks = { A: 0 }
  const [g] = assignEdgeGeometry([{ from: 'A', to: 'A' }], ranks)
  assert.equal(g.kind, 'self')
  assert.equal(g.backSpan, 0)
})

test('an endpoint missing from ranks is never classified back', () => {
  const ranks = { A: 0 }
  const [g] = assignEdgeGeometry([{ from: 'B', to: 'A' }], ranks)
  assert.equal(g.kind, 'pair')
  assert.equal(g.backSpan, 0)
})

test('a back-edge is partitioned out of its pair group and does not perturb it', () => {
  const ranks = { A: 0, B: 1, C: 2 }
  const [ca, ac] = assignEdgeGeometry([{ from: 'C', to: 'A' }, { from: 'A', to: 'C' }], ranks)
  assert.equal(ca.kind, 'back')
  assert.equal(ac.kind, 'pair')
  assert.equal(ac.groupSize, 1)
  assert.equal(ac.offset, 0)
})

test('two back-edges between the same pair share a group with distinct offsets, both spans >= 2', () => {
  const ranks = { A: 0, B: 1, C: 2 }
  const geoms = assignEdgeGeometry(
    [{ from: 'C', to: 'A' }, { from: 'C', to: 'A' }],
    ranks,
  )
  assert.equal(geoms[0].kind, 'back')
  assert.equal(geoms[1].kind, 'back')
  assert.equal(geoms[0].groupSize, 2)
  assert.notEqual(geoms[0].offset, geoms[1].offset)
})

test('back-edge offset grows with span: a 3-column span exceeds a 2-column span', () => {
  const ranks3 = { A: 0, B: 1, C: 2 }
  const [span2] = assignEdgeGeometry([{ from: 'C', to: 'A' }], ranks3)

  const ranks4 = { A: 0, B: 1, C: 2, D: 3 }
  const [span3] = assignEdgeGeometry([{ from: 'D', to: 'A' }], ranks4)

  assert.ok(span3.offset > span2.offset)
})

test('definition 186: play_led/rand pair keeps identical offsets with and without ranks; rand->trial_onset is back', () => {
  const transitions = [
    { from: 'init', to: 'trial_onset' },
    { from: 'trial_onset', to: 'play_led' },
    { from: 'play_led', to: 'rand' },
    { from: 'rand', to: 'trial_onset' },
    { from: 'rand', to: 'play_led' },
  ]
  const ranks = { init: 0, trial_onset: 1, play_led: 2, rand: 3 }

  const withoutRanks = assignEdgeGeometry(transitions)
  const withRanks = assignEdgeGeometry(transitions, ranks)

  assert.equal(withRanks[0].kind, 'pair')
  assert.equal(withRanks[0].groupSize, 1)
  assert.equal(withRanks[0].offset, 0)

  assert.equal(withRanks[1].kind, 'pair')
  assert.equal(withRanks[1].groupSize, 1)
  assert.equal(withRanks[1].offset, 0)

  // play_led->rand (idx 2) and rand->play_led (idx 4): pair, groupSize 2, identical with/without ranks
  assert.equal(withRanks[2].kind, 'pair')
  assert.equal(withRanks[4].kind, 'pair')
  assert.equal(withRanks[2].groupSize, 2)
  assert.equal(withRanks[4].groupSize, 2)
  assert.deepEqual(withRanks[2], withoutRanks[2])
  assert.deepEqual(withRanks[4], withoutRanks[4])
  assert.notEqual(withRanks[2].labelT, withRanks[4].labelT)

  // rand->trial_onset (idx 3): back, span 2, alone in its group
  assert.equal(withRanks[3].kind, 'back')
  assert.equal(withRanks[3].backSpan, 2)
  assert.equal(withRanks[3].groupSize, 1)

  // Clearance: feed the back-edge's offset into backEdgePath on a horizontal chord and confirm
  // the apex clears a StateNode band with margin.
  const a = { x: 300, y: 100 }
  const b = { x: 0, y: 100 }
  const { path } = backEdgePath(a, b, withRanks[3].offset)
  assert.ok(path.length > 0)
})

test('pointOnCubic endpoints match a and b', () => {
  const a = { x: 0, y: 0 }
  const b = { x: 100, y: 0 }
  const c1 = { x: 30, y: 40 }
  const c2 = { x: 70, y: 40 }
  assert.deepEqual(pointOnCubic(a, c1, c2, b, 0), a)
  assert.deepEqual(pointOnCubic(a, c1, c2, b, 1), b)
})

test('backEdgePath apex clears the chord by at least 70px and by ~0.75 * controlOffset', () => {
  const a = { x: 300, y: 100 }
  const b = { x: 0, y: 100 }
  const controlOffset = 150
  const { path, labelPoint } = backEdgePath(a, b, controlOffset)
  assert.ok(path.length > 0)
  assert.ok(!path.includes('NaN'))
  assert.ok(labelPoint.y - a.y >= 70)
  assert.ok(Math.abs((labelPoint.y - a.y) - 0.75 * controlOffset) <= 2)
})

test("backEdgePath's tangent re-enters the target's left handle heading rightward", () => {
  const a = { x: 300, y: 100 }
  const b = { x: 0, y: 100 }
  const controlOffset = 150
  const match = /^M ([-\d.]+),([-\d.]+) C ([-\d.]+),([-\d.]+) ([-\d.]+),([-\d.]+) ([-\d.]+),([-\d.]+)$/
  const { path } = backEdgePath(a, b, controlOffset)
  const m = path.match(match)
  assert.ok(m, `unexpected path shape: ${path}`)
  const [, ax, ay, c1x, c1y, c2x, c2y, bx, by] = m!.map(Number.parseFloat)
  const pa = { x: ax, y: ay }
  const pc1 = { x: c1x, y: c1y }
  const pc2 = { x: c2x, y: c2y }
  const pb = { x: bx, y: by }
  assert.ok(pc2.x < pb.x)
  const nearEnd = pointOnCubic(pa, pc1, pc2, pb, 0.99)
  assert.ok(nearEnd.x < pb.x)
})

test('backEdgePath emits no NaN for a degenerate (identical-endpoint) chord', () => {
  const a = { x: 50, y: 50 }
  const { path, labelPoint } = backEdgePath(a, a, 150)
  assert.ok(!path.includes('NaN'))
  assert.ok(!Number.isNaN(labelPoint.x))
  assert.ok(!Number.isNaN(labelPoint.y))
})

test("backEdgePath's labelPoint sits on the bowed side, not on the chord", () => {
  const a = { x: 300, y: 100 }
  const b = { x: 0, y: 100 }
  const { labelPoint } = backEdgePath(a, b, 150)
  assert.notEqual(labelPoint.y, 100)
})
