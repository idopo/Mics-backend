"""CMP-15b: detect a state whose every exit can be blocked forever.

WHY THIS EXISTS: `entry_actions` run once, on entry. A wait condition that depends on a
variable those entry actions wrote can therefore never change while the state waits -- if it
is false when the state is entered, it is false forever and the run hangs with no error at
all. Task def 186 hit exactly this on run 541: `rand` drew `my_rand` on entry and its only
exit required `my_rand >= 0.5`, so every draw below the threshold parked the task permanently
while the pilot carried on logging licks.

The check is deliberately conservative -- it only fires when EVERY exit from a state is
blockable, and it exempts exits whose static comparisons are complementary (`>=` with `<`),
which is the correct shape for a probabilistic branch and must not be reported.

Stdlib only, no DB. Mirrors variable_scan.py's issue shape so it renders through the existing
preflight path.
"""

_COMPLEMENTS = {
    (">=", "<"), ("<", ">="),
    (">", "<="), ("<=", ">"),
    ("==", "!="), ("!=", "=="),
}


def _entry_written_variables(state: dict) -> set[str]:
    """Variables this state's own entry_actions write — frozen for as long as it waits."""
    written: set[str] = set()

    def walk(actions):
        for action in actions or []:
            if not isinstance(action, dict):
                continue
            out = action.get("output")
            if isinstance(out, str) and out:
                written.add(out)
            elif isinstance(out, list):
                written.update(o for o in out if isinstance(o, str) and o)
            walk(action.get("then"))
            walk(action.get("else"))

    walk((state or {}).get("entry_actions"))
    return written


def _operand_variable(operand) -> str | None:
    """The variable/flag name an operand reads, if it reads one."""
    if isinstance(operand, dict):
        for key in ("flag", "view", "tracker"):
            name = operand.get(key)
            if isinstance(name, str) and name:
                return name
    return None


def _frozen_comparisons(node, frozen: set[str]) -> list[tuple[str, str, object]]:
    """(variable, op, threshold) for every comparison in `node` that reads a frozen variable.

    Only descends AND branches: inside an AND, one false conjunct blocks the whole exit. An OR
    can still be satisfied by its other side, so an OR's children are not treated as blocking.
    """
    if not isinstance(node, dict):
        return []
    op = node.get("op")
    if op == "AND":
        found = []
        for child in node.get("children") or []:
            found.extend(_frozen_comparisons(child, frozen))
        return found
    if op == "OR":
        return []
    left, right = node.get("left"), node.get("right")
    name = _operand_variable(left)
    if name in frozen and not isinstance(right, dict):
        return [(name, op, right)]
    name_r = _operand_variable(right)
    if name_r in frozen and not isinstance(left, dict):
        return [(name_r, op, left)]
    return []


def _covered_by_complementary_pair(blocked: list[list[tuple[str, str, object]]]) -> bool:
    """True when two exits gate the same variable and threshold with complementary operators."""
    for i, comps_a in enumerate(blocked):
        for comps_b in blocked[i + 1:]:
            for var_a, op_a, val_a in comps_a:
                for var_b, op_b, val_b in comps_b:
                    if var_a == var_b and val_a == val_b and (op_a, op_b) in _COMPLEMENTS:
                        return True
    return False


def unsatisfiable_wait_issues(fda_json) -> list[dict]:
    """One issue per state whose every exit can be permanently blocked."""
    if not isinstance(fda_json, dict):
        return []
    states = fda_json.get("states")
    transitions = fda_json.get("transitions")
    if not isinstance(states, dict) or not isinstance(transitions, list):
        return []

    issues = []
    for state_name, state in states.items():
        frozen = _entry_written_variables(state if isinstance(state, dict) else {})
        if not frozen:
            continue

        outgoing = [t for t in transitions if isinstance(t, dict) and t.get("from") == state_name]
        if not outgoing:
            continue  # terminal state — a design choice, not a stuck wait

        blocked: list[list[tuple[str, str, object]]] = []
        for transition in outgoing:
            condition = transition.get("condition_tree") or transition.get("condition")
            comparisons = _frozen_comparisons(condition, frozen)
            if not comparisons:
                break  # this exit can still become true on its own — no deadlock
            blocked.append(comparisons)
        else:
            if _covered_by_complementary_pair(blocked):
                continue
            names = sorted({var for comps in blocked for var, _, _ in comps})
            issues.append({
                "module_id": None,
                "module_name": state_name,
                "issue": "state_wait_unsatisfiable",
                "detail": (
                    f"State '{state_name}' can wait forever: every exit depends on "
                    f"{', '.join(names)}, which its own entry_actions set once on entry and "
                    f"nothing changes while it waits. If the condition is false on entry the "
                    f"run hangs with no error. Add an exit for the opposite case."
                ),
            })

    return issues
