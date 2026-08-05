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

/** Group transitions and assign each member an offset and label position. */
export function assignEdgeGeometry(transitions: ReadonlyArray<{ from: string; to: string }>): EdgeGeometry[] {
  const members: Member[] = transitions.map((t, index) => {
    if (t.from === t.to) {
      return { index, from: t.from, to: t.to, reversed: false, kind: 'self', backSpan: 0 }
    }
    // Canonicalise to [min, max] lexicographically; `reversed` marks the against-canon member.
    const reversed = t.from > t.to
    return { index, from: t.from, to: t.to, reversed, kind: 'pair', backSpan: 0 }
  })

  const buckets = new Map<string, Member[]>()
  for (const m of members) {
    const pairKey = [m.from, m.to].sort().join(' ')
    const key = m.kind === 'self' ? `self:${m.from}` : `pair:${pairKey}`
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

// Base radius (px) of a self-loop before any extraRadius widening.
const BASE_LOOP_RADIUS = 40

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
