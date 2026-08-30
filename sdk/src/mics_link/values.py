"""Call-site dtype validation for signal/event values, plus the shared CSV/stdin token
coercion lifted from the retired POC driver's `coerce_value` (`tools/extlink_driver/`,
deleted in plan 34-05; Phase 18, EXTLINK-12).

`validate_value`/`validate_payload` implement SDK-04 (decision 1, AMENDED 2026-08-30 —
"DLC-Live and Windows"): a bad value raises `InvalidValueError` at the researcher's own
call site — never a frame the Pi silently counts as `type_mismatch` and drops, which is
invisible from the sender. The check is EXACT type (`type(value) is float`), not
`isinstance`: a `numpy.float64` IS a `float` subclass, so an `isinstance` check would let it
through validation only for `msgpack` to raise an un-catchable `TypeError` on the IO thread
later — the exact invisible-failure mode this function exists to prevent, reintroduced by a
check that looks equivalent. `as_scalar` is the documented, opt-in escape hatch for exactly
that case; nothing here coerces silently.
"""
import json

from .errors import InvalidValueError

# bool FIRST: it is an int subclass, order documents intent (decision 2). The exact-type
# check below does not depend on this order — type() is never fooled by subclassing — but
# the tuple order is still the canonical statement of "these four, in this priority."
ALLOWED_DTYPES = (bool, int, float, str)


def _looks_like_array_scalar(value):
    """True for anything exposing a callable, numpy-style `.item()` — str/bytes excluded
    since both happen to define unrelated `.item`-shaped surprises via subclassing in
    principle, and neither is ever the array-scalar case this exists to detect."""
    item = getattr(value, "item", None)
    return callable(item) and not isinstance(value, (bytes, str))


def _rejection_message(signal_name, value):
    type_name = type(value).__name__
    allowed = ", ".join(dtype.__name__ for dtype in ALLOWED_DTYPES)
    message = "signal {!r}: value of type {!r} is not one of the allowed dtypes ({})".format(
        signal_name, type_name, allowed
    )
    if _looks_like_array_scalar(value):
        message += (
            " — this looks like a numpy/array scalar; convert it explicitly with "
            "mics_link.values.as_scalar(value) before sending"
        )
    return message


def validate_value(signal_name, value):
    """Return `value` unchanged if `type(value)` is EXACTLY bool, int, float or str;
    otherwise raise `InvalidValueError` naming the signal, the offending type, and the four
    allowed dtypes (plus a pointer to `as_scalar` when the value looks like an array
    scalar). Duck-typed numerics (anything with `__float__`/`__int__` but not itself one of
    the four types) are REJECTED, not coerced — msgpack cannot pack them anyway, and silent
    coercion is exactly the invisible failure this function exists to prevent.
    """
    for dtype in ALLOWED_DTYPES:
        if type(value) is dtype:
            return value
    raise InvalidValueError(_rejection_message(signal_name, value))


def validate_payload(event_name, payload):
    """Return `payload` unchanged if it is a `dict` with `str` keys and allowed-dtype
    values; otherwise raise `InvalidValueError`.
    """
    if type(payload) is not dict:
        raise InvalidValueError(
            "event {!r}: payload must be a dict, got {!r}".format(
                event_name, type(payload).__name__
            )
        )
    for key, value in payload.items():
        if type(key) is not str:
            raise InvalidValueError(
                "event {!r}: payload keys must be str, got {!r}".format(
                    event_name, type(key).__name__
                )
            )
        validate_value("{}.{}".format(event_name, key), value)
    return payload


def as_scalar(value):
    """numpy (or any array-scalar) -> the equivalent Python scalar; anything else unchanged.
    numpy-free by construction: `.item()` is the documented numpy idiom and preserves the
    int/bool/float distinction that float(...) flattens."""
    item = getattr(value, "item", None)
    return item() if callable(item) and not isinstance(value, (bytes, str)) else value


def coerce_token(token, allow_json_dict=False):
    """str -> bool|int|float|str (|dict when allow_json_dict=True). Never raises, on any
    input — the driver/replay loops calling this must survive a stray or malformed token.

    Lifted from the retired POC driver's `coerce_value` (`tools/extlink_driver/`, deleted in
    plan 34-05; Phase 18, EXTLINK-12). Bools are checked BEFORE any numeric coercion: `bool`
    is an `int` subclass in Python, and this ordering mirrors the receiving side's own guard
    (`external_hardware_wire.coerce_value`), which special-cases `bool` against
    `isinstance(raw, bool)` specifically because `float(True) == 1.0` would otherwise
    silently misrepresent a bool as a float — checking `"true"`/`"false"` first here keeps
    the token parser symmetric with that guard rather than ever routing a bool-looking token
    through `int()`/`float()` first.

    The JSON-dict branch is opt-in (`allow_json_dict`): the retired POC driver passed
    `allow_json_dict=True` to give its EVT-from-stdin mode `{...}`-shaped payloads; plan
    34-07's CSV replay uses the default `False` — a `{...}`-shaped token stays a plain string
    unless the caller opts in.
    """
    try:
        lowered = token.lower()
    except AttributeError:
        return token
    if lowered in ("true", "false"):
        return lowered == "true"
    try:
        return int(token)
    except (ValueError, TypeError):
        pass
    try:
        return float(token)
    except (ValueError, TypeError):
        pass
    if allow_json_dict:
        stripped = token.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                return json.loads(stripped)
            except ValueError:
                pass
    return token
