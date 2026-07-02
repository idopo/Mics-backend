# MICS Behavioral Analysis

Reproducible analysis of two behavioral tasks run on the `RecordingBox` pilot for
10 mice — the **appetitive tone task** and the **generalization (light cue) task** —
plus cross-cutting **behavioral-pattern** analyses. Pure-Python (`requests` +
`numpy` + `matplotlib`), no Elasticsearch client needed, and OS-portable
(headless `Agg` backend + matplotlib's bundled fonts → identical figures on
Windows/macOS/Linux).

## Quickstart — Windows + conda

```bat
:: 1. create + activate the environment (run from the analysis/ folder)
conda env create -f environment.yml
conda activate mics-analysis

:: 2. tell the scripts where Elasticsearch is (edit config.py, or set an env var)
::    PowerShell:  $env:ES_URL = "http://132.77.73.125:9200"
::    cmd.exe:     set ES_URL=http://132.77.73.125:9200
set ES_URL=http://YOUR-ES-HOST:9200

:: 3. run the analyses (each writes figures into a sibling folder)
python appetitive_analysis.py            :: -> appetitive_rasters/
python generalization_analysis.py        :: -> generalization_figs/
python behavior_patterns.py              :: -> behavior_figs/
```

`config.py` holds `ES_URL` / `ES_INDEX` (env vars override). The committed
figures were produced against `ES_INDEX = restored-event_log_v2`. Results are
deterministic: same ES data in → identical numbers and figures out.

## Scripts & outputs

| Script | Produces | Notes |
|---|---|---|
| `config.py` | — | ES host/index (edit or override with env vars) |
| `appetitive_analysis.py` | `appetitive_rasters/` | rasters, learning curves, poke grids, participation figures; `--analysis rasters\|curve\|pokes\|participation\|all` |
| `generalization_analysis.py` | `generalization_figs/` | generalization learning curve, engaged hits/miss, rasters, participation figures |
| `behavior_patterns.py` | `behavior_figs/` | phenotypes, impulsivity, licking, cross-task transfer; `--task appetitive\|generalization\|both` (generalization default + cross-task; appetitive = within-task figures only) |
| `action_sequence_analysis.py` | `action_sequence_figs/` | per-trial decomposition of the behavioral chain (cue→poke→lick→reward) — stacked bars, group trajectory, per-mouse chain dynamics (on/off-cue pokes + licks across sessions), latencies, trial-history, transition matrix, 2 CSVs + summary.txt; `--task appetitive\|generalization\|both --mouse mNNN` |
| `learner_criterion_analysis.py` | `learner_criterion_figs/` | formal learner classification (participation vs competence, never hit rate alone); 7 figures + 2 CSVs + summary.txt; `--task … --mouse …` |
| `trial_history_analysis.py` | `trial_history_figs/` | does current-trial behavior depend on recent history? reward-gating / persistence / off-cue, conditional probabilities + numpy logistic models; 6 figures + 2 CSVs + summary.txt; `--task … --mouse …` |
| `cross_task_transition_analysis.py` | `results/cross_task/appetitive_to_generalization/` | tone→light transition: (1) phenotype shift from each mouse's **last** appetitive session to its **first** generalization session, drawn as first→last arrows in the engagement×competence learner space (reuses learner_criterion metrics/classifier); (2) per-mouse raster of the **first** generalization session with CUSUM step-onset lines marking the trial from which hit rate, on-cue poking, and on-cue poke+lick each step up (when the mouse cracked the new rule / engaged the cue); 2 figures + 2 CSVs + summary.txt |
| `punishment_analysis.py` | `results/<area>/punishment/` | ITI false-alarm punishment: a trial is "punished" if the mouse nose-poked during its inter-trial interval (ITI = 30±5 s; each poke resets the timer + adds ≥10 s), counted directly from the `state_ITI_nose_poke` FSM transition. % punished trials per mouse per session (curve, per-mouse bar, mouse×session heat map) plus within-session dynamics — punishment rate & false-alarms-per-trial vs trial position, a per-mouse trial-position curve, and a per-mouse session×trial map (which trials of which session added ITI); 6 figures + 3 CSVs + summary.txt; `--task appetitive\|generalization\|both --mouse mNNN` |
| `on_off_cue_analysis.py` | `results/<area>/on_off_cue/` | on-cue vs off-cue pokes+licks (share/ratio per trial→session→mouse); lick density after reward vs after off-cue poke (burst size + PSTH); ITI timing measured from **disengagement** (mouse stops the consummatory lick bout AND withdraws its nose — IR1 level→0 poke-out) with the fixed ~10 s end-of-trial response lockout trimmed off — per-trial raster, most-probable-time graph, per-mouse heat map, group curve, first/second-half bars; 8 figures + 4 CSVs + summary.txt; `--task appetitive\|generalization\|both --mouse mNNN` |
| `participation.py` | — | shared participation-vs-competence figure module (imported by both task scripts) |

---

## Scope & data source
- **Task:** `AppetitveTaskReal` (appetitive tone-cued task)
- **Pilot/rig:** `RecordingBox`
- **Period:** November–December 2025
- **Subjects:** 10 mice (ES subjects `m90, m92, m93, m97, m98, m100, m101, m102, m103, m104`, descriptive strings `m<n>_AppetitiveTone_150`)
- **Source:** Elasticsearch index `restored-event_log_v2` (`http://localhost:9200`), event envelope filtered by `task_type`, `pilot`, `subject`, and `timestamp`.
- **Tooling:** single script `analysis/appetitive_analysis.py` (Python; `requests` + `numpy` + `matplotlib`, no ES client needed). One ES fetch + trial-segmentation pass feeds all analyses.

## Event semantics (verified against the raw event stream)
| Behavior | ES event |
|---|---|
| Trial start | `state_transition` → `current_state = "trial_onset"` |
| Tone onset (t=0) | `mixer.AUDIO`, `func_name = set_by_filename`, `level = 1` |
| Tone offset | `mixer.AUDIO`, `func_name = mute` — present on HIT trials (tone cut short at reward); absent on MISS trials, where the audio file plays its full ~8 s length |
| Nose poke | `gpio.Digital_In`, `id = IR1`, `level = 1` (beam-break rising edge) |
| Lick | `gpio.Digital_In`, `id = TOUCH_INT` (capacitive contacts) |
| Reward / HIT | `gpio.Solenoid_mics`, `id = open`, `func_name = store_series` (water-valve open command; one per delivery) |

**Definitions used:**
- A **HIT** = a trial containing a water delivery; the **rewarded lick** = the lick immediately preceding the valve-open command.
- **Rewarded poke** = the poke that earned water (one per HIT).
- **On-cue poke** = nose poke while the tone was playing (t between 0 and the trial's actual tone duration); **off-cue (ITI)** = all other pokes.
- Partial/aborted sessions (< 10 trials) are dropped; each mouse's remaining sessions are re-indexed to a 1..K "session #" axis so trajectories align across mice.

## Analyses produced
1. **Trial rasters** (per subject × session, 123 total) — x = trial time (0 = tone onset), y = trial #; nose pokes (green), licks (black), rewarded licks/HIT (yellow), and a per-trial light-blue band sized to the *actual* tone duration.
2. **Learning curves** — hit rate (% of trials earning water) across sessions: per-mouse overlay + group mean ± SEM, plus a per-mouse small-multiples grid.
3. **Per-mouse / per-session poke bar grids:**
   - Total nose pokes per session
   - Nose pokes during the tone cue per session
   - Poked-and-licked vs poked-no-lick (trial counts)
   - **Nose-poke breakdown** — single stacked bar, 3-way split of all pokes (% rewarded on-cue / on-cue not rewarded / off-cue ITI)
   - **On-cue reward ratio** — rewarded vs not-rewarded among only the during-tone pokes (a learning-sensitive measure that removes ITI noise)
4. **`session_metrics.csv`** — tidy per-session table (`subject, session, training_day, n_trials, n_hits, hit_rate, total_pokes, pokes_during_tone, n_poked_licked, n_poked_nolick`).

## Output files (under `analysis/appetitive_rasters/`, gitignored)
- `<subject>/session_NN.png` — 123 rasters
- `learning_curve_group.png`, `learning_curve_grid.png`
- `pokes_total_per_session.png`, `pokes_during_tone_per_session.png`, `pokes_lick_vs_nolick_per_session.png`
- `pokes_breakdown_per_session.png`, `pokes_ontone_reward_ratio_per_session.png`
- `session_metrics.csv`

## Key observations
- **Learning is heterogeneous.** Clear learners (e.g. **m97**, **m100**, **m102**) increase hit rate across sessions; **m92, m98, m101** stay low (~5–15%). No mouse reliably exceeds 50% hit rate (vs all trials). The group mean is fairly flat (~20%), so signal lives in individual trajectories.
- **Most pokes are off-cue.** ~75–90% of nose pokes occur during the ITI across all mice, which suppresses any reward ratio computed against *total* pokes.
- **Normalizing to on-cue pokes sharpens the learning signal.** Among during-tone pokes, success climbs to ~80–100% in learners (m97, m102) while remaining low/noisy in non-learners (m92, m98) — a more sensitive readout than overall hit rate.

## Reproduce
```bash
cd analysis
python3 appetitive_analysis.py                  # everything, all 10 mice
python3 appetitive_analysis.py --analysis rasters   # or: curve | pokes
python3 appetitive_analysis.py --subject m90_AppetitiveTone_150 --session 7
```
Environment overrides: `ES_URL`, `ES_INDEX`, `MICS_TASK`, `MICS_PILOT`, `MICS_DATE_GTE`, `MICS_DATE_LTE`, `MICS_TONE_S`, `MICS_MIN_TRIALS`, `MICS_OUT`.

> Note: running with `--subject` rebuilds the aggregate figures (learning curves, poke grids, CSV) from only that mouse. Run without `--subject` to regenerate them for all 10 mice.

---

# Generalization Task — Did the Mice Generalize to a Light Cue?

`generalization_analysis.py` — does the learned tone-cued behavior transfer when
the cue becomes a **light**? Covers all 10 mice; rasters are drawn for the two
highlighted learners (m97, m102).

## Scope
- **Task:** `Generalization` ("GenLight") — same poke→lick→reward structure as
  the appetitive task, but the cue is **LED2 (a light)** instead of a tone.
- **Mice:** all 10 are auto-discovered (`m<id>_GenLight_400` subjects). The
  aggregate figures (learning curve, engaged hits/miss, CSV) cover **all mice**;
  the rasters are drawn only for the highlighted learners **m97, m102**
  (`RASTER_MICE`) since a 10-mouse raster grid is unreadable.
- Each mouse's generalization sessions span two ES subject strings
  (`<id>_GenLight_400` then `<id>_GenLight_400_2`, a continuation); they are
  merged and ordered chronologically. Partial/aborted sessions
  (< `MIN_TRIALS`=10 trials) are dropped, and only the first **4 sessions**
  (`MAX_SESSION`, common to all mice; Dec 2025–Jan 2026) are kept.

## Event semantics (verified against the raw stream)
| Behavior | ES event |
|---|---|
| Trial start | `state_transition` → `trial_onset` |
| Cue onset (t=0) | `gpio.Digital_Out` `id=LED2`, `func=set`, `level=1` (LED on) |
| Cue offset | `gpio.Digital_Out` `id=LED2`, `level=0` — cut short on a hit, else ~8 s |
| Nose poke | `gpio.Digital_In` `id=IR1`, `level=1` |
| Lick | `gpio.Digital_In` `id=TOUCH_INT` |
| Reward / HIT | `gpio.Solenoid_mics` `id=open`, `func=store_series` |

**Engagement** is scored strictly: a trial is *engaged* only if the mouse
nose-poked **while LED2 was on** (poke time in `[0, LED-on duration]`). The
hits/miss figure is computed over **engaged trials only** (miss = engaged but no
reward). Hit counts cross-checked vs raw ES (`store_series` count − 1
session-start priming pulse).

## Outputs (under `generalization_figs/`)
- `generalization_learning_curve.png` — hit rate (all trials) + engagement rate across sessions, both mice
- `generalization_engaged_hits_miss.png` — per mouse, per session: engaged trials split into hit vs miss
- `rasters/<mouse>/gen_session_N.png` — per-session rasters (LED2-on band, nose pokes, licks, rewarded/HIT licks)
- `generalization_all_rasters.png` — all rasters in one figure (rows = sessions, m97 left / m102 right)
- `generalization_metrics.csv` — per-session table (incl. `acc_given_engaged`)

## Key finding — the whole cohort generalized
**Whenever a mouse pokes on the light cue, it is almost always right.** Across
all 10 mice, accuracy-given-engagement sits at ~**85–100%** from the very first
session (the engaged hits/miss bars are nearly all green, with thin red slivers).
The light→reward association transferred immediately; understanding was never the
bottleneck. What grows across sessions is **engagement** — how many trials the
mouse bothers to poke on — and the group-mean hit rate rises accordingly
(~44% → ~67% by session 4).

The two highlighted learners illustrate the pattern (accuracy-when-engaged):

| | s1 | s2 | s3 | s4 |
|---|---|---|---|---|
| **m97** | 83% | 90% | 88% | 86% |
| **m102** | 86% | 94% | 100% | 93% |

- **m102 generalized most completely** (near-ceiling engagement and accuracy by session 3).
- Slowest *starters* were m92 and m101 (low session-1 engagement) but they climb steeply and reach the same high accuracy — so they generalized too, just engaged later.

## Reproduce
```bash
cd analysis
python3 generalization_analysis.py
```
Environment overrides: `ES_URL`, `ES_INDEX`, `MICS_PILOT`, `MICS_GEN_OUT`.

---

# Participation vs Competence (both tasks)

`participation.py` — a shared module producing five figures that separate
**participation** (does the mouse engage at all) from **competence** (does it
succeed once engaged). Used by both scripts; an "engaged" trial is one with a
nose poke while the cue is on (tone for the appetitive task, LED2 for
generalization). Output prefix is `appetitive_` or `generalization_`.

Each figure title is stamped with its number `[1]`–`[5]` (matching this list and
the original discussion), and the number is in the filename too.

| Figure | Shows |
|---|---|
| `*_1_engagement_curve.png` | engagement rate (% trials with on-cue poke) across sessions, per mouse + group mean — the participation trajectory |
| `*_2_participation_vs_competence.png` | the dissociation in one axes: group-mean competence (accuracy-when-engaged) vs participation (engagement rate) across sessions, ±SEM, faint per-mouse lines. Competence flat-high from session 1; participation climbs toward it → the across-session gain is participation, not competence ("slow to participate, not to learn") |
| `*_2b_participation_vs_competence_by_mouse.png` | same dissociation, each mouse in its own color across two panels (participation \| competence): participation lines fan upward & vary, competence lines cluster flat-high |
| `*_3_within_session_ramp.png` | group-level warm-up: mean engagement in successive 10-trial blocks within a session (full blocks only, to trial 60), one line per session — rising left→right = within-session warm-up; later-session lines higher = ramp strengthens across sessions |
| `*_3b_within_session_ramp_by_mouse.png` | same binned warm-up, per-mouse grid, one distinct color per session |
| `*_5_sessions_to_criterion.png` | bar per mouse: first session reaching 50% engagement (red = never) — a single "speed of participation" number |

Run via either script's `--analysis participation` (appetitive) or as part of a
full `generalization_analysis.py` run.

---

# Behavioral patterns across mice & tasks

`behavior_patterns.py` — four exploratory, cross-cutting analyses (output under
`behavior_figs/`). Reuses the generalization + appetitive data loaders.

> The same four behavioral analyses run for the **appetitive (tone)** task — and
> the within-task figures from this script — are collected under
> [`behavior_in_appetitive_task/`](behavior_in_appetitive_task/README.md)
> (`--task appetitive`). The cross-task transfer figures below are not duplicated
> there since they describe both tasks at once.

| Figure | Shows |
|---|---|
| `phenotypes.png` | two engagement phenotypes: x = reward-dependence of engagement (P(engage\|prev hit) − P(engage\|prev miss)), y = longest run of consecutive disengaged trials. **m92 & m101** sit top-right (reward-gated / bursty); the rest cluster bottom-left (steady) |
| `impulsivity.png` | off-cue nose pokes per trial (poking with no cue / no reward available), ranked. **m102** is a strong outlier (~8/trial vs median ~3) — most impulsive |
| `licking_dynamics.png` | left: anticipatory licking is ~absent (poke-gated task — licking follows the poke); right: poke→reward-lick latency, the licking signal that exists (bursty m92/m101 are slowest to collect; steady m102/m103 fastest) |
| `cross_task_transfer.png` | appetitive (tone) vs generalization (light) per mouse: participation transfers moderately (r≈0.5 — engagement is a stable trait); competence does **not** (r≈0.1 — generalization accuracy is ceilinged because the rule is already known) |
| `hits_first_vs_generalization.png` | dot plot, one point per mouse: **total hits on the first association task (appetitive, tone)** vs **total hits on the generalization (light) task**. Tests whether the mice that earn the most rewards while first learning the association also earn the most once the cue generalizes. Positive (r≈0.77): high-hit learners (m102, m100, m90) stay high; low-hit mice (m92, m101, m98) stay low. *Caveat:* total hits is a raw count, so it reflects both performance and how many sessions a mouse ran (appetitive uses all sessions; generalization is capped at the first 4) — see the per-session version, which removes that confound. |
| `hits_per_session_first_vs_generalization.png` | same dot plot, but **hits per session** (total hits ÷ kept-session count) on both axes, removing the session-count confound. The relationship weakens to r≈0.54 — still positive, but the standout is **m97**, which earns the most appetitive hits/session (~25) yet only middling generalization hits/session (~30): a fast first-task learner whose per-session reward rate doesn't carry over as strongly. m102 stays top-right on both metrics. |
| `hits_per_engaged_first_vs_generalization.png` | the **third normalization — hits per *engaged* trial** (total hits ÷ total engaged trials = pooled accuracy-when-engaged), i.e. **success fully decoupled from engagement / participation = competence**. The cross-task correlation **collapses to r≈0.09**. Completing the trilogy `total hits (0.77) → per session (0.54) → per engaged trial (0.09)` shows the raw-hits correlation was carried by *participation* (a stable trait), not competence: appetitive competence ranges widely (45–94%) but generalization competence is ceilinged (86–94% for every mouse — the rule is already known), so success-given-engagement in the first task cannot predict it in the second. This is the same conclusion as the `cross_task_transfer.png` competence panel, viewed through the hits lens. |
| `scorecard_generalization.png` | integrated per-mouse scorecard (generalization task) — a heatmap with one row per mouse and one column per metric (engagement %, accuracy when engaged, hits/session, impulsivity = off-cue pokes/trial, reward-collection latency). Color = z-score within each column (red high / blue low); cell text = raw value. Single-glance "who's who": **m102** is red across engagement, accuracy, hits/session *and* impulsivity (best performer + most impulsive, fast collector); **m92** is the coldest row (lowest engagement, slowest to collect reward). |

**Who engaged / tried most during the cue.** "Trying during the cue" is the
**engagement rate** — how often a mouse pokes while the cue (LED/tone) is on. It
is *not* pokes-per-cue: the cue is cut short the instant the rewarded poke lands,
so on-cue pokes per engaged trial are pinned at ≈1 for every mouse and don't
discriminate (this is itself a finding — there's no "hammering" behavior). By
engagement, the generalization order is **m102 (86%) > m100 (77%) > m90 (71%)**
… down to **m101 (48%) > m92 (44%)**; on the appetitive task it is **m97 (44%) >
m102 (38%) > m100 (35%)** … down to **m92 (17%) > m98 (11%)**. m97 leads the
*first* task's engagement but drops to mid-pack on generalization — the same
"doesn't carry over" signal seen in the hits/session plot.

**Headline patterns.** Two phenotypes fall out of trial-to-trial structure:
*reward-gated/bursty* mice (m92, m101) disengage for 20+ trials at a time and
re-engage mainly after reward, and are also the slowest to collect reward; the
other eight are *steady* participators. Impulsivity (off-cue poking) is a
separate axis — m102 is both the best performer and the most impulsive.
Engagement (participation) is a stable individual trait across tasks; competence
is not, because by generalization every mouse already knows the rule.

**What they show.** In the **generalization** task, accuracy-when-engaged is
tightly clustered high (~90%) while engagement spreads wide — participation, not
competence, is what develops. In the **appetitive** task the same axes show
accuracy-when-engaged genuinely scattered (mean ~71%): there the mice are still
*learning the association*, so competence is itself developing. The contrast
across the two `*_participation_vs_competence.png` plots is the clearest single
summary of "already knows the rule" (generalization) vs "still learning it"
(appetitive).

---

# Action-sequence analysis — where the behavioral chain breaks

`action_sequence_analysis.py` — decomposes every trial into the behavioral chain
so a low hit rate can be attributed to a *specific* failed link rather than
treated as one number:

```
cue presented → on-cue poke → lick after poke → reward → (off-cue noise)
```

Loads the appetitive (tone) and generalization (light) tasks, reusing the
existing ES access / subject discovery / session ordering (`appetitive_analysis`,
`generalization_analysis`, `config`). Trials are re-segmented locally only to
capture the absolute cue-onset time and reward time that the existing lean trial
objects drop — the segmentation *logic and event semantics are identical*.

```bash
python3 action_sequence_analysis.py                  # both tasks, all mice
python3 action_sequence_analysis.py --task appetitive
python3 action_sequence_analysis.py --task generalization
python3 action_sequence_analysis.py --mouse m102
```

## Trial categories (mutually exclusive — used for the stacked bars + transitions)
| Category | Meaning |
|---|---|
| `no_response` | cue occurred, no poke during the cue window |
| `cue_poke_no_lick` | on-cue poke, but no lick afterwards |
| `cue_poke_lick_no_reward` | on-cue poke + lick, but no reward |
| `complete_sequence_rewarded` | on-cue poke + lick + reward |
| `offcue_poke_only` | no on-cue poke, but poke(s) outside the cue window |

**Why no exclusive `mixed_offcue_and_oncue` slice (important limitation).**
Off-cue / ITI poking is near-universal here — `percent_mixed_offcue_and_oncue`
reaches **88%** in some sessions. Making "mixed" a sixth *exclusive* stack slice
("any off-cue poke anywhere in the trial") would cannibalise the chain categories
and make every figure unreadable. So the five chain categories are kept exclusive
(they sum to exactly 100% — verified on all 156 sessions), and `mixed` is reported
as a **separate, overlapping diagnostic** (its own summary column + the
`P(off-cue poke | trial)` line in the group trajectory). A trial is "on-cue" only
if the nose poke fell while the cue was active; the cue is cut short at reward on
hits, so the full ~8 s default applies to misses.

## Outputs (under `action_sequence_figs/`)
- `action_sequence_trials.csv` — one row per trial (cue/poke/lick/reward times,
  on/off-cue poke counts, off-cue lick count, category, the three chain latencies,
  and the previous trial's category/rewarded/engaged for history analysis).
- `action_sequence_session_summary.csv` — one row per (task, mouse, session):
  the six category percentages, the conditional chain rates
  (`engagement_rate`, `lick_given_oncue_poke_rate`, `reward_given_oncue_poke_rate`,
  `reward_given_poke_and_lick_rate`) and the three median latencies.
- `action_sequence_stacked_by_mouse.png` — **Fig 1**: stacked category bars,
  one panel per mouse, appetitive block over generalization block. Shows where
  in the chain each mouse fails.
- `action_sequence_group_trajectory.png` — **Fig 2**: group mean ± SEM across
  sessions of `P(on-cue poke | cue)`, `P(lick | poke)`, `P(reward | poke)`,
  `P(reward | poke+lick)`, `P(off-cue poke | trial)`, per task.
- `action_chain_by_mouse.png` — **Fig 3**: per-mouse **dynamics across sessions**
  (one panel per mouse, axes shared across mice). **Left axis (% of trials):**
  `on-cue poke` and `on-cue poke + lick afterwards` — the gap between the two is
  the on-cue pokes *not* followed by a lick. **Right axis (events per trial):**
  `off-cue pokes/trial` and `off-cue licks/trial`. Line style/marker distinguishes
  task when more than one is loaded. *Caveat:* off-cue licks are defined
  symmetrically with off-cue pokes (any lick outside the cue window) and therefore
  **include reward-consumption licking** during the post-cue / ITI period — that
  red line tracks reward earned rather than pure impulsivity.
  (Earlier this figure was a cumulative cue→poke→lick→reward funnel averaged over
  each mouse's last sessions; it now shows the per-session dynamics above.)
- `action_sequence_latencies.png` — **Fig 4**: per-session median latency
  (group mean ± SEM) for cue→poke, poke→lick, lick→reward, one line per task.
- `action_sequence_trial_history.png` — **Fig 5**: reward-gating as a **dumbbell
  plot** — per mouse, `P(engage)` (and `P(off-cue poke)`) on trial *t* after a
  rewarded (green) vs non-rewarded (red) trial; the connector length is the
  gating strength (Δ, annotated), and mice are sorted by the engagement gap so
  reward-gated mice rise to the top.
- `action_sequence_transition_matrix.png` — trial-to-trial transitions collapsed
  onto a **3-level engagement ladder** (`complete → engaged-but-no-reward →
  disengaged`), row-normalized, one heatmap per task; the boxed diagonal is each
  state's persistence. Reads directly as stuck / holds-success / recovers.
- `action_sequence_summary.txt` — plain-text answers to the seven interpretation
  questions (most-reliable sequence, poke-without-lick, engagement failures,
  off-cue poking, reward-gating, task contrast, participation-vs-accuracy).

## Key findings (committed run, 156 sessions / 9,552 trials)
- **The appetitive bottleneck is engagement, not the downstream chain.** Group
  `P(on-cue poke | cue)` sits at ~25% and is roughly flat across sessions, while
  every downstream link (`P(lick | poke)`, `P(reward | poke)`) is high — so the
  grey "no response" + blue "off-cue only" bands dominate Fig 1's appetitive
  block. Mice mostly fail by *not engaging the cue*, not by botching the action.
- **Generalization improves through participation.** Engagement climbs
  ~50% → 75% (s1→s4) while accuracy-when-engaged is near-ceiling from session 1
  (~87% → 91%). The green "complete sequence" band grows session over session;
  the chain links were never the problem.
- **Task contrast:** complete-sequence rate 19% (appetitive) → 58%
  (generalization); engagement 25% → 64%; accuracy-when-engaged 71% → 89%.
- **Reward-gated mice fall straight out of Fig 5:** **m92** engages 62% after a
  rewarded trial vs 31% after an unrewarded one (a +33 pp gap) in generalization,
  with **m101** (+21) next — the bursty/reward-gated phenotype seen in
  `behavior_patterns.py`, now localized to the engagement link.
- **The transition ladder shows where mice get stuck vs hold success.** In
  appetitive, the disengaged state is sticky (disengaged→disengaged 78%) and even
  a complete trial usually drops back to disengaged (complete→disengaged 62%). In
  generalization that flips: success persists (complete→complete 66%) and the
  disengaged state readily recovers into a complete sequence (disengaged→complete
  44%) — engagement, once triggered, sustains itself.
- **m102** is the most complete sequencer (81% complete in generalization) and
  also the most off-cue (≈8 pokes/trial) — high performer *and* most impulsive,
  consistent with the scorecard.

---

# Formal learner-criterion analysis — learned, or just didn't participate?

`learner_criterion_analysis.py` — classifies every mouse on whether it **learned**
the task, **generalized**, or mainly failed from **low participation** — and never
on hit rate alone. A low hit rate is ambiguous: a mouse can fail because it does
not understand the task (low *competence*) or because it rarely engages the cue
(low *participation*). This script separates the two.

Reuses the existing loaders (`appetitive_analysis`, `generalization_analysis`,
`config`) — same ES setup/env vars, no new client. Generalization session
ordering comes from `generalization_analysis.collect_mouse`.

```bash
python3 learner_criterion_analysis.py                  # both tasks, all mice
python3 learner_criterion_analysis.py --task appetitive
python3 learner_criterion_analysis.py --task generalization
python3 learner_criterion_analysis.py --mouse m102
```

## The four orthogonal axes (one consistent definition for both tasks)
| metric | meaning |
|---|---|
| `engagement_rate` | engaged trials / all trials — **participation** (engaged = on-cue poke) |
| `accuracy_when_engaged` | rewarded / engaged — **competence** (success once engaged) |
| `hit_rate` | rewarded / all trials — the **ambiguous** number |
| `offcue_pokes_per_trial` | pokes outside the cue window / trial — **impulsivity** |

## Three rule sets (computed and compared per mouse)
- **A — hit-rate only:** ≥50% hit rate for ≥2 consecutive sessions (traditional, insensitive).
- **B — engagement + competence:** ≥50% engagement AND ≥70% accuracy for ≥2 consecutive sessions.
- **C — late-session:** the same thresholds on the mean of the last 3 sessions.
A robust cohort rule flags **impulsive / off-cue-dominated** mice (late off-cue
pokes/trial above the cohort median + 1 MAD). Thresholds are constants at the top
of the script.

## Final categories (one per mouse)
`strong_learner` · `partial_learner` · `competent_low_participation` ·
`non_learner` · `impulsive_offcue_dominated`. A confidence flag
(`low_confidence_competence`) marks mice whose accuracy rests on < 15 engaged
trials in the late window.

### The "strong-participation bar" is TASK-RELATIVE (and why)
A single absolute engagement threshold cannot serve both tasks, because the
engagement *regimes* differ: the tone is hard to engage (cohort median ≈ 25%), the
light is easy (median ≈ 66%). With an absolute 50% bar, **every** generalization
mouse clears it and is labelled a strong learner — hiding the real variation,
which in generalization is participation *degree* (competence is uniformly high).
So the strong bar = `max(50%, the task cohort's median late engagement)`. This
leaves the appetitive result unchanged (floor binds at 50%, so m97 stays the lone
strong learner) while splitting the light cohort into high vs moderate
participators. Lowering thresholds would make the problem *worse*, not better.

## Outputs (under `learner_criterion_figs/`)
- `session_learning_metrics.csv` — per (task, mouse, session): trials, engaged,
  rewarded, the four axes, and the two median latencies.
- `mouse_learning_classification.csv` — per (task, mouse): max/late metrics,
  first-session-to-threshold, all rule booleans, the task-relative bar, the
  confidence flag, the final class, and a human-readable `classification_reason`.
- `learner_classification_summary.png` — **Fig 1**: each category is a row; member
  mice are labelled chips. Read a row to see exactly who is in each category.
- `engagement_vs_competence_map.png` — **Fig 2** (the core map): x = late
  engagement (participation), y = late accuracy-when-engaged (competence), with the
  50% / 70% threshold lines. Top-left = knows rule but under-participates; top-right
  = strong learners; bottom = non-learners.
- `hit_rate_vs_competence.png` — **Fig 3**: x = late hit rate, y = competence,
  point size ∝ engagement — shows two mice with the same low hit rate splitting
  into competent (small, high) vs genuinely poor (low).
- `hit_rate_decomposition.png` — **the clearest "hit rate misleads" figure**: since
  `hit_rate = engagement_rate × accuracy_when_engaged`, each mouse's faded bar is
  its competence ceiling (accuracy when engaged) and the solid bar is the actual
  hit rate; the gap is reward lost to under-participation (engagement % annotated).
  A tall faded bar over a tiny solid bar (e.g. appetitive **m93** — 88% ceiling,
  13% hit, 15% engagement) = a participation problem; a low faded bar (e.g. **m101**
  — 56% ceiling) = a genuine competence problem. Bars colored by final class.
- `learning_trajectory_by_classification.png` — **Fig 4**: session trajectories of
  hit rate / engagement / accuracy, colored by final class, per task.
- `offcue_behavior_by_classification.png` — **Fig 5**: late off-cue pokes/trial per
  mouse with the cohort impulsivity threshold — who is impulsive vs a true non-learner.
- `learner_classification_heatmap.png` — mouse × metric heatmap (z-score color, raw
  values shown).
- `learner_criterion_summary.txt` — plain-text answers to the 8 questions.

## What we discovered
**Appetitive (tone) — failure is mostly a PARTICIPATION problem, not competence.**
- **m97** is the only strong learner (engages ~53% — far above the ~25% cohort —
  and 97% accurate when engaged).
- **m93** is *competent but low-participation*: 88% accurate when engaged, but
  engages only 15% — its low hit rate is purely participation-limited.
- **m101** is the one true non-learner (accuracy when engaged < 60%).
- **m102** is *impulsive / off-cue-dominated*: it engages a lot (42%) but is only
  51% accurate and pokes off-cue ~4×/trial — the off-cue behavior, not a learning
  failure, explains its low hit rate.
- The remaining six are *partial learners* (know the rule reasonably but engage
  inconsistently). Net: most "low hit rate" in appetitive is under-engagement.

**Generalization (light) — everyone learned the rule; they differ only in participation.**
- **All 10 mice generalized**: accuracy-when-engaged is 84–96% for every mouse and
  flat-high from session 1. Competence is uniform — the rule transferred immediately.
- What varies is *participation*: high participators (**m90, m98, m100, m102, m103**)
  vs moderate participators who learned the rule but engage less / ramp up slower
  (**m92, m93, m97, m101, m104**). m92 and m101 are the known laggards; **m97** —
  the appetitive star — only participates moderately here, the same "participation
  doesn't carry over" signal seen in the hits-per-session analysis.

**Why hit rate alone misleads (the headline).** The traditional hit-rate rule
fails to credit clearly competent mice: **m97** (97% accurate when engaged in
appetitive, 88% in generalization) and **m93** (88% accurate) never satisfy
"≥50% hit rate for 2 consecutive sessions," because they don't engage *often*
enough — even though they plainly know the task. Judging on engagement + competence
recovers them.

---

# Trial-history analysis — learning vs. control by recent reward

`trial_history_analysis.py` — tests whether a mouse's current-trial behavior
depends on what happened on the previous trial(s), separating mice whose
engagement is **self-sustaining** (steady) from those whose engagement must be
**re-triggered by reward** (reward-gated / bursty, e.g. m92, m101).

Reuses the existing loaders (`appetitive_analysis`, `generalization_analysis`,
`config`); builds an enriched per-trial table with history fields computed
**strictly within each mouse × task × session** (the last trial of one session
never becomes the previous trial of the next).

```bash
python3 trial_history_analysis.py                  # both tasks, all mice
python3 trial_history_analysis.py --task generalization
python3 trial_history_analysis.py --mouse m102
```

## Method
- **Descriptive (primary, numpy only):** conditional probabilities with **seeded
  bootstrap CIs** — `P(engage | prev rewarded)` vs `P(engage | prev not)`, the
  same for off-cue poking and for accuracy-once-engaged.
- **Models:** statsmodels/pandas are not installed and the project is kept
  dependency-light, so the three logistic regressions (engagement, accuracy-when-
  engaged, off-cue poking) use a **ridge-regularized IRLS logistic regression
  implemented in numpy**, with mouse dummies as fixed effects, reporting odds
  ratios + 95% CIs. Any model that can't be fit is skipped with a note.
- **Reward-gated score** = `Δengage(after reward − after no-reward) + 0.5·Δoff-cue`.
  `state_persistence_score` = `Δengage(after engaged − after not-engaged)`.

## Outputs (under `trial_history_figs/`)
- `trial_history_trials.csv` — one row per trial: outcomes, previous / 2-back /
  rolling prev-3 & prev-5 rates, latencies, trial-in-session fraction.
- `mouse_trial_history_summary.csv` — per (task, mouse): all conditional
  probabilities, the deltas, the two scores, and `final_interpretation`.
- `trial_history_prev_reward_engagement.png` — **Fig 1**: `P(engage | prev rewarded)`
  vs `| prev not`, per mouse, sorted by the gap — the reward-gating headline.
- `trial_history_engagement_persistence.png` — **Fig 2**: `P(engage | prev engaged)`
  vs `| prev not engaged` — is behavior state-like?
- `trial_history_offcue_after_outcome.png` — **Fig 3**: off-cue poking after
  reward vs after no-reward.
- `trial_history_reward_gated_ranking.png` — **Fig 4**: reward-gated score ranked,
  with bootstrap CIs; mice above threshold highlighted.
- `trial_history_model_coefficients.png` — **Fig 5**: odds-ratio forest plot for
  the three logistic models, one marker per task.
- `trial_history_example_mice.png` — **Fig 6**: concatenated trial timelines for
  m92/m101/m102/m97 (reward / miss / off-cue rasters) — bursty vs steady at a glance.
- `trial_history_summary.txt` — plain-text answers to the 9 questions.

## What we discovered
- **Reward gates *whether* a mouse engages, not *whether it succeeds once engaged*.**
  Group engagement is ~+10pp (appetitive) / +13pp (generalization) higher after a
  rewarded trial, while accuracy-once-engaged barely moves with history — competence
  is stable once the mouse chooses to participate. The logistic models agree (the
  accuracy model's odds ratios sit near 1; the engagement model's `prev-3 reward
  rate` and `session` sit above 1).
- **m92 and m101 are the reward-gated / bursty mice** (generalization Δengage
  **+33pp** and **+21pp**), and they are *also* the most persistent/state-like —
  they sit in a disengaged mode for long runs and re-engage mainly after reward.
  **m97, m100, m102, m103** are steady participators (small reward-gating gap).
  The example-mice timelines show it directly: m92/m101 have sparse, clustered
  rewards early that fill in later; m102 is dense and uniform from the start.
- **This is the dynamic layer hit rate and engagement rate hide.** Two mice with
  the same average engagement can differ sharply in *how* that engagement is
  produced — self-sustained vs reward-triggered — which is exactly the
  reward-gated phenotype flagged in `behavior_patterns.py`, now quantified.

---

# On/off-cue, ITI punishment & cross-task transfer (2026-07-02)

Three analyses added this session: `on_off_cue_analysis.py`,
`punishment_analysis.py`, and `cross_task_transition_analysis.py`. All reuse the
existing loaders/segmentation, so the trial set matches every other analysis. Two
data facts were verified against the raw ES stream and now anchor these analyses:
the nose-poke sensor logs both entry (`IR1` level 1) **and exit** (level 0), and
the FSM logs each ITI false-alarm as a `state_ITI_nose_poke` transition.

## On-cue vs off-cue behaviour, lick density, ITI timing (`on_off_cue`)
- **Only a minority of all pokes+licks are on-cue** — ~17% (tone), ~8% (light);
  most activity is off-cue (consummatory drinking + ITI activity).
- **Licking is a clean reward signal.** Licks in the 1 s after a reward are
  **~2–3× denser** than after an off-cue poke, for every mouse in both tasks; the
  PSTH shows a sharp consummatory burst locked to reward.
- **ITI defined from *disengagement*, not cue offset.** The true off-cue period
  starts only once the mouse has ended its consummatory lick bout *and* withdrawn
  its nose. There is a **fixed ~10 s response lockout** before each next trial
  (no pokes/licks ever occur in it) — this is the task's `min_punish_time`.
- **Within the ITI, activity is front-loaded but ramps up again before the next
  trial** (length-invariant view): pokes are most probable right at disengagement,
  and both pokes and licks rise in the final ITI bin — a mild anticipatory lean
  toward the next trial (stronger in generalization).

## ITI punishment / false alarms (`punishment`)
- The ITI is 30 ± 5 s; poking during it is a **false alarm** that resets the timer
  (+≥10 s). A trial is *punished* if it contains ≥1 `state_ITI_nose_poke`.
- **Punishment is the norm and mouse-specific.** Tone: group mean **57.7%** of
  trials punished (m98 cleanest at 35.5%, m97 worst at 79%). Light: higher across
  the board, **73.4%** (65–81%) — mice were more impulsive under the light cue.
- **Within a session:** punishment is *lowest on the first trial*, ramps up over
  the first ~5 trials (warm-up impatience), then stays high in the tone task but
  **gradually declines through the light task** as the mouse settles. (The final
  1–2 trials dip is an edge artifact — the last ITI is truncated when the session
  ends.) The per-mouse view confirms light > tone for nearly every animal.

## Cross-task transfer: tone → light (`appetitive_to_generalization`)
- **8/10 mice changed learner phenotype** from their last tone session to their
  first light session, almost all moving **up-and-right** (more engagement, high
  accuracy) — e.g. m104 non-learner→strong, m100/m102 impulsive→strong. Caveat:
  the last tone session is over-trained/low-engagement, so part of this shift is
  novelty re-engagement, not only rule transfer.
- **Most mice cracked the light rule fast.** First-session CUSUM onsets: immediate
  transfer (m90 trial 6, m103 trial 5), mid-session steps (m97/m100/m101/m102/m93),
  and two with no step — m98 was already engaged from trial 1 (full transfer),
  m92 never engaged the light. So the tone→light rule generally transferred; the
  main individual difference is *how quickly* and *whether* the mouse re-engaged.
