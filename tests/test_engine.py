from ai_footprint.config import Config
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
