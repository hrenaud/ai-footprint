import sys
import types
import pytest
from agent_carbon.config import Config
from agent_carbon.impact.params import ModelParamsResolver


def _fake_hf(total, monkeypatch):
    """Injecte un faux module huggingface_hub avec model_info()."""
    mod = types.ModuleType("huggingface_hub")
    info = types.SimpleNamespace(safetensors=types.SimpleNamespace(total=total))
    mod.model_info = lambda repo_id, **kw: info
    monkeypatch.setitem(sys.modules, "huggingface_hub", mod)


def test_huggingface_dense_sets_active_equals_total(monkeypatch):
    _fake_hf(7_000_000_000, monkeypatch)
    cfg = Config()
    r = ModelParamsResolver(cfg)
    res = r.resolve("ollama", "Qwen/Qwen2.5-7B")
    assert res.source == "huggingface"
    assert res.active == res.total == 7_000_000_000
    # mis en cache
    assert "ollama/Qwen/Qwen2.5-7B" in cfg.model_params


def test_huggingface_network_error_returns_none(monkeypatch):
    mod = types.ModuleType("huggingface_hub")
    def boom(repo_id, **kw):
        raise OSError("offline")
    mod.model_info = boom
    monkeypatch.setitem(sys.modules, "huggingface_hub", mod)
    r = ModelParamsResolver(Config())
    assert r.resolve("ollama", "whatever") is None


def test_huggingface_missing_lib_returns_none(monkeypatch):
    monkeypatch.setitem(sys.modules, "huggingface_hub", None)
    r = ModelParamsResolver(Config())
    assert r.resolve("ollama", "whatever") is None
