/**
 * Hand-rolled layered auto-layout for the FDA state canvas (CANVAS-07/08).
 *
 * Replaces the index-grid `x:(i%4)*270, y:floor(i/4)*170` `TaskEditor.tsx` stamps in three
 * places (`fdaToNodes`, the toolkit-sync effect, `addState`) with a BFS-ranked layered
 * arrangement, plus (in a later task) a "place one new node without disturbing anything already
 * positioned" rule — the index grid's flaw was dropping a new node directly on top of a
 * positioned one.
 *
 * No imports, no `any`. Dagre/ELK were explicitly rejected (locked decision) in favour of this
 * dependency-free module.
 */

/** A layout coordinate. */
export interface XY {
  x: number
  y: number
}

/** Structural input every layout function shares — mirrors the relevant slice of `FdaJson`. */
export interface LayoutInput {
  /** Every state name in the FDA — `Object.keys(fdaJson.states)`. */
  states: ReadonlyArray<string>
  /** `fdaJson.transitions`, structurally. Self-transitions are ignored for ranking. */
  transitions: ReadonlyArray<{ from: string; to: string }>
  /** `fdaJson.initial_state`. May be '' — a task definition can legitimately have none yet. */
  initialState: string
}

/** Horizontal distance between BFS-depth columns. Wider than the old 270 — bowed edges (CANVAS-13) and their labels need the extra corridor. */
const COLUMN_SPACING = 320
/** Vertical distance between rows within a column. Wider than the old 170 for the same reason. */
const ROW_SPACING = 180

/**
 * BFS depth from `initialState` along transitions: 0 for the initial state, 1 for its targets,
 * etc. States UNREACHABLE from `initialState` (including when `initialState` is '' or names a
 * state absent from `states`) are ABSENT from the map.
 *
 * Exported because `edgeGeometry.mts` needs the same ranking to classify back-edges (CANVAS-13):
 * one BFS implementation means the layout and the back-edge routing can never disagree about
 * which column a state is in.
 */
export function columnRanks(input: LayoutInput): Record<string, number> {
  const { states, transitions, initialState } = input
  const knownStates = new Set(states)
  const ranks: Record<string, number> = {}
  if (!knownStates.has(initialState)) return ranks

  const adjacency = new Map<string, string[]>()
  for (const { from, to } of transitions) {
    if (from === to) continue // self-transitions never affect ranking
    if (!adjacency.has(from)) adjacency.set(from, [])
    adjacency.get(from)!.push(to)
  }

  ranks[initialState] = 0
  const queue: string[] = [initialState]
  while (queue.length > 0) {
    const current = queue.shift()!
    const depth = ranks[current]
    for (const next of adjacency.get(current) ?? []) {
      if (next in ranks) continue // guards cycles: first visit wins
      ranks[next] = depth + 1
      queue.push(next)
    }
  }
  return ranks
}

/** Places one column's states, centred vertically about y=0 so short columns sit beside tall ones without a ragged top. */
function placeColumn(column: ReadonlyArray<string>, x: number, positions: Record<string, XY>): void {
  const size = column.length
  column.forEach((state, rowIndex) => {
    positions[state] = { x, y: (rowIndex - (size - 1) / 2) * ROW_SPACING }
  })
}

/** BFS-ranked layered arrangement. Every input state appears in the result. */
export function layeredLayout(input: LayoutInput): Record<string, XY> {
  const { states } = input
  const positions: Record<string, XY> = {}
  if (states.length === 0) return positions

  const ranks = columnRanks(input) // the one BFS; not re-derived here

  const connectedColumns = new Map<number, string[]>()
  let maxRank = -1
  for (const state of states) {
    const rank = ranks[state]
    if (rank === undefined) continue
    if (!connectedColumns.has(rank)) connectedColumns.set(rank, [])
    connectedColumns.get(rank)!.push(state)
    if (rank > maxRank) maxRank = rank
  }
  for (const [rank, column] of connectedColumns) {
    placeColumn(column, rank * COLUMN_SPACING, positions)
  }

  // Unreachable states: a trailing column for now. Task 3 replaces this with a bounded grid
  // block (CANVAS-14) so a large orphan set reads as a block rather than one tall column.
  const orphans = states.filter(state => ranks[state] === undefined)
  if (orphans.length > 0) placeColumn(orphans, (maxRank + 1) * COLUMN_SPACING, positions)

  return positions
}
