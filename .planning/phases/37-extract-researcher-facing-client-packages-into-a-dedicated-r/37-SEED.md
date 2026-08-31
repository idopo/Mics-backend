# Phase 37 seed — decided in discussion 2026-08-31

Captured mid-Phase-35 execution, from a design conversation about where the CLI tooling and the
hardware libs belong. **Not a plan.** Run `/gsd-discuss-phase 37` before planning; the distribution
channel is genuinely open and it is the decision the rest depends on.

## The problem, stated precisely

Two redistributable, researcher-facing packages live inside the SERVER repo:

| Package | Dir | Runs on | Audience |
|---|---|---|---|
| `mics-link` | `sdk/` | researcher laptop, DLC conda env | lab + outside |
| DLC tooling | `dlc_link/` | Windows box running DeepLabCut | genuinely third-party |

`sdk/pyproject.toml` already says the quiet part out loud: *"a redistributable package meant to be
installed on machines OUTSIDE this repo entirely (a researcher's laptop, a DeepLabCut conda env)"* —
`Operating System :: OS Independent`, `requires-python >=3.8`, dependency floors deliberately picked
to already be satisfied in a scientific Python stack.

So today, "install our SDK" implicitly means "get read access to the mics-backend repo." For a
third-party Windows/DLC user that is an access problem, not a convenience one.

## What is NOT the problem

**Hardware libs are not a repo problem.** They execute from `hardware_lib_versions.source_code`,
selected by the task definition's `hw_lib_versions` pin (`api/hw_introspect.py:175`,
`api/extlink_keys.py:75`). A "plugin repo for hw libs" was proposed and rejected: it would be a
SECOND source of truth the runtime never reads, reproducing the existing trap where a Pi `git pull`
does not deploy them. The generator is a client tool; its OUTPUT is a backend artifact. Different
homes, correctly.

**Pi code is not affected.** `mics_core` is a rig deployment unit (`autopilot/`, `pilot/`,
`deploy/`, `run_pilot.sh`) — everything in it ships to a Pi. The DLC tooling never runs on a Pi.

## Where extlink actually lives (three roles, two repos)

| Role | Repo | Code |
|---|---|---|
| Sender | mics-backend (wrong home) | `dlc_link/`, `sdk/` |
| Ingest / validate / store | mics-backend (correct) | `api/extlink_ast.py`, `api/extlink_keys.py` |
| Consumer | mics_core (correct) | `autopilot/autopilot/hardware/external_hardware_*.py` |

Only the sender row is misplaced.

## Decision: adjacent, not merged

One new repo, TWO packages: `mics-link` and the DLC tooling (dist name suggestion
`mics-dlc-link`), with `dlc-link` depending on `mics-link`.

Folding DLC into `mics-link` as a subpackage/extra was **rejected**:

- The intuitive benefit ("one thing to install") does not exist — `pip install dlc-link` pulls
  `mics-link` transitively, so the researcher types one line either way. Nobody ever installs two.
- **Version coupling.** `mics-link` is a wire codec whose stability is the point. Every DLC-side fix
  would bump the SDK and invite people to re-resolve `pyzmq`/`msgpack` for a change that never
  touched the wire. See 34-CONTEXT.md "DLC-Live and Windows" / SDK-14 on why those floors are
  deliberate.
- **Entry-point leakage.** `dlc-link-generate` / `dlc-link-convert` are declared at package level,
  not per-extra. A plain `pip install mics-link` would install CLIs that fail on missing
  torch/pandas.

## The key move: invert the dependency direction

Today `dlc_link/tests/test_generate_ast_contract.py` reaches sideways into the repo's own `api/`
directory (via `sys.path` insertion) to import the REAL `extlink_ast.extract_extlink_metadata` and
`extlink_keys.derive_extlink_keys`. It is the highest-value test in Phase 35 — it proves generated
lib source is actually ingestible, not merely plausible Python.

That test was initially treated as an argument AGAINST splitting. It is not. It should MOVE to the
backend test suite, with `dlc-link` as a **test-only** dependency:

- before: third-party tool → backend source (a client needing server internals)
- after: backend test suite → client package (the validator pinning its own contract)

The second is strictly better, and it is what makes the split clean rather than lossy.

## Open questions for /gsd-discuss-phase 37

1. **PyPI or private git URL?** This is the actual reason to split. A private git URL just relocates
   the access problem. PyPI is the clean answer if the users are genuinely outside the lab, and is
   far easier from a dedicated repo with its own CI.
2. **Does `mics_post_analysis/` come along?** It is the third `pyproject.toml` in this repo. Check
   whether it has the same redistributable profile so the boundary is drawn once.
3. **Repo name and dist names.** `mics-dlc-link` keeps the family visible in a `pip list` while
   staying a separate distribution. The `dlc-link-*` console script names need not change.
4. **Who owns CI/release?** Two packages, independent versions, one repo — decide tagging scheme
   before the first release.

## Sequencing

Phase 35 must VERIFY first. Plans 35-05 through 35-08 all declare `dlc_link/` paths in
`files_modified`; moving the tree earlier invalidates them.

Independent of Phase 36 — either order works.

## Effort

The current on-disk layout is already the target layout. `sdk/` and `dlc_link/` are independent
`pyproject.toml` packages with a clean dependency edge, and Phase 35-01 proved `dlc_link` imports
with `dlclive`, `torch`, `cv2` and `pandas` all absent. This is closer to a `git mv` of two
directories plus CI and release plumbing than a restructuring.
