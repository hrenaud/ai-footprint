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


def test_sibling_extrapolation_resolves_unknown_recent_model():
    """claude-sonnet-5 est trop récent pour le registre EcoLogits : le palier 4
    doit retrouver claude-sonnet-4-6 (version sœur connue la plus proche) et
    reprendre ses params, avec un warning traçant la provenance."""
    r = ModelParamsResolver(Config())
    res = r.resolve("anthropic", "claude-sonnet-5")
    assert isinstance(res, ParamsResult)
    assert res.source == "extrapolated"
    assert res.warnings == ["params-extrapolated-anthropic:claude-sonnet-4-6"]
    assert res.active == 88.0
    assert res.total == 440.0
    assert res.arch == "moe"


def test_sibling_extrapolation_caches_result():
    """Le résultat extrapolé est mémorisé en cache config (rejoue via le palier
    2 sans re-parcourir le registre), avec ses warnings préservés."""
    cfg = Config()
    r = ModelParamsResolver(cfg)
    r.resolve("anthropic", "claude-sonnet-5")
    entry = cfg.model_params["anthropic/claude-sonnet-5"]
    assert entry["source"] == "extrapolated"
    assert entry["warnings"] == ["params-extrapolated-anthropic:claude-sonnet-4-6"]
    assert entry["active"] == 88.0
    assert entry["total"] == 440.0


def test_registry_supersedes_cached_extrapolation():
    """Si le registre EcoLogits connaît désormais le vrai modèle, il l'emporte
    sur une entrée « extrapolated » restée en cache (bascule automatique,
    sans purge manuelle du cache)."""
    cfg = Config(model_params={
        "openai/gpt-4o-mini": {
            "active": 1.0, "total": 1.0, "arch": "dense", "source": "extrapolated",
            "warnings": ["params-extrapolated-openai:some-old-sibling"]}})
    r = ModelParamsResolver(cfg)
    res = r.resolve("openai", "gpt-4o-mini")
    assert res.source == "registry"
    assert res.warnings == []


def test_sibling_extrapolation_no_sibling_returns_none():
    r = ModelParamsResolver(Config())
    assert r.resolve("anthropic", "claude-quantum-1") is None


def test_sibling_extrapolation_handles_dotted_version():
    """Convention OpenAI (versions à point, ex. gpt-5.5) : le parsing de
    famille/version doit aussi reconnaître ce format, pas seulement les
    versions à tiret façon Anthropic (sonnet-4-6)."""
    r = ModelParamsResolver(Config())
    res = r.resolve("openai", "gpt-5.6-terra")
    assert isinstance(res, ParamsResult)
    assert res.source == "extrapolated"
    assert res.warnings[0].startswith("params-extrapolated-openai:gpt-5.5")
