from pathlib import Path
from unittest.mock import Mock

from ai_footprint.collectors.claude_code import ClaudeCodeCollector
from ai_footprint.models import InferenceEvent

FIXTURES = Path(__file__).parent / "fixtures"


def test_parses_only_assistant_messages_with_usage():
    events = list(ClaudeCodeCollector(str(FIXTURES / "sample.jsonl")).collect())
    assert len(events) == 2  # la ligne user est ignorée


def test_event_fields_mapped_from_real_structure():
    events = {e.msg_id: e for e in ClaudeCodeCollector(str(FIXTURES)).collect()}
    e = events["u1"]
    assert e.provider == "anthropic"
    assert e.model == "claude-opus-4-8"
    assert e.model_raw == "claude-opus-4-8"
    assert e.route_hint == "anthropic"
    assert e.route == "unknown"
    assert e.input_tokens == 8427
    assert e.output_tokens == 287
    assert e.cache_read_tokens == 8020
    assert e.cache_creation_tokens == 7052
    assert e.project == "projA"          # basename de cwd
    assert e.session_id == "sess-A"
    assert e.client == "claude-code"     # outil client à l'origine de l'event


def test_active_seconds_from_timestamp_delta():
    # delta de 30 s entre le message user et la réponse assistant
    events = list(ClaudeCodeCollector(str(FIXTURES / "active.jsonl")).collect())
    assert len(events) == 1
    assert abs(events[0].active_seconds - 30.0) < 0.01


def test_collect_from_single_file():
    # le collecteur accepte un fichier unique (transcript de la session courante)
    f = FIXTURES / "sample.jsonl"
    events = list(ClaudeCodeCollector(str(f)).collect())
    assert len(events) == 2  # les 2 messages assistant du fichier


def test_preserves_model_for_each_assistant_response(tmp_path):
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(
        '{"type":"assistant","timestamp":"2026-07-31T10:00:00Z","cwd":"/x/proj","sessionId":"s1","uuid":"m1","message":{"model":"model-a","usage":{"input_tokens":10,"output_tokens":1}}}\n'
        '{"type":"assistant","timestamp":"2026-07-31T10:00:01Z","cwd":"/x/proj","sessionId":"s1","uuid":"m2","message":{"model":"model-b","usage":{"input_tokens":20,"output_tokens":2}}}\n'
    )

    events = list(ClaudeCodeCollector(str(transcript)).collect())

    assert [event.model for event in events] == ["model-a", "model-b"]


def test_claude_qwen_stays_unknown_route(tmp_path, monkeypatch):
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(
        '{"type":"assistant","message":{"model":"Qwen/Qwen3",'
        '"usage":{"input_tokens":1,"output_tokens":1}}}\n'
    )

    event_factory = Mock(side_effect=InferenceEvent)
    monkeypatch.setattr("ai_footprint.collectors.claude_code.InferenceEvent", event_factory)

    event = next(ClaudeCodeCollector(str(transcript)).collect())

    assert (event.client, event.model_raw, event.route_hint, event.route) == (
        "claude-code", "Qwen/Qwen3", "anthropic", "unknown"
    )
    assert event_factory.call_args.kwargs == {
        "client": "claude-code",
        "model_raw": "Qwen/Qwen3",
        "route_hint": "anthropic",
        "input_tokens": 1,
        "output_tokens": 1,
        "cache_creation_tokens": 0,
        "cache_read_tokens": 0,
        "timestamp": "",
        "project": "unknown",
        "session_id": "",
        "msg_id": "",
        "active_seconds": 0.0,
    }


def test_malformed_json_line_is_logged(tmp_path, caplog):
    import logging
    transcript = tmp_path / "session.jsonl"
    transcript.write_text('{"not": "valid json"\nnot json at all\n')
    with caplog.at_level(logging.DEBUG, logger="ai_footprint.collectors.claude_code"):
        list(ClaudeCodeCollector(str(transcript)).collect())
    assert "session.jsonl" in caplog.text or "JSON" in caplog.text
