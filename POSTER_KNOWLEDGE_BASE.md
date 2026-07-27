# MICS Poster — Knowledge Base

Single source of truth for the conference-poster work (Ido's science-forward take on
MICS). Return here at the start of any poster session. Keep it updated as decisions land.

---

## 1. Goal & current direction

The coworker's poster (`MICS poster final OY_is.pptx`) is **engineering-forward**: it
presents MICS as a problem→solution story about experiment-control software, but never
states the **scientific question** that motivated building MICS.

**Ido's direction:** keep the problem→solution spine, but **inject the science** —
(a) one new *scientific* figure that frames the biological question and shows why it
demands a flexible/robust/reproducible system, and (b) retrofit selected technical
figures so they use *our actual experiment* instead of generic examples.

Work proceeds **step by step** (one figure at a time). Do **not** build the whole poster.

### Figure plan — FINAL 6-panel layout (Ido, 2026-06-16)

Full canvas = A0 landscape 118.9 × 84.1 cm, header + three 39.6 cm columns. Measurements in
§3b, cross-figure colors + timing in §3c. Six panels:

1. **DREAM experiment** (left-top) — the biological question + setup (hardware wired, DLC).
2. **Problem → Solution** (left-bottom) — the "switch": scaling ↔ data accumulation.
3. **Hardware abstraction** (middle-top) — devices our experiment actually used; element
   colors locked to §3c (audio, opto, reward, lick, nosepoke).
4. **Task definition: code vs state machine + timing** (middle-bottom, the big combined
   panel) — opto variant only. State-machine circles are colored per §3c. Below the
   code-vs-FDA comparison, a **local-execution / time-precision** strip reuses the same
   colors and the closed-loop delay numbers from §3c (image34).
5. **MICS Portal + declarative database** (right-top) — Portal defines experiments &
   monitors activity (show **one Core** only), plus the declarative DB (it ties to task
   building/execution).
6. **Structured storage + event logging + experiment reconstruction** (right-bottom) —
   "Closed-loop control of neural perturbation based on behavior"; coloring matches §3c so
   the audio cue is the *same* color here, in #3 hardware abstraction, and in #4 state machine.

Built state-machine versions live in `figure_state_machine_vs_code*.svg` (adapt the opto one).

---

## 2. The science (experiment being run on MICS)

**Big question:** How does **functional connectivity in mPFC** reshape during
**appetitive learning** (cue→reward association), and how do **SST interneurons**
gate that process? Framing chosen: mPFC for **value-guided action selection**.

**Why hard / why high-variance:** three interacting cortical cell types whose dynamics
conflict —
- **Pyr** (pyramidal / excitatory)
- **PV** (parvalbumin interneuron, fast-spiking, inhibitory)
- **SST** (somatostatin interneuron, inhibitory) ← the manipulated population

Their **distribution differs between subjects** → high variance → **many subjects** needed
→ reproducibility is essential.

**Manipulation (optogenetics):**
- **Opsin: GtACR** (anion channelrhodopsin; inhibitory), Cre-dependent.
- **Line: SST-Cre, homozygous** (higher Cre penetrance). Cre-dependent GtACR restricts
  inhibition to SST cells only.
- Inhibition is **SST-only, inhibitory**, because the 3-cell-type network has conflicting
  dynamics and limited clean ways to push it.
- **Flexible timing is required** — perturb **during the cue, during the action, or during
  the reward** ("micro" changes). This on-the-fly retargeting is a core driver for MICS.

**Recording:** **acute Neuropixels** in mPFC, recording all cell types simultaneously,
combined with the closed-loop opto.

**Task arc ("macro" changes), maps to existing Blueprints A/B/C:**
- **A — Association:** tone → reward (the base appetitive task).
- **B — Generalization:** test whether learning is sped up / transfers (e.g. new cue / LED).
- **C — Extinction:** remove reward entirely.

**Tracking:** learning state and cell dynamics must be tracked **rigorously, every trial**
(complete timestamped logging) to estimate where each subject is in learning.

### Assumptions still to confirm with Ido (used as defaults until corrected)
- **Functional-connectivity metric:** assumed spike-train cross-correlograms (CCG) between
  cell types. (Could be noise correlations / GLM coupling.)
- **Cell-type ID:** assumed SST optotagged; Pyr vs PV split by spike waveform/firing rate.
- **Learning readout:** assumed anticipatory licking during the cue.
- **GtACR variant:** "GtACR" given; likely soma-targeted stGtACR2 — confirm exact variant.
- **Generalization cue identity** (LED vs new tone) — confirm.

---

## 2b. Experiment reconstruction — Blueprint A (feeds panels 3, 4, 6)

Reconstructed from the real task `pilot/plugins/AppetitiveTaskReal.py` (Blueprint A:
tone→reward), but described **purely at the diagram / logical-flow level** — the whole point
of the "code vs state machine" panel is the abstraction, so omit code internals, drivers,
pins, timers-as-hardware, lick-counting mechanics, doors/motors.

### Panel 3 — Hardware abstraction (roles, not wiring)
The task is defined over **five semantic elements** + a sync line. Color-locked to §3c.

| Element | Role | §3c color |
|---|---|---|
| **Tone** | the cue (CS+) | audio blue `#5B9BD5` |
| **Lick** | the response | lick black `#000000` |
| **Water** | the reward (US) | reward gold `#C8994C` |
| **Opto** | SST inhibition (GtACR) | opto yellow `#E6C200` |
| **Sync (TTL)** | aligns ephys + DLC camera to behavior | neutral |

The message: the task references named roles, independent of which board/pin they map to.
(Nosepoke exists in legacy A but is dropped from the simplified figure; LED is Blueprint B,
not A; doors/motorized sipper are cage management, not behavioral logic — keep all out.)

### Panel 4 — Task definition: code vs state machine (opto variant, SIMPLIFIED)
States: **Prepare session → Trial start → Tone (cue) → Response window → {Water+Opto | Miss}
→ ITI →** (loop to Trial start).

- **Prepare session** — fires the **TTL** pulse that syncs **electrophysiology + DLC camera**;
  entered once before the trial loop.
- **Tone (cue)** → **Response window**.
- **Response window → Water + Opto** : on **Hit** (the **detection** event); the **tone stops
  on Hit**. The arrow is the **state transition**; **water reward** is the **action**.
- **Response window → Miss** : window elapses.
- **Water+Opto** / **Miss → ITI**; **ITI → Trial start** : interval elapses.
- **Opto rule = the "+1" of the variant:** the manipulation fires **with** the reward
  (closed-loop, action-coupled — NOT cue-coupled). This is the legacy reward-window variant;
  the cue/action retargeting in §2 is the broader goal.

**Latency mapping (matches the coworker's measured stages → §3c timing strip):**
detection = **Hit** → state transition = **arrow into Water+Opto (4.4 ms)** → action =
**water (0.8 ms)** → end-to-end **5.2 ms**.

### Panel 6 — Structured storage + event logging + reconstruction
"Closed-loop control of neural perturbation based on behavior — Blueprint A." Every state
entry / element event is timestamped to structured storage; from the log alone you rebuild
one trial as the image18-style raster (**tone bar → lick tick → water+opto window**), with
neural data aligned through the **TTL sync** line. No pins/drivers appear — just the
behavioral timeline reconstructed from events.

---

## 3. Poster house style (match EXACTLY for cohesion)

From `MICS poster final OY_is.pptx` (square slide, 43200638 × 43200638 EMU ≈ 48"×48")
and the native figures embedded in it (e.g. "Closed-loop delay" = `image34.png`).

**Fonts**
- Display/body: **Aptos** (theme font is Aptos Display / Aptos).
- Monospace (code): **Cascadia Code**.
- TTFs live in `/tmp/fonts/` (Aptos {Regular,Bold,Italic}, CascadiaCode {Regular,Bold,Italic}).
  If `/tmp` was cleared: re-download Aptos from github `ironveil/ttf-aptos` and Cascadia Code
  from `microsoft/cascadia-code` release zip (ttf/static/CascadiaCode-*.ttf).

**Palette** (all sampled from the poster's own shapes)
| token | hex | use |
|---|---|---|
| green | `#0B5B1F` | MICS / "good" / bottom-caption titles |
| sage | `#B5CEC0` | green card stroke / fill accents |
| red | `#AC0B08` | "problem" / "bad" |
| pink | `#FCEBEB` | problem card fill |
| navy | `#1D348B` | logic labels, arrows |
| ink | `#0E2841` | body text, figure titles |
| gold | `#C8994C` | reward accent (text `#8A5A12`) |
| purple | `#5C2C9A` | accent (appears in poster shapes) |
| paper | `#FFFFFF` | box fill |
| bg | `#F5F7FA` | figure background (NOT pure white) |
| subtitle gray | `#5A6068` | italic subtitles / captions |

**Figure anatomy** (the repeating template, see `figure_state_machine_vs_code_poster.svg`)
1. bg rect `#F5F7FA`.
2. Centered title: Aptos bold 23px `#0E2841`; italic subtitle 11.5px `#5A6068`.
3. Optional full-width context strip `#ECEFF3`, ~44px tall, with bold lead-in + body.
4. Two panels (cards `rx=10`, colored 1.2px stroke, tinted fill).
5. Per-panel verdict line (✓ green / ✗ red) ~12px bold.
6. Bottom caption: green bold 19px title + gray 12.5px subtitle (restates takeaway).
- Rounded state boxes: `rx=10`, 2px colored stroke, white fill; gold fill `#FBF3E2` for reward.
- Arrow marker: small navy triangle (`marker-end`), 2px navy strokes; transition labels
  navy 11.5px with bg-colored paint-order halo for legibility.
- **No saturated header bars** (we removed those — the poster's native figures don't use them).

---

## 3b. Conference print constraints (FENS — hard rules)

**Physical size**
- **Max:** 180 cm wide × 84 cm high. Nothing may exceed this envelope.
- **Preferred:** **A0 landscape** = 118.9 cm × 84.1 cm (aspect ≈ 1.41).
- Affix with double-sided tape (provided at poster help desks).

**Logistics**
- Mount: 08:00 (morning) or 13:00–14:00 (afternoon).
- Remove: morning posters by 13:00; afternoon posters 17:30–18:00. Late posters get
  recycled by FENS volunteers.

**⚠️ Proportion mismatch (must fix before laying out content)**
- The reference pptx (`MICS poster final OY_is.pptx`) is a **perfect square: 120 × 120 cm
  (43200638 × 43200638 EMU, aspect 1.0).** That is **not** a legal poster shape — it is
  taller than the 84 cm limit and not landscape.
- **CHOSEN canvas (Ido, 2026-06-16): A0 LANDSCAPE = 118.9 × 84.1 cm** (the FENS *preferred*
  format; safer board fit than the 180×84 max). Three ~37 cm-wide columns. Reading flow
  left→right, top→bottom. Top-left = DREAM/science, then problem→solution, then tech figures.
  NOTE: width is only 118.9 (not 180) — columns are 37 cm, so figures are portrait-ish.
- New content order: **(1) science / DREAM experiment + the idea → (2) problem→solution
  "switch" (scaling vs data accumulation) → (3) the remaining technical figures.**

**FINAL layout & measurements — A0 LANDSCAPE (118.9 × 84.1 cm)**

Vertical budget (top→bottom, unchanged from the 180 plan since height ≈ same): top margin
**2** + header **10** + gap **2** + content **68** + bottom margin **2** = 84 cm. Three columns
of **39.6 cm** each (118.9 ÷ 3, edge-to-edge thirds; ~2 cm gutter lives *inside* the block ⇒
usable figure width ≈ 37 cm). Inter-figure gutter within a column ~2 cm.

```
┌──────────────────── HEADER  (118.9 × 10) ────────────────────┐
├──── Col 1 (39.6) ───┬─── Col 2 (39.6) ──┬──── Col 3 (39.6) ───┤
│ [1] DREAM exp       │ [3] HW abstract   │ [5] MICS Portal +   │
│      39.6 × 33      │     39.6 × 22     │     declarative DB  │
│                     ├───────────────────┤      39.6 × 33      │
├─────────────────────┤ [4] Task def:     │                     │
│ [2] Problem → Soln   │  code → state mc  ├─────────────────────┤
│      39.6 × 33      │  (opto) → timing  │ [6] Structured store│
│                     │  STACKED vert.    │  + event logging +  │
│                     │     39.6 × 44     │  experiment reconstr│
│                     │  (1/3 HW : 2/3)   │      39.6 × 33      │
└─────────────────────┴───────────────────┴─────────────────────┘
```

| # | Panel | Size (cm) | Aspect |
|---|---|---|---|
| 1 | DREAM experiment (L-top) | 39.6 × 33 | 1.20:1 |
| 2 | Problem → Solution (L-bottom) | 39.6 × 33 | 1.20:1 |
| 3 | Hardware abstraction (M-top, the 1/3) | 39.6 × 22 | 1.80:1 |
| 4 | Task-def code-vs-FDA + timing (M-bottom, the 2/3) | 39.6 × 44 | 0.90:1 (portrait, the big one) |
| 5 | MICS Portal + declarative DB (R-top) | 39.6 × 33 | 1.20:1 |
| 6 | Structured storage + reconstruction (R-bottom) | 39.6 × 33 | 1.20:1 |

- Panels 1/2/5/6 all share one size (39.6 × 33, 1.20:1) — reflow the landscape source figures
  to be more vertical/compact. Panel 3 lands ~1.8:1 (near the figures' native 2:1 ✓).
- **Panel 4 must STACK vertically** (no room for side-by-side at ~37 cm usable): code block on
  top → state-machine with colored FDA circles (§3c) in the middle → local-execution /
  time-precision strip at the bottom (same colors + §3c closed-loop times). Internal split of
  its 44 cm ≈ code 16 / state-machine 16 / timing 12.
- A0 costs ~34% of area vs 180×84 — entirely from **width** (height is the same). If a figure
  feels cramped at ~37 cm wide, that is the binding constraint — simplify content, don't shrink type.
- Type: design each figure at a narrower native px (e.g. ~790 px ⇒ ~0.5 mm/px) so template
  title 23 px ⇒ ~33 pt / body 12 px ⇒ ~17 pt holds. Still bump body type **~1.4–1.6×** toward
  the ~24 pt poster minimum; carry less content per figure.

---

## 3c. Cross-figure color & timing map (lock these for cohesion)

**Experiment-element colors** — sampled from the poster's own raster `image18.png` legend
("Audio-aligned trials split by licking"). The SAME element must use the SAME color in
panels #3 (HW abstraction), #4 (state machine), and #6 (reconstruction).

> ⚠️ **Panel 6 sources its state-machine / reconstruction colors from the FINISHED `figure_task_definition.svg`
> (Panel 4), NOT from this §3c table (Ido, 2026-06-24).** Panel 4's state fills/strokes are the lock:
> TONE `#5B9BD5` / fill `#EAF3FA`; REWARD `#C8994C` / fill `#FBF3E2` (text `#8A5A12`); **OPTO `#5C2C9A` /
> fill `#EEE6F7` (purple, NOT the §3c yellow)**; ITI green `#0B5B1F`; STOP-TONE grey `#9AA0A6`; lick `#000000`.

| element | raster fill (image18) | saturated stroke (for vector figs) | note |
|---|---|---|---|
| **audio cue / tone** | `#D5EBF2` light blue | `#5B9BD5` | the cue state/bar |
| **opto (GtACR inhibition)** | `#FFFF7F` yellow | `#E6C200` | the manipulation |
| **nosepoke** | `#FFDFE4` pink | `#E68FB0` | port-entry epoch |
| **reward (water)** | — | gold `#C8994C` (text `#8A5A12`) | from §3 palette |
| **lick** | black ticks `#000000` | `#000000` | event ticks |
| **trial line** | gray `#828282` | `#828282` | trial baseline |

**Closed-loop timing numbers** — from the poster's native `image34.png` ("Closed-loop
delay"). Use these exact values in panel #4's timing strip, with the matching stage colors:

| stage | μ | σ | color |
|---|---|---|---|
| Detection → State Transition | **4.4 ms** | 2.0 ms | blue `#4C72B0` |
| State Transition → Action | **0.8 ms** | 0.8 ms | green `#27AE60` |
| **Detection → Action (end-to-end)** | **5.2 ms** | 2.3 ms | orange `#E67E22` |

These three stage colors (blue/green/orange) are the *latency-pipeline* palette; keep them
distinct from the *element* colors above (which tag experimental signals). image18/image34
live in the pptx at `ppt/media/` (extract via `python3 -m zipfile -e "<pptx>" /tmp/x`).

---

## 4. Render pipeline (SVG → PNG)

Box had no Aptos/Cascadia fonts and no SVG renderer; pipeline was set up in `/tmp`:
- `@resvg/resvg-js` installed in `/tmp/svgrender/`; script `/tmp/svgrender/render.mjs`
  (`fontDirs:['/tmp/fonts']`, `loadSystemFonts:false`, `defaultFontFamily:'Aptos'`,
  `fitTo` width = 1200 × scale).
- **Individual panel figures** (`poster_figures/*.svg`): render at **3×** (3600×1800 for a 1200×600
  figure) — fast, fine for iteration and for embedding into the assembled poster.

```bash
cd /tmp/svgrender
node render.mjs "/home/ido/mics-backend/<figure>.svg" "/home/ido/mics-backend/<figure>.png" 3
```

- **Assembled full poster** (`figure_full_poster.svg`, base 2376×1680 = A0 landscape): use
  `render_poster.mjs` (it takes an explicit base width, unlike `render.mjs` which hardcodes 1200).
  - **Iteration / screen:** **3×** → 7128×5040 (~152 DPI at A0). Quick to render.
  - **PRINT / FINAL EXPORT:** render at **5×** → **11880×8400 (~254 DPI at A0)** — this is the pipeline
    default for the deliverable. (6× → 14256×10080 ≈ 300 DPI if the print shop insists on 300.)
  - Source is vector, so a higher scale is a pure re-render with zero quality loss (only the embedded
    panel PNGs are resolution-bound, and they're already 3× of native). The big PNG (~16 MB at 5×)
    trips PIL's `DecompressionBombWarning` on *read* — set `Image.MAX_IMAGE_PIXELS=None`; harmless.

```bash
cd /tmp/svgrender
node render_poster.mjs "/home/ido/mics-backend/figure_full_poster.svg" "/home/ido/mics-backend/figure_full_poster.png" 2376 5   # 5× print export
```

### Assembly stage — edit a panel, then ALWAYS view the whole (current working mode, 2026-06-28)

Panel polish is no longer reviewed in isolation. The project has reached the **assembly stage**: every
panel edit must flow through to the assembled poster and be reviewed **as a whole** before it's
considered done. The full loop after touching any `poster_figures/<panel>.svg`:

1. **Re-render the panel** 3×: `node render.mjs ".../poster_figures/<panel>.svg" ".../poster_figures/<panel>.png" 3`
2. **Re-assemble the poster** (re-embeds the updated panel PNGs as base64): `python3 scratchpad/build_full_poster.py` → rewrites `figure_full_poster.svg`
3. **Render the full poster** (see §4 command above) → `figure_full_poster.png` (5× = 11880×8400)
4. **View as a whole**: downscale to ≤2000 px (`Image.MAX_IMAGE_PIXELS=None`, `im.thumbnail((2000,2000))`)
   and eyeball the assembled poster — column balance, cross-panel cohesion, legibility at poster scale.
   A change that looks right in the lone panel can read wrong in the grid; the whole-poster view is the
   acceptance check.

> Default expectation from Ido: after any figure tweak, **render and show the full poster**, not just the
> edited panel. The single-panel render is only an intermediate iteration step.

If `/tmp/svgrender` or `/tmp/fonts` are gone, recreate: `npm install @resvg/resvg-js` in
`/tmp/svgrender`, restore fonts (see §3), and re-create `render.mjs` (and `render_poster.mjs`, which
adds an explicit base-width arg) with the settings above.

**Rendering the source pptx → PNG (to recycle native panels "as is", e.g. v2's local-execution
illustration).** Box has no LibreOffice/Inkscape and no sudo, but `aspose.slides` (pure-Python,
.NET-backed) works in a venv once its native deps are satisfied:
- `python3 -m venv /tmp/pptxenv && /tmp/pptxenv/bin/pip install aspose.slides Pillow numpy`
- Aspose bundles **.NET Core 3.1**, which needs **OpenSSL 1.1** (system only has OpenSSL 3) and
  **libgdiplus** + its graphics chain (cairo/pango/harfbuzz/pixman…). None are installed.
- Get them WITHOUT sudo via `apt-get download <pkg>` (works unprivileged) into a dir, then
  `dpkg-deb -x *.deb root/`. Resolve the recursive dep set of `libgdiplus libcairo2 libpango-1.0-0
  libpangocairo-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libgif7 libexif12` via `apt-cache depends`.
  OpenSSL 1.1 is EOL (not in `apt-get download`): fetch `libssl1.1_1.1.1f-1ubuntu2.24_amd64.deb`
  from `security.ubuntu.com/.../pool/main/o/openssl/` and `ar x` + untar it.
- Run with: `DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1 LC_ALL=C
  LD_LIBRARY_PATH=<debroot>/usr/lib/x86_64-linux-gnu:<debroot>/usr/lib:<ssl11dir>
  FONTCONFIG_PATH=<debroot>/etc/fonts /tmp/pptxenv/bin/python render_slide.py`
- `sld.get_image(3.0,3.0)` → 10205² px (slide is 47.24"=3401.6pt @72; render = 216 px/in).
  Crop a panel by its inch coords (parsed from `ppt/slides/slide1.xml` via EMU/914400) × 216.
  Aspose free/eval added **no watermark** on this 1-slide deck.

**Validation:** re-rendering an ORIGINAL svg must pixel-match its original PNG before trusting
new renders.

### FINAL PRINT EXPORT — sharpest A0 PDF (use this when sending to print)

**One command produces the deliverable PDF and runs every print check:**
```bash
bash scratchpad/build_print_pdf.sh            # PANEL_SCALE=5, FULL_SCALE=6  -> ~305 DPI
bash scratchpad/build_print_pdf.sh 5 8        # FULL_SCALE=8 -> ~406 DPI (bigger file, rarely needed)
```
Output: `figure_full_poster.pdf` — **A0 landscape, 1189 × 841 mm, ~305 DPI, lossless raster** (~16 MB).

**What the script does (5 stages, all automated):**
0. **Preflight** — verifies `/tmp/svgrender/render*.mjs`, `/tmp/fonts/*.ttf`, and all 6 panel SVGs exist;
   **auto-bootstraps `/tmp/pdfenv`** (python venv + `img2pdf` + `Pillow`) if missing. Errors with a pointer to
   §3/§4 if svgrender or fonts are gone (those are /tmp-ephemeral — recreate per §4).
1. Renders all 6 panel SVGs **oversampled at 5×** (7.58 px/unit).
2. Runs `scratchpad/build_full_poster.py` (re-embeds the fresh panel PNGs as base64).
3. Renders the full poster at **6×** (6 px/unit) — panels get **down-scaled** (supersampled ⇒ crisp), never upscaled.
4. Flattens to opaque RGB (no SMask) and wraps it losslessly in an **exact A0-landscape page** via img2pdf.
5. **Print-readiness checks** (PASS/FAIL, non-zero exit on FAIL): A0 page size 1189×841 mm; landscape aspect
   1.41379; resolution ≥ 300 DPI; single page. Prints "ALL CHECKS PASSED — ready to send to print."

**Why oversample-then-downscale = sharpest (and a SMALLER file):** panels are 792 units wide and render.mjs
rasterizes them to `1200·PANEL_SCALE` px (= 1.515·scale px/unit) while the poster renders at `FULL_SCALE` px/unit.
If panel density < final density the panels are UPSCALED → bilinear blur smears faint gradients across flat areas,
which Flate compresses *poorly* (the old "straightforward" 18 MB PDF was this — same pixels, just blurry; a 0.7 px
Gaussian blur of the sharp image reproduces 18 MB exactly). Oversampling (panels 5× → downscaled into the 6× poster)
keeps flats truly flat → tighter compression → **15–16 MB and sharper**. img2pdf embeds the PNG stream directly, so
**PDF size == flattened-PNG size** (no recompression, no quality loss).

**Known limitation:** this is a high-DPI *raster* PDF, not vector text. A fully-vector PDF is not achievable here —
panels contain genuine raster art (hand-drawn journey, device photos, behavioral rasters, ES/Pi logos) and no
SVG→vector-PDF tool with the Aptos/Cascadia fonts is installed (no inkscape/rsvg-convert/cairosvg, no sudo). At
305 DPI the difference is invisible at poster viewing distance.

---

## 4c. Illustrator-ready VECTOR SVG pipeline (CURRENT — supersedes status-log 2026-06-30 (2))

This is the **active deliverable pipeline** for the editable, print-sharp vector poster. It is
distinct from the §4 raster PDF pipeline. Goal: a single self-contained SVG that **opens cleanly in
Adobe Illustrator** (and browsers), so Ido installs fonts and exports the PDF himself.

### Build command (one step)
```bash
python3 scratchpad/build_full_poster_illustrator.py      # -> figure_full_poster_illustrator.svg
```
The build is **two stages, both automatic**:
1. **Assemble** — inlines each `poster_figures/figure_*.svg` panel into the A0 master
   (`width=1189mm height=841mm viewBox="0 0 2376 1680"`). **Panels are flattened to `<g transform>`
   groups, NOT nested `<svg viewBox>`** (Illustrator drops nested-SVG content — see pitfalls). Each
   panel is clipped to its box with a `<clipPath>`. Per-panel id namespacing (`p1-`..`p6-`).
2. **`scratchpad/ai_compat.py`** runs in-place on the output (subprocess at end of build) — the
   Illustrator-compatibility pass. **If you edit the build or ai_compat, just re-run the build.**

### `scratchpad/ai_compat.py` — what it rewrites (Illustrator drops all of these on import)
| Construct | Illustrator problem | Fix applied |
|---|---|---|
| nested `<svg viewBox>` | content dropped / mis-scaled | panels already flattened to `<g transform>` in stage 1; histogram sub-SVGs flattened too |
| `<image href=...>` (SVG2 bare href) | image not rendered | add `xlink:href=` (24 images were bare) |
| `<use>` of `<symbol viewBox>` / `<g>` defs | icons vanish or mis-scale; bare-href unresolved | **flatten** each into inlined `<g transform>`, **honoring the use's own `transform=` AND x/y/width/height** (figs 5/6 + why-it-matters bulbs/line-icons position via `transform`, NOT x/y — missing this dumped them at 0,0 = "green smudges") |
| `<marker>` arrowheads (`marker-end`), **incl. inherited from a `<g marker-end=...>` wrapper** | markers ignored → arrowheads gone | **bake** each into a real `<path>` triangle at the shape's endpoint (correct angle/scale from stroke-width). Must walk EVERY stroked descendant of a `<g marker-end>` (state-machine + bottleneck arrows inherit it; only 2 had explicit marker-end) |
| `paint-order:stroke` text halos | AI paints the light stroke OVER the glyphs → text looks "missing" (e.g. "ITI timeout") | replace with stacked **underlay (fat light stroke) + overlay (fill)** copies; same-color faux-bold headers just drop `paint-order` |
| `filter` drop-shadow (`p4-nShadow`) | AI may drop the whole filtered element | **stripped** (boxes keep rendering; lose a subtle shadow — accepted tradeoff) |
| `Cascadia Mono` font fallback | "unknown problem" warning | removed from font-family lists (done when building the bundle) |

After a build the master has **0 nested-svg, 0 markers, 0 paint-order, 0 bare-href, 0 filters** — verify:
```bash
python3 -c "import re;s=open('figure_full_poster_illustrator.svg').read();print('nested',s.count('<svg')-1,'marker',s.count('marker-end='),'po',s.count('paint-order'),'bare-use',sum(1 for t in re.findall(r'<use\b[^>]*?>',s) if 'xlink:href' not in t and re.search(r'(?<![\w:])href=',t)))"
```

### Fonts — Illustrator IGNORES embedded `@font-face`
The SVG embeds fonts as base64 (so browsers render it standalone), but **Illustrator only uses fonts
installed on the system** — it substitutes otherwise. So the deliverable is a **bundle**:
- `scratchpad/poster_bundle/` → `figure_full_poster_illustrator.svg` + `fonts/` (8 TTFs) + `README.txt`
- zipped to **`scratchpad/mics_poster_illustrator_bundle.zip`** (~5.5 MB).
- **Install fonts FIRST (Font Book), THEN open the SVG.** ComicNeue's internal family is renamed
  `Comic Neue`→`ComicNeue` in the bundle to match the SVG's font-family. Aptos + Cascadia Code match as-is.
- Rebuild the bundle after any SVG change:
```bash
python3 -c "import os,zipfile;B='scratchpad/poster_bundle';s=open('figure_full_poster_illustrator.svg').read();s=s.replace(\"'Cascadia Code', 'Cascadia Mono', Consolas, monospace\",\"'Cascadia Code', monospace\").replace(\"'Cascadia Code','Cascadia Mono',Consolas,monospace\",\"'Cascadia Code', monospace\");open(os.path.join(B,'figure_full_poster_illustrator.svg'),'w').write(s);out='scratchpad/mics_poster_illustrator_bundle.zip';z=zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED);[z.write(os.path.join(r,f),os.path.relpath(os.path.join(r,f),B)) for r,_,fs in os.walk(B) for f in fs];z.close();print('zipped',round(os.path.getsize(out)/1e6,2),'MB')"
```

### Verification (cannot run Illustrator here — verify by render diff)
resvg renders the original constructs faithfully, so after ai_compat the render must still match a
pre-pass baseline (the ONLY expected diff is the removed drop-shadow). Loop: `node
/tmp/svgrender/render.mjs figure_full_poster_illustrator.svg scratchpad/out.png 3`, then PIL pixel-diff
vs a baseline render. Mean diff ~0.09/255 = success. **Illustrator behavior itself is verified by Ido
manually** — that feedback loop drove every fix in the table above.

### Histograms (THE LOGIC panel) — embedded as VECTOR, from ES run 401
- Source run = **run_id 401** in ES `event_log_v2` @ `http://132.77.73.217:9200` (matches the poster
  numbers: 1_2 μ4.4/σ2.0, 2_4 μ0.8/σ0.8, 1_4 μ5.2/σ2.3; n=1409). Found by scanning all runs
  (`scratchpad/scan_runs.py`). Run 359 was WRONG.
- `scratchpad/build_histograms_hq.py` (`RUN_ID=401`) emits BOTH `.png` and **`.svg`** (matplotlib
  `svg.fonttype="path"` → text as outlines, no font dep). BLUE end-to-end (0–10 ms), GOLD command
  (0–4 ms), transparent legend (`frameon=False`). The two SVGs are embedded as inline vector groups in
  `poster_figures/figure_task_definition_v2.svg` (replacing the old raster `<image>`s).

### Panel-source edits since the rebuild (all in `poster_figures/figure_*.svg`)
- **fig1 (Challenge)** `figure_dream_experiment.svg`: 12 box captions centered (text-anchor middle, x→column
  centers 152.2/396.0/639.8) + enlarged (font 9→11).
- **fig2 (Bottleneck)** `figure_problem_solution.svg`: red ✗ bullets in 4 traditional panels lowered +10px;
  the blurry baked data-accum PNG **replaced with vector** — two bg-colored (`#F5F7FA`) green-bordered cards,
  the `ic-db` vector cylinder (`fill="#0B5B1F"`, copied from `figure_storage_reconstruction.svg`), the
  **official Elasticsearch logo** (vector, from `https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/elasticsearch.svg`
  — 3 paths #343741/#FEC514/#00BFB3), + labels. The two logos sit at icon-group `translate(...,365)` (lowered
  ~12px inside the cards; cards themselves unchanged).
- **fig4 (Logic)** `figure_task_definition_v2.svg`: subtitles "· Behavior hidden inside code" / "· Blueprints
  represent behavior explicitly" bolded + darkened (`font-weight 400→700`, `#9AA0A6→#5A6068`).
- **fig1 (Challenge)** `figure_dream_experiment.svg` (2026-06-30): concluding sentence dropped (y 712/736 → 738/762)
  + viewBox height 742→772 so it clears the box captions above it. Paired with the assembly geometry change below.
- **fig3 (Hardware)** `figure_hardware_abstraction_v2.svg` (2026-06-30): "Swap hardware freely" why-it-matters body
  shortened to fit ("Abstraction layer maps / commands to sensor modules", capitalized); `lick` in the behavior
  block painted pink `#D6418B` (`<tspan>` like the other colored verbs).
- **fig2 (Bottleneck)** `figure_problem_solution.svg` (2026-06-30): concluding caption raised y 644→621 so its
  baseline (poster ~1636) realigns with fig4/fig6 bottom captions (1633–1639) after panel 2 was lowered ~27px.

### Illustrator-only colored-tspan spacing fix — `scratchpad/fix_illustrator_tspan_gaps.py` (2026-06-30)
- **Symptom (AI only, resvg renders fine):** AI inserts a spurious gap around every colored `<tspan>` inside a
  monospace code `<text>` — e.g. `tone .play()`, `phase, t0 =   "REWARD" , now()`. Lines that are a single text
  node with no tspan (e.g. the old plain `lick.detect()`) render correctly, which is the tell.
- **Fix:** the code font is Cascadia Code (monospace, advance = `1200/2048` em = 0.58594). The script gives every
  run from the first tspan onward an explicit `x = base_x + column*advance`, so AI positions absolutely instead of
  mis-flowing. Scoped to fig3 behavior lines (font 12.5) + fig4 traditional-code `<g>` (font 9.4); proportional text
  is never touched. **resvg-invariant** (verified: pixel-diff pre/post = max 58, 160 sub-pixel px — rounding only).
- Run it on the source panels *before* `build_full_poster_illustrator.py`. Re-running is safe (idempotent: it
  drops any prior `x` before recomputing).

### Assembly geometry — fig1 taller, panel 2 + BOTTLENECK band lowered (2026-06-30)
- Both build scripts now define `H_FIG1 = 687` (was the literal `660`): col-0's top panel is taller so fig1's
  concluding sentence clears its boxes, which lowers fig2 **and** the "THE BOTTLENECK" kicker band by the same
  ~27px (scale preserved, fig1 content unchanged size). Col-0 band/seam decoupled from col-2: `LOW_BAND_0`
  (bottleneck, uses `H_FIG1`) vs `LOW_BAND_13` (data, still 660); `COL0_BOT` vs `CONTENT_BOT` for the x=797 vline.
  Col-0 bottom now 1675 (< 1680 canvas). Mirror any change across `build_full_poster.py` + `build_full_poster_illustrator.py`.

### After ANY panel edit
`python3 scratchpad/build_full_poster_illustrator.py` (auto-runs ai_compat) → render to verify →
rebuild the bundle zip. Render-check the whole poster, not just the panel.

---

## 5. File inventory

**Finished poster figures live in `poster_figures/`** (convention as of 2026-06-17 — every
completed panel SVG+PNG moves here, named `figure_<panel>.svg/.png`, rendered 3× via §4):
- `poster_figures/figure_hardware_abstraction.svg/.png` — **panel 3**, 792×440 (1.800 =
  39.6×22 cm). **Minimal** adaptation of the coworker's "Hardware abstraction enables
  behavior-level programming" figure: keeps its **3-card structure** (Hardware-level control |
  Behavior-level control | Abstraction layer, the last = Task logic → Functional modules →
  Hardware devices stack, kept **verbatim** from the pptx). Card 1 = messy pigpio code with
  devices annotated on the right + `✗ Low-level communication` / `✗ Device-specific task`;
  card 2 = high-level commands with inline device icons + names (Lick sensor, Reward valve…).
  **Illustration rule:** the **valve is RECYCLED from the original poster raster**
  (`pptx ppt/media/image3.png`, base64-embedded) since the device is unchanged; speaker /
  lick-sensor / opto / camera are NEW vector icons (our HW differs from the original
  door/LEDs). Abstraction panel reuses original brain/cube/LED/target rasters. Colors §3c.
  Built via inline python (base64 embeds) — see §6 2026-06-17 entry.
- `poster_figures/figure_task_definition.svg/.png` — **panel 4**, 792×880 (0.900 = 39.6×44 cm).
  Stacked code / state-machine / timing bands (Blueprint A opto variant). Pure vector (no base64) —
  edit with the Edit tool directly. Derived from `figure_state_machine_vs_code_opto_poster.svg` but
  re-stacked vertical + timing strip added. See §6 2026-06-21 (7).
- `poster_figures/figure_portal_database.svg/.png` — **panel 5**, 792×660 (1.200 = 39.6×33 cm).
  "Central coordination across independent setups." **LEFT ~2/3 = coordination diagram:** the
  **MICS Portal** (top, bg pale-blue `#EAF2FC`, 3 cols DEFINE TASKS / ASSIGN TO CORES / CONTROL
  STATUS) feeds two panels below via **bidirectional vertical arrows** centered on each bottom
  panel ("store & serve" ↔ DB, "control & report" ↔ Core). **Declarative Database** (PostgreSQL)
  lists 5 entities — Subjects / Blueprint definitions ("build states & transitions in a visual
  editor") / HW libs & modules ("versioned, semantic hardware abstractions") / Core configurations
  / Protocols & graduation — each a reusable icon `<use href="#ic-{subject,blueprint,hwlib,core,
  protocol}">` **mirrored compactly in the Portal DEFINE column**. **MICS Core** = Pi-logo
  (base64 `<image>`) + Core-status & Session-control lists. Both lower panels were **widened to
  span the Portal's full width** (DB x=16 w=232 center 132; Core x=274 w=232 center 390; gap 26).
  **RIGHT ~1/3 = "Everything in one place"** advantages list — green "💡 WHY IT MATTERS" kicker
  pill (approachable entry point) + 6 neutral boxes (`#EAEDF2`), each a **green icon** (`#adv-1`..
  `#adv-6`) + black headline (no trailing periods) + gray support; the panel **blends into the bg
  (no card)**, divided from the left by a vertical rule at x=517. Bottom caption (green bold 15px,
  matches sibling figures): **"Focus on the science — MICS handles the rest."** Pure vector except
  the Pi-logo base64 — edit with the Edit tool. See §6 2026-06-24.

- `poster_figures/figure_storage_reconstruction.svg/.png` — **panel 6**, 792×660 (1.200 = 39.6×33 cm).
  "Structured storage and full experiment reconstruction." **TWO stacked parts.** **PART 1 (BUILT) —
  "Structured data storage & real-time event logging"** — Ido: **mirror Panel 5 for cohesion**; the already-
  known services are subtle/smaller. Header subtitle = the pptx reference *"MICS separates experiment
  definitions from ongoing events — reliable storage & live data access."* **LEFT 2/3 = MICS-system recap:**
  a compact **blue MICS Portal** box (pale-blue `#EAF2FC` bg, blue frame, its **3 icons** define/assign/control
  reused from Panel 5) on top; a small green **Declarative Database** card bottom-left ("experiment definitions");
  a **MICS Cores** Pi-logo stack (×N, "live execution") bottom-right. Arrows Portal→DB, Portal→Cores, then an
  **orange "stream events" arrow Cores→Elasticsearch** ("ongoing events, logged live"). **MIDDLE = ORANGE
  Elasticsearch panel** (`#FDF2E9` bg, `#DD6B1F` frame, shifted left): ES brand mark + "Elasticsearch · event store",
  divider, then a **6-item orange-icon list**: **One shared hardware clock** ("hardware pin events *and* software events /
  state transitions — all on the same clock") / **True execution time** ("the moment the hardware fired — not when
  Python issued the command or it was logged") / Self-describing records / **Schema-free — nothing forgotten**
  ("every event auto-saved as a document — no schema to design") / Live real-time stream / **Build custom
  dashboards**.
  **RIGHT = green "WHY IT MATTERS" panel** (mirrors Panel 5: green kicker pill + lightbulb, header "Trust every
  record", 3 neutral `#EAEDF2` cards w/ green icons): **Reconstruct any trial** (reconstruction) / **Add
  hardware, change nothing** (new devices & event types log themselves — no schema/pipeline edits) / **Built to
  scale** (Elasticsearch handles millions of events — fast insert + query). Vertical divider at x=528. **PART 2 (PLACEHOLDER):** dashed box reserving space for
  the reconstruction (mini state-machine recap + behavioral raster, colors from Panel 4; ephys aligned via TTL
  sync; "Closed-loop control of neural perturbation based on behavior"). Caption: **"From raw hardware events to
  a fully reconstructable experiment."** Built via `scratchpad/build_panel6.py` (embeds Pi-logo base64 + reuses
  Panel 5's portal/assign/control/db icons). See §6 2026-06-24 (2)+(3).

### Deliverables (repo root)

- `figure_full_poster.svg/.png/.pdf` — RASTER pipeline output (panels embedded as PNG). PDF is ~305-DPI raster
  (text baked to pixels). Build: `scratchpad/build_full_poster.py` → render → `scratchpad/build_print_pdf.sh`.
- **`figure_full_poster_illustrator.svg`** — **VECTOR master for Illustrator** (text/shapes vector; only photos raster;
  A0 1189×841 mm; Illustrator-safe). Build: `scratchpad/build_full_poster_illustrator.py` (auto-runs `scratchpad/ai_compat.py`).
  **Deliverable = `scratchpad/mics_poster_illustrator_bundle.zip`** (SVG + fonts + README; install fonts first).
  Preview: `figure_full_poster_illustrator_preview.png`. **FULL PIPELINE DOC: §4c** (the authoritative current reference;
  supersedes status log 2026-06-30 (2)). Generators: `ai_compat.py`, `build_histograms_hq.py`, `scan_runs.py`.

### Work-in-progress / source figures (repo root)

- `MICS poster final OY_is.pptx` — coworker's poster (REFERENCE; extract to `/tmp/pptx_extract`).
- `figure_state_machine_vs_code.svg/.png` — orig "two ways" figure (tone-reward task).
- `figure_state_machine_vs_code_opto.svg/.png` — orig, opto variant (+1 rule).
- `figure_state_machine_vs_code_poster.svg/.png` — restyled to poster (green header removed).
- `figure_state_machine_vs_code_opto_poster.svg/.png` — restyled opto variant.
- `figure1_redesign.svg` — earlier overview redesign.
- `Screenshot 2026-04-26 ....png` — older "MICS functional overview" figure (Fig 1).

### Useful embedded media in the poster (`/tmp/pptx_extract/ppt/media/`)
- `image1.png` — clean line-art mouse-in-cage with headstage + speaker + reward port.
- `image11.png` — MICS functional-overview schematic (Portal/Core/Setups).
- `image18.png` — **closed-loop opto raster**: "Lick during audio → Optogenetic manipulation"
  (legend: trial / audio=light-blue / opto=yellow / nosepoke=pink / lick=black tick).
- `image34.png` — "Closed-loop delay" histograms (the canonical native figure style).
- `image35.png` — spikes aligned to audio + PSTH (per-subject).
- `image29.png`, `image33.png` — code screenshots (raw pigpio vs flag-based loop).

---

## 6. Status log
- 2026-06-30 (3): **Illustrator-export pipeline made ACTUALLY Illustrator-safe + content edits (full doc now in §4c).**
  Ido opened the 2026-06-30(2) SVG in real Illustrator; it broke in stages, each fixed in `scratchpad/ai_compat.py`
  (new, auto-run by the build): (1) panels re-flattened from nested `<svg viewBox>` → `<g transform>`+clipPath (nested
  SVG content was dropped — "9 boxes missing"); (2) `<image>` bare `href`→`xlink:href` (images invisible); (3) `<use>` of
  `<symbol>`/`<g>` defs flattened **honoring `transform=`** (icons/bulbs landed at 0,0 = "green smudges"; the DB icon
  belonged in the DB box); (4) `<marker>` arrowheads **baked to paths**, incl. those **inherited from `<g marker-end>`**
  (state-machine + bottleneck arrowheads gone — only 2 of ~40 had explicit marker-end); (5) `paint-order:stroke` halos
  split into underlay+overlay (Illustrator buried "ITI timeout" etc. under their own light stroke); (6) drop-shadow
  `filter` stripped. Verified by resvg render-diff each step (mean ~0.09/255, only the shadow differs). Fonts: Illustrator
  ignores embedded `@font-face` → ship **`scratchpad/mics_poster_illustrator_bundle.zip`** (SVG + 8 TTFs + README; install
  first; ComicNeue internal name fixed; Cascadia Mono fallback removed). **Histograms redone** (was descoped): ES **run 401**
  (`scan_runs.py` found it; 359 was wrong), rendered as **vector** SVG (`build_histograms_hq.py`, blue 0–10 / gold 0–4 ms,
  transparent legend) embedded in the Logic panel. **Content edits:** fig1 captions centered+enlarged; fig2 red bullets
  +10px lower + data-accum card rebuilt as vector (bg-color cards, `ic-db` green cylinder, official Elasticsearch vector
  logo from gilbarbara CDN, logos lowered ~12px in-card); fig4 subtitles bold+darker. Master now: 0 nested-svg / markers /
  paint-order / bare-href / filters.
- 2026-06-30 (2): **VECTOR Illustrator-export pipeline built (per Ido — fixes the boss's "low-resolution" print complaint).**
  Root cause diagnosed: the deliverable `figure_full_poster.pdf` is a flat ~305-DPI **raster** (resvg → img2pdf) — every
  glyph is baked to pixels, so it looks soft printed at A0. A PNG is the same (raster) and does **not** help. Illustrator/
  print-shop workflow wants a **vector** PDF (text/shapes infinitely sharp; only photos raster). No SVG→vector-PDF tool is
  installed on the box and the installable ones (puppeteer/svg2pdf) are engine swaps with drift risk on the resvg-tuned
  feDropShadow/paint-order/14-gradients — so instead we **emit one self-contained vector master SVG and let the user export
  the PDF from Illustrator** (or Chrome). NEW generator `scratchpad/build_full_poster_illustrator.py` →
  `figure_full_poster_illustrator.svg` (A0 `width=1189mm height=841mm viewBox="0 0 2376 1680"`): it **INLINES each panel
  SVG's vector content** (nested `<svg viewBox>` at the same place()-positions, incl. dream's 742→660 letterbox via
  `preserveAspectRatio="xMidYMid meet"`) instead of rasterizing panels to PNG; only the 26 genuine raster sub-images stay
  base64. **Per-panel id namespacing** (`p1-`..`p6-`, rewriting `id=`, `url(#)`, `href="#"` but NOT `data:` URIs) fixes the
  cross-panel collisions (`ic-bulb` defined in 4 panels, `arrb` in 3, etc.) — verified 70/70 ids unique, 57/57 refs resolve.
  Fonts (Aptos, Cascadia Code, ComicNeue from `/tmp/fonts`) **embedded via `@font-face` base64** so the file is self-contained
  (browser/Inkscape export works too; Illustrator uses installed fonts of the same name). Verified: 292 live `<text>`
  elements; resvg proxy render (`render_poster.mjs … 2376 3`) is layout-identical to the raster poster (mean diff 1.1/255,
  1.6% px>20). Build does NOT overwrite the raster pipeline (`build_full_poster.py` / `build_print_pdf.sh` kept as fallback).
  Handoff doc: `POSTER_PRINT_HANDOFF.md` (install 3 fonts → open SVG in Illustrator → optional Type▸Create Outlines → export
  PDF/X-4, A0; or zero-install Chrome Print→Save-as-PDF). Open cosmetic risk: Illustrator may drop the Panel-4 state-machine
  drop-shadows on import (re-add natively if so; browser path renders them fine). **DESCOPED per Ido:** histogram high-res
  redo, white-background fixes (panels 2/4/6), and Panel-1 journey art (~150 DPI, source-limited) all left as-is — the
  vector text was the priority. (Investigation found histogram source `image.png`=627×406 is low; high-res original
  `image34.png`/`MICSyeda image14`=1620×927 exists if revisited, but its subplots are ~1.6:1 vs the poster's 2.52:1 crop, so
  a faithful undistorted swap needs reframing — noted for future.)
- 2026-06-30: **content pass across all 6 panels (per Ido).** (a) **All 6 concluding captions bumped to title
  size (23px)** — the long ones wrap to 2 lines: Logic ("Locally executed blueprints ensure / deterministic…"),
  Data ("Ongoing, lossless data logging / for exact tracking…"), Challenge (new text below). (b) **Panel 1 (CHALLENGE)
  caption** → "Scientific questions evolve. / Experimental platforms should evolve with them" (2 lines, 23px) in
  `build_dream_experiment.py`. (c) **Panel 2 (BOTTLENECK)**: red bullet "Individualize setups" → "Individual setups";
  **green Scaling illustration computer icon rebuilt** — the old pie+network blob read as a blob and its hub arrows
  were too thick/rich. New `scaling_hub()` in `build_problem_solution.py` draws a clean monitor silhouette (green
  bezel + white screen + neck + base) + 6 slim spokes (stroke 0.9, new `arrg2` slim marker, ray-exits the monitor
  bbox to the 6 cage targets). Removed the old `HUB_GROUP` extraction. (d) **Panel 4 (THE LOGIC)**: heading subtitles
  "· one tangled loop" → "· Behavior hidden inside code", "· blueprints" → "· Blueprints represent behavior
  explicitly"; **WHY panel** now headed "Think in behavior, not code" (cards reflowed h62→h56 to fit; "Behavior you
  can reason about" subline first added then **removed per Ido**). Optional "make the procedural code messier"
  was **declined by Ido** (a generator existed but was not applied). (e) **Panel 5 (COORDINATION)** caption
  "One portal to oversee and control" → **"One portal. Many experiments."**; in the **purple MICS Core panel**,
  dropped **Elapsed** (Core status) + **New session** (Session control), enlarged item text 9→11, headers →11.5,
  icons ×1.35, spread rows into freed vertical space, shifted icons/text 8px left (icons x293→285, text x316→308)
  to kill right-edge overflow, **Restart kept as label only** (description dropped). Verified longest line ends
  x≤484 < box-right 506. All panels re-rendered 3× → poster reassembled → rendered 3× → whole-poster reviewed ✓.
  NOTE: print export still via `scratchpad/build_print_pdf.sh` (not run this session — iteration renders only).
- 2026-06-29 (5): **FINAL PRINT-EXPORT pipeline built (per Ido — reusable across sessions).**
  `scratchpad/build_print_pdf.sh` (chmod +x): one command → sharpest A0-landscape PDF + all print checks. See
  §4 "FINAL PRINT EXPORT" for the full spec. Self-bootstraps `/tmp/pdfenv` (img2pdf+Pillow); preflights
  svgrender/fonts/panels. Default PANEL_SCALE=5 / FULL_SCALE=6 → `figure_full_poster.pdf` (A0 landscape
  1189×841 mm, 305 DPI, lossless, ~16 MB). Diagnosed the "why is the sharp PDF smaller (16 vs 18 MB)?" puzzle:
  the old straightforward PDF embedded 3×-panels UPSCALED to 6× → bilinear blur inflates Flate size; a 0.7 px
  blur of the sharp image reproduces 18 MB exactly. Oversample→downscale = crisp + smaller. img2pdf embeds the
  PNG stream directly so PDF size == flattened-PNG size (lossless). All 5 checks PASS.
- 2026-06-29 (4): **bottom-row captions aligned (per Ido).** The BOTTLENECK caption sat 14px higher than the
  LOGIC + DATA captions in the assembled poster. Abs-y math (CONTENT_Y=288, GAP=40, all panels placed 1:1):
  Bottleneck panel starts y988, caption local 628 → abs **1616**; Logic panel starts y768, caption local 862 →
  abs **1630**; Data panel starts y988, caption local 642 → abs **1630**. Lowered Bottleneck caption local
  y 628 → **642** (`build_problem_solution.py` line 240) → abs 1630, aligning all three. Regenerated panel →
  rebuilt poster → 3× → verified the 3 captions share one baseline ✓.
- 2026-06-29 (3): **panel-2 (THE BOTTLENECK) ✗/✓ bullet text bolder + larger (per Ido).** Edited the generator
  `poster_figures/build_problem_solution.py` (NOT the SVG — it's regenerated): `BFS 10.5 → 11` and added
  `font-weight="600"` to the bullet `<text>` (line ~119). Kept `wrap()` cw factor at 0.52·fs so **every bullet's
  line-count is identical** to before (verified the boundary cases: "Logging predefined events" = 25ch·5.72 =
  143 < 144.75 wrap budget → stays 1 line; green col0 stays 2+2+3). Full bold/larger was rejected — it forces
  "Logging predefined events" to wrap and overflow the tight green col0 (~9px vertical slack). Ran generator from
  `poster_figures/` (OUT is a relative path; SRC = the frozen bak svg in another session's scratchpad), rendered
  panel 3× → rebuilt full poster (from ROOT) → 3× → reviewed ✓.
- 2026-06-29 (2): **panel-6 (THE DATA) WHY IT MATTERS card spacing normalized (per Ido).**
  `poster_figures/figure_storage_reconstruction.svg`. The 3 "Trust every record" cards (h=56) sat at y=172/234/296
  = **6px gaps**, denser than every sibling WHY panel (Panel 5 cards h56 gaps **12px**; Panel 4 cards h62 gaps 12px).
  Re-spaced to **12px gaps**: card 2 234→240, card 3 296→308 (icons + text lines shifted with each rect), and the
  right vertical divider (x528) extended y352→364 to wrap card 3. Card 3 now ends y364, clears the "2 · Closed-loop"
  strip (y368, far-left) with no collision. Re-rendered panel 3× → rebuilt full poster (from ROOT) → 3× → reviewed ✓.
- 2026-06-29: **panel-6 (THE DATA) header reworded (per Ido).** `poster_figures/figure_storage_reconstruction.svg`.
  (a) **Title** "Structured storage and full experiment reconstruction" → **"Data streaming and full experiment
  reconstruction"**. (b) **Gray subtitle** → **"every MICS event is timestamped, indexed and logged to a
  centralized DB"**. (c) **Section-1 strip heading** "1 · Structured data storage & real-time event logging" →
  **"1 · Live & schema-free event logging"** (kept the blue `#1E47A8` accent-bar strip + "1 ·" number so it
  still pairs with the "2 · Closed-loop control" section). Header positions unchanged (title y32 / subtitle
  y51 / strip 64/78/93). NOTE: a first pass mistakenly added the blue phrase as a *separate centered line*
  under the subtitle — Ido clarified it should *replace* the strip heading, not be an extra line. Re-rendered
  panel 3× → rebuilt full poster (run `build_full_poster.py` from repo ROOT, not /tmp/svgrender) → 3× →
  reviewed whole ✓.
- 2026-06-28 (9): **panel-4 (THE LOGIC) dividers + bullet (per Ido).** `figure_task_definition_v2.svg`.
  (a) Bullet "On-device — no network in the loop" → **"Internal mechanism — no network in the loop"**.
  (b) **Vertical divider (x480) shortened** from full-height (y840) to **end at y384** = where THE MICS WAY
  (state machine) begins, so the histograms are NOT walled off from the state-machine drawing they belong to.
  (c) Added a **subtle horizontal divider** (`#C2C9D3` width 1, x492–772, **y401**) between the WHY-IT-MATTERS
  cards and the histograms — mirrors the bolder "Behavior you can reason about" rule (y165) but lighter — so the
  histograms read as grouped with the state machine below, not with the WHY panel above. Panel 3× → poster 5× ✓.
- 2026-06-28 (8): **panel-4 (THE LOGIC) histogram alignment + legends (per Ido).** `figure_task_definition_v2.svg`.
  (a) **Aligned the two histograms horizontally** — blue's "Density"/axes sat ~4px right of gold's (different
  source-subplot widths); nudged blue img x 524→522 then →574 and gold 524→526 then →578, keeping a **+4px gold
  offset** (gold_x − blue_x = 4 keeps the Density labels aligned at any shared width, since left-ink fractions
  differ by ~0.018·w). (b) **Added μ/σ legends to the LEFT of each histogram** — a leader-colored dashed
  mean-line sample + "μ = X ms" / "σ = X ms" (blue `#2E75B6` / gold `#C8994C`), vertically centered on each plot
  (blue ~y451–468, gold ~y546–563, text at x500/520). To make room, the histograms were **shrunk 216→194 wide**
  (blue x574 h77, gold x578 h81) and shifted right. (c) **State-machine dotted-leader callouts**: the
  descriptions "end-to-end · lick → water" / "command → valve" **recolored from gray/brown to their leader
  colors** (blue/gold) + bolded, kept on top of the dotted lines. **Both μ and σ removed from the callouts** —
  the timing numbers (5.2/0.8 ms etc.) now live ONLY in the left-of-histogram legends; the dotted leaders carry
  just the colored description. Re-rendered panel 3× → full poster 5× → reviewed ✓.
- 2026-06-28 (7): **panel-4 (THE LOGIC) title + histograms (per Ido).** `figure_task_definition_v2.svg`.
  (a) **Title merged + subtitle removed** — now two ink-23 lines "Defining task logic as states and transitions, /
  an intuitive way to represent a closed-loop task" (the old gray subtitle line deleted). (b) **Context strip**:
  "a tone **opens** a response window" → "**onsets**". (c) **The two state-machine dotted leaders now show their
  actual distributions**: cropped the matching subplots from `image.png` (= image34) and placed them on the right
  where "Runs locally on each setup" was; that block moved DOWN below them. **BLUE** leader (end-to-end, μ=5.2/
  σ=2.3) = source ORANGE "Detection→Action"; **GOLD** leader (command→valve, μ=0.8) = source GREEN "State
  Transition→Action" — each **recolored to its leader's hue** (HSV hue-swap of colored px S>22, keep S/V; blue
  H=148/#2E75B6, gold H=26/#C8994C). **Baked μ/σ legend boxes removed by UN-MIXING, not whiteout** (Ido): the
  legend is white at **framealpha≈0.5**, so `true=(observed−0.5·255)/0.5` inverts the overlay and recovers the
  curve, the bars (incl. ones poking ABOVE the KDE curve) AND the dashed mean line that were hidden under it.
  `unmix_legend()` strips the opaque legend graphics (gray border / black text / dashed sample / old mean line —
  identified as **R−B<10**, true gray; the recovered pale fill is R−B≈16 and the curve R−B≈36, both kept) and
  whites the empty text corner (x≥346, no data there). **Key gotcha:** the recovered fill is too pale to survive
  the transparency pass, so each occluded bar is **repainted SOLID** with the canonical fill `(242,190,144)`
  using its *connected run up from the baseline* (gaps ≤2px) — this fills the under-curve wedge AND the
  above-curve bars without overfilling the short right-shoulder bars to the curve height. Repainting buries the
  KDE line, so the **darker curve is redrawn ON TOP** of the pale bars: the curve profile is captured per-column
  as the *most-saturated* orange row (R−B>30) BEFORE repaint — rejecting box-bottom hits (y≥y1−1, where the line
  is the legend border/exit, intact below anyway) so no flat-clamp stub — then drawn (curve `(229,125,33)`,
  recolors to the dark leader blue) only between the first/last detected points, interpolating gaps. Finally a
  **crisp dashed mean line** is redrawn at x=321 (2px-on/2px-off, source phase y%4∈{1,2}) on top. The gold legend
  sat over empty space so it only needs a whiteout. **Backgrounds made transparent** (near-white→alpha 0) so both plots blend
  into the figure bg `#F5F7FA`. No section header (Ido: dropped "Measured closed-loop timing" + sub-line).
  Re-runnable generator: `scratchpad/build_timing_histograms.py`
  → `poster_figures/hist_endtoend_blue.png` / `hist_command_gold.png`; SVG splice via
  `scratchpad/edit_logic_rightcol*.py`. Right-column divider extended y800→840. Re-rendered panel 3× → rebuilt
  full poster → 5× (11880×8400) → reviewed whole ✓.
- 2026-06-28 (6): **panel-2 (THE BOTTLENECK / problem→solution) relayout (per Ido).** Rebuilt
  `figure_problem_solution.svg` via a NEW re-runnable generator `poster_figures/build_problem_solution.py`
  (extracts the 7 base64 rasters + the vector state-machine + the scaling hub-overlay from the original and
  rebuilds the whole layout parametrically). **⚠️ the script reads SRC from a frozen backup
  `scratchpad/figure_problem_solution.bak.svg`, NOT the live output** — source==output meant a second run read
  its own rebuilt file and broke the line-based extraction (keep that backup, or point SRC at a fresh copy of
  the pre-rebuild SVG). Changes: (a) **subtitle removed** ("Four bottlenecks…"). (b) **one column title per
  column, OUTSIDE/above the red panel** (was duplicated inside both red+green) — heads both stacked panels.
  (c) **down-arrows between rows removed**; rows pulled closer. (d) **vertical left row-labels** "THE
  TRADITIONAL WAY" (red) / "THE MICS WAY" (green) = the Logic figure's `| TEXT` lead-in flipped 90°: text
  rotated -90 (reads bottom→top), font 17 / letter-spacing 0.8 (215px at 18 nearly filled the 216px row, so
  17 leaves room). Text-anchor=middle puts the **baseline at `base_x=42`** (right edge of the strip, close to
  the panels); the `|` is a short horizontal stroke **centred under the text strip** at `bar_cx=base_x-6`
  (≈baseline−capheight/2), `bar_cy=cy+textlen/2+7` (measured textlen red 191.6 / green 122.6) — reads as a
  leading `|` when the head is tilted, matching the Logic figure. (e) **small
  connector arrows** red-bottom-left → green-top-left, tucked at the left edge (x=colx+15) below the
  bullets / above the green illustration so they clear content; stroke is a **vertical red→green gradient**
  (`#r2g`, userSpaceOnUse y1=RED_B-12 → y2=GRN_Y+8, RED_C→GRN_C) with a **green arrowhead** (`#arrcg`) at the
  solution end — visually carries problem→solution. (f) **illustrations enlarged to fill panel
  width** (esp. scaling), bullet font 8.2→10.5 with auto word-wrap; panels narrowed (PANEL_X0=52) to free a
  50px left gutter for the vertical labels. The green-scaling raster + its hub-arrow vector are transformed as
  ONE group to stay aligned. (g) **green "Writing task logic" state machine = colored boxes only** — the per-
  state `<text>` labels (PREPARE/TONE/REWARD/OPTO/STOP/ITI) are stripped from `SM_INNER` (filter out lines
  starting `<text`) so this illustration does NOT mirror the labelled state machines in THE LOGIC / THE DATA
  panels. Re-rendered panel 3× → rebuilt `figure_full_poster.svg` → rendered 3× → reviewed whole ✓.
  (h) **green "Controlling hardware" Door box → Speaker box (per Ido).** The GRN_CH raster (valve+door device
  stack) is a base64 PNG, so the swap is a **raster edit**: `poster_figures/build_grn_ch_speaker.py`
  (self-contained — decodes GRN_CH from the bak SVG) erases the bottom door icon + "Door" label (sage
  fill `#B5CEC0` over the front-face interior), draws a **grey speaker icon** (cone + sound waves) + bold
  "Speaker" label, writes `poster_figures/src_grn_ch_speaker.png`. `build_problem_solution.py` overrides
  `GRN_CH` with that PNG (same 280×543 dims/aspect, placement unchanged). Valve box untouched.
- 2026-06-28 (5): **panel-1 cell-8 typo + cell-7 note (per Ido).** In `build_dream_experiment.py`:
  (a) **cell-8 baked label** "8 - Conceptual caos" → **"8 - Conceptual chaos"** (typo) using the same re-bake
  approach as cell 1 — added `cell8_uri = cell_uri(8, paint_boxes=[(10,10,640,78,white)],
  text_labels=[(22,16,50,"8 - Conceptual chaos")])`; the per-idx loop now uses a `cell_overrides` dict
  `{1: cell1_uri, 8: cell8_uri}`. (b) **cell-7 note** "individual preferences / and manual configuration"
  → single line **"adjusting preferences manually"**. Re-rendered panel 3× → rebuilt poster → 5× → viewed ✓.
- 2026-06-28 (4): **panel-1 title/caption wording + size (per Ido).** In `build_dream_experiment.py`:
  (a) **title** reworded to "The scientific question is determined by what we can do, / rather than what
  we want to ask" and **bumped 19→23px** to match the other figures' titles (KB §3; measured both lines fit
  at 23px Aptos-Bold: 587 / 331 px < 792); (b) **bottom caption** → "If the science is dynamic, so should the
  system" (dropped trailing "be"); (c) **cell-2 note** "cue recording" → "cue report"; (d) **no terminal
  periods** on title/caption (house style). Re-rendered panel 3× → rebuilt poster → 5× → reviewed whole ✓.
- 2026-06-28 (3): **panel-1 label cohesion + kicker rename → "THE CHALLENGE" (per Ido).** Two fixes, then
  full-poster pass. (a) **Full-poster kicker** col1-top renamed `THE QUESTION → THE CHALLENGE` in
  `scratchpad/build_full_poster.py` (line 116 + the comment on line 98). (b) **Panel-1 cell-1 label made
  cohesive** in `poster_figures/build_dream_experiment.py`: a prior model had whited-out the baked "1 - Idea"
  (erasing the cell's top border too) and overlaid tiny Aptos SVG text "what do we want to ask" — visually
  off from the other cells' hand-drawn labels. Now the label is **baked back into the raster** in the matching
  Comic-Sans-family font: downloaded **Comic Neue** to `/tmp/fonts/` (ComicNeue-{Regular,Bold}.ttf, from
  `raw.githubusercontent.com/google/fonts/main/ofl/comicneue/`); **Bold** chosen objectively (ink density 0.278
  vs baked "2 - Define Task" 0.257; Regular 0.189 = too thin), **size 50** = 36px cap-height (exact match to
  baked siblings). `cell_uri()` gained a `text_labels` param (draws via `ImageFont.truetype(COMIC_TTF)`).
  Clear box narrowed to `(10,12,645,76)` so the **cell border is preserved** (the old `(0,0,661,78)` ate it).
  Label now reads **"1 - What do we want to ask"** (capital W to match the sibling "N - Word…" pattern). (c)
  **Removed the in-figure "THE CHALLENGE" eyebrow** (it duplicated the kicker — the figure shouldn't carry it);
  title shifted up to y=34/56. Re-rendered panel 3× → rebuilt `figure_full_poster.svg` → rendered 5×
  (11880×8400) → reviewed whole: kicker + cell-1 label both correct, no duplication, column balance unchanged.
  NOTE: `build_dream_experiment.py` now depends on `/tmp/fonts/ComicNeue-Bold.ttf` (re-download if /tmp cleared).
- 2026-06-28 (2): **panel 1 "THE QUESTION" built and wired into the full poster (per Ido).** Created
  `poster_figures/figure_dream_experiment.svg/.png` (792×660) via `poster_figures/build_dream_experiment.py`.
  Hero = the hand-drawn 9-step "journey" art from `MICSyeda.pptx` slide *"All we wanted was to do science…"*
  (media image1.png → `poster_figures/src_dream_9steps.png`). Build script auto-detects the raster's cell
  gutters, SLICES it into 9 cells and RE-ASSEMBLES them in a spaced 3×3 grid so three science notes sit in the
  gutter directly below their cell (plain ink text, left-aligned, hugging the cell above — no pill/color/frame):
  ④ "Inhibit SST only (GtACR) + acute Neuropixels", ⑥ "High inter-subject variance → many subjects",
  ⑧ "Must flex: cue / action / reward · generalize → extinguish". Title = the science question (bold-23 ink)
  "How does mPFC connectivity reshape during appetitive learning?"; subtitle (bold-13 #5A6068, matches the
  other panels exactly — NOT italic) "All we wanted was to do science…"; single green caption (size 15, no
  gray sub-line, like every other panel) "Doing the science was never the hard part". Science context refined from the ISF grant
  `ISF_2879_2026_1584501_0.pdf` (Yizhar 2879/26 "Reshaping the Prefrontal Map" — inhibitory sequence model
  SST→PV, appetitive cue→reward, closed-loop wireless event-locked opto, high-throughput longitudinal). NOTE:
  grant predates the experiment — actual recording is **Neuropixels** (not the grant's planned miniscopes).
  Wired into `scratchpad/build_full_poster.py` as `P1` (placed `col_x[0], CONTENT_Y, 792, 660`); the old text
  placeholder block was removed. Re-assembled + re-rendered the full poster at 5× — all six panels now filled.
  OPEN: cell-8 source-art typo "Conceptual caos"; whether to broaden SST→ SST/PV sequence framing.
- 2026-06-28: **panel descriptions boldened + ASSEMBLY STAGE reached (per Ido).** Made the small sub-text
  *descriptions* readable in 3 panels: **Declarative Database** + **MICS Core** (`figure_portal_database.svg`,
  COORDINATION column) and **Elasticsearch** (`figure_storage_reconstruction.svg`, THE DATA column). The gray
  `#6E7682` / un-weighted `#3C4654` description lines (e.g. "build states & transitions in a visual editor",
  the MICS Core "— offline / idle / executing" tspans, and the ES "true execution time" lines) were bumped to
  **`font-weight=600` + slate `#3C4654`** so they hold up at poster scale while staying secondary to the bold
  item titles. Re-rendered both panels 3×, rebuilt `figure_full_poster.svg`, re-rendered at 5×
  (11880×8400) and **reviewed the whole poster** — both right-hand columns read cleanly. **Marks the move to
  the assembly stage**: from here on, panel edits are validated on the assembled full poster, not in isolation
  (new §4 "Assembly stage" subsection documents the edit→assemble→render→view-whole loop).
- 2026-06-27 (6): **full-poster header + bigger title bands (per Ido, `build_full_poster.py`).** (a) **Header**
  teal band **extended down to `HEADER_BOT=255.5`** to touch the top title bands (closed the whitish gap); header
  **text centered** (was left-aligned); **Weizmann white logo now on BOTH sides** (left + right), enlarged
  proportionally (`logo_h=168*BAND_BOT/240≈179`). (b) **6 kicker titles enlarged**: `KICK_FS 15→19`, band
  `BAND_H 24→32`, added a 0.5 same-color text stroke for extra weight (they were disappearing next to the figures'
  own ~23px titles). (c) **Figures shifted DOWN 8px** (`CONTENT_Y 280→288 = HEADER_BOT+BAND_H+GAP_BF`) to fit the
  taller bands while keeping the band→figure gap constant (`GAP_BF=0.5`); figures themselves unchanged. Bottom
  margin now 32px (content bottom 1648). `kicker()` refactored to take `band_top` and vertically center the text;
  seams/dividers recomputed from the new band tops (`TOP_BAND_TOP=255.5`, `LOW_BAND_13`, `LOW_BAND_2`).
- 2026-06-27 (5): **full-poster title bands + separator grid (per Ido, `build_full_poster.py`).** Each of the
  6 narrative kicker titles now sits on a **flat subtle pale-teal band** (`#D9E6EB`, a tint of header teal
  `#156082`; no pill/border) filling the **whole title area edge-to-edge between the vertical seams**
  (`SEAMS=[0,797,1584,2376]`). Reordered so bands draw first, then the **separator grid on top** (lines stay
  crisp). **Vertical seams extended up** to the top band's top edge (`TOP_Y-16.5=255.5`) so they run through and
  separate the 3 top titles. **Horizontal dividers**: lowered to **kiss the top edge of each lower band**
  (`H_COL13=957.5`, `H_COL2=737.5`) and **extended to span seam→seam** (via `SEAMS`) so they touch the vertical
  lines (previously ended at the column edge 792, 5px short of seam1 at 797).
- 2026-06-27 (4): **panel 2 (problem→solution) polish (per Ido).** (a) **Removed "MICS Portal" subheading** from
  the Scaling-experiments solution card and **shifted its checklist up 14px** so all 4 green panels' first
  checkmark aligns at y=477. (b) **Scaling-experiments illustration reworked**: the green MICS-Portal monitor +
  old arrows were baked into the raster — masked out the green pixels (kept the 6 black line-art cages, cleared
  the central ghost band), then overlaid a **smaller centered vector monitor** (pie + network glyph, `#0B5B1F`)
  with **6 green arrows radiating to the 6 cages** (hub-and-spoke; `arrg` marker added). (c) **4 inter-row
  arrows** (problem→solution) changed from fat grey block-arrows (`#8D949E`) to **thin navy line arrows**
  (`#1D348B` stroke 2.4, `arrb` marker) to match the poster's other arrows. All via python (raster is base64);
  re-rendered + rebuilt poster.
- 2026-06-27 (3): **panel 2 (problem→solution) — "Writing task logic" solution illustration swapped (per Ido).**
  Replaced the rasterized state-machine drawing (`<image x="237.3" y="382" w=124.1 h=86>`, line 59, white bg
  baked in) with the **vector mini state machine** ported from the data figure (panel 6, the legend FDA:
  PREPARE/TONE/REWARD/OPTO/STOP/ITI + navy arrows, all 7 transitions incl. STOP→ITI). Wrapped in
  `<g transform="translate(190.4,-89) scale(1.1)">` to center it in the green solution card (x207.2–391.4),
  between the title (y374) and the ✓ descriptions (y484). **No white backing rect** — boxes sit directly on the
  green panel `#F2F8F4` (only PREPARE/ITI are white state boxes, by design). Added the `arrb` navy arrowhead
  marker to the figure defs (copied from the data figure). Done via python (target line is a huge base64 blob).
  Re-rendered panel 3× + rebuilt/re-rendered poster.
- 2026-06-27 (2): **panel 6 data figure — nosepoke recolor + raster key (per Ido).** The two trial-
  reconstruction graphs (ONE embedded raster `<image x="130" y="417" w=372 h=170.8>`, 1248×573, cropped
  from image18) showed the **nosepoke** band in a **faint GOLD** (`#FFF8E9` family, ~42k px — a leftover of
  the earlier pink→gold recolor). Gold reads as *reward/valve* elsewhere, but **this graph has no reward** (only
  tone/nosepoke/opto/licks). Fix: per-pixel remap of the gold family → **faint red** (`#FFE2E2` median, scale
  1.3) via `/tmp/pptxenv/bin/python` (no numpy on host; mask `R≥240 & G≥222 & B≤242 & R≥G≥B & 6≤R−B≤70`,
  newGB=255−(255−B)·1.3). Decoded the base64 straight from the live SVG, recolored, re-embedded (string
  replace), so no dependence on the now-missing `build_panel6.py`/`raster_b64.txt` (those live in another
  session's scratchpad — panel 6 has **no canonical regenerator**; edit the SVG directly). Added a small
  legend directly below the mini state machine (open zone x≈16–125, y≈540–580, inserted before the bottom
  caption line): faint-red swatch → "nosepoke"; black tick → "lick" (no header, no "(each |)" per Ido).
  Re-rendered panel 3× + rebuilt
  full poster + re-rendered. NOTE: KB §5 still calls panel-6 Part 2 a placeholder — it is **fully built** now.
- 2026-06-27: **panel 4 state-machine beautified (per Ido — keep 100% wording/colors/dotted lines/logic).**
  Restyled THE-MICS-WAY state diagram in `figure_task_definition_v2.svg` (band-2 group `translate(0,26)`,
  was "too simple/squared"): added a soft drop-shadow filter (`feDropShadow`, resvg-js supports it) + subtle
  per-state vertical gradients + node `rx 10→15` + curved bezier feedback arrows (ITI→TONE, TONE→STOP,
  OPTO→STOP) with round caps; spine arrows kept straight. Box positions/sizes UNCHANGED so the dotted timing
  leaders (blue 5.2/2.3 bracket, gold 0.8/0.8) stay anchored. Z-order: nodes (shadow group) → arrows → labels.
  Verified the embedded panel PNG was a pixel-identical render of the SVG (SVG is the live source; full-poster
  markup == fresh `build_full_poster.py`), so no hand edits were lost. Re-rendered 3× + rebuilt/re-rendered poster.
- 2026-06-26 (5): **cross-figure consistency pass.** (a) **All figure titles unified** to the largest/boldest:
  size **23 bold `#0E2841`** (problem_solution + hardware bumped 20→23; task/portal/storage already 23).
  (b) **All FOUR "WHY IT MATTERS" panels unified** — they live in panels **3 (hardware), 4 (task), 5 (portal),
  6 (storage)** (easy to miss the hardware one). Unified spec: header **16 bold**, card title **12 bold**,
  card detail **9 bold** (`#0E2841` titles, `#3C4654` details), green pill + `#ic-bulb`. (c) Bigger bold text
  overflowed the narrower cards (portal 238px, hardware 220px) — fixed by **widening those cards into the
  figure's right margin** (portal 238→252, hardware 220→230; also centered them better) rather than shrinking
  text or editing copy; task(280)/storage(232) already fit. Verified clearance by pixel-measuring the longest
  detail line vs card edge. (d) Data-figure Elasticsearch panel recolored orange→**gold** (reuses reward
  `#C8994C`/`#FBF3E2`/`#8A5A12`; zero orange tokens remain; Elastic brand mark left as-is). (e) The three red
  cards (hardware-level / bottleneck / traditional-way) unified to fill **`#FFF7F7`**.
- 2026-06-26 (4): **reading orientation via narrative kicker labels** (Ido chose this over arrows/numbers;
  flow = top-to-bottom per column, then left-to-right). Six teal (`#156082`) uppercase letter-spaced eyebrow
  labels, left-aligned just above each panel: **THE QUESTION→THE BOTTLENECK** (col1) / **HARDWARE→TASK LOGIC**
  (col2) / **COORDINATION→THE DATA** (col3). The header band / horizontal divider above each doubles as the
  eyebrow rule; the two lower-panel dividers were nudged up 8px (col1/3 y=952, col2 y=732) to open the kicker
  band. Vertical adjacency (QUESTION→BOTTLENECK etc.) pulls the eye down before across. In `build_full_poster.py`
  (`kicker()` helper) — labels are plain strings, trivially editable. Separator-line opacity settled at **0.22**.
- 2026-06-26 (3): **poster polish.** (a) Header subtitle + affiliation lines restyled to **match the
  authors line** (bold, solid white, non-italic). (b) Added an **elegant separator grid** in the header
  color (`#156082`, 2px, opacity 0.5): two vertical column dividers + one horizontal divider per column at
  its gutter midpoint (col1/col3 y=960, col2 y=740); **no line on the bottom edge** of the bottom row.
  (c) Vertical dividers **nudged to the midpoint of the measured figure-content gap** (strong-content edge
  detection, run-length filtered): **seam1 x=797** (driven by problem_solution↔task_def), **seam2 x=1584**
  (hw/task↔portal/storage) — note `task_definition_v2` fills its column nearly edge-to-edge so its faint
  full-width strip must be ignored (use thr≥45). (d) **DREAM placeholder is now TEXT ONLY** — removed the
  dashed white card (distracting) and it must NOT anchor the seam1 divider. All in `build_full_poster.py`.
- 2026-06-26 (2): **header corrected to match pptx exactly.** The poster header is a **full-width solid band
  fill `#156082`** (pptx theme **accent1**, resolved via the top banner shape `(0,0) 47.2×8.5"` whose
  `<p:style> fillRef idx="1" schemeClr accent1`; theme accent1 = `156082`, fillStyleLst[1] = plain solidFill,
  no tint). Header **text is white** (`schemeClr bg1` → lt1 → `#FFFFFF`) and **LEFT-aligned** (pptx `algn`
  default = l). The Weizmann **logo is the original WHITE** `image47.png` (sits on the teal band — do NOT
  recolor). ⚠️ `#1D358B` is the deck's **figure-title navy** (all section headers), NOT the header fill — do
  not confuse them. (pptx subtitle run is `accent5`@lumMod20% ≈ dark magenta; rendered as soft-white instead
  for legibility — revisit if exact match wanted.) Build script `scratchpad/build_full_poster.py` updated
  (`HEADER_BG="#156082"`, white logo b64 `/tmp/logo_white_b64.txt`).
- 2026-06-26: **assembled FULL POSTER** `figure_full_poster.svg/.png` (2376×1680 px = A0 landscape
  118.9×84.1 cm @ 20 px/cm; PNG rendered 3× → 7128×5040). Build script `scratchpad/build_full_poster.py`
  (re-runnable; base64-embeds each panel PNG so the SVG is self-contained). Layout per §3b: top margin 2 +
  header 10 + gap 2 + content 68 + bottom 2 cm; three 39.6 cm (792 px) columns. **Panels (v2 used where
  duplicates exist — latest):** col1 = [1] DREAM placeholder (top) + [2] `figure_problem_solution` (bottom);
  col2 = [3] `figure_hardware_abstraction_v2` (h22) + [4] `figure_task_definition_v2` (h44); col3 =
  [5] `figure_portal_database` + [6] `figure_storage_reconstruction`. **Panel 1 (DREAM) not ready →** styled
  dashed placeholder ("The scientific question" + framing subtitle + "DREAM EXPERIMENT / figure in progress").
  **Header** recreated as native SVG from the pptx title box (text runs 62–65): title "MICS: When experiments
  run themselves" (navy `#1D358B` bold 58) + tagline + authors + affiliation; **author order switched so
  "Ido Porat*" is first** (was "Noa Levy*, Ido Porat*…"). **Weizmann logo** = pptx `image47.png` (white,
  transparent) **recolored to navy** via alpha-mask (`/tmp/logo_navy_b64.txt`), top-right. Render via
  `/tmp/svgrender/render_poster.mjs <svg> <png> 2376 3` (the default render.mjs hardcodes width 1200 — use the
  poster variant). NEXT: build panel 1 (DREAM experiment) to replace the placeholder.
- 2026-06-25 (3): **panel 4 v2 polish.** (a) **Illustration enlarged** to 278×132 (was 232×110) — left
  cards narrowed to **w=448** (code's longest line measured at x≈457, so the divider could move to x=480),
  right column widened to **w=280**. (b) **Fixed crowding INSIDE the pptx illustration** (the coworker's source
  labels were oversized): edited a **copy** of the pptx (`/tmp/work2.pptx`) — reduced font `sz` of "Update VIEW"
  1200→900, "State transitions"/"Hardware modules" 1200→1000, "Physical connection" 1200→950 (regex over each
  `<p:sp>` block, repacked with python `zipfile`), then re-rendered + re-cropped + re-recolored + re-embedded.
  Now "Update VIEW" fits one line above the eye, the side labels clear the connector lines/top cube, and
  "Physical connection" wraps fully (was clipped). (c) **State-machine label fixes**: the short inter-box arrows
  were being masked by their own centered labels — moved "once"/"lick (Hit)"/"then ITI" **above** their arrow
  lines; moved "opto pulse ended" beside (not on) its arrow; baseline-aligned "response time expired" &
  "ITI timeout" at y=640 and **dropped "trial++"** to declutter. (d) **σ restored** on both timing callouts as a
  2nd line under μ (block nudged up): blue end-to-end μ=5.2/σ=2.3 ms, gold command→valve μ=0.8/σ=0.8 ms.
  Rendered 3× (0.900 ✓).
- 2026-06-25 (2): **panel 4 v2 RESTRUCTURED into two columns** (rebuilt via `/tmp/build_v2b.py`, splices the
  band-1 code block verbatim). **LEFT column** = the two cards, both **narrowed to w=496** (were 744): code
  ("THE TRADITIONAL WAY") + state machine ("THE MICS WAY"). State machine pushed left & PREPARE SESSION shrunk
  to a small **INIT** box (72px). The per-card **✓/✗ verdict bullets were removed** and re-expressed on the
  right. **RIGHT column** (x540–772, mirrors panel 5/6 coords, divider x528): **top = WHY IT MATTERS panel**
  (green kicker pill + `#ic-bulb` + header "Behavior you can reason about" + 3 `#EAEDF2` cards w/ green icons
  `wm-eye`/`wm-flow`/`wm-puzzle`: Readable at a glance / Explicit transitions / Extend in one place — encapsulates
  the old ✗/✓ contrast, consistent with panels 5&6); **bottom = the local-execution illustration** ("Runs locally
  on each setup" + image + caption + 3 green-check bullets: on-device·no network / autonomous / ms closed loop).
  **Illustration bg fixed**: the white slide bg + inter-card gap recolored to figure bg `#F5F7FA` (threshold:
  pixels with all channels ≥247 → 245,247,250, done on the hi-res crop before downscale). Rendered 3× (0.900 ✓).
- 2026-06-25: **panel 4 v2** `figure_task_definition_v2.svg/.png` (copy of panel 4, 792×880, 0.900 — v1
  left untouched). Added a **local-execution illustration** recycled **as-is** from the pptx panel
  "Independent local execution on each setup": the two cards **MICS Core** (raspberry + State transitions
  loop → Update VIEW → Hardware modules → Physical-connection GPIO pins) **↔ wires ↔ Experimental setup**
  (Hardware icons + mouse-in-cage). Rendered the source slide via the new aspose pipeline (§4), cropped the
  two cards (slide inch-coords ×216 px/in), trimmed, embedded as base64 `<image>`. **State machine compacted
  LEFT** to make room: rebuilt band 2 via `/tmp/build_v2.py` (arrows computed from box geometry) — PREPARE→TONE
  and TONE→REWARD(Hit) arrows shortened, TONE center 396→290, REWARD/OPTO 660→470, bottom row kept symmetric
  about TONE; timing callouts shortened to `μ=5.2 ms`/`μ=0.8 ms` so they don't collide at the tighter spacing.
  Panel sits x=548–762 with green title "Runs locally on each setup" + caption "The cage wires into the Core's
  pins → updates the VIEW that drives the transitions — no network in the loop." Rendered 3× (0.900 ✓).
- 2026-06-24 (2): started **panel 6** `poster_figures/figure_storage_reconstruction.svg/.png` (792×660, 1.200).
  Built **PART 1 (structured storage & real-time event logging)** + a dashed **PART 2 placeholder** so Ido can
  judge overall fit. Decisions: (a) the diagram is an **icon-only recap of Panel 5** (Portal/Core/DB carry NO
  text labels per Ido) extended with the NEW event-stream→Elasticsearch story; (b) **multiple Cores** shown as
  a fanned Pi-logo deck + "×N"; (c) the three key logging guarantees live in an expanded **event-document**
  (precise `t_hw` stamped at the **GPIO pin edge / hardware clock**, fully **contextualized** with session/
  subject/blueprint) AND a 4-item navy property list; (d) **state value `TONE → REWARD` uses Panel-4 gold** —
  state-machine/reconstruction colors come from `figure_task_definition.svg`, not §3c (see §3c note). Elastic-
  search is the only labeled node (it's new). Rendered 3× → 3600×3000 (1.200 ✓). NEXT: build Part 2.
- 2026-06-24 (3): **panel 6 Part 1 REDESIGNED per Ido — now mirrors Panel 5 for cohesion.** Replaced the
  standalone event-document deck + navy property list with the Panel-5 layout: subtle/smaller **blue MICS
  Portal** (3 icons, pale-blue bg) / green **Declarative Database** / **MICS Cores** stack on the LEFT (=
  "experiment definitions" + "live execution"), feeding an **orange Elasticsearch panel** on the RIGHT (the
  "ongoing events" store) that holds the 4 logging guarantees + orange icons. Header subtitle is the pptx ref
  line. Orange = `#DD6B1F`/bg `#FDF2E9` (distinct from the blue/green system panels). The hardware-clock /
  pin-edge-not-Python-command-or-recording-time / contextualized points now live inside the orange panel.
  Rendered 3× (1.200 ✓).
- 2026-06-24 (4): **panel 6 Part 1 → THREE columns per Ido** (now fully Panel-5-cohesive). (a) **Cores** lost
  its wrapping panel — just a fanned stack of **purple Pi-logo cards** (×N); (b) **Portal + Declarative DB
  panels narrowed**; (c) the **bidirectional Portal↔DB / Portal↔Cores arrows lengthened** (y155→183, gap was
  too short); (d) **Elasticsearch panel shifted LEFT + narrowed** (PX=272, PW=242) to free the right third;
  (e) added a **green "WHY IT MATTERS" panel** (kicker pill + bulb, "Trust every record", 3 cards: Reconstruct
  any trial / Closed-loop you can trust / Compare across the cohort) like Panel 5; (f) stream arrow still exits
  the Portal. Rendered 3× (1.200 ✓). Part 1 DONE; NEXT: build Part 2 reconstruction.
- 2026-06-24 (5): **panel 6 orange ES panel expanded to 6 items per Ido** (panel grew, Part 2 nudged down).
  (a) clock item reworded to **make the shared timebase evident** — software events (state transitions) carry
  the **same hardware clock** as pin events; (b) "Pin-level precision" → **"True execution time"** ("the moment
  the hardware fired — not when Python issued the command or it was logged"); (c) added **"Schema-free — nothing
  forgotten"** (every event auto-saved as a document, no schema to design — the "we got you" point); (d) added
  **"Build custom dashboards"**. New orange icons p-exec (bolt) / p-doc / p-dash. Rendered 3× (1.200 ✓).
- 2026-06-24 (6): **panel 6 orange spacing + WHY-panel refocus per Ido.** (a) clock line dropped
  "(state transitions)" → just "software events alike — all on the same hardware clock"; (b) **more vertical
  breathing room** between orange items (text unchanged — Ido liked it — only spacing); (c) WHY panel rewritten
  to Ido's 3 topics: **Reconstruct any trial** / **Add hardware, change nothing** (zero-config extensibility) /
  **Built to scale** (ES designed for high-volume insert + query). New green icons w-add (＋box) / w-scale
  (ascending bars). Part 2 nudged to y=368. Rendered 3× (1.200 ✓).
- 2026-06-24 (7): **panel 6 icon swaps per Ido.** (a) orange-panel header now uses the **real Elastic mark**
  extracted from the pptx ("Structured data storage" figure = `ppt/media/image20.png`, 78×86, base64-embedded
  via `scratchpad/elastic_b64.txt`) — vertically centered against the 2-line "Elasticsearch / event store" title
  (drawn `ic-elastic` def removed); (b) WHY "Reconstruct any trial" icon → a **green puzzle piece** (`w-puzzle`,
  filled, tab top+right). Rendered 3× (1.200 ✓).
- 2026-06-24: built **panel 5** `poster_figures/figure_portal_database.svg/.png` (792×660, 1.200).
  Reworked a 2-panel draft into: Portal (3 cols) → DB + Core diagram (left 2/3) + a 6-item
  **"Everything in one place"** advantages list (right 1/3). Key decisions: (a) the Portal DEFINE
  column shows the **same entity icons** as the DB panel (shared `<defs>`), mirroring the existing
  CONTROL-STATUS↔Core pattern; (b) added the **HW libs & modules** DB entity (microchip icon); (c)
  the two lower panels were **widened to match the Portal's width** (centers 132 / 390, gap 26) and
  the connector arrows made **bidirectional + vertical, centered** on each panel; (d) the advantages
  panel is a **benefit list** (mixed-voice "No more…" / affirmative headlines, periods removed),
  monochrome **black text + green `#1F9D55` icons** on neutral `#EAEDF2` boxes, **no card bg** (blends
  into figure), with a green **"WHY IT MATTERS"** kicker pill + lightbulb as an approachable entry
  point; box #4 = "No more spreadsheets" / "no typos, filename conventions, or tracking sheets"; (e)
  bottom caption **"Focus on the science — MICS handles the rest"** (sibling-figure voice); Portal bg
  recolored pale blue `#EAF2FC`. All edits via the Edit tool (pure vector). 3× → 3600×3000 (1.200 ✓).
- 2026-06-22 (3): **panel 4 transition/inset polish per Ido.** (a) **Gold (command&#8594;valve, 0.8 ms)
  inset resized 120&#215;42 &#8594; 126&#215;47 to match the orange end-to-end inset's proportion**, and recentered
  on x=660 (REWARD center). (b) **Gold dotted leader made straight vertical** (`M660,494 L660,522`,
  was the angled `M666,489 L661,522`). (c) **Transition labels moved onto the arrows themselves**
  (centered on each arrow midpoint), the bg-color halo (`paint-order:stroke; stroke:#F2F8F4; width 3.5`)
  masking the line behind the text. (d) **Angled arrows are split into two collinear segments with a
  gap where the label sits** (TONE&#8594;STOP TONE, REWARD&#8594;STOP TONE, ITI&#8594;TONE), marker-end only on the
  segment reaching the target; **horizontal arrows kept whole** (halo alone masks them, no gap needed).
  Re-rendered 3&#215; (aspect 0.900 &#10003;).
- 2026-06-22 (2): **panel 4 timing insets re-added per Ido.** Two small histogram insets at the top
  of the state-machine card, each from `image.png` (= image34, the closed-loop-delay figure): (a)
  **orange** "Detection&#8594;Action" (&#956;=5.2 ms) captioned **"end-to-end closed-loop / lick &#8594; water"**,
  tied to the TONE&#8594;REWARD path by the orange dotted span; (b) **gold** "State Transition&#8594;Action"
  (&#956;=0.8 ms) captioned **"command &#8594; valve / (actual execution)"** (Ido: frame the 0.8 as command&#8594;
  actual execution, NOT "state transition"), tied to REWARD by a gold dotted leader. The 0.8 subplot
  was **recolored green&#8594;reward-gold** (`#C8994C`) via per-pixel HSV hue-rotate of greenish pixels
  (keeps black legend/axes). **Gotcha:** `image.png` is **RGBA with a transparent bg** &#8212; a naive
  `.convert('RGB')` turns transparent &#8594; **black**, so resvg rendered black-bg insets; fix is to
  composite onto white first (`bg.paste(src, mask=src.split()[3])`) before cropping. `<image>` boxes
  use `preserveAspectRatio="none"`. Crops in `/tmp/hist_orange.png` + `/tmp/hist_gold.png`; embedded
  base64. Re-rendered 3&#215; (aspect 0.900 &#10003;).
- 2026-06-22: **panel 4 simplified per Ido (band 2 rewrite).** (a) **TRIAL ONSET box removed**;
  `trial++` folded onto the ITI&#8594;TONE timeout arrow. (b) **ITI + STOP TONE now share one bottom
  row, symmetric about card center x=396** &#8594; states read as a clean cycle (PREPARE&#8594;TONE&#8594;REWARD
  &#8594;STOP TONE&#8594;ITI&#8594;TONE, with a symmetric V under TONE). (c) **TONE&#8594;STOP TONE arrow relabeled
  "response time expired"** (was "no lick"). (d) **All 3 histogram images dropped** (blue 4.4 / green
  0.8 too); **only the orange 5.2 ms dotted span over TONE&#8594;REWARD remains**, with "end-to-end
  closed-loop delay" sublabel. (e) **Green &#10003; verdict moved BELOW the card** (mirrors band 1).
  Card height trimmed 424&#8594;388; freed space gives the diagram breathing room. Band 2 was rewritten
  wholesale via `/tmp/rewrite_band2.py` (the old block held base64 histograms Edit can't match);
  re-rendered 3&#215; &#8594; 3600&#215;4000 (aspect 0.900 &#10003;).
- 2026-06-21: revised **panel 3** per Ido. (a) The recycled valve raster (image3.png) had
  "Valve (solenoid)" text baked in — **cropped to y=134** (graphic ends ~y128) and re-embedded
  as a reusable `#ic-valve` symbol (text-free) used in all 3 cards. (b) **Card 1 device-icon
  order now matches Card 2**: speaker → lick → valve → opto → camera. (c) **Abstraction layer
  re-centered**: Task logic / Functional modules / Hardware devices are icon-on-top, centered on
  card center x=654 with centered titles + descriptions + vertical flow arrows + centered footer.
  (d) Hardware-devices row icons changed from valve+LED to **clean-valve + speaker** (caption now
  "(e.g., valve, speaker)"). All edits done via inline python (regex over base64 blobs); re-rendered
  3× → 3600×2000 (aspect 1.800 ✓).
- 2026-06-21 (2): **Card 2 (behavior-level) now mirrors Card 1's "code left, icon right"** —
  commands left-aligned (x=292), device icons moved to a fixed right column (x=468), and the
  right-hand text labels (Speaker / Lick sensor / Reward valve / Opto / Camera) removed.
- 2026-06-21 (3): **Card 1 (hardware-level): removed** the vertical separator line (x=188) between
  the code and the device-icon column, plus the 5 dashed connector paths (`M188,… h16`). Icons now
  float in a clean right column with no divider. (Note: card-1 ✗ verdict glyphs `&#10007;` render
  as tofu in Aptos — candidate to replace with a vector ✗ symbol like card 2's ✓.)
- 2026-06-21 (4): **Card 1 ✗ verdict glyphs fixed** — the tofu `&#10007;` font glyphs replaced
  with a new vector `#ic-x` symbol (red circled X, mirrors `#ic-chk`), placed via `<use>` before
  each verdict text (Low-level communication / Device-specific task). **Card 3 (abstraction layer)
  description text enlarged** 8/8.2 → 9.5 under Task logic / Functional modules / Hardware devices,
  with small y-nudges on multi-line blocks for leading. Re-rendered 3× → 3600×2000 (aspect 1.800 ✓).
- 2026-06-21 (5): **Card 1 device icons shifted up 7px** (y-slots 104/150/198/242/288 → 97/143/191/235/281)
  so the Card 1 speaker aligns with the Card 2 speaker (both at y=97); internal spacing unchanged.
- 2026-06-21 (6): **Hardware-devices caption trimmed** — dropped "(e.g., valve, speaker)" (the valve +
  speaker icons above already convey it); now 2 lines: "Specific hardware instances / controlled with
  device-specific commands".
- 2026-06-21 (7): built **panel 4 (task definition)** `poster_figures/figure_task_definition.svg/.png`,
  792×880 (0.90 portrait). STACKED 3 bands per §3b: (1) **code** — traditional nested-if loop, amber =
  the 4 scattered edits the opto rule needs (flag / pick-type / laser_on branch / laser_off cleanup);
  (2) **state machine** — the MICS way: same rule = ONE new purple OPTO box wired to the reward
  transition ("same Hit" + dashed "co-fire", action-coupled per §2b); (3) **timing** — closed-loop
  latency pipeline Lick→[4.4ms]→transition→[0.8ms]→Water+opto, 5.2ms end-to-end, blue/green/orange
  per §3c. Shell = Blueprint A opto variant; same semantic hw as panel 3. Vector ✗/✓ symbols (ic-x /
  ic-chk) reused to avoid the Aptos tofu glyph. Rendered 3× → 3600×4000 (aspect 0.900 ✓).
- 2026-06-21 (7-rev): **panel 4 REDESIGNED per Ido** (now 2 bands, no bottom timing band). Corrected
  task logic: prepare session → TONE → (lick=REWARD, OPTO co-fires) → ITI; no lick → ITI; ITI timeout
  → TRIAL ONSET (trial++) → TONE. **5 states**: ITI, TRIAL ONSET (grey, its own state), TONE (blue),
  REWARD (gold), OPTO (purple, drawn as a SEPARATE event though it always co-fires — that's the
  modularity point). Small dashed grey pills for true technicalities: prepare session (one-time entry),
  stop tone. **Histograms**: the pptx `image34` is NOT embedded whole; it is cropped into its 3 colored
  pieces (titles removed) and distributed over the relevant transitions — blue 4.4ms (lick→transition)
  over TONE, orange 5.2ms (end-to-end) over the Hit arrow, green 0.8ms (transition→action) over REWARD,
  each tied down by a color-matched dashed leader. Context strip is "The task:" (NOT "new rule"). Crops
  in `/tmp/hist_{blue,green,orange}.png`; box coords in §6 build notes. Rendered 3× (aspect 0.900 ✓).
- 2026-06-21 (7-rev2): panel 4 polish per Ido. **STOP TONE is now its own grey state** (convergence of
  the no-lick and reward-done paths → ITI). **PREPARE SESSION** promoted from a floating dashed pill to
  a real state in the main row (white fill + navy stroke, NOT grey). **OPTO sits WITH reward** — plain
  purple connector + "with reward" label, the "co-fire" arrow/wording removed (still a separate box).
  **Histograms shrunk** to 88×42 (were 118×56). **Traditional code now shows opto scattered across 3
  amber edit sites** (laser_setup / laser_on / laser_off) with lead-in "amber = the 3 scattered places
  you must touch just to add opto" + verdict "adding opto = 3 scattered edits". Fixed the band-1 ✗ icon
  that was sitting on the card border (code card shortened to 150–350; ✗ use at y356, text baseline 367).
  Re-crop coords (no titles): blue (250,126,746,360) green (838,126,1332,360) orange (535,686,1026,922).
- 2026-06-21 (7-rev3): panel 4 timing + framing polish. **OPTO is now a minimized purple "OPTO pulse"
  pill INSIDE the REWARD box** (separate OPTO box + "with reward" removed). **All state boxes inset
  ~20px from the card frame** (content x44–740, return row y748–798) so nothing sits on the border.
  **Timing semantics clarified**: blue 4.4 ms = lick→reward-state-starts → leadered to the Hit arrow
  (the transition); green 0.8 ms = reward execution → leadered to REWARD; orange 5.2 ms = end-to-end →
  drawn as a DOTTED SPAN bracketing over BOTH TONE and REWARD (x404→720), not a single point.
- 2026-06-08: restyled the two state-machine figures to poster style (green header removed).
- 2026-06-15: gathered science (GtACR / SST-Cre homozygous / acute Neuropixels / mPFC =
  value-guided action selection); wrote this KB; building the new science figure next.
- 2026-06-16: logged FENS print constraints (§3b). Confirmed reference pptx is square
  120×120 cm — **does NOT match** the A0-landscape / 180×84 poster envelope; layout must be
  reproportioned to landscape. New content order: science → problem/solution → tech figures.
- 2026-06-17: built **panel 3 (hardware abstraction)** `poster_figures/figure_hardware_abstraction.svg`
  (792×440 = 1.800 = 39.6×22 cm, 3×). Decoded the coworker figure from native pptx vector
  shapes via slide-XML coord parsing (3 cards at x≈17/22/27", y≈11–16.5"). Kept the 3-card
  structure; abstraction panel reproduced **verbatim** (text + recycled brain/cube/LED/target).
  **Device-illustration rule (Ido):** recycle the original poster's illustration when the
  device is unchanged (valve = image3.png, base64-embedded); draw NEW vector icons where our HW
  differs (speaker/lick-sensor/opto/camera vs the original door/LEDs). Card 1 = crowded pigpio
  code + right-side device annotations + ✗ Low-level/✗ Device-specific; card 2 = high-level
  commands with inline icons + names (lick→Lick sensor, valve→Reward valve), "Same devices" row
  dropped. Build script: inline python (base64) — re-run to regenerate. **Convention: finished
  figures live in `poster_figures/`.**
- 2026-06-17: reconstructed Blueprint A from legacy `AppetitiveTaskReal.py` at diagram level
  → added §2b (panels 3/4/6). Panel-4 simplified to Prepare-session→Tone→Response-window→
  {Water+Opto | Miss}→ITI; opto is reward/action-coupled; Hit=detection, arrow=transition,
  water=action mapped to the 4.4/0.8/5.2 ms strip; TTL syncs ephys + DLC.
- 2026-06-16: **FINAL layout locked** (§1 + §3b): **A0 landscape 118.9 × 84.1** (FENS preferred,
  not the 180×84 max), 10 cm header, three **39.6 cm** columns, 6 panels (L: DREAM /
  Problem→Solution; M: HW abstraction 1/3 over combined code-vs-FDA+timing 2/3, stacked
  vertically; R: Portal+declarative-DB / storage+reconstruction). Panels 1/2/5/6 share size
  39.6×33. Sampled cross-figure element colors from image18 and closed-loop timing
  (4.4/0.8/5.2 ms) from image34 → §3c. Build panels next.
