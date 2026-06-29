# AppetitiveTaskReal — Behavioral Analysis Summary

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

# Generalization Task — Did the Good Learners Generalize? (m97, m102)

`generalization_analysis.py` — does the learned tone-cued behavior transfer when
the cue becomes a **light**?

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
| `*_4_latency_to_engage.png` | grouped bars, x = mouse, one bar per session (color = session #). Left: trials until first engaged trial; right: median reaction time (cue→first on-cue poke) |
| `*_5_sessions_to_criterion.png` | bar per mouse: first session reaching 50% engagement (red = never) — a single "speed of participation" number |

Run via either script's `--analysis participation` (appetitive) or as part of a
full `generalization_analysis.py` run.

---

# Behavioral patterns across mice & tasks

`behavior_patterns.py` — four exploratory, cross-cutting analyses (output under
`behavior_figs/`). Reuses the generalization + appetitive data loaders.

| Figure | Shows |
|---|---|
| `phenotypes.png` | two engagement phenotypes: x = reward-dependence of engagement (P(engage\|prev hit) − P(engage\|prev miss)), y = longest run of consecutive disengaged trials. **m92 & m101** sit top-right (reward-gated / bursty); the rest cluster bottom-left (steady) |
| `impulsivity.png` | off-cue nose pokes per trial (poking with no cue / no reward available), ranked. **m102** is a strong outlier (~8/trial vs median ~3) — most impulsive |
| `licking_dynamics.png` | left: anticipatory licking is ~absent (poke-gated task — licking follows the poke); right: poke→reward-lick latency, the licking signal that exists (bursty m92/m101 are slowest to collect; steady m102/m103 fastest) |
| `cross_task_transfer.png` | appetitive (tone) vs generalization (light) per mouse: participation transfers moderately (r≈0.5 — engagement is a stable trait); competence does **not** (r≈0.1 — generalization accuracy is ceilinged because the rule is already known) |

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
