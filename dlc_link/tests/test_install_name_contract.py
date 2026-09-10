"""The install line is a contract, and it has already drifted once.

Renaming the distribution `dlc-link` -> `mics-dlc-link` (2026-09-10) left a runtime error
message in `convert.py` telling the researcher to `pip install "dlc-link[convert]"` -- a
name that no longer resolves anywhere. It was found by a grep, not by a test, and it would
have shipped. These tests read the name from `pyproject.toml` rather than restating it, so
the next rename cannot leave a stale hint behind.

The install must also never route through the MICS repository: the researchers this package
exists for have no access to it, which is the entire reason it is published on PyPI.
"""
import re
import sys
from pathlib import Path

import pytest

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - the target env is 3.12; keeps this file importable on 3.10
    tomllib = pytest.importorskip("tomli")

_ROOT = Path(__file__).parents[1]
_PYPROJECT = _ROOT / "pyproject.toml"
_DOCS = (_ROOT / "README.md", _ROOT / "RUNBOOK.md")
_SOURCES = sorted((_ROOT / "src" / "dlc_link").glob("*.py"))

# Names a `pip install` line in this package may name: its own distribution (read from
# pyproject, never restated), the SDK it depends on, and the third-party inference stack
# the `live` extra pulls.
_ALLOWED_EXTRA_NAMES = frozenset({"mics-link", "deeplabcut-live"})

_INSTALL_LINE = re.compile(r"pip install\s+(.+)")


def _install_targets(text):
    """Distribution names named by every `pip install` line in `text`.

    Takes the FIRST real target on each line and stops. Two things make a naive rule
    wrong here: the offline path puts a flag VALUE between the flags and the target
    (`pip install --no-index --find-links ./kit "mics-dlc-link[live]"`, where `./kit` is
    not a package), and both the README table and the RUNBOOK continue in prose on the
    same line after the command. So: skip flags, skip anything path-shaped, take the next
    token as the target, and stop before the prose. Quotes, brackets, backticks and
    trailing punctuation are stripped; an `[extra]` suffix is dropped.
    """
    names = set()
    for rest in _INSTALL_LINE.findall(text):
        for token in rest.split():
            token = token.strip("\"'`,.()")
            if not token or token.startswith("-"):
                continue
            if "/" in token or "\\" in token:  # a --find-links path, not a package
                continue
            names.add(token.split("[", 1)[0])
            break
    return names


def _distribution_name():
    return tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))["project"]["name"]


def test_distribution_name_is_the_mics_prefixed_one():
    """`mics-dlc-link`, not `dlc-link`: the prefix keeps the family visible in a `pip
    list` and leaves the generic name to the wider DeepLabCut community. The IMPORT
    package stays `dlc_link` -- only the installed name carries the prefix.
    """
    assert _distribution_name() == "mics-dlc-link"
    assert (_ROOT / "src" / "dlc_link" / "__init__.py").exists()


@pytest.mark.parametrize("path", list(_DOCS) + _SOURCES, ids=lambda p: p.name)
def test_every_install_hint_names_a_real_distribution(path):
    """A `pip install` line anywhere in this package -- docs or a runtime error message --
    must name this distribution or one of its declared dependencies. Nothing else exists
    to install.
    """
    allowed = _ALLOWED_EXTRA_NAMES | {_distribution_name()}
    named = _install_targets(path.read_text(encoding="utf-8"))
    unknown = sorted(named - allowed)
    assert unknown == [], (
        "{} tells the reader to install {} -- no such distribution is published. "
        "Allowed: {}".format(path.name, unknown, sorted(allowed))
    )


@pytest.mark.parametrize("path", _DOCS, ids=lambda p: p.name)
def test_docs_do_not_route_the_install_through_the_mics_repo(path):
    """No `git+` requirement, no release-asset URL, no build-from-source instruction, and
    no network share. The researcher has none of those and must not need them.
    """
    forbidden = ("git+http", "github.com/idopo", "python -m build", "storwis")
    present = [f for f in forbidden if f in path.read_text(encoding="utf-8")]
    assert present == [], (
        "{} routes the install through the MICS repo or the SMB share via {!r}".format(
            path.name, present
        )
    )


def test_readme_carries_the_one_line_install():
    readme = (_ROOT / "README.md").read_text(encoding="utf-8")
    assert 'python -m pip install "{}[live]"'.format(_distribution_name()) in readme
