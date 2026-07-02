# Analysis results

Behavioral analyses of 10 mice (`m90, m92, m93, m97, m98, m100, m101, m102,
m103, m104`) on the `RecordingBox` pilot, across two tasks:

- **appetitive tone** (`AppetitveTaskReal`) — tone-cued nose-poke-for-reward
- **generalization light** (`Generalization`) — same rule, LED cue

Source: Elasticsearch index `restored-event_log_v2`. Sessions with too few
trials are dropped by each script's filter.

## Layout: analysis type → task

Results are organized **by analysis module first, then by task**, so a single
module's output for all tasks sits side by side (the headline questions here are
cross-task, e.g. "does engagement transfer from tone to light?"):

```
results/<analysis_type>/<task>/
```

where `<task>` is `appetitive`, `generalization`, or `cross_task` (the `--task
both` comparison). `overview/` has only `appetitive` and `generalization`;
`cross_task_transition/` is cross-task by nature and keeps its
`appetitive_to_generalization/` subfolder.

## The modules

| Module | Script | Question it answers |
|---|---|---|
| `overview/` | `appetitive_analysis.py`, `generalization_analysis.py` | Did they learn? Rasters, hit-rate + lick-hit-rate learning curves, poke breakdown |
| `learner_criterion/` | `learner_criterion_analysis.py` | Who is a learner? Formal classification — participation vs competence, never hit rate alone |
| `learning_trajectories/` | `learning_trajectories_analysis.py` | How does the phenotype move over sessions? Per-metric trajectories, radar, cue→first-poke latency |
| `action_sequence/` | `action_sequence_analysis.py` | Where in cue→poke→lick→reward does behaviour break? Chain decomposition, funnel, transition matrix |
| `trial_history/` | `trial_history_analysis.py` | Does behaviour depend on the recent past? Reward-gating / persistence / off-cue, logistic models |
| `on_off_cue/` | `on_off_cue_analysis.py` | On-cue vs off-cue licking, lick-density PSTH, ITI timing |
| `punishment/` | `punishment_analysis.py` | How often do they burn the ITI by poking early? False alarms |
| `engagement_bouts/` | `engagement_bouts_analysis.py` | Runs of consecutive engaged trials — summary + raster (+ per-mouse rasters) |
| `trial_engagement_licks/` | `trial_engagement_licks_analysis.py` | Lick-level SDT: hits/FA, catch trials, lick hit rate *(exploratory)* |
| `cross_task_transition/` | `cross_task_transition_analysis.py` | How did tone learning carry to the light rule? Phenotype shift + first-light learning onset |

See `../FINDINGS.md` for the synthesis and `../ANALYSIS_INVENTORY.md` for the
per-module keep/trim rationale.

## Regenerating

Each script takes a `--task {appetitive,generalization,both}` switch and writes
to `results/<module>/<task>/` by default (override with the module's `MICS_*_OUT`
env var):

```bash
cd analysis
export ES_URL=http://132.77.73.125:9200   # the lab ES host

python3 appetitive_analysis.py            --task appetitive   # -> overview/appetitive/
python3 generalization_analysis.py                            # -> overview/generalization/
python3 learner_criterion_analysis.py     --task both         # -> learner_criterion/{appetitive,generalization,cross_task}/
python3 learning_trajectories_analysis.py --task both
python3 cross_task_transition_analysis.py                     # -> cross_task_transition/appetitive_to_generalization/
# ...one per module; `--task both` also emits the cross_task/ comparison.
```
