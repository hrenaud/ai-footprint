import pytest

from ai_footprint.models import InferenceEvent


def test_event_defaults_to_unknown_route():
    event = InferenceEvent(client="claude-code", model_raw="Qwen/Qwen3")

    assert event.route == "unknown"
    assert event.model_canonical == ""


def test_legacy_construction_preserves_event_fields():
    keyword_event = InferenceEvent(
        provider="anthropic",
        model="claude-opus-4-8",
        input_tokens=100,
        output_tokens=200,
        cache_creation_tokens=30,
        cache_read_tokens=40,
        timestamp="2026-08-02T12:00:00Z",
        project="project",
        session_id="session",
        msg_id="message",
    )
    positional_event = InferenceEvent(
        "anthropic", "claude-opus-4-8", 100, 200, 30, 40,
        "2026-08-02T12:00:00Z", "project", "session", "message",
    )

    for event in (keyword_event, positional_event):
        assert event.provider == "anthropic"
        assert event.model == "claude-opus-4-8"
        assert event.input_tokens == 100
        assert event.output_tokens == 200
        assert event.cache_creation_tokens == 30
        assert event.cache_read_tokens == 40
        assert event.timestamp == "2026-08-02T12:00:00Z"
        assert event.project == "project"
        assert event.session_id == "session"
        assert event.msg_id == "message"
        assert event.route == "unknown"


def test_event_rejects_unknown_route():
    with pytest.raises(ValueError, match="Unsupported route"):
        InferenceEvent(client="claude-code", model_raw="Qwen/Qwen3", route="invalid")
