# Roadmap: MICS Offline Analysis Toolkit

## Overview

Replace ~20 copy-pasted, data-coupled legacy notebooks with one generic notebook backed by a clean `mics/` package. Built in five phases that each deliver an independently-runnable notebook section, so the picture builds up gradually and earlier sections keep working even when later layers (or their data) are absent. The Elasticsearch events layer is the always-present base; Open Ephys and spikes attach only when a recording exists. `m74s4` (`m74_cue_reward` session 4, a legacy session) is the end-to-end fixture throughout.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): planned milestone work
- Decimal phases (2.1): urgent insertions (marked INSERTED)

- [x] **Phase 1: Foundation & Session Resolver** — `mics/` scaffold, convention resolver, `SESSIONS` config, notebook skeleton
- [ ] **Phase 2: Elasticsearch Events Layer** — unified `ElasticClient` → tidy events DataFrame; notebook Section 1
- [ ] **Phase 3: Open Ephys Layer** — `EphysRecording` TTL/trigger extraction + visualizer; notebook Section 2
- [ ] **Phase 4: Alignment & Spikes Layer** — `aligned_time` into events DF + `SpikeTable` + unified DataFrame; notebook Section 3
- [ ] **Phase 5: Canonical Figure** — one raster + PSTH helper; notebook Section 4

## Phase Details

### Phase 1: Foundation & Session Resolver
**Goal**: A `mics/` package skeleton and a generic notebook whose top block lists sessions minimally and resolves them by naming convention — including events-only sessions with no ephys.
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: CONF-01, CONF-02, CONF-03, CONF-04, CONF-05, CONF-06, DOC-01
**Success Criteria** (what must be TRUE):
  1. `load_sessions()` resolves an `m74s4` entry — deriving the ephys folder from convention, auto-finding `Record Node 110`, and auto-finding `spikes_m74s4.pkl`
  2. An entry with no ephys folder resolves cleanly as events-only (no error, ephys/spike fields empty)
  3. Channel/sampling defaults (trigger, ttl, sampling rate) apply per session and a per-entry override replaces them
  4. The resolve cell prints a one-line summary per session: key, ES coordinates, ephys found?, spike source found?
  5. The notebook opens with markdown on purpose, how to add a session, the convention rules, and running sections independently
**Plans**: 2
- **Wave 1** — `01-01` mics/ scaffold + SessionConfig + convention resolver + cache scaffold + unit tests
- **Wave 2** — `01-02` notebook skeleton (nbformat build script): docs header + SESSIONS block + resolve cell

### Phase 2: Elasticsearch Events Layer
**Goal**: One `ElasticClient` returning a tidy events DataFrame for a resolved session, reading legacy and new-portal schemas through one path, across the two ES hosts, surfaced in a documented section that runs without ephys.
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: ES-01, ES-02, ES-03, ES-04, ES-05, DOC-02
**Success Criteria** (what must be TRUE):
  1. `ElasticClient` fetches `m74_cue_reward` session 4 from host `217`/`event_log_v2` and returns ~2137 rows with columns `event_type, hardware_id, level, raw_time, relative_time`
  2. Legacy docs (no `run_id`) and new-portal docs (with `run_id`/`subjects`) flow through one path; `run_id`/`subjects` are null/empty for legacy m74 data
  3. Host/index are configurable per session (defaulting to primary `217`); session-less indices and scroll/pagination work
  4. AUDIO/LICKER/TTL/TRIGGERS/IR events appear with expected counts
  5. Notebook Section 1 displays the events DataFrame standalone (no ephys), with markdown docs, cached per session key
**Plans**: 2
- **Wave 1** — `02-01` unified `ElasticClient`: query builder + scroll + tidy row mapping (legacy + new-portal) + live tests
- **Wave 2** — `02-02` notebook Section 1: cached events fetch + display + docs (standalone/graceful)

### Phase 3: Open Ephys Layer
**Goal**: An `EphysRecording` that auto-discovers the Record Node recording and extracts TTL/trigger rising edges, with a raw-channel visualizer — lazily imported and skippable.
**Mode:** mvp
**Depends on**: Phase 1 (independent of Phase 2)
**Requirements**: EPHYS-01, EPHYS-02, EPHYS-03
**Success Criteria** (what must be TRUE):
  1. `EphysRecording` opens the auto-discovered `m74s4` recording and returns TTL and trigger rising-edge timestamps, with the detection threshold a named, overridable constant
  2. The visualizer plots raw TTL/trigger channels for a sanity check
  3. The layer imports lazily and Section 2 is skipped without error when no recording is present; earlier sections still run
**Plans**: TBD during planning

### Phase 4: Alignment & Spikes Layer
**Goal**: Tie events to the ephys clock and attach spikes — `SessionAligner` writes `aligned_time` into the events DF via the first trigger edge, `SpikeTable` loads + aligns spikes, producing the unified DataFrame; events-only sessions degrade gracefully.
**Mode:** mvp
**Depends on**: Phase 2 (events DF) and Phase 3 (ephys edges)
**Requirements**: ALIGN-01, ALIGN-02, ALIGN-03, SPIKE-01, SPIKE-02, FIG-02
**Success Criteria** (what must be TRUE):
  1. After alignment the events DF has a populated `aligned_time` that is monotonic and within recording bounds; a spot-checked AUDIO event aligns near its ephys TTL
  2. `SpikeTable` loads spikes (pickle-first, `.xls`/`.plx` fallback) into a tidy DataFrame (`channel, unit, spike_time`) aligned to the first TTL
  3. The unified DataFrame combines events (always) with `aligned_time` + spikes (when present); a session with no ephys yields a valid events-only DataFrame with null `aligned_time`
  4. Notebook Section 3 shows the unified aligned DataFrame, documents the graceful-degradation behavior, and caches results per session key
**Plans**: TBD during planning

### Phase 5: Canonical Figure
**Goal**: One consolidated raster/PSTH helper combining aligned spikes and events, surfaced in a documented, cacheable notebook section — the end-to-end proof.
**Mode:** mvp
**Depends on**: Phase 4
**Requirements**: FIG-01
**Success Criteria** (what must be TRUE):
  1. One helper produces a raster + PSTH around a chosen task event (e.g. AUDIO) from the aligned data, reproducing the existing `m74s4` figure
  2. Notebook Section 4 renders the figure for `m74s4` and is cached; the section no-ops cleanly for events-only sessions
**Plans**: TBD during planning

## Progress

**Execution Order:** 1 → (2 ∥ 3) → 4 → 5  (Phases 2 and 3 are independent and may run in parallel)

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation & Session Resolver | 2/2 | Complete | 2026-06-15 |
| 2. Elasticsearch Events Layer | 0/2 | Planned | - |
| 3. Open Ephys Layer | 0/TBD | Not started | - |
| 4. Alignment & Spikes Layer | 0/TBD | Not started | - |
| 5. Canonical Figure | 0/TBD | Not started | - |
