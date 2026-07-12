from datetime import datetime, timedelta, timezone

from ai_footprint.cache import load_json_cache, save_json_cache, should_refresh


def test_load_json_cache_missing_file_returns_empty_dict(tmp_path):
    assert load_json_cache(tmp_path / "missing.json") == {}


def test_load_json_cache_corrupted_file_returns_empty_dict(tmp_path):
    p = tmp_path / "cache.json"
    p.write_text("not json", encoding="utf-8")
    assert load_json_cache(p) == {}


def test_save_json_cache_roundtrips_arbitrary_fields(tmp_path):
    p = tmp_path / "sub" / "cache.json"
    save_json_cache(p, checked_at="2026-07-12T00:00:00+00:00", latest="1.3.0")
    assert load_json_cache(p) == {"checked_at": "2026-07-12T00:00:00+00:00", "latest": "1.3.0"}


def test_should_refresh_true_when_cache_missing():
    assert should_refresh({}, now=datetime.now(timezone.utc), ttl=timedelta(hours=24)) is True


def test_should_refresh_false_when_cache_fresh():
    now = datetime.now(timezone.utc)
    cache = {"checked_at": (now - timedelta(hours=1)).isoformat()}
    assert should_refresh(cache, now=now, ttl=timedelta(hours=24)) is False


def test_should_refresh_true_when_cache_stale():
    now = datetime.now(timezone.utc)
    cache = {"checked_at": (now - timedelta(hours=25)).isoformat()}
    assert should_refresh(cache, now=now, ttl=timedelta(hours=24)) is True


def test_should_refresh_true_when_checked_at_unparseable():
    now = datetime.now(timezone.utc)
    assert should_refresh({"checked_at": "not-a-date"}, now=now, ttl=timedelta(hours=24)) is True


def test_should_refresh_uses_custom_key():
    now = datetime.now(timezone.utc)
    cache = {"self_update_checked_at": (now - timedelta(hours=1)).isoformat()}
    assert should_refresh(cache, now=now, ttl=timedelta(hours=24), key="self_update_checked_at") is False
