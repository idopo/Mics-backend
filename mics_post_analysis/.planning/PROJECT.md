# MICS Offline Analysis Toolkit

## What This Is

A clean-slate Python package (`mics/`) plus one generic Jupyter notebook for assembling MICS behavioral experiment data offline. You add a session to a `SESSIONS` config block and the toolkit resolves it by naming convention, then unifies three data sources onto one timeline: Elasticsearch behavioral events, Open Ephys electrophysiology signals, and sorted spikes. It replaces ~20 copy-pasted, data-specific legacy notebooks with one documented, reusable pipeline. For the Yizhar lab (appetitive-learning / mPFC ephys research).

## Core Value

One unified, clock-aligned events+spikes DataFrame per session — where the Elasticsearch events layer always works on its own, and ephys/spike alignment layers attach automatically only when an ephys recording exists for that session.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Convention-derived session resolver driven by a minimal `SESSIONS` config block
- [ ] Unified `ElasticClient` returning a tidy events DataFrame (legacy + new-portal schemas)
- [ ] Optional Open Ephys layer: TTL/trigger rising-edge extraction
- [ ] Optional alignment + spikes layer: `aligned_time` into events DF, spikes loaded and TTL-aligned
- [ ] One canonical raster + PSTH figure around a task event (proof of end-to-end)
- [ ] Generic, documented notebook with independently-runnable sections
- [ ] Graceful degradation: events-only sessions (no ephys/spikes) produce a valid DataFrame

### Out of Scope

- DLC video / LED alignment — deferred to v2 (legacy was flaky with silent frame truncation; video files not guaranteed present)
- Multi-subject batch aggregation loop — v2 (v1 proves the single-session path; `SESSIONS` is a list but exercised on one entry)
- Full legacy figure suite (sync-check, all waveform variants) — v2 beyond the one canonical figure
- Reusing/refactoring legacy module code — legacy is conceptual reference only; implementation starts from scratch
- Writing back to Elasticsearch or any data ingestion — read-only analysis

## Context

**Legacy reference (study, do not reuse):** `~/mics_post_analysis/` (noale17 `thesis_ready` snapshot). Key modules capture the *intent*: `ElasticSearchClient.py` / `ElasticSearchClientV2.py` (two near-duplicate clients — the core patchiness to eliminate), `OpenEphysProcessor.py`, `SpikeExlProcessor.py`, `SessionAligner.py`, `DLCProcessor.py`. Problems to avoid: duplicated ES clients, hardcoded URLs/channels/paths, per-notebook copy-paste.

**Data environment (all reachable from this Linux host):**
- **Sessions share (SMB):** `/mnt/mics-smb/yizharlab/Ido/Mics/sessions/` (= `\\isi.storwis.weizmann.ac.il\labs\...`)
- **Naming convention:** ephys folder `<subject>s<n>_<YYYY-MM-DD>_<HH-MM-SS>` (e.g. `m74s4_2025-07-09_16-21-05`); loose pickled spikes `spikes_<subject>s<n>.pkl`; inline spikes also appear as `processed.xls` inside the folder.
- **Open Ephys layout:** `<folder>/Record Node <id>/experiment1/recording1` + `processed.dat`.
- **Elasticsearch:** primary `http://132.77.73.217:9200` (indices `event_log`, `event_log_v2`); secondary `http://132.77.73.125:9200` (`restored-event_log_v2`, restored/backup). Which host/index holds a session depends on the subject — must be configurable per `SESSIONS` entry.
- **ES subject keys are descriptive strings, not the short key.** Subject `m74` maps to several protocol strings: `m74_cue_reward`, `m74_appetitive`, `m74_stochastic`, `m74_find_threshold_80`, `m74_ass_cue_reward`. The session key (`m74s4`) cannot derive the ES subject — each `SESSIONS` entry carries an explicit `es_subject`.
- **Legacy vs new-portal schema:** legacy docs have `subject` (string) + `session` (int), no `run_id`/`subjects`. New-portal docs add `run_id` and `subjects`. Client reads both through one path.

**End-to-end fixture — `m74s4` (a legacy session):**
- ES: `217/event_log_v2`, `subject=m74_cue_reward`, `session=4` → 2137 events (TTL 602, LICKER 504, state_transition 394, IR 238, AUDIO 52, TRIGGERS 52, VALVE 52, hit 52, …)
- Ephys: `m74s4_2025-07-09_16-21-05/Record Node 110` + `processed.dat`
- Spikes: `spikes_m74s4.pkl` (~5.9 MB pre-parsed) — also `processed.xls`/`processed2.xls` (~192 MB Plexon export) and `processed.plx`
- **Alignment anchor:** ES `TRIGGERS` events ↔ ephys trigger-channel rising edges; first edge ties ES `relative_time` to the ephys clock.
- Second fixture `m74s1` (`m74s1_2025-07-06_12-16-42`) has inline `processed.xls` spikes — exercises the inline-xls spike path.

## Constraints

- **Tech stack**: Python + Jupyter; `elasticsearch-py`, `pandas`, `numpy`, Open Ephys reader (e.g. `open-ephys-python-tools`), `matplotlib`. Optional layers must import lazily so an events-only run needs no ephys deps installed.
- **Location**: code in `mics-backend/mics_post_analysis/` (dedicated folder inside the backend repo); planning in `mics_post_analysis/.planning/` (separate from the backend's root `.planning/`).
- **Data access**: ES hosts on the lab network; SMB share mounted at `/mnt/mics-smb`. Large `.xls` spike files (~192 MB) — prefer the pre-parsed pickle; cache intermediates like legacy.
- **Graceful optionality**: ephys + spikes are optional per session; the pipeline must never require them.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Clean-slate architecture, legacy = reference only | Legacy is patchy/data-coupled; user wants the intent, not the code | — Pending |
| ES events are the always-present base; ephys/spikes are optional layers | Not all ES sessions have ephys/spikes; pipeline must degrade gracefully | — Pending |
| New-portal schema primary, legacy read-compat through one path | Must read both old m74 data and current portal runs | — Pending |
| `SESSIONS` entry carries explicit `es_subject` (+ optional host/index) | Session key can't derive the descriptive ES subject; data spans two ES hosts | — Pending |
| Single-session end-to-end first; multi-subject batch deferred | Prove the path on `m74s4` before generalizing | — Pending |
| Fixture = `m74s4` (`m74_cue_reward` s4), a legacy session | Complete across all three legs; exercises the legacy read path | — Pending |
| DLC alignment deferred to v2 | Legacy flaky; video files not guaranteed present | — Pending |
| Dedicated `.planning/` in subfolder; hand-driven GSD | Native /gsd:* commands are pinned to the backend's root .planning | — Pending |

---
*Last updated: 2026-06-15 at project initialization*
