from ai_footprint.models import InferenceEvent


def test_event_defaults_to_unknown_route():
    event = InferenceEvent(client="claude-code", model_raw="Qwen/Qwen3")

    assert event.route == "unknown"
    assert event.model_canonical == ""
