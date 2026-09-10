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
2. ~~**Does `mics_post_analysis/` come along?**~~ **CLOSED 2026-09-10 (user): NO.** It is not
   relevant to this repo split at all. The scope is exactly two packages -- `mics-link` and the DLC
   tooling. Do not re-open it, and do not spend a plan step checking its redistributable profile.
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

---

## DECIDED 2026-09-10 (user): public PyPI. Open question 1 is closed.

> *"I want to just be able to pip install those libs, not download them from the SMB server. In the
> future it should be one very simple command."*

**Target UX, and the phase's acceptance test:** on a fresh Windows/DeepLabCut box with no lab
network, no SMB mount, no repo access and no `--index-url` flag:

```
pip install mics-dlc-link
```

That is the whole install. `mics-link` arrives transitively. SMB wheel staging
(`yizharlab/Mics/wheel/`) is retired as a distribution channel by this phase — it stays only as a
break-glass path for an air-gapped box.

**A private git URL is therefore OUT**, not merely less preferred: it relocates the access problem
this phase exists to remove, and it is not one simple command.

### Name availability — checked against PyPI 2026-09-10

| Name | PyPI | Note |
|---|---|---|
| `mics-link` | **free** (404) | keep as-is |
| `dlc-link` | **free** (404) | current dist name in `dlc_link/pyproject.toml` |
| `mics-dlc-link` | **free** (404) | seed's suggestion; prefer it — `dlc-link` is generic enough that a DeepLabCut-adjacent project could plausibly want it, and the `mics-` prefix keeps the family visible in `pip list`. Console scripts stay `dlc-link-generate` / `-convert` / `-live`. |
| `mics` | **TAKEN** (200) | noted only so nobody reaches for it later. `mics_post_analysis/` is OUT OF SCOPE for this phase (user, 2026-09-10) and is not part of the split. |

Register both `mics-link` and the DLC name early — free today is not free in three months.

### Pre-publish blocker: `sdk/README.md` becomes the public PyPI project page

`sdk/pyproject.toml` sets `readme = "README.md"`, so that file is embedded verbatim in the dist
metadata and rendered on pypi.org. It currently publishes lab-internal topology:
`132.77.72.28` (pilot 1), `132.77.73.213` (pilot 3 / RecordingBox), `132.77.73.125` (backend) and
`132.77.73.217` (the live Elasticsearch), plus port/`source_id` pairs. Same content is in
`sdk/examples/*.py` (`DEFAULT_HOST = "132.77.73.213"`) and `sdk/tests/test_transport_config.py`.

**`dlc_link/` is clean** — zero hits for any lab host, including `RUNBOOK.md`. The scrub is
`sdk/`-only.

Scrub to placeholders (`PILOT_HOST`, `192.0.2.10`) before the first upload, and keep the real
addresses in the internal runbook. **PyPI releases are immutable**: a file can be yanked, never
un-published, so this must be fixed before upload 1, not after.

### Mechanics the plan must carry

- **Publish order: `mics-link` first.** `dlc-link` declares `mics-link>=0.1.0`; uploading the DLC
  package to an index that has no `mics-link` yields a package that installs broken.
- **Auth: PyPI Trusted Publishing (GitHub Actions OIDC), not a long-lived API token.** This lab has
  already leaked credentials into a public repo once — see `OPEN-ITEMS-2026-08-30.md` §1.
- **The new repo starts with fresh history.** Do NOT `filter-repo` it out of mics-backend:
  that history carries the `secrets/` blobs. A `git mv`-equivalent copy of `sdk/` + `dlc_link/`
  into a clean repo sidesteps the problem entirely.
- **Version bumps become public events.** Both packages are at `0.1.0` and have been distributed by
  hand as `0.2.0`/`0.3.0` wheels (Phase 35/38); reconcile the numbering before the first upload so
  `pip install -U` is monotonic for anyone already holding a hand-installed wheel.
- **Phase 38 ships wheel `0.2.0` and `0.3.0` over SMB** (plans 38-04, 38-06). That is fine and stays
  — 38 lands before 37. But 38-06's `INSTALL.md` and `dlc-link-bootstrap` describe the hand-install
  path, and 37 must rewrite them to the one-line `pip install`.

### Repo count RECONFIRMED 2026-09-10 (user): ONE repo, TWO packages

Asked directly and answered: a single new repo holding `sdk/` and `dlc_link/`, publishing two
independent distributions with independent version numbers. This matches the 2026-08-31 shape
decision above — it is now confirmed rather than merely proposed. Two separate repos were offered
and declined. Do not re-open.

Scope of the move is exactly those two directories. `mics_post_analysis/` stays in mics-backend.

### Do the shipped docs already support a PyPI install? NO — verified 2026-09-10, not assumed

Checked the actual files rather than assuming they were generic. Every install path currently
documented is a mics-backend path, so the docs do not merely lack PyPI — they actively contradict
it, and they break on the repo move independently of the channel decision.

| Doc | State today | Work in 37 |
|---|---|---|
| `sdk/README.md` §2 "Install" | Documents exactly two paths, both hardcoding this repo: a pinned GitHub release wheel URL (`.../idopo/Mics-backend/releases/download/sdk-v0.1.0/...`) and `pip install "git+https://github.com/idopo/Mics-backend.git#subdirectory=sdk"`. Closes with a standing note that the repo being public is load-bearing, and a literal **"Not supported today:** installing `mics_link` by name from PyPI. Publishing this package under a public PyPI name is a separate, deferred decision."** | **Rewrite.** Both URLs die at the move; the "not supported" paragraph is the exact sentence this decision reverses. The offline-wheel fallback survives as break-glass. |
| `dlc_link/README.md` | States **"`mics-link` and `dlc-link` are not published on PyPI today"** and redirects the reader to *"the wheel/git paths `sdk/README.md` §2 documents (the same two paths apply to this package, built from `dlc_link/` instead of `sdk/`)"* — a cross-package reference by section number, to a build-from-a-subdirectory-of-the-backend procedure. Its only real `pip install` line is `deeplabcut-live[pytorch]`. | **Rewrite**, and drop the cross-reference: after the split each package documents its own one-line install. |
| `dlc_link/RUNBOOK.md` | **Least affected.** Step 2 says "Install `deeplabcut-live[pytorch]`, `mics-link`, and `dlc-link` into the clone" and names **no channel**, so it is already channel-neutral. Its load-bearing content (clone the `DEEPLABCUT` env first, stop if pip proposes a `pyzmq` UPGRADE, `selfcheck` is mandatory) is unaffected. | Light touch — fill in the concrete command; do not disturb the surrounding warnings. |

**Trap for the `sdk/` IP scrub — the README is test-gated.**
`sdk/tests/test_readme_contract.py::test_readme_contains_the_ten_line_examples_counted_lines_verbatim`
asserts every counted line of `sdk/examples/ten_line_sender.py` appears **verbatim** in
`sdk/README.md`. That example contains `with connect("132.77.72.28", 5599, "demo") as link:`.
Scrubbing the IP from the README alone therefore **fails the suite** — README and example must be
changed in one commit. The same file also carries a device-neutrality guard banning
`deeplabcut|keypoint|bodypart|pose|dlc` from the sdk README and source, so DLC install instructions
can never be folded into the SDK README. Both guards are worth keeping.
