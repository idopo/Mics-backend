"""Live integration tests for ElasticClient against the m74_cue_reward s4 fixture.

Skipped automatically if the primary ES host is unreachable.
"""

import pandas as pd
import pytest

from mics.config import ES_PRIMARY, SessionConfig
from mics.elastic import ElasticClient
from mics.resolve import resolve_one

FIXTURE = SessionConfig(key="m74s4", es_subject="m74_cue_reward", es_session=4)


def _es_up() -> bool:
    try:
        return ElasticClient(ES_PRIMARY).ping()
    except Exception:
        return False


needs_es = pytest.mark.skipif(not _es_up(), reason="primary ES unreachable")


@pytest.fixture(scope="module")
def events_df():
    return ElasticClient(ES_PRIMARY).fetch_events(resolve_one(FIXTURE))


@needs_es
def test_columns_and_count(events_df):
    expected = {
        "event_type", "hardware_id", "level", "raw_time", "pi_time",
        "relative_time", "run_id", "subjects", "task_type", "event_data",
    }
    assert set(events_df.columns) == expected
    assert 2100 <= len(events_df) <= 2200  # fixture is ~2137


@needs_es
def test_pi_time(events_df):
    # pi_time = precise on-Pi GPIO time. It is extracted generically wherever an
    # event reports event_data.pi_timestamp — the set of event types that carry
    # it varies by experiment/task, so the contract is driven by field presence,
    # not by a hardcoded event-type list.
    has_pi = events_df.event_data.apply(
        lambda d: isinstance(d, dict) and "pi_timestamp" in d
    )
    assert has_pi.any()  # fixture has some GPIO-timestamped events
    assert events_df.loc[has_pi, "pi_time"].notna().all()
    assert events_df.loc[~has_pi, "pi_time"].isna().all()
    # GPIO time precedes the ES ingest time.
    assert (events_df.loc[has_pi, "pi_time"] <= events_df.loc[has_pi, "raw_time"]).all()


@needs_es
def test_event_type_counts(events_df):
    vc = events_df.event_type.value_counts()
    assert vc.get("TTL", 0) > 500          # ~602
    assert vc.get("LICKER", 0) > 400       # ~504
    assert vc.get("state_transition", 0) > 300  # ~394
    assert vc.get("AUDIO", 0) >= 40        # ~52
    assert vc.get("TRIGGERS", 0) >= 40     # ~52


@needs_es
def test_legacy_schema_nulls(events_df):
    # m74s4 is a legacy session: no run_id / subjects fields.
    assert events_df.run_id.isna().all()
    assert events_df.subjects.isna().all()


@needs_es
def test_level_nullability(events_df):
    # state_transition has no event.level; hardware events do.
    st = events_df[events_df.event_type == "state_transition"]
    assert st.level.isna().all()
    ttl = events_df[events_df.event_type == "TTL"]
    assert ttl.level.notna().all()


@needs_es
def test_relative_time_monotonic(events_df):
    rt = events_df.relative_time
    assert rt.iloc[0] == pytest.approx(0.0, abs=1e-6)
    assert rt.is_monotonic_increasing


@needs_es
def test_hardware_id_mapping(events_df):
    ttl = events_df[events_df.event_type == "TTL"]
    assert (ttl.hardware_id == "TTL1").any()
    st = events_df[events_df.event_type == "state_transition"]
    assert st.hardware_id.isna().all()


@needs_es
def test_discovery_helpers():
    client = ElasticClient(ES_PRIMARY)
    subjects = client.subjects("m74")
    assert "m74_cue_reward" in subjects
    sessions = client.sessions("m74_cue_reward")
    assert sessions.get(4, 0) == 2137
