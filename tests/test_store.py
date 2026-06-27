from agent_carbon.config import Config
from agent_carbon.impact.engine import EcoLogitsEngine
from agent_carbon.impact.resolver import ModelResolver
from agent_carbon.models import InferenceEvent
from agent_carbon.store.db import SQLiteStore


def _events():
    return [
        InferenceEvent("anthropic", "claude-opus-4-8", 100, 287, 0, 0,
                       "2026-06-27T10:00:00.000Z", "projA", "sess-A", "u1"),
        InferenceEvent("anthropic", "claude-opus-4-8", 100, 200, 0, 0,
                       "2026-06-27T10:10:00.000Z", "projA", "sess-A", "u2"),
    ]


def _engine():
    return EcoLogitsEngine(ModelResolver({}))


def test_ingest_is_idempotent(tmp_path):
    store = SQLiteStore(str(tmp_path / "c.db"))
    n1 = store.ingest(_events(), _engine(), Config())
    n2 = store.ingest(_events(), _engine(), Config())  # rejoue
    assert n1 == 2
    assert n2 == 0  # aucun nouveau
    assert len(store.rows_for_report(None)) == 2


def test_session_duration_computed(tmp_path):
    store = SQLiteStore(str(tmp_path / "c.db"))
    store.ingest(_events(), _engine(), Config())
    assert store.session_count() == 1
    assert store.total_duration_seconds() == 600.0  # 10 min entre u1 et u2


def test_impact_columns_persisted(tmp_path):
    store = SQLiteStore(str(tmp_path / "c.db"))
    store.ingest(_events(), _engine(), Config())
    row = store.rows_for_report(None)[0]
    assert row["gwp_min"] > 0 and row["gwp_max"] >= row["gwp_min"]
    assert row["wcf_max"] > 0
