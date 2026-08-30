"""AST-based import-hygiene guard for mics_link (Phase 34, Plan 01, Task 3).

Generalizes the retired POC driver's `test_wire_module_never_imports_zmq`
(`tools/extlink_driver/`, deleted in plan 34-05) from one hardcoded file to a walk of the
WHOLE `mics_link` package, so it keeps guarding modules plans 34-02..34-07 have not written
yet.

Extended per the 34-01-PLAN.md "DLC-Live and Windows" amendment: no module-scope zmq
import, no import-time side effects, and none of a short list of POSIX-only / process-
control names anywhere in the package — none of them exist on Windows, and
`multiprocessing` on Windows uses *spawn*, which re-imports every module, so an import-time
side effect becomes a duplicated socket or thread in a researcher's parallel pipeline.
"""
import ast
import os
import subprocess
import sys

MICS_LINK_SRC = os.path.join(os.path.dirname(__file__), "..", "src", "mics_link")

# Names that must never appear anywhere in the package source (substring search, same
# posture as the existing zmq-substring check in tools/extlink_driver). None of these exist
# on Windows.
FORBIDDEN_SUBSTRINGS = [
    "os.fork",
    "signal.SIGALRM",
    "import resource",
    "os.getuid",
    "import fcntl",
    "import termios",
    "ipc://",
]


def _iter_package_py_files():
    for root, _dirs, files in os.walk(MICS_LINK_SRC):
        for name in files:
            if name.endswith(".py"):
                yield os.path.join(root, name)


def _module_scope_statements(tree):
    """Yields (statement, in_class) for every statement that executes AT IMPORT TIME:
    direct children of the module body, and direct children of any class body nested at
    module scope (a class body executes when the class statement runs, i.e. at import
    time). Statements inside function/method bodies are deliberately excluded — that is
    how transport.py (plan 34-02) will reach zmq lazily, and the allowance is intentional,
    not an oversight.
    """
    for node in tree.body:
        yield node, False
        if isinstance(node, ast.ClassDef):
            for sub in node.body:
                yield sub, True


def _is_zmq_import(node):
    if isinstance(node, ast.Import):
        return any(alias.name.startswith("zmq") for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        return (node.module or "").startswith("zmq")
    return False


def _is_main_guard(node):
    """`if __name__ == "__main__":` — the one module-scope statement allowed to contain a
    call, since it never executes at import time.
    """
    if not isinstance(node, ast.If):
        return False
    test = node.test
    return (
        isinstance(test, ast.Compare)
        and isinstance(test.left, ast.Name)
        and test.left.id == "__name__"
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.Eq)
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value == "__main__"
    )


def _has_import_time_side_effect(node):
    """A bare call expression at module scope IS a side effect (e.g. `connect()` or
    `threading.Thread(...).start()` run the moment the module is imported). Imports,
    def/class statements, assignments and docstrings are not calls and are allowed.
    """
    return isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)


def test_no_module_scope_zmq_import_anywhere_in_package():
    for path in _iter_package_py_files():
        tree = ast.parse(open(path).read(), filename=path)
        for node, _in_class in _module_scope_statements(tree):
            assert not _is_zmq_import(node), "module-scope zmq import in {}".format(path)


def test_wire_module_contains_no_zmq_substring_at_all():
    wire_path = os.path.join(MICS_LINK_SRC, "wire.py")
    src = open(wire_path).read()
    assert "zmq" not in src


def test_no_import_time_side_effects_in_package():
    for path in _iter_package_py_files():
        tree = ast.parse(open(path).read(), filename=path)
        for node in tree.body:
            if _is_main_guard(node):
                continue
            assert not _has_import_time_side_effect(node), (
                "import-time side effect (bare call at module scope) in {}: {}".format(
                    path, ast.dump(node)
                )
            )


def test_no_forbidden_posix_only_names_anywhere_in_package():
    for path in _iter_package_py_files():
        src = open(path).read()
        for forbidden in FORBIDDEN_SUBSTRINGS:
            assert forbidden not in src, "{!r} found in {}".format(forbidden, path)


def test_wire_importable_with_zmq_unavailable():
    """Proves mics_link.wire imports on a machine with no pyzmq installed, by running a
    subprocess with a sys.meta_path finder that raises ImportError for `zmq` before any
    real zmq (if present on this dev host) can be found.
    """
    src_dir = os.path.abspath(os.path.join(MICS_LINK_SRC, ".."))
    script = (
        "import sys\n"
        "class _BlockZmq:\n"
        "    def find_module(self, name, path=None):\n"
        "        if name == 'zmq' or name.startswith('zmq.'):\n"
        "            raise ImportError('zmq blocked for hygiene test')\n"
        "        return None\n"
        "sys.meta_path.insert(0, _BlockZmq())\n"
        "import mics_link.wire\n"
        "print('OK')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=src_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout
