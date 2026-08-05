/**
 * Pure geometry behind CANVAS-01/02/04/13: which transitions share a "parallel group", how far
 * each bows off the straight line, where its label rides, how a self-loop is drawn, and (a later
 * task) how a multi-column backward transition routes clear of the states it spans.
 *
 * THE SIGN-FLIP TRAP (read before touching assignEdgeGeometry): `TransitionEdge` only ever knows
 * its own source/target endpoints, so it can only bow along the normal of its own direction
 * vector — for A->B that normal points one physical way, for B->A the opposite physical way.
 * Handing the two members of a bidirectional pair naively opposite emitted offsets (-S/2, +S/2)
 * therefore puts BOTH curves on the SAME physical side (the hourglass bug this phase fixes). The
 * fix: canonicalise the pair to [min(from,to), max(from,to)], compute one CANONICAL offset per
 * member ordered by index, then flip the sign only for the member whose `from > to` (`reversed`).
 * A reversed member's emitted offset equals its NON-reversed sibling's, not its negative — do not
 * "fix" this into looking symmetric, that reintroduces the bug. See the test file's named cases.
 *
 * No imports. This module takes structural `{ from, to }` inputs and stays dependency-free.
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

// Perpendicular spacing (px) between adjacent members of a same-direction/opposite-direction pair group.
const PAIR_SPACING = 46
// Radius growth (px) per additional self-loop stacked on the same node.
const SELF_LOOP_SPACING = 26
// Fractional stagger between adjacent group members' label positions along their own curve.
const LABEL_STAGGER = 0.14

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
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
 */
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
