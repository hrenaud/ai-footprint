import io
import json
from contextlib import redirect_stdout

from ai_footprint import __main__ as cli
from ai_footprint import nudge as nudge_mod
from ai_footprint.config import Config
from ai_footprint.impact.engine import EcoLogitsEngine
from ai_footprint.impact.resolver import ModelResolver
from ai_footprint.models import InferenceEvent
from ai_footprint.store.db import SQLiteStore


def _engine():
    return EcoLogitsEngine(ModelResolver({}))


def _patch_config(monkeypatch, path):
    original_load = Config.load.__func__
    original_save = Config.save

    def load(cls, p=None):
        return original_load(cls, p or path)

    def save(self, p=None):
        return original_save(self, p or path)

    monkeypatch.setattr(Config, "load", classmethod(load))
    monkeypatch.setattr(Config, "save", save)


def _ingest_uncovered_event(db):
    store = SQLiteStore(db)
    store.ingest(
        [InferenceEvent("ollama", "x:y", 100, 200, 0, 0,
                         "2026-06-27T10:00:00.000Z", "p", "s", "u1")],
        _engine(),
        Config(electricity_mix_zone="FRA"),
    )
    return store


def _no_update(monkeypatch):
    monkeypatch.setattr(nudge_mod, "check_self_update",
                         lambda config, cache_path: None)


def test_nudge_json_reports_new_uncovered(tmp_path, monkeypatch):
    db = str(tmp_path / "c.db")
    _patch_config(monkeypatch, str(tmp_path / "config.json"))
    _no_update(monkeypatch)
    _ingest_uncovered_event(db)

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cli.main(["nudge", "--db", db, "--json"])

    assert rc == 0
    data = json.loads(buf.getvalue())
    assert data == {"update_available": None, "uncovered_new": ["ollama/x:y"]}


def test_nudge_json_empty_lists_when_nothing_uncovered(tmp_path, monkeypatch):
    db = str(tmp_path / "c.db")
    _patch_config(monkeypatch, str(tmp_path / "config.json"))
    _no_update(monkeypatch)
    SQLiteStore(db)

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cli.main(["nudge", "--db", db, "--json"])

    assert rc == 0
    assert json.loads(buf.getvalue()) == {"update_available": None, "uncovered_new": []}


def test_nudge_mark_prompted_closes_batch(tmp_path, monkeypatch):
    db = str(tmp_path / "c.db")
    config_path = str(tmp_path / "config.json")
    _patch_config(monkeypatch, config_path)
    _no_update(monkeypatch)
    _ingest_uncovered_event(db)

    with redirect_stdout(io.StringIO()):
        rc = cli.main(["nudge", "--db", db, "--mark-prompted"])
    assert rc == 0
    assert Config.load(config_path).resolve_prompt_state["prompted_keys"] == ["ollama/x:y"]

    buf = io.StringIO()
    with redirect_stdout(buf):
        cli.main(["nudge", "--db", db, "--json"])
    assert json.loads(buf.getvalue())["uncovered_new"] == []


def test_nudge_claude_hook_empty_stdout_when_nothing_to_report(tmp_path, monkeypatch):
    db = str(tmp_path / "c.db")
    _patch_config(monkeypatch, str(tmp_path / "config.json"))
    _no_update(monkeypatch)
    SQLiteStore(db)

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cli.main(["nudge", "--db", db, "--claude-hook"])

    assert rc == 0
    assert buf.getvalue() == ""


def test_nudge_claude_hook_reports_uncovered(tmp_path, monkeypatch):
    db = str(tmp_path / "c.db")
    _patch_config(monkeypatch, str(tmp_path / "config.json"))
    _no_update(monkeypatch)
    _ingest_uncovered_event(db)

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cli.main(["nudge", "--db", db, "--claude-hook"])

    assert rc == 0
    envelope = json.loads(buf.getvalue())
    assert envelope["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "ollama/x:y" in envelope["hookSpecificOutput"]["additionalContext"]
