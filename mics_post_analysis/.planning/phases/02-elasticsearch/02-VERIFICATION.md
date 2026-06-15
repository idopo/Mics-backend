# Phase 2 Verification — Elasticsearch Events Layer

**Verified:** 2026-06-15 · **Score: 5/5 success criteria met**

**Goal:** One clean `ElasticClient` returning a tidy events DataFrame for a resolved session, reading legacy + new-portal schemas through one path across configurable hosts/indices, surfaced in a documented section that runs without ephys.

| # | Success criterion | Result | Evidence |
|---|---|---|---|
| 1 | Fetch `m74_cue_reward` s4 from `217/event_log_v2` → ~2137 rows, columns `event_type, hardware_id, level, raw_time, relative_time` | ✅ | `test_columns_and_count`; live run = 2137 rows, full tidy column set |
| 2 | Legacy + new-portal docs through one path; `run_id`/`subjects` null for legacy | ✅ | `test_legacy_schema_nulls` (all null); single `fetch_events` path |
| 3 | Host/index configurable per session (default `217`); session-less + scroll work | ✅ | host/index read from `ResolvedSession`; `_scroll` paginates; `_build_query` omits session term when None |
| 4 | AUDIO/LICKER/TTL/TRIGGERS/IR appear with expected counts | ✅ | `test_event_type_counts`; live counts TTL 602, LICKER 504, state_transition 394, IR 238, AUDIO/TRIGGERS ~52 |
| 5 | Notebook Section 1 displays events standalone (no ephys), docs, cached per key | ✅ | notebook executed: `m74s4: 2137 events`, df displayed, `cache/m74s4/events.pkl` written + re-served without ES call |

**Bonus (usability gap raised in discussion):** `subjects()` / `sessions()` discovery helpers — live: `subjects("m74")` → 5 strings, `sessions("m74_cue_reward")` → `{1:960,…,4:2137,…}`. Wired into a notebook discovery cell. Covered by `test_discovery_helpers`.

**Tests:** `pytest` → 12 passed (5 resolve + 7 elastic).
**Program run:** ElasticClient + discovery + notebook Section 1 all executed live.

**Requirements covered:** ES-01..05, DOC-02, FIG-02 (caching).

**Deviation handled:** es-py auto-installed as 9.x, which the 8.10.2 server rejects (`compatible-with=9` header). Pinned `elasticsearch>=8.10,<9` (now 8.19.3) — `ping: True`. Documented in commit `e21559f`.

**Commits:** `e21559f` (02-01 ElasticClient + discovery), `c346351` (02-02 notebook Section 1).

**Enhancement (post-verify, user-raised):** precise-time handling.
- Added nullable `pi_time` — the on-Pi **GPIO** timestamp (`event_data.pi_timestamp`), extracted **generically by field presence** (not a hardcoded event-type list, since which events carry it varies by task). ~23–32 ms before ES ingest `raw_time`; 742 events in the fixture (IR/LICKER).
- Added canonical **`time`** column = `pi_time` where present, else `raw_time` (ingest is fallback only — never the primary clock). `relative_time` and sort order derive from `time`. `raw_time`/`pi_time` retained for provenance.
- Tests: `test_pi_time`, `test_canonical_time_prefers_gpio`, `test_relative_time_monotonic` (now checks derivation from `time`). **14 tests pass.**

**Note for Phase 3:** `relative_time` is session-relative on the canonical `time` clock. The ephys-anchored `aligned_time` is added by the Phase 4 aligner, not here.
