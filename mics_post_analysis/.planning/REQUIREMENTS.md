# Requirements: MICS Offline Analysis Toolkit

**Defined:** 2026-06-15
**Core Value:** One unified, clock-aligned events+spikes DataFrame per session — ES events always work alone; ephys/spike layers attach only when an ephys recording exists.

## v1 Requirements

### Configuration & Session Resolution (CONF)

- [ ] **CONF-01**: A `SESSIONS` config block lists sessions with a minimal entry: session key, `es_subject`, `es_session`; optional `es_host`/`es_index`, ephys/spike path overrides, and channel/cluster settings
- [ ] **CONF-02**: `load_sessions()` derives the ephys folder from the convention `<subject>s<n>_<date>_<time>` and auto-finds the `Record Node *` recording path
- [ ] **CONF-03**: The resolver auto-finds a spike source per session — loose `spikes_<subject>s<n>.pkl`, else inline `processed.xls` — and a per-entry override can replace it
- [ ] **CONF-04**: Channel/sampling defaults (trigger ch, ttl ch, sampling rate) are named, overridable constants applied per session
- [ ] **CONF-05**: An entry whose ephys folder and/or spikes are absent resolves cleanly as an events-only session (no error)
- [ ] **CONF-06**: Resolving prints a one-line summary per session (key, ES coordinates, ephys found?, spike source found?)

### Elasticsearch Events (ES)

- [ ] **ES-01**: One `ElasticClient` fetches events for a resolved session and returns a tidy DataFrame with columns: `event_type`, `hardware_id`, `level`, `raw_time`, `relative_time` (and `aligned_time`, populated later)
- [ ] **ES-02**: Legacy docs (`subject` string + `session` int, no `run_id`) and new-portal docs (`run_id`, `subjects`) are handled through one code path; `run_id`/`subjects` columns are null/empty for legacy docs
- [ ] **ES-03**: The client targets a configurable ES host + index per session (primary `217`, secondary `125`), defaulting to primary
- [ ] **ES-04**: Sessioned and session-less indices are both handled; large result sets use scroll/pagination
- [ ] **ES-05**: For the `m74_cue_reward` session-4 fixture the client returns ~2137 events with the expected types (TTL, AUDIO, TRIGGERS, LICKER, state_transition, …)

### Open Ephys (EPHYS) — optional layer

- [ ] **EPHYS-01**: `EphysRecording` opens the auto-discovered Record Node recording and returns TTL and trigger rising-edge timestamps, with the detection threshold a named, overridable constant
- [ ] **EPHYS-02**: A visualizer plots raw TTL/trigger channels for a sanity check
- [ ] **EPHYS-03**: The ephys layer imports lazily and is skipped without error when no recording is present

### Alignment & Spikes (ALIGN / SPIKE) — optional layer

- [ ] **ALIGN-01**: `SessionAligner` anchors ES `relative_time` to the ephys clock via the first trigger edge (ES `TRIGGERS` ↔ ephys trigger channel) and writes a populated `aligned_time` into the events DataFrame; `aligned_time` is monotonic and within recording bounds
- [ ] **ALIGN-02**: A spot-checked AUDIO event aligns near its corresponding ephys TTL
- [ ] **ALIGN-03**: When no ephys recording exists, `aligned_time` is left null and the events-only DataFrame remains valid (graceful degradation)
- [ ] **SPIKE-01**: `SpikeTable` loads spikes into a tidy DataFrame (`channel`, `unit`, `spike_time`), preferring the pre-parsed pickle and falling back to parsing `processed.xls`/`.plx`, and aligns spike times to the first TTL
- [ ] **SPIKE-02**: The unified DataFrame combines events (always) with `aligned_time` and spikes (when ephys/spikes present)

### Figures (FIG)

- [ ] **FIG-01**: One consolidated helper produces a raster + PSTH around a chosen task event (e.g. AUDIO/reward) from aligned spikes + events, reproducing the existing `m74s4` result
- [ ] **FIG-02**: Results (events DF, aligned DF, spikes) are cached per session key like the legacy pickles

### Notebook & Docs (DOC)

- [ ] **DOC-01**: One generic notebook opens with markdown explaining purpose, how to add a session, the convention rules, and how to run sections independently
- [ ] **DOC-02**: Notebook sections (Events → Ephys → Alignment+Spikes → Figure) each run standalone; earlier sections work even if later layers/data are absent

## v2 Requirements

### DLC Alignment (DLC)

- **DLC-01**: Align DLC pose/LED data to the ephys clock, fixing the legacy LED-vs-TTL count-mismatch (no silent truncation; frames→seconds correct)

### Batch (BATCH)

- **BATCH-01**: Loop over many subjects/sessions and aggregate results across sessions
- **BATCH-02**: Per-session caching and isolation for batch runs

### Figures (FIG)

- **FIG-03**: Full legacy figure suite — robust waveform plots, sync-check diagnostics

## Out of Scope

| Feature | Reason |
|---------|--------|
| Refactoring/porting legacy module code | Clean-slate; legacy is conceptual reference only |
| Writing to Elasticsearch / data ingestion | Read-only offline analysis |
| Spike sorting itself | Consumes already-sorted spikes (pickle/Plexon export) |
| DLC alignment in v1 | Deferred to v2 (flaky legacy, video not guaranteed present) |
| Multi-subject batch in v1 | Deferred to v2 (prove single-session path first) |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CONF-01..06 | Phase 1 | Pending |
| DOC-01 | Phase 1 | Pending |
| ES-01..05 | Phase 2 | Pending |
| DOC-02 (Events) | Phase 2 | Pending |
| EPHYS-01..03 | Phase 3 | Pending |
| ALIGN-01..03 | Phase 4 | Pending |
| SPIKE-01..02 | Phase 4 | Pending |
| FIG-02 (caching) | Phase 4 | Pending |
| FIG-01 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 21 total
- Mapped to phases: 21
- Unmapped: 0

---
*Requirements defined: 2026-06-15*
