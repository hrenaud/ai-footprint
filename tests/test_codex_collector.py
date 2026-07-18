import os
import tempfile
from pathlib import Path

from ai_footprint.collectors.codex import CodexCollector

FIXTURES = Path(__file__).parent / "fixtures" / "codex"


def test_parses_only_token_count_events_with_last_usage():
    # task_started, turn_context, task_complete et le token_count final
    # (last_token_usage=null) sont ignorés
    events = list(CodexCollector(str(FIXTURES / "codex-sample.jsonl")).collect())
    assert len(events) == 2


def test_event_fields_mapped_from_real_structure():
    events = list(CodexCollector(str(FIXTURES / "codex-sample.jsonl")).collect())
    e = events[0]
    assert e.provider == "openai"
    assert e.model == "gpt-5.5"
    assert e.input_tokens == 17242 - 10496
    assert e.output_tokens == 117
    assert e.cache_read_tokens == 10496
    assert e.cache_creation_tokens == 0
    assert e.project == "projA"
    assert e.session_id == "sess-A"
    assert e.client == "codex"


def test_model_varies_per_turn():
    events = list(CodexCollector(str(FIXTURES / "codex-sample.jsonl")).collect())
    assert events[0].model == "gpt-5.5"
    assert events[1].model == "gpt-5.1-codex-mini"
    assert events[1].input_tokens == 18779 - 10496
    assert events[1].output_tokens == 15
    assert events[1].cache_read_tokens == 10496


def test_active_seconds_from_timestamp_delta():
    # delta de 30 s entre le turn_context et le token_count
    events = list(CodexCollector(str(FIXTURES / "codex-active.jsonl")).collect())
    assert len(events) == 1
    assert abs(events[0].active_seconds - 30.0) < 0.01


def test_collect_from_single_file():
    f = FIXTURES / "codex-sample.jsonl"
    events = list(CodexCollector(str(f)).collect())
    assert len(events) == 2


def test_collect_from_directory_recursive():
    events = list(CodexCollector(str(FIXTURES)).collect())
    assert len(events) >= 3


def test_ignores_missing_and_malformed_files():
    events = list(CodexCollector("/non/existent/dir").collect())
    assert events == []

    fd, malforme = tempfile.mkstemp(suffix=".jsonl")
    os.write(fd, b"not json {{{\n")
    os.close(fd)
    events = list(CodexCollector(malforme).collect())
    assert events == []
    os.unlink(malforme)


def test_missing_cwd_falls_back_to_unknown_project():
    fd, f = tempfile.mkstemp(suffix=".jsonl")
    os.write(fd, (
        '{"timestamp":"2026-07-18T10:00:00.000Z","type":"session_meta",'
        '"payload":{"id":"s1","model_provider":"openai"}}\n'
        '{"timestamp":"2026-07-18T10:00:01.000Z","type":"turn_context",'
        '"payload":{"turn_id":"t1","model":"gpt-5.5"}}\n'
        '{"timestamp":"2026-07-18T10:00:02.000Z","type":"event_msg","payload":'
        '{"type":"token_count","info":{"last_token_usage":'
        '{"input_tokens":1,"cached_input_tokens":0,"output_tokens":1}}}}\n'
    ).encode())
    os.close(fd)
    events = list(CodexCollector(f).collect())
    assert len(events) == 1
    assert events[0].project == "unknown"
    os.unlink(f)


def test_non_dict_json_lines_skipped_without_crashing():
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.write(fd, b'[1, 2, 3]\n"just a string"\n')
    os.close(fd)
    try:
        events = list(CodexCollector(path).collect())
        assert events == []
    finally:
        os.remove(path)
