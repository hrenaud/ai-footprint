import pytest

from ai_footprint.config import Config
from ai_footprint.impact.engine import EcoLogitsEngine
from ai_footprint.impact.resolver import ModelResolver
from ai_footprint.ingest.cli import ingest_and_save
from ai_footprint.models import InferenceEvent
from ai_footprint.store.db import SQLiteStore


def _engine():
    return EcoLogitsEngine(ModelResolver({}))


def _unknown_opencode_gpt_event(*, msg_id="m1", route="unknown"):
    return InferenceEvent(
        "openai", "gpt-5.6-terra", 10, 20, 0, 0,
        "2026-08-02T00:00:00Z", "p", "s", msg_id,
        client="opencode", route=route,
    )


class _FakeConfig:
    def __init__(self):
        self.model_params = {}
        self.hf_unresolved = {}
        self.saved = False

    def save(self):
        self.saved = True


class _CrashingStore:
    def ingest(self, events, engine, config):
        config.model_params["partial/model"] = {"total_params": 1.0}
        raise RuntimeError("boom")


class _OkStore:
    def ingest(self, events, engine, config):
        config.model_params["org/model"] = {"total_params": 7.0}
        return 3


class _NoopStore:
    def ingest(self, events, engine, config):
        return 0


def test_ingest_and_save_does_not_save_config_when_ingest_raises():
    config = _FakeConfig()
    with pytest.raises(RuntimeError):
        ingest_and_save(_CrashingStore(), [], engine=None, config=config)
    assert config.saved is False


def test_ingest_and_save_saves_config_when_ingest_succeeds_and_changed():
    config = _FakeConfig()
    n = ingest_and_save(_OkStore(), [], engine=None, config=config)
    assert n == 3
    assert config.saved is True


def test_ingest_and_save_skips_save_when_config_unchanged():
    config = _FakeConfig()
    n = ingest_and_save(_NoopStore(), [], engine=None, config=config)
    assert n == 0
    assert config.saved is False


def test_ingest_applies_persisted_resolution_before_calculation(tmp_path):
    config = Config(model_resolutions={"opencode/gpt-5.6-terra": {
        "route": "openai", "model": "gpt-5.6-terra",
    }})
    store = SQLiteStore(str(tmp_path / "footprint.db"))

    store.ingest([_unknown_opencode_gpt_event()], _engine(), config)

    row = store.conn.execute(
        "SELECT route, model_raw, model_canonical FROM events"
    ).fetchone()
    assert tuple(row) == ("openai", "gpt-5.6-terra", "gpt-5.6-terra")


def test_ingest_keeps_collector_confirmed_route_when_resolution_matches(tmp_path):
    config = Config(model_resolutions={"opencode/gpt-5.6-terra": {
        "route": "openai", "model": "gpt-5.6-terra",
    }})
    store = SQLiteStore(str(tmp_path / "footprint.db"))

    store.ingest([_unknown_opencode_gpt_event(route="local")], _engine(), config)

    row = store.conn.execute(
        "SELECT route, model_canonical FROM events"
    ).fetchone()
    assert tuple(row) == ("local", "")
