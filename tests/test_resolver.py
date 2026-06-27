from agent_carbon.impact.resolver import ModelResolver


def test_passthrough_when_no_alias():
    r = ModelResolver({})
    assert r.resolve("claude-opus-4-8") == ("claude-opus-4-8", False)


def test_applies_alias():
    r = ModelResolver({"claude-future-9": "claude-opus-4-8"})
    assert r.resolve("claude-future-9") == ("claude-opus-4-8", True)
