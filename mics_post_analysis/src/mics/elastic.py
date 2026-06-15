"""Unified Elasticsearch client → tidy events DataFrame.

One client replaces the two near-duplicate legacy clients. Reads legacy docs
(``subject`` + ``session``, no ``run_id``) and new-portal docs (``run_id`` /
``subjects``) through a single path; the schema difference is just nullable
columns. Host + index come from the resolved session.

Note: ``relative_time`` here is seconds from the session's first event (a
standalone events view). The cross-clock ``aligned_time`` (ephys trigger anchor)
is added later by the aligner, not at this layer.
"""

from __future__ import annotations

import pandas as pd
from elasticsearch import Elasticsearch

from .config import ES_PRIMARY

COLUMNS = [
    "event_type", "hardware_id", "level", "raw_time", "pi_time",
    "relative_time", "run_id", "subjects", "task_type", "event_data",
]


class ElasticClient:
    """Thin wrapper over an Elasticsearch host with event-fetch + discovery."""

    _clients: dict[str, Elasticsearch] = {}

    def __init__(self, host: str = ES_PRIMARY, request_timeout: int = 30):
        self.host = host
        if host not in self._clients:
            self._clients[host] = Elasticsearch([host], request_timeout=request_timeout)
        self.es = self._clients[host]

    def ping(self) -> bool:
        return bool(self.es.ping())

    # --- discovery (so users look subjects up instead of memorizing strings) ---

    def subjects(self, contains: str = "", index: str = "event_log_v2", size: int = 50) -> list[str]:
        """Distinct ES subject strings, optionally filtered to those containing a substring."""
        terms: dict = {"field": "subject.keyword", "size": size}
        if contains:
            terms["include"] = f".*{contains}.*"
        r = self.es.search(index=index, size=0, aggs={"s": {"terms": terms}})
        return sorted(b["key"] for b in r["aggregations"]["s"]["buckets"])

    def sessions(self, es_subject: str, index: str = "event_log_v2", size: int = 100) -> dict[int, int]:
        """Map of session number → event count for a subject (sorted by session)."""
        r = self.es.search(
            index=index, size=0,
            query={"term": {"subject.keyword": es_subject}},
            aggs={"sess": {"terms": {"field": "session", "size": size}}},
        )
        buckets = r["aggregations"]["sess"]["buckets"]
        return {int(b["key"]): b["doc_count"] for b in sorted(buckets, key=lambda b: b["key"])}

    # --- fetch ---

    @staticmethod
    def _build_query(es_subject: str, es_session: int | None, run_id: int | None, event_type: str | None) -> dict:
        must: list[dict] = [{"term": {"subject.keyword": es_subject}}]
        if es_session is not None:
            must.append({"term": {"session": es_session}})
        if run_id is not None:
            must.append({"term": {"run_id": run_id}})
        if event_type is not None:
            must.append({"term": {"event.event_type.keyword": event_type}})
        return {"bool": {"must": must}}

    def _scroll(self, index: str, query: dict, page: int = 1000, keep: str = "2m"):
        resp = self.es.search(index=index, query=query, size=page, scroll=keep)
        scroll_id = resp.get("_scroll_id")
        try:
            hits = resp["hits"]["hits"]
            while hits:
                yield from hits
                resp = self.es.scroll(scroll_id=scroll_id, scroll=keep)
                scroll_id = resp.get("_scroll_id")
                hits = resp["hits"]["hits"]
        finally:
            if scroll_id:
                try:
                    self.es.clear_scroll(scroll_id=scroll_id)
                except Exception:
                    pass  # scroll context may already be gone

    @staticmethod
    def _row(src: dict) -> dict:
        ev = src.get("event", {})
        data = ev.get("event_data", {}) or {}
        return {
            "event_type": ev.get("event_type"),
            "hardware_id": data.get("id"),
            "level": ev.get("level"),
            "raw_time": src.get("timestamp"),
            # precise on-Pi GPIO time when the event reports it (varies by task);
            # extracted generically by field presence, not by event type.
            "pi_time": data.get("pi_timestamp"),
            "run_id": src.get("run_id"),
            "subjects": src.get("subjects"),
            "task_type": src.get("task_type"),
            "event_data": data,
        }

    def fetch_events(self, resolved, event_type: str | None = None) -> pd.DataFrame:
        """Return a tidy events DataFrame for a resolved session."""
        query = self._build_query(resolved.es_subject, resolved.es_session, resolved.run_id, event_type)
        rows = [self._row(h["_source"]) for h in self._scroll(resolved.es_index, query)]
        df = pd.DataFrame(rows, columns=[c for c in COLUMNS if c != "relative_time"])

        if df.empty:
            df["relative_time"] = pd.Series(dtype="float64")
            return df[COLUMNS]

        df["raw_time"] = pd.to_datetime(df["raw_time"], utc=True, format="ISO8601")
        df["pi_time"] = pd.to_datetime(df["pi_time"], utc=True, format="ISO8601")
        df = df.sort_values("raw_time", kind="stable").reset_index(drop=True)
        df["relative_time"] = (df["raw_time"] - df["raw_time"].iloc[0]).dt.total_seconds()
        return df[COLUMNS]
