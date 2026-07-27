# Poster → Print: Vector PDF Handoff

**Deliverable:** `figure_full_poster_illustrator.svg` (A0 landscape, 1189 × 841 mm).

This is a **vector** master: every title, caption, bullet, code line, state machine,
arrow and icon is live vector (infinitely sharp at any print size). Only genuine
photos/illustrations stay raster (journey art, device photos, histograms, Pi/Elastic
logos) — those are raster in any workflow. Fonts (Aptos, Cascadia Code, ComicNeue)
are **embedded** in the file, so it is self-contained.

Regenerate anytime: `python3 scratchpad/build_full_poster_illustrator.py`

---

## Why this fixes the "low-resolution" complaint
The old `figure_full_poster.pdf` was a flat raster (every glyph baked to pixels at
~305 DPI → soft at A0). A PNG would be the same. This file keeps text/shapes as
vector → razor-sharp at any size, which is what a print shop / Illustrator produces.

## Option A — Illustrator (recommended, print-shop standard)
1. Install the 3 fonts on the machine (free): **Aptos** (Microsoft, ships with Office),
   **Cascadia Code** (github.com/microsoft/cascadia-code), **Comic Neue**
   (fonts.google.com/specimen/Comic+Neue). This keeps text correct on open.
2. `File ▸ Open` → `figure_full_poster_illustrator.svg`. Document opens at A0 landscape.
3. *(optional, font-proof)* `Select All` → `Type ▸ Create Outlines` — converts text to
   vector paths so the PDF no longer depends on fonts. Save a copy first if you want
   editable text later.
4. `File ▸ Save As` (PDF) → preset **[PDF/X-4]** or **[Press Quality]**; keep page size
   A0 landscape. If the print shop wants CMYK, set it in `Edit ▸ Color Settings` /
   on export.
5. Verify: zoom to 800% — text edges stay crisp (vs the old PDF where they pixelate).

## Option B — Browser (zero install, any machine)
Because fonts are embedded, Chrome/Edge render it correctly:
1. Open the `.svg` in Chrome → `Ctrl/Cmd+P`.
2. Destination **Save as PDF**, Margins **None**, **Background graphics ON**.
3. Save. Text stays vector. (If paper size isn't A0, set it in the print dialog or
   use `chrome --headless --print-to-pdf=out.pdf --no-pdf-header-footer file.svg`.)

## Known cosmetic check (Panel 4 — THE LOGIC)
The state-machine boxes use SVG drop-shadows + text "halo" outlines. Illustrator's
SVG import usually keeps these, but occasionally rasterizes/drops a filter. After
opening, glance at the TONE/REWARD/OPTO boxes; if a shadow is missing, re-add it in
AI (`Effect ▸ Stylize ▸ Drop Shadow`) — one-off, cheap. (The browser path renders
them natively.)

## Not changed (per decision)
Panel-1 journey art (~150 DPI, source-limited), the histograms, and the embedded
illustration white backgrounds were intentionally left as-is.
