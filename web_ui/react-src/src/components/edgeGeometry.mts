/**
 * Pure geometry behind CANVAS-01/02/04/13: parallel-group membership, bow offset, label
 * position, self-loop shape, and (a later task) back-edge routing — all derived from the
 * transition list alone. No imports; takes structural `{ from, to }` inputs.
 *
 * THE SIGN-FLIP TRAP: `TransitionEdge` only knows its own source/target, so it can only bow
 * along the normal of ITS OWN direction — A->B's normal points one physical way, B->A's the
 * opposite way. Handing a bidirectional pair naively opposite emitted offsets (-S/2, +S/2)
 * therefore bows BOTH to the SAME physical side (the hourglass bug this phase fixes). Fix:
 * canonicalise to [min(from,to), max(from,to)], compute one CANONICAL offset per member
 * (ordered by index), then negate it only for the member with `from > to` (`reversed`). A
 * reversed member's emitted offset equals its non-reversed sibling's, not its negative — do
 * not "fix" this into looking symmetric, that reintroduces the bug.
 */

export interface XY {
  x: number
  y: number
}
export type EdgeKind = 'pair' | 'self' | 'back'
export interface EdgeGeometry {
  index: number
  kind: EdgeKind
  groupSize: number
  memberIndex: number
  offset: number
  reversed: boolean
  labelT: number
  backSpan: number
}

const PAIR_SPACING = 46 // px between adjacent members of a same/opposite-direction pair group
const SELF_LOOP_SPACING = 26 // px radius growth per additional self-loop on the same node
const LABEL_STAGGER = 0.14 // fractional stagger between adjacent members' label positions

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}
/** Round to 2 decimals so emitted SVG path strings are stable and testable. */
function round2(n: number): number {
  return Math.round(n * 100) / 100
}

interface Member {
  index: number
  from: string
  to: string
  reversed: boolean
  kind: EdgeKind
  backSpan: number
}

/**
 * Group transitions and assign each member an offset and label position.
 *
 * `ranks` (CANVAS-13) is `columnRanks(...)` from `fdaLayout.mts`, the SAME BFS the layout uses,
 * passed in rather than recomputed. Optional: without it no edge is ever classified `back`.
 * Classification precedence: `self` first, then a backward span >= 2 columns (both endpoints
 * ranked) is `back`, everything else is `pair` — partitioned into its own keyspace BEFORE
 * bucketing, so a `back` edge never shares a group with a `pair` edge between the same nodes.
 */
export function assignEdgeGeometry(
  transitions: ReadonlyArray<{ from: string; to: string }>,
  ranks?: Readonly<Record<string, number>>,
): EdgeGeometry[] {
  const members: Member[] = transitions.map((t, index) => {
    if (t.from === t.to) {
      return { index, from: t.from, to: t.to, reversed: false, kind: 'self', backSpan: 0 }
    }
    if (ranks && t.from in ranks && t.to in ranks) {
      const span = ranks[t.from] - ranks[t.to]
      if (span >= 2) {
        return { index, from: t.from, to: t.to, reversed: false, kind: 'back', backSpan: span }
      }
    }
    // Canonicalise to [min, max] lexicographically; `reversed` marks the against-canon member.
    const reversed = t.from > t.to
    return { index, from: t.from, to: t.to, reversed, kind: 'pair', backSpan: 0 }
  })

  const buckets = new Map<string, Member[]>()
  for (const m of members) {
    const pairKey = [m.from, m.to].sort().join(' ')
    const key = m.kind === 'self' ? `self:${m.from}` : m.kind === 'back' ? `back:${pairKey}` : `pair:${pairKey}`
    const bucket = buckets.get(key)
    if (bucket) bucket.push(m)
    else buckets.set(key, [m])
  }

  const result: EdgeGeometry[] = new Array(members.length)
  for (const bucket of buckets.values()) {
    bucket.sort((a, b) => a.index - b.index)
    const n = bucket.length
    bucket.forEach((m, memberIndex) => {
      const labelT = clamp(0.5 + (memberIndex - (n - 1) / 2) * LABEL_STAGGER, 0.15, 0.85)
      let offset: number
      if (m.kind === 'self') {
        offset = memberIndex * SELF_LOOP_SPACING
      } else if (m.kind === 'back') {
        offset = BACK_EDGE_BASE + (m.backSpan - 1) * BACK_EDGE_PER_COLUMN + memberIndex * BACK_EDGE_MEMBER_STEP
      } else {
        const canonical = (memberIndex - (n - 1) / 2) * PAIR_SPACING
        // `|| 0` normalises -0 (from negating a zero canonical) to +0 — a reversed singleton
        // member must compare strictly equal to 0, not to a distinct-looking negative zero.
        offset = (m.reversed ? -canonical : canonical) || 0
      }
      result[m.index] = {
        index: m.index,
        kind: m.kind,
        groupSize: n,
        memberIndex,
        offset,
        reversed: m.reversed,
        labelT,
        backSpan: m.backSpan,
      }
    })
  }
  return result
}

const BASE_LOOP_RADIUS = 40 // px radius of a self-loop before any extraRadius widening

// Back-edge clearance (CANVAS-13). A StateNode is minWidth:180px, ~70px tall, handles at
// vertical centre, so a back-edge must clear ~35px plus margin. backEdgePath's cubic apex sits
// at 0.75 * controlOffset below the chord (both control points share that y offset), so
// BACK_EDGE_BASE=150 gives ~112px of apex clearance for a 2-column span.
const BACK_EDGE_BASE = 150
const BACK_EDGE_PER_COLUMN = 90 // px added per extra column spanned beyond the first
const BACK_EDGE_MEMBER_STEP = 60 // px separation between back-edges sharing the same node pair

/**
 * Normal convention (pinned, never vary): n = normalize({x: -(b.y-a.y), y: b.x-a.x}). For a
 * horizontal chord pointing +x this is {x:0, y:1} (screen-down): a positive offset bows toward
 * larger y. `assignEdgeGeometry`'s sign flip relies on this: reversing a/b flips the normal.
 */
export function quadraticControlPoint(a: XY, b: XY, offset: number): XY {
  const dx = b.x - a.x
  const dy = b.y - a.y
  const len = Math.hypot(dx, dy)
  const mid = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }
  if (len === 0) {
    // Degenerate chord: fall back to a fixed direction rather than dividing by zero.
    return { x: mid.x, y: mid.y - offset }
  }
  const nx = -dy / len
  const ny = dx / len
  return { x: mid.x + nx * offset, y: mid.y + ny * offset }
}

/** SVG path string `M ax,ay Q cx,cy bx,by`, coordinates rounded to 2 decimals for stability. */
export function quadraticPath(a: XY, c: XY, b: XY): string {
  return `M ${round2(a.x)},${round2(a.y)} Q ${round2(c.x)},${round2(c.y)} ${round2(b.x)},${round2(b.y)}`
}

/** Point on the quadratic Bezier a->c->b at parameter t (t=0 -> a, t=1 -> b). */
export function pointOnQuadratic(a: XY, c: XY, b: XY, t: number): XY {
  const u = 1 - t
  return {
    x: u * u * a.x + 2 * u * t * c.x + t * t * b.x,
    y: u * u * a.y + 2 * u * t * c.y + t * t * b.y,
  }
}

/**
 * Loop between a node's source handle (right, `source`) and target handle (left, `target`):
 * leaves right, arcs above, re-enters left. `R` widens with `extraRadius` so N self-loops stack
 * distinguishably.
 */
export function selfLoopPath(source: XY, target: XY, extraRadius: number): { path: string; labelPoint: XY } {
  const R = BASE_LOOP_RADIUS + extraRadius
  const path = `M ${round2(source.x)},${round2(source.y)} C ${round2(source.x + R)},${round2(source.y - R)} ${round2(target.x - R)},${round2(target.y - R)} ${round2(target.x)},${round2(target.y)}`
  const labelPoint = { x: (source.x + target.x) / 2, y: Math.min(source.y, target.y) - R }
  return { path, labelPoint }
}

/** Point on the cubic Bezier a->c1->c2->b at parameter t. */
export function pointOnCubic(a: XY, c1: XY, c2: XY, b: XY, t: number): XY {
  const u = 1 - t
  return {
    x: u * u * u * a.x + 3 * u * u * t * c1.x + 3 * u * t * t * c2.x + t * t * t * b.x,
    y: u * u * u * a.y + 3 * u * u * t * c1.y + 3 * u * t * t * c2.y + t * t * t * b.y,
  }
}

/**
 * Return-path curve for a back-edge (CANVAS-13): leaves the source, drops `controlOffset`
 * below the chord, runs left past the target, re-enters the target's left handle heading
 * rightward. Both control points share `controlOffset` below the chord, so the cubic apex at
 * t=0.5 is exactly 0.75 * controlOffset below it — pin this factor, the clearance constants
 * above are sized against it.
 */
export function backEdgePath(a: XY, b: XY, controlOffset: number): { path: string; labelPoint: XY } {
  const dx = b.x - a.x
  const lead = Math.max(30, Math.abs(dx) * 0.15)
  const c1 = { x: a.x + dx * 0.25, y: a.y + controlOffset }
  // c2 sits to the LEFT of b by `lead` so the tangent at b points rightward into b's left handle.
  const c2 = { x: b.x - lead, y: b.y + controlOffset }
  const path = `M ${round2(a.x)},${round2(a.y)} C ${round2(c1.x)},${round2(c1.y)} ${round2(c2.x)},${round2(c2.y)} ${round2(b.x)},${round2(b.y)}`
  const labelPoint = pointOnCubic(a, c1, c2, b, 0.5)
  return { path, labelPoint }
}
