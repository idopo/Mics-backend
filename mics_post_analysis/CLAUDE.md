# MICS Offline Analysis Toolkit

Clean-slate Python package (`mics/`) + one generic Jupyter notebook that assembles MICS behavioral data offline: Elasticsearch events (always) + Open Ephys signals + sorted spikes (optional, when a recording exists), unified onto one clock. Replaces ~20 copy-pasted legacy notebooks.

## Planning

This sub-project has its OWN dedicated GSD planning under `.planning/` here — **separate from the backend's root `.planning/`**. Native `/gsd:*` commands are pinned to the backend root, so GSD here is hand-driven (write plans/state directly). Start: `.planning/ROADMAP.md`, `.planning/STATE.md`.

## Layout

```
src/mics/      # the package (ElasticClient, EphysRecording, SessionAligner, SpikeTable, config resolver)
notebooks/     # the single generic analysis notebook + nbformat build script
tests/         # pytest
.planning/     # dedicated GSD docs for this sub-project
```

## Legacy reference (study, DO NOT reuse code)

`~/mics_post_analysis/` (noale17 `thesis_ready`). Captures intent: `ElasticSearchClient.py`/`...V2.py` (two near-duplicate clients — the patchiness to eliminate), `OpenEphysProcessor.py`, `SpikeExlProcessor.py`, `SessionAligner.py`, `DLCProcessor.py`.

## Data environment (reachable from this host)

- **Sessions (SMB):** `/mnt/mics-smb/yizharlab/Ido/Mics/sessions/`
- **Naming:** ephys folder `<subject>s<n>_<YYYY-MM-DD>_<HH-MM-SS>`; loose spikes `spikes_<subject>s<n>.pkl`; inline spikes `processed.xls`. Open Ephys at `<folder>/Record Node <id>/experiment1/recording1` + `processed.dat`.
- **Elasticsearch:** primary `http://132.77.73.217:9200` (`event_log`, `event_log_v2`); secondary `http://132.77.73.125:9200` (`restored-event_log_v2`). Host/index per session.
- **ES subjects are descriptive strings** (`m74_cue_reward`, `m74_appetitive`, …) — NOT the short key. Each session entry needs explicit `es_subject`.
- **Schema:** legacy docs = `subject`+`session`, no `run_id`; new-portal adds `run_id`/`subjects`. Read both via one path.

## Fixture — m74s4 (legacy session)

ES `217/event_log_v2` `m74_cue_reward` s4 → 2137 events. Ephys `m74s4_2025-07-09_16-21-05/Record Node 110`. Spikes `spikes_m74s4.pkl`. Alignment anchor: ES `TRIGGERS` ↔ ephys trigger-channel rising edges. Second fixture `m74s1` uses inline `processed.xls`.

## Principles

- ES events are the always-present base; ephys + spikes are optional layers that import lazily and degrade gracefully when absent.
- Each notebook section runs standalone; earlier sections work even if later layers/data are missing.
- Cache intermediates per session key (like legacy pickles).
