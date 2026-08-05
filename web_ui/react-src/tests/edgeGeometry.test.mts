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
  selfLoopPath,
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
