---
created: 2026-08-05T12:39:26.069Z
title: Fix stale React bundle trap in web_ui static output
area: ui
files:
  - web_ui/react-src/vite.config.ts
  - web_ui/static/react/
  - web_ui/Dockerfile
---

## Problem

A researcher can silently run **months-old editor code** after a correct deploy, with no error
and no visible signal. This cost a full debugging cycle during phase 23 sign-off.

Three things combine:

1. **`main.js` is not content-hashed.** `vite.config.ts` pins `entryFileNames: 'main.js'`, and
   `templates/react/index.html` has a single `<script src="/static/react/main.js">`. It is the
   one file that decides which chunk loads.
2. **It is served with no `cache-control` header** — only `etag`/`last-modified`. Browsers cache
   it heuristically, so a stale copy can survive a rebuild.
3. **Old unhashed chunks are never purged and stay servable.** `web_ui/static/react/` is the Vite
   output dir; a rebuild overwrites `main.js` and adds new *content-hashed* chunks
   (`TaskEditor-ChKt7TTP.js`) but leaves the previous *unhashed* ones (`TaskEditor.js`,
   `Index.js`, …) in place. They get COPYd into the image and return HTTP 200 forever.

Result: a cached `main.js` imports `TaskEditor.js` — which still resolves — and the browser runs
that build indefinitely. Observed 2026-08-05: all 33 files in `web_ui/static/react/` were dated
**May 3**, three months stale, while the container's freshly built `main.js` (Aug 5) correctly
referenced only hashed chunks. A hard refresh (`Ctrl+Shift+R`) fixed it instantly.

This masqueraded as a missing feature: phase 23's CMP-21 fix (variables selectable in `if`-action
conditions) looked un-delivered in the browser while being provably present in the shipped bundle
and correct through the whole prop chain.

## Solution

Any one of these closes it; the first two are the durable fixes.

- **Hash the entry filename** — drop `entryFileNames: 'main.js'` so `main.js` becomes
  `main-[hash].js` and `index.html` references it. Requires confirming nothing else hardcodes
  `/static/react/main.js` (check `web_ui/app.py` and the Jinja2 templates — CLAUDE.md flags the
  `main.js` name as a "critical vite.config.ts" setting, so verify why before changing it).
- **Purge the output dir before build** — `emptyOutDir: true` in vite config, or an `rm -rf` step
  in the Dockerfile's Node stage, so no orphan chunk can outlive its build.
- **Send `cache-control: no-cache` for `/static/react/main.js`** in `web_ui/app.py` — narrowest
  change, forces revalidation while leaving hashed chunks cacheable.

Do NOT rely on telling people to hard-refresh; the failure is silent and looks like a bug in
whatever feature shipped most recently.
