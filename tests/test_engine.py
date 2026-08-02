from ai_footprint.config import Config
import ai_footprint.impact.engine as engine_mod
from ai_footprint.impact.engine import EcoLogitsEngine, ImpactRecord, CRITERIA
from ai_footprint.impact.resolver import ModelResolver
from ai_footprint.models import InferenceEvent


def _event(model, out=1000, route="anthropic", canonical=None):
    return InferenceEvent(
        "anthropic", model, 100, out, 0, 0,
        "2026-06-27T10:00:00Z", "projA", "s1", "m1",
        route=route, model_canonical=canonical or model,
    )


def test_compute_returns_five_positive_ranges():
    eng = EcoLogitsEngine(ModelResolver({}))
    rec = eng.compute(_event("claude-opus-4-8"), Config())
    assert rec.error is None
    for c in CRITERIA:
        lo, hi = rec.totals[c]
        assert hi >= lo > 0
    assert rec.zone is None
    assert "ecologits=" in rec.methodology_version


def test_unknown_model_yields_error_not_crash():
    eng = EcoLogitsEngine(ModelResolver({}))
    rec = eng.compute(_event("claude-does-not-exist"), Config())
    assert rec.error is not None
    assert rec.totals == {}


def test_unestimated_routes_are_kept_without_calculation():
    eng = EcoLogitsEngine(ModelResolver({}))
    for route in ("openrouter", "custom", "unknown"):
        rec = eng.compute(_event("Qwen/Qwen3", route=route), Config())
        assert rec.error == "route-not-estimated"
        assert rec.totals == {}


def test_openai_uses_confirmed_route_not_legacy_provider():
    eng = EcoLogitsEngine(ModelResolver({}))
    event = InferenceEvent(
        provider="anthropic", model="legacy-name", input_tokens=100,
        output_tokens=1000, timestamp="2026-06-27T10:00:00Z", project="projA",
        session_id="s1", msg_id="m1", route="openai", model_canonical="gpt-4o",
    )
    rec = eng.compute(event, Config())
    assert rec.error is None
    assert rec.model_resolved == "gpt-4o"


def test_alias_is_recorded_in_warnings():
    eng = EcoLogitsEngine(ModelResolver({"claude-x": "claude-opus-4-8"}))
    rec = eng.compute(_event("claude-x"), Config())
    assert rec.error is None
    assert any(w.startswith("alias:") for w in rec.warnings)


def test_openai_registry_miss_uses_prior_sibling(monkeypatch):
    event = InferenceEvent(
        "openai", "gpt-5.6-terra", 10, 20, 0, 0, "2026-08-02T00:00:00Z",
        route="openai", model_canonical="gpt-5.6-terra",
    )
    calls = []
    original = engine_mod.llm_impacts

    def unknown_model_then_gpt_55(**kwargs):
        calls.append(kwargs["model_name"])
        return original(**kwargs)

    monkeypatch.setattr(engine_mod, "llm_impacts", unknown_model_then_gpt_55)
    record = EcoLogitsEngine(ModelResolver({})).compute(event, Config())

    assert record.error is None
    assert record.model_resolved == "gpt-5.6-terra"
    assert calls == ["gpt-5.6-terra", "gpt-5.5"]
    assert "model-source:sibling:openai:gpt-5.5" in record.warnings


def test_unknown_route_never_uses_sibling(monkeypatch):
    event = InferenceEvent(
        "openai", "gpt-5.6-terra", 10, 20, 0, 0, "2026-08-02T00:00:00Z",
        route="unknown",
    )
    monkeypatch.setattr(
        engine_mod,
        "llm_impacts",
        lambda **_: (_ for _ in ()).throw(AssertionError("sibling must not run")),
    )

    assert EcoLogitsEngine(ModelResolver({})).compute(event, Config()).error == "route-not-estimated"


def test_openai_huggingface_mapping_calculates_after_registry_miss():
    config = Config(model_params={"openai/Org/Model": {
        "active": 7.0, "total": 7.0, "arch": "dense", "source": "resolve",
        "hf_repo": "Org/Model",
    }})
    record = EcoLogitsEngine(ModelResolver({})).compute(
        _event("Org/Model", route="openai"), config)

    assert record.error is None
    assert record.model_resolved == "Org/Model"
    assert "model-source:huggingface:Org/Model" in record.warnings


def test_provider_registry_miss_never_looks_up_huggingface_automatically(monkeypatch):
    import ai_footprint.impact.params as params_mod

    monkeypatch.setattr(
        params_mod, "fetch_hf_params",
        lambda _: (_ for _ in ()).throw(AssertionError("HF lookup must not run")),
    )

    record = EcoLogitsEngine(ModelResolver({})).compute(
        _event("Org/Unconfirmed", route="openai"), Config())

    assert record.error == "model-not-registered"


def test_provider_registry_miss_rejects_legacy_automatic_huggingface_cache():
    config = Config(model_params={"openai/Org/Legacy": {
        "active": 7.0, "total": 7.0, "arch": "dense", "source": "huggingface",
    }})

    record = EcoLogitsEngine(ModelResolver({})).compute(
        _event("Org/Legacy", route="openai"), config)

    assert record.error == "model-not-registered"
    assert record.totals == {}
