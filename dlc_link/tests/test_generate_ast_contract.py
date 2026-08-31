"""Proof the generator's emitted source is consumable by the REAL backend AST extractor.

Per the pattern map, this is the single highest-value test the phase can write: it proves
`dlc_link.generate`'s output is actually usable by `api/extlink_ast.py` -- the exact code
path the backend runs at lib-upload time -- without a live database, a running API, or the
Pi. No DB, no TestClient, matching `api/tests/test_extlink_keys.py`'s pure-function style.

Extends the sys.path idiom `dlc_link/tests/conftest.py` already uses for `dlc_link`/
`mics_link`, inserting the repository's own `api/` directory from this file's location so
the import below is the REAL extractor, never a vendored copy. If the package is installed
outside this repository (so `api/` cannot be found), the whole module is skipped with a
named reason -- it must not silently pass without having run.
"""
import os
import sys

import pytest

from dlc_link.config_read import read_dlc_config
from dlc_link.generate import generate
from dlc_link.names import flat_signal_names

_HERE = os.path.dirname(__file__)
_API_DIR = os.path.abspath(os.path.join(_HERE, "..", "..", "api"))
if os.path.isdir(_API_DIR) and _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

# api/extlink_keys.py (and api/lib_version_resolution.py, which it imports) import
# sqlalchemy at module scope for functions this test never calls
# (pilot_extlink_keys/module_extlink_signals take a caller-owned `db`); the function
# actually exercised here, derive_extlink_keys, is pure and touches no database. The dev
# host (outside the api Docker image) has no sqlalchemy installed, so a minimal stub
# satisfies that unrelated import without installing a package or vendoring any
# extractor logic -- the REAL derive_extlink_keys still runs, unmodified.
if "sqlalchemy" not in sys.modules:
    try:
        import sqlalchemy  # noqa: F401
    except ImportError:
        import types

        _sqlalchemy_stub = types.ModuleType("sqlalchemy")
        _sqlalchemy_stub.text = lambda *args, **kwargs: None
        sys.modules["sqlalchemy"] = _sqlalchemy_stub

try:
    from extlink_ast import extract_extlink_metadata
    from extlink_keys import derive_extlink_keys
except ImportError as exc:  # pragma: no cover - only hit when run outside this repo
    pytest.skip(
        "api/extlink_ast.py or api/extlink_keys.py is not importable ({}); this test "
        "only runs from inside the mics-backend repository, against the real "
        "extractor -- it must not silently pass without having run".format(exc),
        allow_module_level=True,
    )

FIXTURES = os.path.join(_HERE, "fixtures")
MADLC_CONFIG = os.path.join(FIXTURES, "dlc3_multianimal_config.yaml")
POSE_ORDER_FILE = os.path.join(FIXTURES, "pose_order_declared.txt")


def _pose_order():
    with open(POSE_ORDER_FILE) as handle:
        return [
            line.strip() for line in handle if line.strip() and not line.strip().startswith("#")
        ]


def _generate_three_bodyparts_two_with_coords():
    source = read_dlc_config(MADLC_CONFIG)
    return generate(
        source=source,
        pose_order=_pose_order(),
        pose_order_source="probe",
        wanted=["LED_on", "LED_off", "NW"],
        coords_for={"LED_on", "NW"},
        source_id="dlc_cam1",
        allow_signals=10,
    )


@pytest.fixture
def generated():
    result = _generate_three_bodyparts_two_with_coords()
    metadata = extract_extlink_metadata(result.lib_source)
    return result, metadata


def test_extractor_registers_exactly_one_class_matching_generated_name(generated):
    result, metadata = generated
    assert list(metadata.keys()) == [result.provenance["class_name"]]


def test_signal_keys_equal_generator_own_expected_set(generated):
    """Computed from the generator's own output, not hardcoded, so a future
    name-transform change fails this test rather than drifting past it."""
    result, metadata = generated
    class_meta = metadata[result.provenance["class_name"]]
    expected = set(flat_signal_names(result.name_map))
    assert set(class_meta["signals"].keys()) == expected


def test_every_signal_dtype_is_the_float_string(generated):
    """`_signal_dtype` resolving the `-> float` return annotation -- what the FDA
    editor's picker renders next to each operand."""
    _result, metadata = generated
    class_meta = metadata[list(metadata.keys())[0]]
    for name, info in class_meta["signals"].items():
        assert info["dtype"] == "float", (name, info)


def test_stale_policy_per_kind_and_nonzero_stale_after_ms(generated):
    _result, metadata = generated
    class_meta = metadata[list(metadata.keys())[0]]
    for name, info in class_meta["signals"].items():
        assert isinstance(info["stale_after_ms"], int) and info["stale_after_ms"] != 0
        if name.endswith("_likelihood"):
            assert info["stale_policy"] == "return_default"
        elif name.endswith("_x") or name.endswith("_y"):
            assert info["stale_policy"] == "hold_last"
        else:  # pragma: no cover - defensive, every emitted name is one of the above
            pytest.fail("unexpected signal name shape: {!r}".format(name))


def test_events_commands_empty_decoder_none(generated):
    _result, metadata = generated
    class_meta = metadata[list(metadata.keys())[0]]
    assert class_meta["events"] == {}
    assert class_meta["commands"] == {}
    assert class_meta["decoder"] is None


def test_derive_extlink_keys_backs_d36_runbook_ordering(generated):
    """The direct, offline demonstration of D-36's forced runbook ordering: a config
    with no `source_id` derives no keys at all (a class must be assigned a source_id
    before the FDA editor can offer anything from it), while a config with `source_id`
    derives every signal key PLUS `<source_id>.alive`."""
    result, metadata = generated
    class_meta = metadata[result.provenance["class_name"]]
    signal_names = sorted(class_meta["signals"].keys())
    source_id = result.provenance["source_id"]

    assert derive_extlink_keys({"source_id": source_id}, signal_names) == sorted(
        {"{}.{}".format(source_id, name) for name in signal_names} | {"{}.alive".format(source_id)}
    )
    assert derive_extlink_keys({}, signal_names) == []
    assert derive_extlink_keys(None, signal_names) == []


def test_class_with_no_extlink_decorators_is_not_registered_at_all():
    """Proves the "at least one of the four decorators" rule -- and therefore that an
    empty selection cannot produce an invisible lib, since `dlc_link.generate` always
    emits at least one `@signal` per selected bodypart."""
    stripped_source = (
        "from autopilot.hardware.external_hardware import ExternalHardware\n\n\n"
        "class NoExtlinkDecorators(ExternalHardware):\n"
        "    def plain_method(self):\n"
        "        pass\n"
    )
    metadata = extract_extlink_metadata(stripped_source)
    assert metadata == {}
