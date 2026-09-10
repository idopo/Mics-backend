"""Parsing and evaluation of the researcher's own authored overlay threshold clauses
(D-60).

The FDA's authored thresholds live in the task definition's `fda_json` on the backend.
This module does NOT read them -- doing so would couple the vision box to a backend
schema Phase 37 is about to move out of this repo, for a display nicety. Instead the
researcher types `--overlay "nose_x>0.50,nose_likelihood>0.6"` and this module parses
and evaluates those clauses against the SAME normalised signal values
`dlc_link.processor.DLCProcessor.process` sends over the wire (normalised 0..1 for
coordinates, per `processor.py:110-111`).

`evaluate()`'s result is a DISPLAY aid computed from the researcher's own numbers on
the vision box. The Pi evaluates its own FDA conditions from its own tracker values,
through its own code path, entirely separately -- and the two can legitimately
disagree for a moment. The viewer is not a substitute for the FDA and must never be
described as one.
"""
from dataclasses import dataclass

# Longer operators first: "in text" membership checks must see ">=" / "<=" before the
# single-character ">" / "<" they contain, or a ">=" clause would be misread as ">".
_OPERATORS = (">=", "<=", ">", "<")


class OverlayError(Exception):
    """Raised for every refusal in this module. Always quotes the offending clause."""


@dataclass(frozen=True)
class Clause:
    signal: str
    op: str
    value: float
    text: str


def _parse_one(clause_text, signal_map):
    text = clause_text.strip()
    if not text:
        raise OverlayError("empty clause in overlay string")

    has_comparison = ">" in text or "<" in text
    if not has_comparison and "=" in text:
        raise OverlayError(
            "{!r}: '=' / '==' is never what was meant here -- an equality test on a "
            "float coordinate or likelihood almost never matches the live value. Use "
            "one of {} instead.".format(text, _OPERATORS)
        )

    op = None
    for candidate in _OPERATORS:
        if candidate in text:
            op = candidate
            break
    if op is None:
        raise OverlayError(
            "{!r}: no recognised operator found -- expected one of {}".format(text, _OPERATORS)
        )

    signal, _, raw_value = text.partition(op)
    signal = signal.strip()
    raw_value = raw_value.strip()
    if not signal or not raw_value:
        raise OverlayError("{!r}: malformed clause, expected SIGNAL{}VALUE".format(text, op))

    try:
        value = float(raw_value)
    except ValueError:
        raise OverlayError("{!r}: {!r} is not a float".format(text, raw_value)) from None

    if signal_map is not None:
        declared = list(signal_map.SIGNAL_NAMES)
        if signal not in declared:
            raise OverlayError(
                "{!r}: signal {!r} is not declared. Declared SIGNAL_NAMES are: {}".format(
                    text, signal, declared
                )
            )

    return Clause(signal=signal, op=op, value=value, text=text)


def parse_overlay(text, signal_map=None):
    """Parse a comma-separated overlay string into a list of `Clause`.

    Splits on commas, tolerates surrounding whitespace, and refuses (raising
    `OverlayError`, always quoting the offending clause): an empty string or empty
    clause, a clause with no recognised operator, `=`/`==`, a non-float right-hand
    side, and -- when `signal_map` is given -- any signal absent from
    `SIGNAL_NAMES` (listing the declared names in the message). That last refusal is
    the point of the whole function: a typo'd signal name that silently never matches
    is exactly the failure class this repository keeps finding on the rig, and it
    costs one comparison to make impossible.
    """
    if not text or not text.strip():
        raise OverlayError("empty overlay string")
    return [_parse_one(part, signal_map) for part in text.split(",")]


def evaluate(clauses, values):
    """Evaluate `clauses` against a `{signal_name: value}` dict.

    Returns `(overall_bool, [(clause, result_or_None), ...])`. A clause whose signal
    is absent from `values` evaluates to `None` (unknown), and `overall` is the AND
    over clauses treating `None` as False. Never raises.

    This is a DISPLAY aid computed from the researcher's own numbers on the vision
    box. The Pi evaluates its own FDA conditions from its own tracker values, and the
    two can legitimately disagree for a moment; the viewer is not a substitute for
    the FDA and must never be described as one.
    """
    results = []
    overall = True
    for clause in clauses:
        if clause.signal not in values:
            results.append((clause, None))
            overall = False
            continue
        value = values[clause.signal]
        if clause.op == ">":
            result = value > clause.value
        elif clause.op == ">=":
            result = value >= clause.value
        elif clause.op == "<":
            result = value < clause.value
        else:  # "<="
            result = value <= clause.value
        results.append((clause, result))
        if not result:
            overall = False
    return overall, results
