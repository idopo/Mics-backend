"""CMP-15b: a state whose every exit can be permanently blocked.

The rig case this comes from (task def 186, run 541): state `rand` drew my_rand once in its
entry_actions and its only exit was `detector == 0 AND my_rand >= 0.5`. A draw below 0.5 made
that exit unsatisfiable forever -- entry_actions do not re-run while waiting, so my_rand could
never change. The task hung with the pilot still happily logging licks, which is the worst
failure shape: nothing errors, the run just never finishes.

Adding the complementary exit (`my_rand < 0.5`) fixes it, so the check must NOT fire once both
branches exist or it would cry wolf on every correct probabilistic branch.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wait_analysis import unsatisfiable_wait_issues


def _fda(states, transitions, variables=None):
    return {
        "states": states,
        "transitions": transitions,
        "variables": variables if variables is not None else {"my_rand": {}},
        "trigger_assignments": [],
    }


_DRAW = {"ref": "COMPUTE", "type": "compute", "method": "random_float", "args": [0, 1], "output": "my_rand"}
_DETECTOR_CLEAR = {"op": "==", "left": {"view_detector": {"ref": "MPR121", "channel": 1}}, "right": 0}


def test_flags_the_run_541_deadlock():
    fda = _fda(
        {"rand": {"entry_actions": [_DRAW]}, "trial_onset": {}},
        [{"from": "rand", "to": "trial_onset", "condition_tree": {
            "op": "AND", "children": [_DETECTOR_CLEAR, {"op": ">=", "left": {"flag": "my_rand"}, "right": 0.5}],
        }}],
    )
    issues = unsatisfiable_wait_issues(fda)
    assert len(issues) == 1, issues
    assert issues[0]["issue"] == "state_wait_unsatisfiable"
    assert issues[0]["module_name"] == "rand"
    assert "my_rand" in issues[0]["detail"]


def test_complementary_branches_are_not_flagged():
    """The fix for run 541 — both >= and < exist, so exactly one is always true."""
    fda = _fda(
        {"rand": {"entry_actions": [_DRAW]}, "trial_onset": {}, "play_led": {}},
        [
            {"from": "rand", "to": "trial_onset", "condition_tree": {
                "op": "AND", "children": [_DETECTOR_CLEAR, {"op": ">=", "left": {"flag": "my_rand"}, "right": 0.5}],
            }},
            {"from": "rand", "to": "play_led", "condition_tree": {
                "op": "<", "left": {"flag": "my_rand"}, "right": 0.5,
            }},
        ],
    )
    assert unsatisfiable_wait_issues(fda) == []


def test_condition_on_a_changing_detector_is_not_flagged():
    """A detector can change while the state waits — that is an ordinary wait, not a deadlock."""
    fda = _fda(
        {"play_led": {}, "rand": {}},
        [{"from": "play_led", "to": "rand", "condition_tree": _DETECTOR_CLEAR}],
    )
    assert unsatisfiable_wait_issues(fda) == []


def test_unconditional_exit_is_not_flagged():
    fda = _fda({"play_led": {}, "rand": {}}, [{"from": "play_led", "to": "rand"}])
    assert unsatisfiable_wait_issues(fda) == []


def test_variable_written_by_another_state_is_not_flagged():
    """Only a variable written by THIS state's entry_actions is frozen while it waits."""
    fda = _fda(
        {"rand": {"entry_actions": [_DRAW]}, "wait_here": {}},
        [{"from": "wait_here", "to": "rand", "condition_tree": {
            "op": ">=", "left": {"flag": "my_rand"}, "right": 0.5,
        }}],
    )
    assert unsatisfiable_wait_issues(fda) == []


def test_state_with_no_outgoing_transitions_is_not_flagged():
    """A terminal state is a design choice, not an unsatisfiable wait."""
    fda = _fda({"done": {"entry_actions": [_DRAW]}}, [])
    assert unsatisfiable_wait_issues(fda) == []


def test_equality_pair_counts_as_complementary():
    fda = _fda(
        {"rand": {"entry_actions": [{**_DRAW, "method": "random_bool", "output": "coin"}]}, "a": {}, "b": {}},
        [
            {"from": "rand", "to": "a", "condition_tree": {"op": "==", "left": {"flag": "coin"}, "right": True}},
            {"from": "rand", "to": "b", "condition_tree": {"op": "!=", "left": {"flag": "coin"}, "right": True}},
        ],
        variables={"coin": {}},
    )
    assert unsatisfiable_wait_issues(fda) == []


def test_two_exits_both_blocked_on_the_same_side_are_flagged():
    """Two exits are not automatically safe — both gating on >= leaves the < case dead."""
    fda = _fda(
        {"rand": {"entry_actions": [_DRAW]}, "a": {}, "b": {}},
        [
            {"from": "rand", "to": "a", "condition_tree": {"op": ">=", "left": {"flag": "my_rand"}, "right": 0.5}},
            {"from": "rand", "to": "b", "condition_tree": {"op": ">", "left": {"flag": "my_rand"}, "right": 0.9}},
        ],
    )
    assert len(unsatisfiable_wait_issues(fda)) == 1


def test_malformed_fda_returns_no_issues():
    assert unsatisfiable_wait_issues(None) == []
    assert unsatisfiable_wait_issues({}) == []
    assert unsatisfiable_wait_issues({"states": None, "transitions": None}) == []
