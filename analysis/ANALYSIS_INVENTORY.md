# Analysis inventory — what we have, what's useful, what's redundant

10 mice (`m90 m92 m93 m97 m98 m100 m101 m102 m103 m104`), two tasks:
**appetitive tone** (`AppetitveTaskReal`) and **generalization light** (`Generalization`).
Every module writes into `results/{appetitive,generalization,cross_task}/<module>/`.
There are ~14 analysis modules and **~200 figures across the 3 areas** — this file
orders them from basic → complex, rates each, and lists what to cut.

Verdicts: **CORE** (foundational, unique) · **KEEP** (useful, distinct angle) ·
**TRIM** (useful but over-produces figures) · **RETIRE** (superseded / redundant) ·
**EXPLORATORY** (recent probe, decide).

---

## Tier 1 — Foundational (the base everything else reuses)

| Module | Script | What it gives | Verdict |
|---|---|---|---|
| **overview** | `appetitive_analysis.py`, `generalization_analysis.py` | per-session rasters, **learning curves** (trial hit rate + new lick hit rate), poke bar-grids, `session_metrics.csv` | **CORE** — but TRIM the poke bars |
| **participation** | `participation.py` (shared module) | participation-vs-competence figures reused by both task scripts | **CORE** (library) |

- The trial segmentation here (pokes / licks / rewards / ITI boundary / hit) is the
  single source of truth every other module imports. Keep.
- **Trim:** the poke bar-grids are 5 figures (`total`, `during_tone`,
  `lick_vs_nolick`, `breakdown`, `ontone_reward_ratio`). The **breakdown** stacked
  bar subsumes most of them — keep breakdown (+ maybe during_tone), drop the other 3.
- **Trim:** generalization `overview` has 11 figures; the `*_by_mouse` variants
  (participation_2b, within_session_ramp_3b) duplicate their group versions.

## Tier 2 — Behavioural characterisation (mid complexity)

| Module | What it gives | Verdict |
|---|---|---|
| **action_sequence** | per-trial decomposition of the chain cue→poke→lick→reward (stacked bars, chain dynamics, latencies, transition matrix) | **KEEP** — unique lens, no overlap |
| **trial_history** | does current-trial behaviour depend on recent history? reward-gating / persistence / off-cue, logistic models | **KEEP** — unique (the dynamic layer) |
| **behavior_patterns** | phenotypes, impulsivity, licking, transfer (4 figs, no CSV, nothing in cross_task) | **RETIRE** — an early coarse pass; every part is now done deeper elsewhere (see below) |

- `behavior_patterns` was the first cut at phenotype/impulsivity/licking/transfer.
  Each of those is now covered in more depth: **phenotypes →** learner_criterion,
  **impulsivity →** punishment + on_off_cue, **licking →** on_off_cue +
  trial_engagement_licks, **transfer →** cross_task_transition. It produces no CSVs
  and nothing for cross_task. Safe to retire once you've confirmed nothing unique.

## Tier 3 — Learning & phenotype (the crowded middle)

| Module | Figs | Verdict |
|---|---|---|
| **learner_criterion** | 8 | **KEEP (canonical)** but TRIM map variants |
| **learning_trajectories** | 7 | **KEEP** but consolidate latency + phenotype compressors |
| **phenotype_transition** | 1 | **RETIRE** — subsumed |
| **engagement_bouts** | 7 (+10 per-mouse rasters) | **TRIM hard** (biggest over-production) |

- **learner_criterion** is the authoritative learner classification — keep the
  classification heatmap/summary and the main `engagement_vs_competence_map`. It
  ships **three** engagement/competence scatter variants
  (`engagement_vs_competence_map`, `..._last_session`, `hit_rate_vs_competence`) —
  keep one, drop the other two.
- **learning_trajectories** overlaps itself and overview: `phenotype_radar`,
  `learning_index_heatmap`, and `trajectories_by_metric` all compress the same
  per-session metrics — keep `trajectories_by_metric` (the richest) + one summary,
  drop the other. The **3 latency figures** (`cue_to_first_poke_latency_*`)
  duplicate overview's `latency_to_engage` and the latency line already inside
  `trajectories_by_metric` — keep **one** latency view total.
- **phenotype_transition** (within-task first→last, 1 figure) is covered by
  learner_criterion (trajectories) and cross_task_transition. Retire.
- **engagement_bouts** produces 7 group figures + a per-mouse raster each for one
  concept (runs of consecutive engaged trials). Keep `engagement_bouts_summary` +
  `engagement_bouts_raster`; the other five (`hit_matrix`, `hit_position`,
  `timing`, `length_by_mouse`, `by_session`) are secondary — drop or move to an
  appendix.

## Tier 4 — Fine-grained licking / timing (recent, deeper)

| Module | Figs | Verdict |
|---|---|---|
| **on_off_cue** | 8 | **KEEP** — deep & unique (on/off split, lick-density PSTH, ITI timing) |
| **punishment** | 6 | **KEEP** — unique & valuable (ITI false-alarm punishment + within-session) |
| **trial_engagement_licks** | 8 | **EXPLORATORY** — decide (overlaps on_off_cue + punishment) |

- **on_off_cue**: the ITI-timing trio (`iti_timing_map`, `iti_timing_curve`,
  `iti_begin_vs_end`) partly overlap — the normalized `iti_timing_curve` is the
  keeper; map is a nice per-mouse companion; `begin_vs_end` can go.
- **punishment**: lean and distinct; keep. The per-mouse by-trial curve and the
  session×trial map are the standouts.
- **trial_engagement_licks** (the lick-level SDT view: hits = reward-related licks,
  FA = ITI licks, catch trials, lick hit rate) overlaps on_off_cue (licking) and
  punishment (catch/FA). It's the only place the **hits/(hits+FA) "lick hit rate"**
  and **catch trials** live. Decide: promote it to KEEP as the lick-SDT summary, or
  fold catch-trials + lick-hit-rate into on_off_cue and retire the rest.

## Tier 5 — Cross-task (tone → light)

| Module | Figs | Verdict |
|---|---|---|
| **cross_task_transition** | 2 | **KEEP** — tone→light phenotype shift + first-light learning-onset raster |
| **transfer** (in behavior_patterns) | 4 | **REVIEW** — overlaps cross_task_transition; keep only unique transfer metrics |

---

## Recommended cuts (highest payoff first)

1. **RETIRE `phenotype_transition`** — 1 figure, fully subsumed. (−3 figs across areas)
2. **RETIRE `behavior_patterns`** after confirming nothing unique — superseded pass. (−8)
3. **TRIM `engagement_bouts` 7 → 2** group figures. (−15)
4. **One latency view, not four** — drop overview `latency_to_engage` *or* the 3
   `learning_trajectories/cue_to_first_poke_latency_*`; keep a single one. (−6 to −9)
5. **learner_criterion: keep 1 engagement×competence scatter**, drop 2 variants. (−6)
6. **overview poke bars 5 → 2** (keep `breakdown`, drop `total`/`lick_vs_nolick`/
   `ontone_reward_ratio`). (−9)
7. **Decide `trial_engagement_licks`** — promote as the lick-SDT summary or fold
   catch-trials + lick-hit-rate into on_off_cue and retire the rest.

Doing 1–6 removes ~45–50 redundant figures (~25%) with no loss of a distinct result.

## The keeper set (one line per unique question it answers)

- **overview** — did they learn? (hit rate, lick hit rate, rasters)
- **participation** — do they show up? (participation × competence)
- **learner_criterion** — who is a learner? (formal classification)
- **learning_trajectories** — how does the phenotype move over sessions?
- **action_sequence** — where in cue→poke→lick→reward does behaviour break?
- **trial_history** — does behaviour depend on the recent past? (reward-gating)
- **on_off_cue** — on-cue vs off-cue licking, lick density, ITI timing
- **punishment** — how often do they burn ITI by poking early? (false alarms)
- **cross_task_transition** — how did they carry tone learning to the light rule?
- **trial_engagement_licks** *(exploratory)* — lick-level hits/FA, catch trials
