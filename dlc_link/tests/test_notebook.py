"""Tests for `dlc_link/notebooks/live_view.ipynb` -- the four-cell notebook the
researcher actually opens (Task 3, plan 38-03).

A rename in the parameters cell must not leave the argv cell silently broken: every
bare-name variable reference the argv cell's source uses is asserted present as an
assignment target in the parameters cell.
"""
import ast
import json
import os
import re

_NOTEBOOK_PATH = os.path.join(
    os.path.dirname(__file__), "..", "notebooks", "live_view.ipynb"
)


def _load_notebook():
    with open(_NOTEBOOK_PATH) as handle:
        return json.load(handle)


def _cell_source(cell):
    source = cell["source"]
    return "".join(source) if isinstance(source, list) else source


def test_notebook_is_valid_nbformat_4_with_four_cells():
    nb = _load_notebook()
    assert nb["nbformat"] == 4
    assert len(nb["cells"]) == 4


def test_first_cell_is_markdown_and_the_rest_are_code():
    nb = _load_notebook()
    kinds = [cell["cell_type"] for cell in nb["cells"]]
    assert kinds == ["markdown", "code", "code", "code"]


# Every one of these is a parameter the argv cell builds `argv`/`dlc_link.live_cli.main`
# from. If a future rename drops one from the parameters cell without updating the
# argv cell (or vice versa), this test catches it rather than leaving a silent
# NameError the first time the notebook is actually run.
_EXPECTED_PARAMETER_NAMES = {
    "source", "model_path", "signal_map", "host", "port", "source_id", "pilot_name",
    "orchestrator_url", "es_url", "es_index", "overlay", "view_min_likelihood",
    "max_seconds",
}


def _assigned_names(source):
    tree = ast.parse(source)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return names


def _loaded_names(source):
    tree = ast.parse(source)
    return {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }


def test_every_parameter_the_argv_cell_references_is_defined_in_the_parameters_cell():
    nb = _load_notebook()
    parameters_source = _cell_source(nb["cells"][1])
    argv_source = _cell_source(nb["cells"][2])

    defined_in_parameters = _assigned_names(parameters_source)
    loaded_in_argv = _loaded_names(argv_source)

    assert _EXPECTED_PARAMETER_NAMES <= defined_in_parameters
    assert _EXPECTED_PARAMETER_NAMES <= loaded_in_argv


def test_notebook_text_has_no_imshow_and_no_plain_opencv_install_command():
    with open(_NOTEBOOK_PATH) as handle:
        text = handle.read()
    assert "imshow" not in text
    # An actual pip-install command naming the non-headless package (not the prose
    # warning against installing it) would match "pip install ... opencv-python"
    # with no "-headless" suffix on the match.
    for match in re.finditer(r"pip install[^\n]*?opencv-python(?!-headless)", text):
        raise AssertionError("found a plain opencv-python install command: {!r}".format(match.group()))


def test_notebook_states_it_writes_nothing():
    nb = _load_notebook()
    markdown = _cell_source(nb["cells"][0])
    assert "writes nothing" in markdown.lower()
