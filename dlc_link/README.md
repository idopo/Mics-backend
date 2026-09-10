# dlc_link

A DeepLabCut adapter and hardware-lib-source generator for MICS. `dlc_link` is an
ordinary third-party consumer of the `mics-link` public API — it depends on `mics-link`
as a normal installed package, exactly the way `sdk/examples/callback_sender.py`
demonstrates a foreign caller using it. Nothing under `sdk/` knows `dlc_link` exists.

## Console scripts

| Script | Purpose | Extra required |
|---|---|---|
| `dlc-link-generate` | Reads a DeepLabCut `config.yaml` and emits (a) an `ExternalHardware` subclass source file the researcher pastes into the hardware-lib upload page, and (b) a machine-readable bodypart -> signal-name map. | none (core) |
| `dlc-link-convert` | Converts a DeepLabCut `.h5` pose export into a wide `(t, signal)` replay file consumable by `mics-link-replay`. | `convert` |
| `dlc-link-live` | Runs a `DLCLive` processor against a video source (camera or file) and streams keypoint signals to a pilot over `mics-link`. `--view` adds an annotated live picture in a notebook or a localhost browser tab. | `live` |

## Extras

- `live` — `deeplabcut-live[pytorch]`, `opencv-python-headless`. Installs the live
  inference stack. DLC-Live's own metadata pins `requires-python >=3.10,<3.13`, which pip
  enforces automatically when this extra is requested.
- `convert` — `pandas`, `tables`. Installs the `.h5` reader for the offline converter.

## Write footprint

Every script in this package obeys one rule: no module writes any file unless an
explicit path flag says where, no writing flag has a default, and no module writes to
the current working directory or the system temp root. This matters because the
researcher's DLC project directory is read-only by requirement, and their shell prompt
typically sits inside it.

| Script | Writes |
|---|---|
| `dlc-link-generate` | Only to the directory named by its explicit `--out-dir` flag; refuses if that directory is the project directory or a descendant of it. |
| `dlc-link-convert` | Only to the file named by its explicit output-path flag. |
| `dlc-link-live` | Writes nothing anywhere, with or without `--view`. Reads frames and sends over the network; counts go to stdout. |

## Live view

`dlc-link-live --view` draws the declared keypoints (with their likelihoods), the
researcher's own authored overlay thresholds (`--overlay`), the pilot's run identity,
and the FDA state, all updating while the task runs on the Pi. The viewer runs on its
own threads and can never slow, stall, or raise into the sender: a slow, absent, or
crashed viewer changes nothing about what reaches the Pi.

Two render sinks, chosen with `--view-sink`:

- **`notebook`** (default) — displays in a Jupyter cell via `IPython.display`. Needs
  IPython in the environment; if it is absent, construction fails with a message
  naming `--view-sink mjpeg` as the alternative. See
  [`notebooks/live_view.ipynb`](notebooks/live_view.ipynb).
- **`mjpeg`** — a stdlib `http.server` bound to **`127.0.0.1` only** (never reachable
  from the network), serving the same annotated stream as an ordinary browser tab.
  Needs `--view-port`, and needs nothing installed — this is the answer when Jupyter
  is not, or must not be, in this environment (installing it risks a `pyzmq` upgrade
  that `mics-link`'s own transport depends on; see `RUNBOOK.md` step 2).

`--overlay`'s thresholds are the researcher's own authored numbers, never read from
the task definition's `fda_json` — every frame with an overlay carries the label
`overlay: authored locally, not read from the task definition` so it is never mistaken
for the Pi's own ground truth.

## Runbook

The researcher-facing step-by-step runbook lives in
[`dlc_link/RUNBOOK.md`](RUNBOOK.md) — the numbered path from a working DeepLabCut model to an
FDA transition authored in the browser, including the read-only-project-directory procedure
and the named ordering obstacle in the backend half. This README documents the package itself,
not the install/setup procedure for the vision box.

## Install

Inside a conda env cloned from your DeepLabCut training env (`RUNBOOK.md` step 1), one line:

```bash
python -m pip install "mics-dlc-link[live]"
```

That is the whole install. You do not need git, a GitHub account, access to any lab
repository, or a file from a network share. `mics-link` arrives automatically as a
dependency — you never install it separately.

Three names, and they are deliberately not identical:

| You type | What it is |
|---|---|
| `pip install mics-dlc-link` | the **distribution** name on PyPI |
| `import dlc_link` | the **import** package |
| `dlc-link-generate`, `dlc-link-convert`, `dlc-link-live` | the **console scripts** |

Drop the `[live]` extra if you only need `dlc-link-generate` or `dlc-link-convert` — the
core install pulls no torch, no OpenCV and no DeepLabCut, so it runs on a machine with no
GPU. `[live]` adds `deeplabcut-live[pytorch]` and `opencv-python-headless`; pip enforces
DLC-Live's own `>=3.10,<3.13` Python cap only when that extra is requested.

**Always invoke with `python -m pip`, never bare `pip`.** On a Windows box with a `py`
launcher and several Pythons installed, bare `pip` can install into the wrong interpreter
— you then get a `ModuleNotFoundError` in the environment you actually meant to use, with
no clue why.

**If pip proposes to UPGRADE `pyzmq`, stop** and read `RUNBOOK.md` step 2 before
continuing: Jupyter, IPython, Spyder and napari all depend on it.

**Offline** (an isolated vision box): `python -m pip download "mics-dlc-link[live]" --dest
./kit` on a connected machine with the same interpreter version and platform, copy `./kit`
across, then `python -m pip install --no-index --find-links ./kit "mics-dlc-link[live]"`.
