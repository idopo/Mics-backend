# Within-trial binning analyses (Gili)

Interactive HTML dashboards that cut each trial into time bins and look at where
nose-pokes / licks / lick-bouts happen — on-cue vs during the ITI. All figures are
self-contained offline HTML (Plotly embedded, no server); open them in a browser.

## Figures

| Script | Output (`../results/bining/<area>/`) | What it shows |
|---|---|---|
| `bin_trial_analysis.py` | `bin_profile_dashboard.html` | line profile of a metric across the bins |
| `bin_dotplot.py` | `bin_dotplot.html` | mouse×bin dot matrix: size = poke prob, colour = licks/poke |
| `bin_timecourse.py` | `bin_timecourse.html` | continuous time course (no binning), 0.5 s steps |
| `bin_barplot.py` | `bin_bouts_barplot.html` | lick-BOUT bars per bin (+ trial-type filter incl. catch) |
| `bin_roc.py` | `roc_curves.html` | ROC curves + AUC/d′ across sessions |

`<area>` is `appetitive`, `generalization`, or `cross_task` (for `--task both`).

## Regenerate

```bash
cd analysis/bining
python3 bin_trial_analysis.py --task both     # or --task appetitive / generalization
python3 bin_dotplot.py       --task both
python3 bin_timecourse.py    --task both
python3 bin_barplot.py       --task both
python3 bin_roc.py           --task both
```

Every script also takes `--mouse m102` to restrict to one subject. Data comes from
Elasticsearch via the shared loaders (`trial_history_analysis.load_appetitive/…`),
so ES must be reachable (see `../config.py`).

## Definitions (shared across the figures)

- **Bins** (fixed structure): `on-cue` = `[0, cue_dur)` (the actual tone/LED window);
  then **4 fixed-width bins** tiling the *nominal* ITI `[iti_start, iti_start+nominal_iti]`
  (each `nominal_iti/4` s wide); then one **added-ITI (punishment)** bin
  `[nominal_end, iti_end]` for time added by ITI pokes resetting the timer.
- **nominal_iti** = median ITI length of *unpunished* trials (`≈30 s` tone / `29 s` light).
- **Lick bout** = a run of licks with gaps ≤ `LICK_BOUT_GAP` (1.0 s), from
  `learning_trajectories_analysis`. `licks_per_bout` = mean bout size.
- **Catch trial** = the canonical `cue_poke_lick_no_reward` from
  `action_sequence_analysis`: on-cue poke + a **response-window lick** (in `[0, iti_start)`)
  + **no reward**. (Not just any lick after the poke.)
- **On-cue band** (blue) and **added-ITI band** (red) mark those regions; in the
  single-mouse view they track that mouse's own mean cue / ITI timing.
- **ROC**: sweeps a threshold on a decision property (response licks, biggest bout,
  etc.) to separate two classes (reward vs non-reward, engaged vs not). AUC 0.5 =
  chance, 1 = perfect. `reward_vs_catch` is cohort-only (catch too rare per session
  for per-mouse curves); `reward_vs_nonreward` / `engaged_vs_not` populate every mouse.

## Shared-loader change made for this work (affects ALL analyses)

`trial_history_analysis.load_appetitive` now segments sessions by **lab-day**, not by
the unreliable ES `session` counter (it sometimes merged two days into one ~120-trial
session, e.g. m100). Implemented in `appetitive_analysis.py`:

- `group_by_day()` — bins a subject's events by lab-local day (`LAB_TZ`, default
  `Asia/Jerusalem`).
- `keep_main_run()` — drops a same-day aborted false-start when a full ~60-trial run
  also ran that day (gap > `FALSE_START_GAP_S`, 300 s).
- `base_fields()` now also carries `n_false_alarms` (needed for the nominal-ITI / catch logic).

Result: m100 went 4 → 12 sessions; appetitive total 107 → 116. Every analysis that
imports the shared loader picks this up automatically.
