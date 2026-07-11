from ai_footprint.config import Config
from ai_footprint.impact.params import ModelParamsResolver, ParamsResult


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


def test_cache_tier_propagates_warnings():
    """Un mapping manuel (ex. params extrapolés d'une version sœur) porte ses
    warnings jusqu'au ParamsResult, pour être signalé en aval (report/statusline)."""
    cfg = Config(model_params={
        "anthropic/claude-sonnet-5": {
            "active": 88.0, "total": 440.0, "arch": "moe", "source": "extrapolated",
            "warnings": ["params-extrapolated-anthropic:claude-sonnet-4-6"]}})
    r = ModelParamsResolver(cfg)
    res = r.resolve("anthropic", "claude-sonnet-5")
    assert res.source == "extrapolated"
    assert res.warnings == ["params-extrapolated-anthropic:claude-sonnet-4-6"]


def test_registry_range_value_resolved_as_mean():
    """Teste que les paramètres RangeValue du registre sont résolus par moyenne."""
    r = ModelParamsResolver(Config())
    # mistralai/devstral-medium-latest a architecture.parameters = RangeValue(70, 120)
    res = r.resolve("mistralai", "devstral-medium-latest")
    assert isinstance(res, ParamsResult)
    assert res.source == "registry"
    assert res.active == 95.0  # (70 + 120) / 2
    assert res.total == 95.0
    assert res.arch == "dense"
