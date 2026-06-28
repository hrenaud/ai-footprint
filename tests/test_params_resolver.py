from agent_carbon.config import Config
from agent_carbon.impact.params import ModelParamsResolver, ParamsResult


def test_registry_tier_resolves_known_model():
    r = ModelParamsResolver(Config())
    # gpt-4o-mini est dans le registre EcoLogits 0.11.0
    res = r.resolve("openai", "gpt-4o-mini")
    assert isinstance(res, ParamsResult)
    assert res.source == "registry"
    assert res.total > 0


def test_cache_tier_resolves_declared_model():
    cfg = Config(model_params={
        "ollama/qwen2.5:7b": {"active": 7e9, "total": 7e9,
                              "arch": "dense", "source": "user"}})
    r = ModelParamsResolver(cfg)
    res = r.resolve("ollama", "qwen2.5:7b")
    assert res.source == "user"
    assert res.total == 7e9
    assert res.active == 7e9


def test_unknown_model_returns_none():
    r = ModelParamsResolver(Config())
    assert r.resolve("ollama", "modele-inexistant-xyz") is None
