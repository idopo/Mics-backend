"""Assemble the single generic analysis notebook from code.

We build `mics_analysis.ipynb` programmatically (nbformat) instead of hand-editing
JSON — the giant copy-pasted legacy notebooks are exactly what this replaces.
Later phases append their sections by adding cells in `build()`.

Run:  python notebooks/build_notebook.py
"""

from __future__ import annotations

from pathlib import Path

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

OUT = Path(__file__).resolve().parent / "mics_analysis.ipynb"


# --- cell content (kept as labeled blocks so phases can append cleanly) ---

MD_TITLE = """\
# MICS Offline Analysis

Assemble MICS behavioral data offline. The **Elasticsearch events layer always
works on its own**; the Open Ephys and spike layers attach automatically only
when a recording exists for that session.

This one notebook replaces the per-session legacy notebooks: add a session to
the `SESSIONS` block below and run the sections you need."""

MD_ADD_SESSION = """\
## How to add a session

Edit the `SESSIONS` list. Minimum fields per entry:

- `key` — short id like `"m74s4"` (subject `m74`, session `4`)
- `es_subject` — the **descriptive** Elasticsearch subject string (e.g.
  `"m74_cue_reward"`), *not* the key
- `es_session` — the ES session number

Everything else is derived by convention from the sessions share:

- ephys folder `<subject>s<n>_<date>_<time>` → auto-found, with its `Record Node`
- spikes → loose `spikes_<subject>s<n>.pkl`, else inline `processed.xls`

Optional overrides: `es_host`, `es_index`, `run_id`, `ephys_folder`,
`record_node`, `spike_path`, `trigger_channel`, `ttl_channel`, `sampling_rate`."""

MD_HOW_TO_RUN = """\
## How to run

Sections are independent and build up the picture:

1. **Events** (Elasticsearch) — always available, no ephys needed
2. **Open Ephys** — TTL/trigger edges (skips itself when no recording)
3. **Alignment & Spikes** — unify onto the ephys clock (graceful when absent)
4. **Figure** — raster + PSTH around a task event

A session with no ephys recording still produces a valid events-only result."""

CODE_IMPORTS = """\
import sys
sys.path.insert(0, "../src")  # harmless if `mics` is pip-installed (-e .)

from mics.config import SessionConfig
from mics.resolve import load_sessions
from mics.elastic import ElasticClient
from mics.cache import cached_pickle"""

MD_DISCOVER = """\
## Find your subject + session (optional)

ES subjects are descriptive strings (e.g. `m74_cue_reward`), not the short key.
Look one up instead of memorizing it, then copy it into `SESSIONS` below."""

CODE_DISCOVER = """\
es = ElasticClient()                  # primary host
es.subjects("m74")                    # -> ['m74_cue_reward', 'm74_appetitive', ...]"""

CODE_DISCOVER_SESS = """\
es.sessions("m74_cue_reward")         # -> {1: 960, 2: 781, 4: 2137, ...} (session -> #events)"""

CODE_SESSIONS = """\
SESSIONS = [
    SessionConfig(key="m74s4", es_subject="m74_cue_reward", es_session=4),
    # SessionConfig(key="m74s1", es_subject="m74_cue_reward", es_session=1),
]"""

CODE_RESOLVE = """\
sessions = load_sessions(SESSIONS)
for s in sessions:
    print(s.summary())"""

MD_SECTION1 = """\
## Section 1 · Behavioral Events (Elasticsearch)

The always-available base layer — no ephys required. Columns: `event_type`,
`hardware_id`, `level`, `raw_time`, `relative_time` (seconds from session start),
`run_id`/`subjects` (null for legacy data), `event_data` (raw dict).

Results are cached per session key under `cache/<key>/events.pkl`; pass
`force=True` to refetch."""

CODE_S1_FETCH = """\
events = {}
for s in sessions:
    events[s.key] = cached_pickle(
        s.key, "events",
        lambda s=s: ElasticClient(s.es_host).fetch_events(s),
    )
    print(f"{s.key}: {len(events[s.key])} events")"""

CODE_S1_DISPLAY = """\
key = sessions[0].key
df = events[key]
display(df.head(20))
df.event_type.value_counts()"""


def build() -> nbformat.NotebookNode:
    nb = new_notebook()
    nb.cells = [
        new_markdown_cell(MD_TITLE),
        new_markdown_cell(MD_ADD_SESSION),
        new_markdown_cell(MD_HOW_TO_RUN),
        new_code_cell(CODE_IMPORTS),
        new_markdown_cell(MD_DISCOVER),
        new_code_cell(CODE_DISCOVER),
        new_code_cell(CODE_DISCOVER_SESS),
        new_code_cell(CODE_SESSIONS),
        new_code_cell(CODE_RESOLVE),
        new_markdown_cell(MD_SECTION1),
        new_code_cell(CODE_S1_FETCH),
        new_code_cell(CODE_S1_DISPLAY),
        # Phase 3+ append Section 2..4 cells here.
    ]
    nb.metadata.update(
        {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
        }
    )
    return nb


if __name__ == "__main__":
    nbformat.write(build(), OUT)
    print(f"wrote {OUT} ({len(build().cells)} cells)")
