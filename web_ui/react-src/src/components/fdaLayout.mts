/**
 * Hand-rolled layered auto-layout for the FDA state canvas (CANVAS-07/08). Replaces the
 * index-grid `x:(i%4)*270, y:floor(i/4)*170` stamped in three places in `TaskEditor.tsx`
 * (`fdaToNodes`, the toolkit-sync effect, `addState`) — that grid could drop a new node
 * directly on top of a positioned one, which `placeNewState`/`resolvePositions` fix below.
 *
 * No imports, no `any`. Dagre/ELK were explicitly rejected (locked decision).
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

// Wider than the old 270/170 — bowed back-edges (CANVAS-13) and their labels need the corridor.
const COLUMN_SPACING = 320
const ROW_SPACING = 180

/**
 * BFS depth from `initialState`: 0 for the initial state, 1 for its targets, etc. Unreachable
 * states (including `initialState === ''` or naming a state absent from `states`) are ABSENT.
 *
 * Exported so `edgeGeometry.mts` can classify back-edges (CANVAS-13) off the SAME BFS — two
 * independent traversals could disagree about which column a state is in.
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

/** Places one column's states, centred about y=0 so short columns sit beside tall ones. */
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

  // Unreachable states: trailing column for now. Task 3 replaces this with a bounded grid block.
  const orphans = states.filter(state => ranks[state] === undefined)
  if (orphans.length > 0) placeColumn(orphans, (maxRank + 1) * COLUMN_SPACING, positions)

  return positions
}

/** Row offsets scanned outward from the centre row: 0, 1, -1, 2, -2, ... */
function* rowOffsets(limit: number): Generator<number> {
  yield 0
  for (let k = 1; k <= limit; k++) {
    yield k
    yield -k
  }
}

/** A position colliding with nothing in `taken`. Never mutates or returns `taken`. */
export function placeNewState(taken: Readonly<Record<string, XY>>): XY {
  const existing = Object.values(taken)
  const budget = existing.length + 3 // rows and columns to try before giving up on the lattice

  for (let col = 0; col <= budget; col++) {
    const x = col * COLUMN_SPACING
    for (const rowOffset of rowOffsets(budget)) {
      const y = rowOffset * ROW_SPACING
      const collides = existing.some(
        pos => Math.abs(pos.x - x) < COLUMN_SPACING / 2 && Math.abs(pos.y - y) < ROW_SPACING / 2,
      )
      if (!collides) return { x, y }
    }
  }
  return { x: (budget + 1) * COLUMN_SPACING, y: 0 } // never throw: a fresh trailing column is always free
}

/**
 * The one function TaskEditor calls. Stored positions win verbatim; states absent from `stored`
 * are placed without moving anything stored. A null/empty `stored` means a full `layeredLayout`.
 */
export function resolvePositions(
  input: LayoutInput,
  stored: Readonly<Record<string, XY>> | null | undefined,
): Record<string, XY> {
  const knownStates = new Set(input.states)
  const sanitized: Record<string, XY> = {}
  if (stored) {
    for (const [name, pos] of Object.entries(stored)) {
      if (!knownStates.has(name)) continue // a deleted state must not resurrect
      if (!pos || !Number.isFinite(pos.x) || !Number.isFinite(pos.y)) continue // ui_layout is free-form JSONB
      sanitized[name] = { x: pos.x, y: pos.y }
    }
  }
  if (Object.keys(sanitized).length === 0) return layeredLayout(input)

  const positions: Record<string, XY> = { ...sanitized }
  for (const state of input.states) {
    if (!(state in positions)) positions[state] = placeNewState(positions)
  }
  return positions
}
