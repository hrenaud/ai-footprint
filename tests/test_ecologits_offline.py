from ecologits.tracers.utils import llm_impacts

CRITERIA = ("energy", "gwp", "adpe", "pe", "wcf")


def _minmax(criterion):
    v = criterion.value
    return (float(v.min), float(v.max)) if hasattr(v, "min") else (float(v), float(v))


def test_offline_call_returns_five_criteria_for_current_claude_model():
    out = llm_impacts(
        provider="anthropic",
        model_name="claude-opus-4-8",
        output_token_count=1000,
        request_latency=20.0,
        electricity_mix_zone="USA",
    )
    assert out.errors is None
    for name in CRITERIA:
        lo, hi = _minmax(getattr(out, name))
        assert hi >= lo > 0, f"{name} doit être une fourchette positive"
