"""Read-only Elasticsearch access + small parsing helpers for tools/es_clock_check.py.

Split out of es_clock_check.py to keep each file under this repo's 300-line soft limit (500
hard limit, see .claude coding standards). `ReadOnlyESClient.search` is the ONLY method in this
whole module tree that ever calls Elasticsearch, and it only ever calls `_search`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests

NS_PER_TICK_WRAP = 2**32 * 1000  # a 32-bit monotonic tick, in nanoseconds, wraps every 4294.967296 s
PLAUSIBILITY_WINDOW_S = 60


class ReadOnlyESClient:
    """The ONLY method on this class that talks to Elasticsearch is `search`, and the ONLY
    endpoint it ever calls is `_search`. Do not add a write method to this class.
    """

    def __init__(self, host: str, index: str, timeout_s: float):
        self.base = f"http://{host}/{index}"
        self.timeout_s = timeout_s

    def search(self, body: dict) -> dict:
        r = requests.post(f"{self.base}/_search", json=body, timeout=self.timeout_s)
        r.raise_for_status()
        return r.json()


def iter_run_documents(client: ReadOnlyESClient, subject: str, page_size: int):
    """Yield the run's documents one at a time via `search_after` pagination.

    Sorted by `t_mono_ns` (missing sorts last, so software/tracker docs without a monotonic
    field still come through, just at the tail) then `_seq_no` as a tiebreaker so pagination is
    deterministic even across many documents sharing one `t_mono_ns` (the cross-route pairs C3
    is looking for). Each page is discarded once consumed -- never materializes the whole run.
    """
    sort = [{"t_mono_ns": {"order": "asc", "missing": "_last"}}, {"_seq_no": "asc"}]
    search_after = None
    while True:
        body: dict[str, Any] = {
            "size": page_size,
            "sort": sort,
            "query": {"match_phrase": {"subject": subject}},
        }
        if search_after is not None:
            body["search_after"] = search_after
        result = client.search(body)
        hits = result.get("hits", {}).get("hits", [])
        if not hits:
            return
        for hit in hits:
            yield hit
        search_after = hits[-1].get("sort")
        if len(hits) < page_size or search_after is None:
            return


def get_nested(source: dict, dotted_path: str) -> Any:
    node: Any = source
    for part in dotted_path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def has_suffix_field(node: Any, suffix: str, _depth: int = 0) -> bool:
    """True if any key anywhere in this (possibly nested) document ends with `suffix`.

    Used for C4's "no document claims hardware without a *_mono_ns field" check -- the field
    could be top-level (`t_mono_ns`) or nested (`event.event_data.pi_timestamp_mono_ns`).
    Depth-bounded so a malformed/circular document can never spin this forever.
    """
    if _depth > 8 or not isinstance(node, dict):
        return False
    for key, value in node.items():
        if key.endswith(suffix):
            return True
        if isinstance(value, dict) and has_suffix_field(value, suffix, _depth + 1):
            return True
    return False


def parse_pi_timestamp(value: Any) -> datetime | None:
    """Best-effort parse of a raw timestamp value into an aware UTC datetime.

    Used for both `event.event_data.pi_timestamp` (the value under test) and `@timestamp` (the
    plausibility window's ground truth). Handles the two known corruption modes (see plan's C5)
    by trying, in order: ISO 8601 string, epoch seconds (float/int), epoch milliseconds. A value
    that parses to a wildly implausible date (e.g. 2017, or near the Unix epoch) is NOT rejected
    here -- that is exactly what the plausibility window check downstream is for; this function
    only turns a raw value into a datetime or gives up.
    """
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            try:
                value = float(value)
            except ValueError:
                return None
    if isinstance(value, (int, float)):
        # Heuristic: values above ~1e12 are almost certainly milliseconds, not seconds.
        seconds = value / 1000.0 if value > 1e12 else value
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    return None
