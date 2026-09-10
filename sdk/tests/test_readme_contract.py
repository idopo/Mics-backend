"""Automated enforcement of the README contract (Phase 34, Plan 08, SDK-13 + SDK-14d).

Locates every file relative to `__file__` (`Path(__file__).parents[1]`), not the CWD, so
this test works under both `cd sdk && pytest` and a repo-root invocation.

`count_real_lines` is the load-bearing piece behind the ten-line bar: it strips blank
lines and full-line `#` comments, and excludes the MODULE docstring's own line range via
`ast` -- not string-matching -- so a future "clever" example (e.g. one that hides real
code behind a fake docstring) cannot game it. It has its own unit tests below, separate
from the example-file tests, per this plan's own instruction not to weaken the check to
make it pass.
"""
import ast
import re
from pathlib import Path

import pytest

import mics_link

_SDK_ROOT = Path(__file__).parents[1]
_README = _SDK_ROOT / "README.md"
_EXAMPLES_DIR = _SDK_ROOT / "examples"
_SRC_DIR = _SDK_ROOT / "src" / "mics_link"
_TEN_LINE_EXAMPLE = _EXAMPLES_DIR / "ten_line_sender.py"
_CALLBACK_EXAMPLE = _EXAMPLES_DIR / "callback_sender.py"
_WINDOWS_SMOKE_EXAMPLE = _EXAMPLES_DIR / "windows_smoke.py"

# Word-boundary, case-insensitive: a plain substring match on "pose" would also flag
# ordinary English words like "purpose"/"exposed"/"supposed" throughout the README and
# source docstrings -- that is not what CONTEXT.md's device-neutrality guard means to
# ban. Word-boundary matching catches the real term ("pose", "DLC") without punishing
# unrelated prose.
_DEVICE_NEUTRALITY_PATTERN = re.compile(
    r"\b(deeplabcut|keypoint|bodypart|pose|dlc)\b", re.IGNORECASE
)


def _module_docstring_line_range(tree):
    """1-based inclusive (start, end) line range of `tree`'s module docstring, or `None`
    if the module has none.
    """
    if (
        tree.body
        and isinstance(tree.body[0], ast.Expr)
        and isinstance(tree.body[0].value, ast.Constant)
        and isinstance(tree.body[0].value.value, str)
    ):
        node = tree.body[0]
        return node.lineno, getattr(node, "end_lineno", node.lineno)
    return None


def count_real_lines(source):
    """Count of `source`'s non-blank, non-full-line-comment lines, excluding the MODULE
    docstring's own line range. A trailing `# comment` on an otherwise-real line does
    NOT exclude that line -- only a line that is ENTIRELY a comment (after stripping
    leading whitespace) is excluded.
    """
    docstring_range = _module_docstring_line_range(ast.parse(source))
    count = 0
    for lineno, line in enumerate(source.splitlines(), start=1):
        if docstring_range and docstring_range[0] <= lineno <= docstring_range[1]:
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        count += 1
    return count


def _counted_lines(source):
    """The actual counted lines themselves (not just their number) -- used to check the
    README embeds them verbatim.
    """
    docstring_range = _module_docstring_line_range(ast.parse(source))
    lines = []
    for lineno, line in enumerate(source.splitlines(), start=1):
        if docstring_range and docstring_range[0] <= lineno <= docstring_range[1]:
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(line)
    return lines


# --- count_real_lines: unit tests with their own fixtures (CONTEXT.md's own instruction:
# a future "clever" example must not be able to game this by raising the limit or by
# hiding real code inside a fake docstring) ---


def test_count_real_lines_excludes_docstring_blank_full_comment_and_trailing_comment():
    fixture = (
        '"""A module docstring.\n'
        "spanning two lines.\n"
        '"""\n'
        "\n"
        "# a full-line comment\n"
        "x = 1  # a trailing comment on a real line\n"
        "y = 2\n"
    )
    assert count_real_lines(fixture) == 2


def test_count_real_lines_single_line_docstring():
    assert count_real_lines('"""One line."""\nx = 1\n') == 1


def test_count_real_lines_no_docstring_at_all():
    assert count_real_lines("x = 1\ny = 2\n# comment\n\n") == 2


def test_count_real_lines_all_blank_and_comment_is_zero():
    assert count_real_lines("\n\n# just a comment\n   \n") == 0


# --- the ten-line bar (decision 5) ---


def test_ten_line_sender_parses():
    ast.parse(_TEN_LINE_EXAMPLE.read_text(encoding="utf-8"))


def test_ten_line_sender_is_ten_lines_or_fewer():
    source = _TEN_LINE_EXAMPLE.read_text(encoding="utf-8")
    counted = count_real_lines(source)
    assert counted <= 10, (
        "sdk/examples/ten_line_sender.py counts {} real lines (> 10) -- "
        "the API needs simplifying, not the counter".format(counted)
    )


def test_ten_line_sender_imports_only_names_in_mics_link_all():
    tree = ast.parse(_TEN_LINE_EXAMPLE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "mics_link":
            for alias in node.names:
                assert alias.name in mics_link.__all__, (
                    "ten_line_sender.py imports {!r} from mics_link, which is not in "
                    "mics_link.__all__".format(alias.name)
                )


def test_readme_contains_the_ten_line_examples_counted_lines_verbatim():
    """The doc and the file cannot drift: every one of the example's counted lines must
    appear, verbatim, somewhere in the README's embedded copy.
    """
    source = _TEN_LINE_EXAMPLE.read_text(encoding="utf-8")
    readme = _README.read_text(encoding="utf-8")
    for line in _counted_lines(source):
        assert line in readme, (
            "sdk/README.md is missing the example's line {!r} verbatim -- "
            "the doc and the file have drifted".format(line)
        )


# --- callback / push example (SDK-15): exempt from the ten-line bar, still parsed and
# still checked against mics_link.__all__ ---


def test_callback_sender_parses():
    ast.parse(_CALLBACK_EXAMPLE.read_text(encoding="utf-8"))


def test_callback_sender_imports_only_names_in_mics_link_all():
    tree = ast.parse(_CALLBACK_EXAMPLE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "mics_link":
            for alias in node.names:
                assert alias.name in mics_link.__all__, (
                    "callback_sender.py imports {!r} from mics_link, which is not in "
                    "mics_link.__all__".format(alias.name)
                )


# --- Windows install smoke (34-09 addition): standalone, rig-free, deliberately reaches
# past mics_link.__all__ into wire/selfcheck/replay -- unlike ten_line_sender.py and
# callback_sender.py it is NOT checked against __all__ (that would be wrong for this
# file: proving the internal wire codec, the selfcheck guard, and the replay path all work
# on a fresh install IS the point). It IS still parsed and still covered by the
# device-neutrality and ASCII-only parametrized tests above, via the same
# `_EXAMPLES_DIR.glob("*.py")` sweep. ---


def test_windows_smoke_parses():
    ast.parse(_WINDOWS_SMOKE_EXAMPLE.read_text(encoding="utf-8"))


def test_windows_smoke_deliberately_uses_internal_submodules_not_just_all():
    """Documents the exemption above as an executable fact, not just a comment: this file
    imports at least one of mics_link's internal submodules (wire/selfcheck/replay), which
    ten_line_sender.py and callback_sender.py are forbidden from doing. If a future edit
    strips all of them out, this file no longer needs the exemption and this test should be
    deleted along with it.
    """
    tree = ast.parse(_WINDOWS_SMOKE_EXAMPLE.read_text(encoding="utf-8"))
    internal_submodules = {"mics_link.wire", "mics_link.selfcheck", "mics_link.replay"}
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in internal_submodules:
            imported.add(node.module)
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in internal_submodules:
                    imported.add(alias.name)
    assert imported, (
        "windows_smoke.py no longer imports any of mics_link's internal submodules -- "
        "the __all__-exemption comment above is now stale"
    )


# --- README's mandatory markers ---

_REQUIRED_MARKERS = [
    # The one-line install IS the contract as of 2026-09-10: `mics-link` is published on
    # PyPI and resolves by name, so the README must not send a researcher to a repo, a
    # release URL or a file share. The two markers that used to live here -- the
    # `git+https://...#subdirectory=sdk` line and `python -m build` -- were the old
    # repo-dependent story and are now forbidden rather than required; see
    # test_readme_does_not_route_the_install_through_this_repo below.
    "python -m pip install mics-link",
    "router_bind",
    "source_id",
    "listen_port",
    "stale_ms",
    "mics-link-replay",
    "send_signal",
    "send_event",
    "close",
    "on_state_change",
    "Python 3.8",
]


@pytest.mark.parametrize("marker", _REQUIRED_MARKERS)
def test_readme_contains_required_marker(marker):
    readme = _README.read_text(encoding="utf-8")
    assert marker in readme, "sdk/README.md is missing the required marker {!r}".format(
        marker
    )


# Phase 34 decision 2 ("state the public-repo dependency risk") and decision 4 ("no bare
# `pip install mics-link` line, as if it worked") are both RETIRED, superseded by the
# 2026-09-10 decision to publish on PyPI. The risk they guarded -- that the install breaks
# for every outside machine if `idopo/Mics-backend` is made private -- no longer exists,
# because the install no longer touches the repo at all. The guards are INVERTED rather
# than deleted, so the repo-dependent story cannot quietly come back.


def test_readme_does_not_route_the_install_through_this_repo():
    """The install must not depend on repo access in any form: no `git+` requirement, no
    release-asset URL, no instruction to build a wheel from the source tree. A researcher
    on a Windows/DeepLabCut box has none of those things and should not need them.
    """
    readme = _README.read_text(encoding="utf-8")
    forbidden = ("git+http", "github.com/idopo", "python -m build")
    present = [f for f in forbidden if f in readme]
    assert present == [], (
        "sdk/README.md routes the install through this repository via {!r} -- the package "
        "is on PyPI and installs by name; repo-dependent install paths are retired".format(
            present
        )
    )


def test_readme_recommends_python_m_pip_not_bare_pip():
    """Still enforced, and for the ORIGINAL reason, which PyPI does not change: on a
    Windows box with a `py` launcher and several Pythons, bare `pip` can install into an
    interpreter the researcher did not mean, producing a `ModuleNotFoundError` with no
    visible cause. Every install line in the README must carry the `python -m` prefix.
    """
    readme = _README.read_text(encoding="utf-8")
    for number, line in enumerate(readme.splitlines(), start=1):
        assert not re.match(r"^\s*pip install\b", line, re.IGNORECASE), (
            "sdk/README.md line {} starts an install with bare 'pip' -- use "
            "'python -m pip install' so the interpreter is unambiguous".format(number)
        )


# --- no latency/jitter/round-trip claim outside its own section (decision 9) ---


def _latency_section_line_range(lines):
    start = None
    end = len(lines)
    for i, line in enumerate(lines):
        if start is None and re.match(
            r"^#+\s*9\.\s*Why there is no latency readout", line
        ):
            start = i
            continue
        if start is not None and i > start and line.startswith("#"):
            end = i
            break
    assert start is not None, (
        "sdk/README.md is missing the 'Why there is no latency readout' section heading"
    )
    return start, end


def test_no_latency_jitter_or_round_trip_claim_outside_its_own_section():
    lines = _README.read_text(encoding="utf-8").splitlines()
    start, end = _latency_section_line_range(lines)
    outside = "\n".join(lines[:start] + lines[end:])
    for term in ("latenc", "jitter", "round-trip"):
        assert not re.search(term, outside, re.IGNORECASE), (
            "sdk/README.md mentions {!r} outside the 'Why there is no latency readout' "
            "section (decision 9)".format(term)
        )


# --- device-neutrality guard (CONTEXT.md: nothing in mics_link may know what a
# keypoint is) ---


def _device_specific_matches(path):
    return _DEVICE_NEUTRALITY_PATTERN.findall(path.read_text(encoding="utf-8"))


def test_readme_is_device_neutral():
    assert _device_specific_matches(_README) == []


@pytest.mark.parametrize(
    "path", sorted(_EXAMPLES_DIR.glob("*.py")), ids=lambda p: p.name
)
def test_examples_are_device_neutral(path):
    assert _device_specific_matches(path) == []


@pytest.mark.parametrize("path", sorted(_SRC_DIR.glob("*.py")), ids=lambda p: p.name)
def test_src_is_device_neutral(path):
    assert _device_specific_matches(path) == []


# --- ASCII-only (SDK-14d): the README and every example must encode to ASCII cleanly,
# so a curly quote or em dash pasted into an example does not kill a Windows run at its
# last printed line ---


@pytest.mark.parametrize(
    "path", [_README] + sorted(_EXAMPLES_DIR.glob("*.py")), ids=lambda p: p.name
)
def test_readme_and_examples_are_ascii_only(path):
    text = path.read_text(encoding="utf-8")
    text.encode("ascii")


# --- every public name is documented (Phase 35's adapter is writable from the README
# alone must be a testable claim, not an aspiration) ---


def test_every_public_name_appears_in_the_readme():
    readme = _README.read_text(encoding="utf-8")
    for name in mics_link.__all__:
        assert name in readme, (
            "mics_link.__all__ name {!r} is not documented anywhere in "
            "sdk/README.md".format(name)
        )


def test_readme_meets_the_minimum_length_bar():
    line_count = len(_README.read_text(encoding="utf-8").splitlines())
    assert line_count >= 120, (
        "sdk/README.md is only {} lines -- below the 120-line minimum this plan's own "
        "must_haves artifact spec requires".format(line_count)
    )
