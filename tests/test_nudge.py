from datetime import datetime, timedelta, timezone

from ai_footprint.cache import save_json_cache
from ai_footprint.config import Config
from ai_footprint.impact.engine import EcoLogitsEngine
from ai_footprint.impact.resolver import ModelResolver
from ai_footprint.models import InferenceEvent
from ai_footprint.nudge import (
    RESOLVE_NUDGE_TTL,
    build_claude_hook_output,
    check_self_update,
    check_uncovered_batch,
    mark_batch_prompted,
    reset_prompted_keys,
)
from ai_footprint.store.db import SQLiteStore


def _engine():
    return EcoLogitsEngine(ModelResolver({}))


def _store_with_uncovered(db_path, keys):
    store = SQLiteStore(db_path)
    events = [
        InferenceEvent("ollama", model, 100, 200, 0, 0,
                        f"2026-06-27T10:00:0{i}.000Z", "p", "s", f"u{i}")
        for i, (provider, model) in enumerate(keys)
    ]
    store.ingest(events, _engine(), Config(electricity_mix_zone="FRA"))
    return store


# --- check_self_update ---

def test_check_self_update_none_when_up_to_date(tmp_path, monkeypatch):
    import ai_footprint.nudge as nudge_mod
    monkeypatch.setattr(nudge_mod, "_latest_github_tag", lambda: "1.2.1")
    cache_path = tmp_path / "nudge-cache.json"
    result = check_self_update(Config(), cache_path=cache_path, current_version="1.2.1")
    assert result is None


def test_check_self_update_returns_current_and_latest_when_newer(tmp_path, monkeypatch):
    import ai_footprint.nudge as nudge_mod
    monkeypatch.setattr(nudge_mod, "_latest_github_tag", lambda: "1.3.0")
    cache_path = tmp_path / "nudge-cache.json"
    result = check_self_update(Config(), cache_path=cache_path, current_version="1.2.1")
    assert result == {"current": "1.2.1", "latest": "1.3.0"}


def test_check_self_update_none_when_network_unavailable(tmp_path, monkeypatch):
    import ai_footprint.nudge as nudge_mod
    monkeypatch.setattr(nudge_mod, "_latest_github_tag", lambda: None)
    cache_path = tmp_path / "nudge-cache.json"
    result = check_self_update(Config(), cache_path=cache_path, current_version="1.2.1")
    assert result is None


def test_check_self_update_throttled_reuses_cache(tmp_path, monkeypatch):
    import ai_footprint.nudge as nudge_mod
    calls = []
    monkeypatch.setattr(nudge_mod, "_latest_github_tag", lambda: calls.append(1) or "1.3.0")
    cache_path = tmp_path / "nudge-cache.json"
    check_self_update(Config(), cache_path=cache_path, current_version="1.2.1")
    check_self_update(Config(), cache_path=cache_path, current_version="1.2.1")
    assert len(calls) == 1


def test_check_self_update_refreshes_after_ttl(tmp_path, monkeypatch):
    import ai_footprint.nudge as nudge_mod
    from ai_footprint.cache import save_json_cache
    monkeypatch.setattr(nudge_mod, "_latest_github_tag", lambda: "1.3.0")
    cache_path = tmp_path / "nudge-cache.json"
    stale = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    save_json_cache(cache_path, self_update_checked_at=stale, self_update_latest="1.2.9")
    result = check_self_update(Config(), cache_path=cache_path, current_version="1.2.1")
    assert result == {"current": "1.2.1", "latest": "1.3.0"}


# --- check_uncovered_batch ---

def test_check_uncovered_batch_lists_all_when_none_prompted(tmp_path):
    store = _store_with_uncovered(str(tmp_path / "c.db"), [("ollama", "x:y")])
    assert check_uncovered_batch(store, Config()) == ["ollama/x:y"]


def test_check_uncovered_batch_excludes_already_prompted(tmp_path):
    store = _store_with_uncovered(str(tmp_path / "c.db"), [("ollama", "x:y")])
    config = Config(resolve_prompt_state={"prompted_keys": ["ollama/x:y"]})
    assert check_uncovered_batch(store, config) == []


def test_check_uncovered_batch_reproposes_new_model_not_in_batch(tmp_path):
    store = _store_with_uncovered(
        str(tmp_path / "c.db"), [("ollama", "x:y"), ("ollama", "z:w")]
    )
    config = Config(resolve_prompt_state={"prompted_keys": ["ollama/x:y"]})
    assert check_uncovered_batch(store, config) == ["ollama/z:w"]


def test_check_uncovered_batch_not_throttled_when_no_cache_path(tmp_path):
    store = _store_with_uncovered(str(tmp_path / "c.db"), [("ollama", "x:y")])
    assert check_uncovered_batch(store, Config()) == ["ollama/x:y"]
    assert check_uncovered_batch(store, Config()) == ["ollama/x:y"]


def test_check_uncovered_batch_throttled_when_recently_shown(tmp_path):
    store = _store_with_uncovered(str(tmp_path / "c.db"), [("ollama", "x:y")])
    cache_path = tmp_path / "nudge-cache.json"
    now = datetime.now(timezone.utc)
    save_json_cache(cache_path, resolve_nudge_shown_at=now.isoformat())
    assert check_uncovered_batch(store, Config(), cache_path=cache_path, now=now) == []


def test_check_uncovered_batch_shows_again_after_ttl(tmp_path):
    store = _store_with_uncovered(str(tmp_path / "c.db"), [("ollama", "x:y")])
    cache_path = tmp_path / "nudge-cache.json"
    stale = (datetime.now(timezone.utc) - RESOLVE_NUDGE_TTL - timedelta(hours=1)).isoformat()
    save_json_cache(cache_path, resolve_nudge_shown_at=stale)
    assert check_uncovered_batch(store, Config(), cache_path=cache_path) == ["ollama/x:y"]


def test_check_uncovered_batch_records_shown_at_on_success(tmp_path):
    store = _store_with_uncovered(str(tmp_path / "c.db"), [("ollama", "x:y")])
    cache_path = tmp_path / "nudge-cache.json"
    now = datetime.now(timezone.utc)
    check_uncovered_batch(store, Config(), cache_path=cache_path, now=now)
    from ai_footprint.cache import load_json_cache
    assert load_json_cache(cache_path)["resolve_nudge_shown_at"] == now.isoformat()


def test_check_uncovered_batch_no_throttle_write_when_nothing_new(tmp_path):
    store = _store_with_uncovered(str(tmp_path / "c.db"), [("ollama", "x:y")])
    cache_path = tmp_path / "nudge-cache.json"
    config = Config(resolve_prompt_state={"prompted_keys": ["ollama/x:y"]})
    assert check_uncovered_batch(store, config, cache_path=cache_path) == []
    from ai_footprint.cache import load_json_cache
    assert load_json_cache(cache_path) == {}


# --- mark_batch_prompted ---

def test_mark_batch_prompted_persists_current_uncovered_keys(tmp_path):
    store = _store_with_uncovered(str(tmp_path / "c.db"), [("ollama", "x:y")])
    config = Config()
    mark_batch_prompted(config, store)
    assert config.resolve_prompt_state["prompted_keys"] == ["ollama/x:y"]


def test_mark_batch_prompted_merges_with_existing_prompted_keys(tmp_path):
    store = _store_with_uncovered(str(tmp_path / "c.db"), [("ollama", "z:w")])
    config = Config(resolve_prompt_state={"prompted_keys": ["ollama/x:y"]})
    mark_batch_prompted(config, store)
    assert config.resolve_prompt_state["prompted_keys"] == ["ollama/x:y", "ollama/z:w"]


# --- reset_prompted_keys ---

def test_reset_prompted_keys_clears_existing_keys(tmp_path):
    config = Config(resolve_prompt_state={"prompted_keys": ["ollama/x:y", "ollama/z:w"]})
    reset_prompted_keys(config)
    assert config.resolve_prompt_state["prompted_keys"] == []


# --- build_claude_hook_output ---

def test_build_claude_hook_output_none_when_nothing_to_report():
    assert build_claude_hook_output(None, []) is None


def test_build_claude_hook_output_mentions_update():
    output = build_claude_hook_output({"current": "1.2.1", "latest": "1.3.0"}, [])
    assert output["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "1.2.1" in output["hookSpecificOutput"]["additionalContext"]
    assert "1.3.0" in output["hookSpecificOutput"]["additionalContext"]
    assert "reset-prompted" in output["hookSpecificOutput"]["additionalContext"]


def test_build_claude_hook_output_mentions_uncovered_models():
    output = build_claude_hook_output(None, ["ollama/x:y"])
    assert "ollama/x:y" in output["hookSpecificOutput"]["additionalContext"]


def test_build_claude_hook_output_mentions_both_when_combined():
    output = build_claude_hook_output(
        {"current": "1.2.1", "latest": "1.3.0"}, ["ollama/x:y"]
    )
    context = output["hookSpecificOutput"]["additionalContext"]
    assert "1.2.1" in context
    assert "1.3.0" in context
    assert "ollama/x:y" in context
