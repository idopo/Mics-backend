"""Call-site dtype validation + shared token coercion (Phase 34, Plan 02, Task 1).

Covers `mics_link.values` (`validate_value`, `validate_payload`, `coerce_token`,
`as_scalar`) and `mics_link.errors` (`MicsLinkError`, `InvalidValueError`). See the
34-02-PLAN.md amendment "DLC-Live and Windows" for why the dtype check is EXACT type,
not `isinstance` — a `numpy.float64` IS a `float` subclass, so `isinstance` would let it
through only for msgpack to raise later, off the caller's call site.
"""
import pytest

from mics_link.errors import InvalidValueError, MicsLinkError
from mics_link.values import ALLOWED_DTYPES, as_scalar, coerce_token, validate_payload, validate_value


class Floatish:
    """Duck-typed numeric with `__float__` but not itself a `float` — decision 1: rejected,
    not coerced."""

    def __float__(self):
        return 0.5


class FakeF64(float):
    """numpy.float64 stand-in: a float SUBCLASS exposing `.item()`, exactly like a real
    numpy scalar. `isinstance(FakeF64(...), float)` is True (the isinstance trap the
    amendment describes); `type(FakeF64(...)) is float` is False (why the exact-type check
    still rejects it)."""

    def item(self):
        return float(self)


class FakeStr(str):
    """numpy.str_ stand-in: a str subclass exposing `.item()`."""

    def item(self):
        return str(self)


# --- validate_value: accepted values, exact type preserved ---


@pytest.mark.parametrize(
    "value",
    [0.7, 3, True, "armed"],
)
def test_validate_value_accepts_allowed_dtypes_unchanged(value):
    result = validate_value("x", value)
    assert result == value
    assert type(result) is type(value)


def test_validate_value_preserves_bool_exact_type():
    assert type(validate_value("x", True)) is bool


def test_validate_value_preserves_int_exact_type():
    assert type(validate_value("x", 3)) is int


# --- validate_value: rejected values ---


@pytest.mark.parametrize(
    "value",
    [None, [1, 2], {"a": 1}, b"bytes", 1 + 2j],
)
def test_validate_value_rejects_disallowed_types(value):
    with pytest.raises(InvalidValueError):
        validate_value("x", value)


def test_validate_value_rejects_duck_typed_float_not_coerced():
    with pytest.raises(InvalidValueError):
        validate_value("x", Floatish())


def test_validate_value_rejects_numpy_style_float_subclass_despite_isinstance_pass():
    """Pins the trap: `isinstance(FakeF64(0.9), float)` is True, but the exact-type check
    still rejects it — an `isinstance`-based implementation would silently let this through."""
    value = FakeF64(0.9)
    assert isinstance(value, float)  # the trap: isinstance says yes
    with pytest.raises(InvalidValueError):
        validate_value("x", value)  # exact-type check says no


def test_validate_value_rejects_numpy_style_str_subclass_despite_isinstance_pass():
    value = FakeStr("x")
    assert isinstance(value, str)
    with pytest.raises(InvalidValueError):
        validate_value("x", value)


def test_validate_value_message_names_signal_and_type_and_allowed_dtypes():
    with pytest.raises(InvalidValueError) as excinfo:
        validate_value("my_signal", None)
    message = str(excinfo.value)
    assert "my_signal" in message
    assert "NoneType" in message
    for word in ("int", "float", "bool", "str"):
        assert word in message


def test_validate_value_message_names_as_scalar_when_value_exposes_item():
    with pytest.raises(InvalidValueError) as excinfo:
        validate_value("x", FakeF64(0.9))
    assert "as_scalar" in str(excinfo.value)


def test_validate_value_message_omits_as_scalar_when_value_has_no_item():
    with pytest.raises(InvalidValueError) as excinfo:
        validate_value("x", None)
    assert "as_scalar" not in str(excinfo.value)


def test_invalid_value_error_is_catchable_as_mics_link_error():
    with pytest.raises(MicsLinkError):
        validate_value("x", None)


def test_invalid_value_error_is_catchable_as_type_error():
    with pytest.raises(TypeError):
        validate_value("x", None)


def test_allowed_dtypes_is_exactly_bool_int_float_str():
    assert ALLOWED_DTYPES == (bool, int, float, str)


# --- validate_payload ---


def test_validate_payload_accepts_dict_of_allowed_dtypes_unchanged():
    payload = {"object": "paw", "confidence": 0.9}
    assert validate_payload("evt", payload) is payload


def test_validate_payload_rejects_non_dict():
    with pytest.raises(InvalidValueError):
        validate_payload("evt", ["not", "a", "dict"])


def test_validate_payload_rejects_non_str_key():
    with pytest.raises(InvalidValueError):
        validate_payload("evt", {1: "value"})


def test_validate_payload_rejects_value_outside_allowed_dtypes():
    with pytest.raises(InvalidValueError):
        validate_payload("evt", {"object": ["not", "allowed"]})


# --- coerce_token ---


def test_coerce_token_float():
    result = coerce_token("0.7")
    assert result == 0.7
    assert type(result) is float


def test_coerce_token_int_not_bool():
    result = coerce_token("3")
    assert result == 3
    assert type(result) is int


def test_coerce_token_negative_int():
    result = coerce_token("-2")
    assert result == -2
    assert type(result) is int


@pytest.mark.parametrize("token", ["true", "True", "TRUE"])
def test_coerce_token_true_variants_produce_real_bool(token):
    result = coerce_token(token)
    assert result is True
    assert type(result) is bool


def test_coerce_token_false():
    result = coerce_token("false")
    assert result is False
    assert type(result) is bool


def test_coerce_token_plain_string_passthrough():
    result = coerce_token("armed")
    assert result == "armed"
    assert type(result) is str


def test_coerce_token_json_dict_when_allowed():
    result = coerce_token('{"object":"paw"}', allow_json_dict=True)
    assert result == {"object": "paw"}


def test_coerce_token_json_dict_stays_string_by_default():
    token = '{"object":"paw"}'
    result = coerce_token(token)
    assert result == token
    assert type(result) is str


@pytest.mark.parametrize(
    "token",
    ["", "   ", "not json {", "{unterminated", None, 123, [1, 2]],
)
def test_coerce_token_never_raises(token):
    coerce_token(token)  # must not raise, on any input
    coerce_token(token, allow_json_dict=True)


# --- as_scalar ---


def test_as_scalar_unwraps_array_scalar_to_exact_python_type():
    result = as_scalar(FakeF64(0.5))
    assert type(result) is float
    assert result == 0.5


def test_as_scalar_leaves_plain_str_unchanged():
    assert as_scalar("x") == "x"
    assert type(as_scalar("x")) is str


def test_as_scalar_leaves_plain_int_unchanged():
    assert as_scalar(3) == 3
    assert type(as_scalar(3)) is int


def test_as_scalar_is_noop_on_object_with_no_item():
    value = Floatish()
    assert as_scalar(value) is value


def test_as_scalar_never_raises_on_plain_values():
    for value in (None, [1, 2], {"a": 1}, b"bytes"):
        as_scalar(value)  # must not raise
