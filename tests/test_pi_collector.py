import os
import tempfile
from pathlib import Path

from ai_footprint.collectors.pi import PiCollector

FIXTURES = Path(__file__).parent / "fixtures" / "pi"


def test_parses_only_assistant_messages_with_usage():
    # la ligne session, la ligne user et la ligne model_change sont ignorées
    events = list(PiCollector(str(FIXTURES / "pi-sample.jsonl")).collect())
    assert len(events) == 2


def test_event_fields_mapped_from_real_structure():
    events = {e.msg_id: e for e in PiCollector(str(FIXTURES / "pi-sample.jsonl")).collect()}
    e = events["u1"]
    assert e.provider == "anthropic"
    assert e.model == "claude-opus-4-8"
    assert e.input_tokens == 8427
    assert e.output_tokens == 287
    assert e.cache_read_tokens == 8020
    assert e.cache_creation_tokens == 7052
    assert e.project == "projA"          # basename du cwd de l'en-tête session
    assert e.session_id == "sess-A"      # id de l'en-tête session
    assert e.client == "pi"


def test_provider_and_model_vary_per_message():
    # chaque event porte son propre provider/model (session multi-modèle)
    events = {e.msg_id: e for e in PiCollector(str(FIXTURES / "pi-sample.jsonl")).collect()}
    e = events["u2"]
    assert e.provider == "lm-studios"
    assert e.model == "qwen/qwen3.6-35b-a3b"


def test_active_seconds_from_timestamp_delta():
    # delta de 30 s entre le message user et la réponse assistant
    events = list(PiCollector(str(FIXTURES / "pi-active.jsonl")).collect())
    assert len(events) == 1
    assert abs(events[0].active_seconds - 30.0) < 0.01


def test_collect_from_single_file():
    f = FIXTURES / "pi-sample.jsonl"
    events = list(PiCollector(str(f)).collect())
    assert len(events) == 2


def test_collect_from_directory_recursive():
    events = list(PiCollector(str(FIXTURES)).collect())
    msg_ids = {e.msg_id for e in events}
    assert {"u1", "u2", "a1"}.issubset(msg_ids)


def test_ignores_missing_and_malformed_files():
    events = list(PiCollector("/non/existent/dir").collect())
    assert events == []

    fd, malforme = tempfile.mkstemp(suffix=".jsonl")
    os.write(fd, b"not json {{{\n")
    os.close(fd)
    events = list(PiCollector(malforme).collect())
    assert events == []
    os.unlink(malforme)


def test_missing_cwd_falls_back_to_unknown_project():
    fd, f = tempfile.mkstemp(suffix=".jsonl")
    os.write(fd, (
        '{"type":"session","version":3,"id":"s1","timestamp":"2026-06-27T10:00:00.000Z"}\n'
        '{"type":"message","id":"m1","timestamp":"2026-06-27T10:00:01.000Z",'
        '"message":{"role":"assistant","provider":"anthropic","model":"x",'
        '"usage":{"input":1,"output":1,"cacheRead":0,"cacheWrite":0}}}\n'
    ).encode())
    os.close(fd)
    events = list(PiCollector(f).collect())
    assert len(events) == 1
    assert events[0].project == "unknown"
    os.unlink(f)
