# Artifact sources

Published HTML for the two rig-hardware documents, plus the read-only Pi probe wrapper.
Kept here because the session scratchpad they were authored in is temporary.

| File | Published at | Notes |
|---|---|---|
| `rig-board-plan.html` | https://claude.ai/code/artifact/e4502582-2247-480e-8561-7421b58cdada | Technical: pin budget, audio bug, assembly, I2C design, timestamping. 13 sections, interactive header diagram. |
| `rig-component-options.html` | https://claude.ai/code/artifact/210c78a3-c293-49df-b108-26569a3646fb | Planning doc for the PI and the electronics engineer. 10 sections, system diagram, print CSS. Source of `MICS-rig-component-options.pdf`. |
| `_head.html` + `_body.html` | — | `rig-board-plan.html` is built as `_head + _body`. Edit those two and concatenate; do not hand-edit the combined file or the next rebuild overwrites you. |
| `mics-ro` | — | Forced-command read-only probe wrapper for a Pi. Never installed — see the KB for the `authorized_keys` line. |

## Republishing

These are **fragments**, not complete documents — the Artifact host adds
`<!doctype html><head>…</head><body>` at publish time. Publishing means calling the Artifact
tool with the file path and the artifact's `url`.

## Rendering locally (PDF or screenshot)

Local chromium is missing ~10 system libs and `sudo` needs a password, so use a container.
Wrap the fragment in a full HTML document first, then:

```bash
docker run --rm --user $(id -u):$(id -g) -v <dir>:/data \
  --entrypoint chromium-browser zenika/alpine-chrome \
  --headless=new --no-sandbox --disable-gpu --disable-dev-shm-usage \
  --virtual-time-budget=20000 --run-all-compositor-stages-before-draw \
  --no-pdf-header-footer --print-to-pdf=/data/out.pdf file:///data/print.html
```

Swap `--print-to-pdf` for `--screenshot=/data/x.png --window-size=1100,1400` to look at a page.
The `bus.cc … dbus` errors are noise; check for the "N bytes written to file" line.

Full write-up: `../pi_rig_hardware_kb.md`
