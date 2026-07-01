# Behavior in the appetitive (tone) task

The same suite of behavioral analyses we ran for the **generalization (light)**
task, applied to the **appetitive tone task** (`AppetitveTaskReal`) for all 10
mice (`m90, m92, m93, m97, m98, m100, m101, m102, m103, m104`) on the
`RecordingBox` pilot. Source: Elasticsearch index `restored-event_log_v2`.

Coverage on this task: **116 sessions, 7150 trials** (sessions with < 10 trials
dropped).

## How these were produced

All four analysis scripts live one level up in `analysis/`. Each takes a
`--task` switch and an output-dir env var, so the appetitive outputs were
generated without forking any code:

```bash
cd analysis
export ES_URL=http://132.77.73.125:9200   # the lab ES host

MICS_ACTSEQ_OUT=behavior_in_appetitive_task/action_sequence \
    python3 action_sequence_analysis.py   --task appetitive
MICS_LEARNER_OUT=behavior_in_appetitive_task/learner_criterion \
    python3 learner_criterion_analysis.py --task appetitive
MICS_TRIALHIST_OUT=behavior_in_appetitive_task/trial_history \
    python3 trial_history_analysis.py     --task appetitive
MICS_BEH_OUT=behavior_in_appetitive_task/patterns \
    python3 behavior_patterns.py          --task appetitive
```

## Contents

| Subfolder | Script | What it answers |
|---|---|---|
| `action_sequence/` | `action_sequence_analysis.py` | Per-trial decomposition of the cue→poke→lick→reward chain — stacked bars, group trajectory, funnel, latencies, trial-history, transition matrix (6 figures, 2 CSVs, summary.txt) |
| `learner_criterion/` | `learner_criterion_analysis.py` | Formal learner classification — participation vs competence, never hit rate alone (7 figures, 2 CSVs, summary.txt) |
| `trial_history/` | `trial_history_analysis.py` | Does current-trial behavior depend on recent history? reward-gating / persistence / off-cue, with numpy logistic models (6 figures, 2 CSVs, summary.txt) |
| `patterns/` | `behavior_patterns.py` | Within-task behavior — engagement phenotypes, impulsivity (off-cue poking), licking dynamics, integrated per-mouse scorecard (4 figures) |

Cross-task transfer figures (appetitive↔generalization) are **not** duplicated
here — they live with the generalization outputs in `analysis/behavior_figs/`,
since they describe both tasks at once.

## Caveat specific to this task

The phenotype split in `patterns/phenotypes_appetitive.png` uses the same
absolute threshold as the generalization version (`BURSTY_RUN = 10`
consecutive disengaged trials → "bursty"). Appetitive sessions are much
**longer** than generalization sessions, so every mouse's longest disengaged
run exceeds 10 and all 10 land on the "bursty" side of that line. The threshold
was kept identical on purpose so the two tasks are directly comparable — read
the appetitive phenotype figure by the *position* of each mouse along the
win-stay (reward-dependence) and max-run axes, not by the binary bursty/steady
color, which saturates here. The reward-dependence ranking is still
informative: `m101 (+17pp)`, `m102 (+16pp)`, `m92 (+16pp)` are the most
reward-gated, `m103 (≈0pp)` the most outcome-independent.
