// FDA JSON normalisation for the task editor, extracted verbatim from TaskEditor.tsx.
//
// These functions migrate stored FDA JSON of any vintage into the canonical Phase 16+ shape
// (condition_tree, no handler/config) so the editor can always assume the current schema after
// seeding. See tests/fdaNormalise.test.mts for coverage of every legacy branch.
import type { ConditionGroup, ConditionNode, FdaCondition, FdaJson, FdaOperand, FdaTransition, FdaTriggerAssignment } from '../types/index.ts'

// Normalise a stored transition to v2 format (handles legacy from_state/next_state/condition)
export function normaliseTransition(t: Record<string, unknown>): FdaTransition {
  const from: string = (t.from ?? t.from_state ?? '') as string
  const to: string   = (t.to   ?? t.next_state  ?? '') as string

  // Already has condition_tree — use as-is (canonical Phase 16+ format)
  if (t.condition_tree !== undefined) {
    return { from, to, condition_tree: t.condition_tree as ConditionNode, description: t.description as string | undefined }
  }

  // Migrate condition_groups (DNF) → OR-of-AND tree
  const groups = t.condition_groups as ConditionGroup[] | undefined
  if (groups && groups.length > 0) {
    // Build OR-of-AND tree
    const andNodes = groups
      .filter(g => g.conditions.length > 0)
      .map(g =>
        g.conditions.length === 1
          ? g.conditions[0]
          : ({ op: 'AND' as const, children: g.conditions })
      )
    const tree: ConditionNode | null =
      andNodes.length === 0 ? null :
      andNodes.length === 1 ? andNodes[0] :
      { op: 'OR', children: andNodes }
    return { from, to, condition_tree: tree ?? undefined, description: t.description as string | undefined }
  }

  // Migrate legacy conditions[] → single AND-leaf (or null if empty)
  let legacyConditions: FdaCondition[] = (t.conditions ?? []) as FdaCondition[]
  if (legacyConditions.length === 0 && t.condition) {
    const c = t.condition as Record<string, unknown>
    if ('left' in c) {
      legacyConditions = [c as unknown as FdaCondition]
    } else {
      legacyConditions = [{ left: { view: (c.view ?? '') as string }, op: (c.op ?? '==') as FdaCondition['op'], right: (c.rhs ?? 0) as FdaOperand }]
    }
  }
  const tree: ConditionNode | undefined =
    legacyConditions.length === 0 ? undefined :
    legacyConditions.length === 1 ? legacyConditions[0] :
    { op: 'AND', children: legacyConditions }

  return { from, to, condition_tree: tree, description: t.description as string | undefined }
}

export function normaliseFda(fdaJson: FdaJson): FdaJson {
  return {
    ...fdaJson,
    transitions: (fdaJson.transitions ?? []).map(t => normaliseTransition(t as unknown as Record<string, unknown>)),
    trigger_assignments: (fdaJson.trigger_assignments ?? []).map(normaliseTriggerAssignment),
    variables: fdaJson.variables ?? {},
  }
}

/**
 * Heal a trigger assignment saved before the handler enum was removed.
 *
 * Legacy rows (e.g. task definitions 181 and 185) carry `handler` and no `actions`
 * at all, so rendering `a.actions.length` throws and the whole editor fails to mount.
 * `actions` is required in the current schema, so default it and drop the dead keys.
 */
export function normaliseTriggerAssignment(a: FdaTriggerAssignment): FdaTriggerAssignment {
  const { handler: _handler, config: _config, ...rest } =
    a as FdaTriggerAssignment & { handler?: unknown; config?: unknown }
  return {
    ...rest,
    trigger_name: rest.trigger_name ?? '',
    actions: Array.isArray(rest.actions) ? rest.actions : [],
  }
}

export function parseStateWarnings(validationMessage: string | null | undefined): Record<string, string> {
  if (!validationMessage) return {}
  const result: Record<string, string> = {}
  for (const line of validationMessage.split('\n')) {
    const m = line.match(/^State '([^']+)': (.+)$/)
    if (m) {
      result[m[1]] = result[m[1]] ? `${result[m[1]]}\n${m[2]}` : m[2]
    }
  }
  return result
}
