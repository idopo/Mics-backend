# Phase 35: DeepLabCut Keypoint Likelihood Integration - Pattern Map

**Mapped:** 2026-08-31
**Files analyzed:** 11 (new package files + generated artefacts + tests)
**Analogs found:** 7 strong / 2 partial / 2 explicit "no analog"

## ⚠️ Guard the planner must not miss

`sdk/tests/test_readme_contract.py:34-36` defines the device-neutrality regex:

```python
_DEVICE_NEUTRALITY_PATTERN = re.compile(
    r"\b(deeplabcut|keypoint|bodypart|pose|dlc)\b", re.IGNORECASE
)
```

...and applies it (word-boundary, case-insensitive) to **every** file in `sdk/README.md`,
`sdk/examples/*.py` (`test_examples_are_device_neutral`, line 305) and `sdk/src/mics_link/*.py`
(`test_src_is_device_neutral`, line 309). This is a real, currently-passing pytest guard, not
aspirational — confirmed present in the tree at the cited path/lines. **Nothing this phase writes
may live under `sdk/`, and no file under `sdk/` may be edited to add DLC vocabulary**, including
comments/docstrings. `dlc_link/` must be a wholly separate installable package that depends on
`mics-link` (the built `sdk/` package) as an ordinary third-party dependency, exactly the way
`sdk/examples/callback_sender.py` demonstrates a foreign caller using it.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `dlc_link/processor.py` (dlclive-compatible `Processor` subclass) | adapter/callback | streaming (per-frame push) | `sdk/examples/callback_sender.py` | role-match (device-neutral shape only; DLC specifics have no analog) |
| `dlc_link/live.py` or `dlc_link/loop.py` (standalone paced video-file loop) | CLI entry point | streaming, paced (file-substituted-for-camera) | `sdk/src/mics_link/replay.py` (`replay()`/`main()`) | strong role+flow match |
| `dlc_link/decimate.py` (deadband + per-signal Hz cap) | utility/policy | transform | **no analog** — see below | none |
| `dlc_link/convert.py` (DLC `.h5` → wide replay file) | utility, file-I/O | batch/transform | `sdk/src/mics_link/replay_io.py` (defines the **target contract**, not a converter) | partial — contract-only match |
| `dlc_link/generate.py` (CLI: `config.yaml` → hw-lib source + bodypart map) | CLI generator/codegen | transform | **no analog** — see below | none |
| generated `<source_id>_map.py` (bodypart→signal-name mapping, imported by adapter) | generated config module | — | **no analog** (new artefact class) | none |
| generated hardware-lib source (`DLCKeypoints`/`ExternalHardware` subclass) | hardware-lib source (OUTPUT of generator, uploaded not committed) | event-driven (Pi ingestion) | `api/seed_libs/compute_ops.py` (shape reference only — rejected as delivery mechanism by D-14) + `~/mics_core/.../external_hardware.py` (decorator contract) | role-match for shape, explicit non-match for delivery |
| `dlc_link/pyproject.toml` | config/packaging | — | `sdk/pyproject.toml` | strong match |
| `dlc_link/README.md` / runbook doc (DLC-13d) | docs | — | `sdk/README.md` (structure/tone precedent, itself device-neutral so cannot be copied verbatim) | partial |
| `dlc_link/tests/test_*.py` | test | — | `sdk/tests/test_client_integration.py`, `sdk/tests/fake_transport.py`, `api/tests/test_extlink_keys.py` | strong match (pattern, not literal reuse) |

## Pattern Assignments

### `dlc_link/processor.py` (adapter/callback, streaming)

**Analog:** `sdk/examples/callback_sender.py` (whole file, 38 lines)

**The three load-bearing rules to copy verbatim** (`sdk/examples/callback_sender.py:1-20`):
```python
"""Callback / push shape MICS-Link sender.
...
  1. The client is created OUTSIDE the callback and OUTLIVES it -- the `with` block owns
     the lifetime; the callback only borrows `link`.
  2. The callback returns whatever its host expects -- never swallow the return value.
  3. Per-callback state (deadbands, last-values, ...) lives on the callback object, not
     in the SDK -- decimation and rate policy are the caller's, not mics_link's.

Never open a client INSIDE a callback, and never rely on a library's teardown hook to
close it -- some hosts have no guaranteed teardown, so a client created inside a callback
object's constructor may never be closed.
"""
from mics_link import connect
from mics_link.values import as_scalar

with connect("132.77.72.28", 5599, "demo") as link:
    def on_sample(value):
        link.send_signal("left_paw_x", as_scalar(value))
        return value  # hand the host back what it expects
```

**What differs for `dlc_link.processor.DLCProcessor`:**
- It is a real `dlclive.Processor` **subclass**, not a bare function — `dlclive` calls
  `self.processor.process(pose, **kwargs)` and **assigns `self.pose` from the return value**
  (verified in `35-DLC-LIVE-NOTES.md` "How a trained model is actually executed", D-33). The
  `link` must be passed into `__init__` (constructed in the caller's `with connect(...)` block per
  rule 1) — mirroring the analog's rule 1 exactly, just via constructor injection instead of a
  closure, because `Processor()` is instantiated by the caller and handed to `DLCLive(...)`.
- `process(self, pose, **kwargs)` **must** `return pose` (rule 2, and D-33/D-08 both restate it).
- Per-bodypart last-value + deadband state (rule 3) lives on `self` (the Processor instance), not
  in `mics_link` — this is D-20's placement decision, and it is literally rule 3 of the analog
  applied to DLC.
- Convert every pose scalar with `mics_link.values.as_scalar` (`.item()`), **never `float(...)`**
  (D-34) — the analog already imports and uses `as_scalar` for exactly this reason
  (`callback_sender.py:22,34`).
- `pose.ndim == 2` guard is new (D-08): assert and raise loudly naming `single_animal=True`
  by name, never blaming the engine — no analog for this guard exists; it is DLC-specific by
  construction and belongs in `dlc_link`, not `sdk/`.
- Coordinates are normalised 0..1 by the frame width/height the adapter already holds — no SDK
  involvement; purely arithmetic in the Processor, sourced from `35-DLC-LIVE-NOTES.md`'s worked
  example (not a codebase file — that worked `MicsProcessor` class at
  `35-DLC-LIVE-NOTES.md:434-449` is the fullest concrete reference the planner has, but it is
  **research material describing DLC 2.2.3's `model_type="base"`**; D-01/D-02 correct it to
  `model_type="pytorch"` — copy its *shape* (deadband dict, per-part loop, likelihood-then-
  coordinate send order), not its literal `model_type` value).

### `dlc_link/live.py` (standalone paced video-file loop, CLI entry point)

**Analog:** `sdk/src/mics_link/replay.py` — full file read; key excerpts:

**`connect()` ownership + Pacer usage pattern** (`sdk/src/mics_link/replay.py` `replay()`, lines
~34-64 of that function; see docstring lines 6-9 and the loop body):
```python
def replay(link, rows, mode="realtime", scale=1.0, stats=None, sleep=time.sleep, clock=time.monotonic):
    if stats is None:
        stats = ReplayStats()
    pacer = Pacer(mode=mode, scale=scale, clock=clock, sleep=sleep)
    origin_t = None
    for t, signal, value in rows:
        if origin_t is None:
            origin_t = t
            pacer.start()
        pacer.wait_until(t - origin_t)
        try:
            accepted = link.send_signal(signal, value)
        except InvalidValueError:
            stats.rejected += 1
            continue
        if accepted:
            stats.sent += 1
        else:
            stats.dropped += 1
    return stats
```
`replay()` takes `link`, it does **not create one** — `main()` builds it via public `connect(...)`
inside a `with` block (module docstring, replay.py lines 8-11). `dlc_link.live`'s video-file loop
must follow the identical split: a pure `run(link, cap, live, pacer, ...)` function the tests drive
with a fake `link`, and a `main()` that does the real `with connect(...)` + argparse.

**Argparse CLI shape** — mirror `_build_parser()` (replay.py, further down in the file) and/or
`sdk/examples/rig_checkpoint_sender.py:153-166` (`_build_parser`, `--mode` dispatch,
`--host`/`--port`/`--source-id` flags with sane defaults, never hardcoded past the default).

**What differs:**
- The paced dimension is `i / fps` (video frame index / native fps), not a recorded file's `t`
  column — `Pacer.wait_until(i / fps)` per D-30, exactly as shown in the (research-only) worked
  example `35-DLC-LIVE-NOTES.md:466-473`. `mics_link.timing.Pacer` is re-exported at
  `sdk/src/mics_link/__init__.py:17-21,25,44` specifically so Phase 35 does not reimplement it.
- `cv2.VideoCapture` frame loop replaces `read_rows(path)` — DLC-specific, no SDK analog; use
  `DLCLive.get_pose(frame)` inside the loop, which internally calls `Processor.process` (so
  `dlc_link.processor.DLCProcessor` and `dlc_link.live` share the same Processor instance).
- Print a `stats.snapshot()` summary at the end, same posture as `replay.py`'s `main()` and
  `rig_checkpoint_sender.py:44-55` (`_print_stats`) — counts and a wall-clock duration only, never
  a number that could be read as latency (both analogs make this an explicit rule; DLC-10 repeats
  it: "no latency is asserted anywhere").
- Dropping the `pacer.wait_until(...)` call is explicitly the one-line swap to a live camera later
  (D-29, comment already present verbatim in the worked example, `35-DLC-LIVE-NOTES.md:472`) —
  worth carrying into the real module's docstring so the swap point is self-documenting.

### `dlc_link/decimate.py` (deadband + Hz cap) — NO ANALOG, genuinely new

No file in this codebase implements a deadband/rate-cap decimation policy standalone; the only
prior art is the worked (non-codebase) example's inline `MOVE_EPS` check
(`35-DLC-LIVE-NOTES.md:432,444-448`) and `callback_sender.py` rule 3's *placement* directive
("decimation and rate policy are the caller's, not mics_link's" — i.e., it belongs in `dlc_link`,
confirmed by D-20). Recommend the planner treat this as new code with only a placement precedent,
not a shape precedent — write it as a small stateful class (`last_value`, `last_sent_ms` per
signal name) that `dlc_link.processor.DLCProcessor` composes, not inherits, keeping it unit-testable
in isolation with a fake clock (mirroring `Pacer`'s injectable `clock`/`sleep` seam at
`sdk/src/mics_link/timing.py:34,41-42` — that IS a strong analog for **testability shape**, even
though the decimation logic itself has none).

### `dlc_link/convert.py` (DLC `.h5` → wide replay file)

**Analog (target-contract only):** `sdk/src/mics_link/replay_io.py` — read in full (232 lines).

The wide-format contract the converter's OUTPUT must satisfy, verbatim from the module docstring
(`replay_io.py:8-13`):
```
  wide: a "t" column plus one column per signal; every non-empty cell in a row becomes one
        (t, signal, value) tuple sharing that row's t. An empty cell is skipped SILENTLY —
        it means "no sample" (an occluded tracked feature is the motivating case), not a
        malformed row.
```
Shape-detection logic the converter's output must not accidentally trip (`replay_io.py:83-95`,
`_detect_shape`): a header containing `"signal"` without `"value"` is treated as **ambiguous** and
raises — so a generated column must never be literally named `signal`. Wide-row parsing the
converter's CSV must satisfy exactly (`replay_io.py:149-163`, `_parse_wide_csv_row`): empty/blank
cells are skipped per-column, not per-row; every non-empty cell becomes its own `(t, column, value)`
tuple.

**What differs — the READ half has no analog at all:** DLC's `.h5` export is a 3-row
scorer/bodyparts/coords MultiIndex-column pandas DataFrame (`35-DLC-LIVE-NOTES.md:85-90`,
D-31), not a `(t, signal, value)` file. There is no pandas/`.h5`-reading code anywhere in this
repo to copy from — `tables`/`h5py`/`pandas` versions are confirmed present on the vision box
(D-01) but the read-and-flatten logic is new. The converter must: (1) read the `.h5` with
`pandas.read_hdf`, (2) flatten the MultiIndex columns `(scorer, bodypart, coord)` into
`<bodypart>_<coord>` signal-name columns using the **exact same name-transform the generator
emits** (D-12 — one transform, never re-derived), (3) write a CSV with header `t,<sig1>,<sig2>,...`
matching the wide contract above. Row count target from D-31: ~36k rows for a 20-min 30fps
8-bodypart export (vs ~864k for a long-format equivalent) — this is a sizing sanity-check for
tests, not a design constraint.

### `dlc_link/generate.py` (CLI: `config.yaml` → hw-lib source + bodypart map) — NO ANALOG, genuinely new

No codegen/templating precedent exists anywhere in this repo (checked `api/`, `orchestrator/` for
`Template(`/jinja/codegen — none found; the only "template.py" hits in the whole tree are inside
third-party `.venv` site-packages, not project code). This is the single largest "build from
research, not from an analog" file in the phase.

**What the generator's OUTPUT must satisfy** (this IS a strong, precisely-verified analog — the
`ExternalHardware` decorator contract at `~/mics_core/autopilot/autopilot/hardware/external_hardware.py`,
read-only, never edited by this phase per DLC-01):

Decorator signatures (`external_hardware.py:19-28`, the class-level docstring's own worked example,
already naming a `DLC_Cam1` class):
```python
from autopilot.hardware.external_hardware import ExternalHardware, signal, event, command

class DLC_Cam1(ExternalHardware):
    @signal(default=0.0, stale_after_ms=200, stale_policy="hold_last")
    def left_paw_x(self) -> float: ...
    @event(payload={"object": str, "confidence": float})
    def object_detected(self): ...
    @command
    def reset_tracker(self) -> None: ...
```
Both bare (`@command`) and called (`@command()`) forms are accepted identically
(`external_hardware.py:45-60`, `_make_decorator`).

`ALLOWED_DTYPES` / `resolve_dtype` — class-build-time `TypeError`, enforced from
`~/mics_core/.../external_hardware_wire.py:28-60`:
```python
ALLOWED_DTYPES = frozenset({float, int, bool, str})

def resolve_dtype(annotation, default):
    """Explicit annotation wins; else inferred from type(default). TypeError (class-build
    time, never on ingress) when neither is given or the dtype is outside ALLOWED_DTYPES."""
```
So the generator MUST emit either a `-> float` return annotation or a typed `default=` on every
`@signal` (D-15c) — never neither.

`resolve_stale_value` (`external_hardware_wire.py:141-156`) — the two facts D-15(a)/(b) require the
generator to enforce at generation time:
```python
def resolve_stale_value(spec, last_value, last_ts_ms, now_ms):
    """... stale_after_ms == 0 -> never stale. last_ts_ms is None -> always stale."""
    if spec.stale_after_ms == 0:
        return False, last_value
    ...
    if spec.stale_policy == "hold_last": return False, last_value
    if spec.stale_policy == "return_default": return True, spec.default
    if spec.stale_policy == "return_none": return True, None
    raise ValueError("resolve_stale_value: unknown stale_policy {!r}".format(spec.stale_policy))
```
Legal `stale_policy` values are exactly `hold_last` / `return_default` / `return_none` (raises
`ValueError` **inside FDA evaluation on the rig** for anything else — D-15b) and `stale_after_ms`
must never generate as `0` on a DLC lib (D-15a). The generator's validation step should therefore
hard-fail before emitting source if these are violated, not merely document the requirement.

`liveness_hook` (`external_hardware.py:67-75`, `validate_role_liveness` at
`external_hardware_wire.py:246-258`) — only load-bearing if the generated lib uses `role: "none"`;
DLC's `role_bind`/`router_bind` role (an ordinary socketed device, per DLC-01's "role:
`router_bind`") does NOT require a `liveness_hook` override, so the generator likely emits none —
confirm this against DLC-01's stated role before assuming an override is needed.

**Shape reference only, explicitly rejected as delivery mechanism** — `api/seed_libs/compute_ops.py`
(92 lines, full file read): shows the `@log_action`, mandatory no-op `release()` override
(base `Hardware.release()` raises if unimplemented — `Task.end()` calls it unconditionally on
every hardware object every run), and no-`__init__`-override pattern for a Pi-side class whose
fields are injected by `init_hardware()`. **D-14 explicitly rejects `api/seed_libs/` as the
delivery path for the generated DLC lib** ("Generated-and-uploaded, not seeded... a first-party
seeded lib... is the wrong mechanism for real models") — cite this file to the planner as the
closest **shape** precedent only; the delivery mechanism must be the ordinary hardware-lib upload
API, not a seed script.

**AST-extractor compatibility (must-parse constraint):** the generator's emitted source is parsed,
never imported, by `api/extlink_ast.py` (`extract_extlink_metadata`, full file read, 117 lines).
Two traps the generator must specifically avoid tripping:
- `_kwarg_value` (`extlink_ast.py:12-27`) renders **dict-valued kwargs via `ast.unparse`, never
  `ast.literal_eval`** — so `@event(payload={"bodypart": str, "likelihood": float})`-style bare
  type names work (they are `ast.Name` nodes, not literals) but any kwarg value the generator
  emits must be either an `ast.Constant` or a `dict` — nothing more exotic.
- `_signal_dtype` (`extlink_ast.py:39-50`) mirrors `resolve_dtype`'s annotation-then-default chain
  **for description only** — it does not raise, so a generator bug here fails silently at the AST
  layer (no editor signal offered) rather than loudly; the generator's own D-15(c) validation is
  the only thing that catches it before upload.
- A class is only registered by the extractor **if it declares at least one of the four
  decorators** (`extlink_ast.py:71-73,113`) — an empty/control-only class still needs at least a
  liveness override or a real `@signal` to be visible to the picker at all.

### `dlc_link/pyproject.toml`

**Analog:** `sdk/pyproject.toml` (full file, 41 lines) — the one place in this repo's convention
(root CLAUDE.md: `requirements.txt` everywhere else) that a PEP 621 `pyproject.toml` is the correct
choice, because the package is meant to be installed **outside this repo** (a researcher's own
conda env) — exactly `dlc_link`'s situation too.

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "mics-link"
...
requires-python = ">=3.8"
dependencies = ["pyzmq>=22", "msgpack>=1.0"]

[project.scripts]
mics-link-replay = "mics_link.replay:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

**What differs:** `dlc_link`'s `dependencies` must include `mics-link` itself (as an ordinary
installed dependency, never a path-relative `sdk/` import — D-29's whole point) plus
`deeplabcut-live[pytorch]` per D-03 (`requires_python = ">=3.10,<3.13"` — this floor is DLC-Live's
own, and is **tighter** than `sdk/pyproject.toml`'s `>=3.8`, so `dlc_link/pyproject.toml` cannot
just copy the `>=3.8` floor verbatim; it must state its own, narrower one). The `[project.scripts]`
mechanism is the exact precedent for `dlc_link`'s own CLI entry points (`dlc-link-generate`,
`dlc-link-convert`, or similar) — declare them the same way (`name = "module:function"`), noting
setuptools does not verify the target exists at build time (comment at
`sdk/pyproject.toml:28-29`), so this can be declared before the target module is finished.

### `dlc_link/tests/*`

**Analogs:**
- `sdk/tests/conftest.py` (13 lines, full file) — the `sys.path` shim making a `src/`-layout
  package importable without an editable install, needed if `dlc_link` also adopts a `src/`
  layout (Claude's discretion per CONTEXT.md).
- `sdk/tests/fake_transport.py` / `sdk/tests/test_client_integration.py:1-7,24-38` — the pattern
  of a hand-rolled fake standing in for a real transport so tests run with zero sockets. For
  `dlc_link`, the equivalent seam is simpler: a fake `link` object exposing only
  `send_signal(name, value) -> bool` (recording calls in a list) is sufficient for testing
  `DLCProcessor`/`decimate.py`/`generate.py` logic — there is no need to reach into
  `mics_link.client.MicsLink` or `mics_link.transport` internals, and doing so would violate the
  "public API only" posture `rig_checkpoint_sender.py`'s own docstring states (line 3-5: "Public
  API only... no `mics_link._internal`"). Recommend the planner scope `dlc_link` tests to a
  duck-typed fake link, not an imported SDK internal.
- `api/tests/test_extlink_keys.py:1-11,20-43` — pure-function test style (`FakeDb`
  dispatching on query-text substrings, no real DB/TestClient) is the closest precedent for
  testing `dlc_link.generate`'s AST-compatibility claims: a test that runs the generator's output
  string through `api.extlink_ast.extract_extlink_metadata` (importable cross-package if `api/` is
  on the test's `sys.path`, or vendored as a golden fixture) and asserts the expected
  `{"signals": {...}}` shape comes back — this is the single highest-value test the phase can
  write, since it proves the generator's output is actually consumable by the real extractor
  without needing a live DB or the Pi.

**Two test suites, per CLAUDE.md:** backend `docker compose exec -T api python -m pytest -q tests/`
(352 pass baseline) and `sdk`'s own `pytest -q` (per `sdk/pyproject.toml`'s `[tool.pytest.ini_options]`,
`addopts = "-q -m 'not zmq_loopback'"`). `dlc_link` should get its own third, analogous
`pyproject.toml`-driven `pytest -q` — it cannot run inside the api container (no `deeplabcut-live`
there) and should not be folded into `sdk/tests/` (device-neutrality guard).

## Shared Patterns

### "Own the client outside, pass it in" (SDK-09 lifecycle rule)
**Source:** `sdk/examples/callback_sender.py:8-9,14-16,31` + `sdk/src/mics_link/replay.py`
module docstring lines 8-11.
**Apply to:** `dlc_link/processor.py` and `dlc_link/live.py` both — neither may construct or close
a `MicsLink` internally; both take a `link` built by the caller's `with connect(...)` block.

### Value conversion — `as_scalar`, never `float()`
**Source:** `sdk/src/mics_link/values.py:82-87` (`as_scalar`) and its rationale in the module
docstring (`values.py:1-14`, exact-type check vs `isinstance`).
**Apply to:** every value `dlc_link.processor` sends — D-34 makes this a correctness requirement,
not a style preference, because `numpy.float64` passes an `isinstance(value, float)` check but
cannot be packed by msgpack, turning a call-site error into an invisible IO-thread failure.

### Counts-only reporting, never a latency number
**Source:** `sdk/src/mics_link/replay.py` module docstring + `sdk/examples/rig_checkpoint_sender.py:7-8,44-55`
(`_print_stats`).
**Apply to:** `dlc_link/live.py`'s end-of-run summary and any soak-mode output — DLC-10 states this
explicitly ("No latency is asserted anywhere"); `SenderStats` fields available for this are
`enqueued`, `sent`, `dropped`, `abandoned`, `send_failed` (`sdk/src/mics_link/sender.py:52-56`,
exposed via `link.stats.snapshot()`, property at `sdk/src/mics_link/client.py:154-156`).

### Pacer injection for testability
**Source:** `sdk/src/mics_link/timing.py:34,41-42` (`clock`/`sleep` constructor injection) and
`replay.py`'s `replay(..., sleep=time.sleep, clock=time.monotonic)` signature.
**Apply to:** `dlc_link/live.py` (already gets `Pacer` for free) and, as a testability idiom worth
copying even without a shared implementation, `dlc_link/decimate.py`'s own time-based Hz cap.

### Hardware-lib pipeline is unmodified — the generated lib is an ordinary customer
**Source:** `api/extlink_keys.py` (`derive_extlink_keys:52-62`, `module_extlink_signals:82-167`),
`api/fda_validation.py` (`validate_compute_variables:209-276`, `reject_if_hard_errors:301-...`),
`api/routers/toolkits.py` (`_build_toolkit_row:70-108`, `extlink_signals_by_module` wiring at
lines 145-162 and 210-211).
**Apply to:** nothing in `dlc_link/` touches these files (DLC-01: "Zero new Pi ingress, zero new
dispatch shapes, zero substrate change") — cited here only so the planner does not accidentally
scope backend work into this phase. The ordering constraint they impose (D-36) belongs in the
runbook doc, not in code: `derive_extlink_keys` returns `[]` without a non-empty
`config["source_id"]` in a `pilot_hardware_config` row (`extlink_keys.py:56-60`), so "upload lib"
must precede "author transition" by at least two more steps (module registration, config row).

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `dlc_link/decimate.py` | utility/policy | transform | No deadband/rate-cap decimation code exists anywhere in this repo; only a non-codebase worked example in research notes and a placement directive (`callback_sender.py` rule 3) exist as prior art. |
| `dlc_link/generate.py` | CLI codegen | transform | No template/codegen precedent anywhere in the project (checked `api/`, `orchestrator/`; only third-party `.venv` hits for "template"). The OUTPUT contract (ExternalHardware decorators, AST-extractor compatibility) is well-specified above; the generation mechanism itself (string templates vs AST-building vs f-strings) is unconstrained by any existing file. |
| `dlc_link/convert.py` (the `.h5`-reading half specifically) | file-I/O | batch | No pandas/`.h5`-reading code exists in this repo. The wide-CSV-writing half has a precise contract analog (`replay_io.py`); the DLC-side read/flatten half does not. |
| generated `<source_id>_map.py` (bodypart→signal-name map) | generated config module | — | New artefact class — nothing in the codebase generates-then-imports a sibling mapping module today. D-12 requires it exist as an importable module, not a JSON/YAML side-file, specifically so the adapter's `import` fails loudly on drift; no precedent for that exact mechanism was found. |

## Metadata

**Analog search scope:** `sdk/` (src, examples, tests, pyproject.toml), `api/` (extlink_keys.py,
extlink_ast.py, fda_validation.py, routers/toolkits.py, seed_libs/compute_ops.py, tests/), root
`CLAUDE.md`, and the read-only reference tree `~/mics_core/autopilot/autopilot/hardware/` (three
files: `external_hardware.py`, `external_hardware_wire.py`, `external_hardware_ingress.py` —
consulted per the required-reading list; `_ingress.py` confirmed the "no ingress queue" finding
already recorded in `35-DLC-LIVE-NOTES.md` but contributed no new pattern beyond what
`external_hardware.py`/`external_hardware_wire.py` already supply).
**Files scanned (read in full or targeted range):** `sdk/tests/test_readme_contract.py`,
`sdk/examples/callback_sender.py`, `sdk/examples/rig_checkpoint_sender.py`,
`sdk/examples/ten_line_sender.py`, `sdk/src/mics_link/__init__.py`, `timing.py`, `values.py`,
`replay_io.py`, `replay.py` (partial), `client.py` (partial), `sender.py` (partial),
`sdk/pyproject.toml`, `sdk/tests/conftest.py`, `sdk/tests/fake_transport.py` (partial),
`sdk/tests/test_client_integration.py` (partial), `api/extlink_keys.py`, `api/extlink_ast.py`,
`api/fda_validation.py` (partial), `api/routers/toolkits.py` (partial), `api/seed_libs/compute_ops.py`,
`api/tests/test_extlink_keys.py` (partial), `~/mics_core/autopilot/autopilot/hardware/external_hardware.py`,
`external_hardware_wire.py`.
**Pattern extraction date:** 2026-08-31
