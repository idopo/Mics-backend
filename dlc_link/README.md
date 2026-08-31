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
| `dlc-link-live` | Runs a `DLCLive` processor against a video source (camera or file) and streams keypoint signals to a pilot over `mics-link`. | `live` |

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
| `dlc-link-live` | Writes nothing anywhere. Reads frames and sends over the network; counts go to stdout. |

## Runbook

The researcher-facing step-by-step runbook lives in
[`dlc_link/RUNBOOK.md`](RUNBOOK.md) — the numbered path from a working DeepLabCut model to an
FDA transition authored in the browser, including the read-only-project-directory procedure
and the named ordering obstacle in the backend half. This README documents the package itself,
not the install/setup procedure for the vision box.

One-line install of the PyPI-published half (inside a conda env cloned from your DeepLabCut
training env, per `RUNBOOK.md` step 1):

```bash
python -m pip install "deeplabcut-live[pytorch]"
```

`mics-link` and `dlc-link` are not published on PyPI today — install them from the wheel/git
paths `sdk/README.md` §2 documents (the same two paths apply to this package, built from
`dlc_link/` instead of `sdk/`).
