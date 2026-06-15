# Phase 1 Verification — Foundation & Session Resolver

**Verified:** 2026-06-15 · **Score: 5/5 success criteria met**

**Goal:** A `mics/` package skeleton and a generic notebook whose top block lists sessions minimally and resolves them by naming convention — including events-only sessions with no ephys.

| # | Success criterion | Result | Evidence |
|---|---|---|---|
| 1 | `load_sessions()` resolves `m74s4` — derives folder, auto-finds `Record Node 110` + `spikes_m74s4.pkl` | ✅ | `test_resolve_m74s4_full` pass; live run shows `recording1` path + `spike_kind=pickle` |
| 2 | Entry with no ephys folder resolves as events-only (no error) | ✅ | `test_resolve_events_only_no_ephys` pass; live `behavior_only_s7` → `ephys — spikes —` |
| 3 | Channel/sampling defaults apply per session; per-entry override replaces them | ✅ | `test_channel_override` (trigger 17→99, ttl default kept) |
| 4 | Resolve cell prints one-line summary per session | ✅ | notebook executed top-to-bottom prints `m74s4: ES …/event_log_v2 m74_cue_reward s4 \| ephys ✓ Record Node 110 \| spikes pickle` |
| 5 | Notebook opens with markdown: purpose, add-a-session, convention, independent sections | ✅ | `mics_analysis.ipynb` cells 0–2 (markdown) |

**Tests:** `pytest tests/test_resolve.py` → 5 passed.
**Program run:** resolver + notebook both executed live against the SMB share.

**Requirements covered:** CONF-01..06, DOC-01.

**Commits:** `b737b23` (01-01 package + resolver), `261eb39` (01-02 notebook skeleton).

**Notes for later phases:**
- Deps are installed project-local in `.pylibs/` (PEP 668 blocked system/venv installs; `python3-venv` absent). Run anything with `PYTHONPATH=.pylibs:src`. The user's own analysis environment would `pip install -e .` normally.
- Full Jupyter execution stack (nbconvert/ipykernel) is not installed; the notebook is verified by executing its code cells in-process. Install the jupyter stack if true `nbconvert --execute` is wanted.
