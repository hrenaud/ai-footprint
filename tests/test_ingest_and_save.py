import pytest

from ai_footprint.ingest.cli import ingest_and_save


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
