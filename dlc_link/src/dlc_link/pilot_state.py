"""Run identity from the orchestrator, FDA state name from ElasticSearch -- both
fail-soft and never raising into the caller (D-57).

**Verified fact that decides this module's shape.** `GET /pilots/live`'s `state`
field is the pilot's COARSE state (IDLE/RUNNING), not the FDA state.
`orchestrator/orchestrator/orchestrator_station.py`'s `on_state` (lines 236-253)
writes whatever the pilot reports straight into `redis pilot:<name> state`, seeded as
IDLE/RUNNING at lines 214-228; `orchestrator/orchestrator/api.py`'s
`list_live_pilots` (lines 24-56) reads it back with a default of `UNKNOWN`. There is
no FDA state name anywhere in that payload.

The FDA state name exists only as an ElasticSearch `state_transition` document:
`autopilot/autopilot/utils/FiniteDeterministicAutomaton.py:17` emits
`Event(event_type='state_transition', event_data={"current_state": next_state_name})`.
Phase 35 run 588 put 232 of those documents into `event_log_v2` on `132.77.73.217`.

So both sources are queried, each for the one thing it alone holds: the orchestrator
supplies `active_run.subject_key` VERBATIM, which becomes the ElasticSearch filter;
ElasticSearch supplies the FDA state name the orchestrator's payload never carries.

**No caching layer, no last-known-good value, anywhere in this module.** A failed
fetch returns `available=False`, and the renderer shows `unavailable - <reason>`.
Presenting a stale FDA state as current is the same class of error as a coordinate
signal surviving past tracking loss (DLC-05), and it is refused here for the same
reason.

No timestamp read from either source is ever compared against any other clock, or
turned into a duration, anywhere in this package (DLC-10, carried).
"""
import json
import urllib.request
from dataclasses import dataclass
from typing import Optional


@dataclass
class RunIdentity:
    """The orchestrator's view of one pilot. `available=False` means the fetch or
    parse itself failed; `available=True` with `run_id=None` means the fetch
    succeeded and the pilot simply has no active run right now."""

    available: bool
    reason: str
    connected: Optional[bool] = None
    coarse_state: Optional[str] = None
    run_id: Optional[int] = None
    session_id: Optional[int] = None
    subject_key: Optional[str] = None


@dataclass
class StateReading:
    """The FDA state name, as read from ElasticSearch."""

    available: bool
    reason: str
    state: Optional[str] = None

    def render(self):
        """`FDA state: <name>` when available, `FDA state: unavailable - <reason>`
        otherwise. There is no code path that renders a value fetched on a previous
        call -- an unavailable reading never falls back to `state`."""
        if self.available:
            return "FDA state: {}".format(self.state)
        return "FDA state: unavailable - {}".format(self.reason)


def parse_pilots_live(payload, pilot_name):
    """Parse a `GET /pilots/live` response for one pilot's run identity.

    Total: any shape this function does not understand becomes an unavailable
    `RunIdentity` naming what was seen. Never raises.
    """
    if not isinstance(payload, dict) or pilot_name not in payload:
        return RunIdentity(
            available=False,
            reason="pilot {!r} not present in /pilots/live response".format(pilot_name),
        )

    entry = payload[pilot_name]
    if not isinstance(entry, dict):
        return RunIdentity(
            available=False,
            reason="pilot {!r} entry is not an object: {!r}".format(pilot_name, entry),
        )

    connected = entry.get("connected")
    coarse_state = entry.get("state")
    active_run = entry.get("active_run")

    if not active_run:
        return RunIdentity(
            available=True,
            reason="no active run",
            connected=connected,
            coarse_state=coarse_state,
        )

    if not isinstance(active_run, dict):
        return RunIdentity(
            available=False,
            reason="pilot {!r} active_run is not an object: {!r}".format(pilot_name, active_run),
        )

    return RunIdentity(
        available=True,
        reason="",
        connected=connected,
        coarse_state=coarse_state,
        run_id=active_run.get("id"),
        session_id=active_run.get("session_id"),
        subject_key=active_run.get("subject_key"),
    )


def parse_state_transition(response):
    """Parse an ElasticSearch `_search` response for the newest `state_transition`
    hit's `event_data.current_state`.

    Total: any shape this function does not understand becomes an unavailable
    `StateReading` naming what was seen. Never raises.
    """
    hits_block = response.get("hits") if isinstance(response, dict) else None
    hits = hits_block.get("hits") if isinstance(hits_block, dict) else None
    if not hits:
        return StateReading(available=False, reason="no state_transition document was found")

    first = hits[0]
    source = first.get("_source", {}) if isinstance(first, dict) else {}
    event_data = source.get("event_data", {}) if isinstance(source, dict) else {}

    if not isinstance(event_data, dict) or "current_state" not in event_data:
        found_keys = sorted(event_data.keys()) if isinstance(event_data, dict) else event_data
        return StateReading(
            available=False,
            reason="hit's event_data lacks current_state; keys found: {!r}".format(found_keys),
        )

    return StateReading(available=True, reason="", state=event_data["current_state"])


def _default_opener(url, data, timeout_s):
    """Real HTTP via stdlib `urllib.request`. `data=None` sends a GET; non-`None`
    `data` (already-serialised JSON bytes) sends a POST. Never used by a test --
    every test injects its own `opener`."""
    method = "POST" if data is not None else "GET"
    headers = {"Content-Type": "application/json"} if data is not None else {}
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout_s) as response:
        return response.read()


def fetch_run_identity(base_url, pilot_name, timeout_s=2.0, opener=None):
    """GET `<base_url>/pilots/live` and parse the named pilot's run identity.

    Every exception -- connection, timeout, HTTP status, JSON decode -- is caught
    and turned into an unavailable `RunIdentity`. Nothing here may raise into the
    caller, because the caller is the process feeding a Pi that is driving hardware
    with an animal in it.
    """
    opener = opener or _default_opener
    url = "{}/pilots/live".format(base_url.rstrip("/"))
    try:
        raw = opener(url, None, timeout_s)
    except Exception as exc:
        return RunIdentity(available=False, reason="{}: {}".format(type(exc).__name__, exc))

    try:
        payload = json.loads(raw)
    except Exception as exc:
        return RunIdentity(
            available=False,
            reason="could not parse response as JSON ({}: {})".format(type(exc).__name__, exc),
        )

    return parse_pilots_live(payload, pilot_name)


def fetch_fda_state(es_url, index, subject_key, timeout_s=2.0, opener=None):
    """POST a search to `<es_url>/<index>/_search` filtering `event_type:
    state_transition` AND `subject: <subject_key>`, sorted by the document's
    timestamp descending, `size: 1`. The body is built as a dict and serialised --
    never hand-written JSON text.

    Every exception is caught and turned into an unavailable `StateReading`. Nothing
    here may raise into the caller.
    """
    opener = opener or _default_opener
    url = "{}/{}/_search".format(es_url.rstrip("/"), index)
    body = {
        "query": {
            "bool": {
                "filter": [
                    {"term": {"event_type": "state_transition"}},
                    {"term": {"subject": subject_key}},
                ]
            }
        },
        "sort": [{"@timestamp": {"order": "desc"}}],
        "size": 1,
    }
    try:
        raw = opener(url, json.dumps(body).encode("utf-8"), timeout_s)
    except Exception as exc:
        return StateReading(available=False, reason="{}: {}".format(type(exc).__name__, exc))

    try:
        response = json.loads(raw)
    except Exception as exc:
        return StateReading(
            available=False,
            reason="could not parse response as JSON ({}: {})".format(type(exc).__name__, exc),
        )

    return parse_state_transition(response)
