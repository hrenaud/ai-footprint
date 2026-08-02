import sqlite3

from ai_footprint.store.db import SQLiteStore


_LEGACY_EVENTS = """
CREATE TABLE events (
  session_id TEXT, msg_id TEXT, provider TEXT, model TEXT,
  input_tokens INTEGER, output_tokens INTEGER,
  cache_creation_tokens INTEGER, cache_read_tokens INTEGER,
  timestamp TEXT, project TEXT,
  active_seconds REAL DEFAULT 0,
  client TEXT DEFAULT '',
  PRIMARY KEY (session_id, msg_id)
)
"""


def legacy_store_with_events(tmp_path, events):
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.execute(_LEGACY_EVENTS)
    conn.executemany(
        "INSERT INTO events (session_id, msg_id, provider, model, input_tokens, "
        "output_tokens, cache_creation_tokens, cache_read_tokens, timestamp, project) "
        "VALUES (?, ?, ?, ?, 1, 2, 0, 0, '2026-01-01T00:00:00Z', 'project')",
        events,
    )
    conn.commit()
    conn.close()
    return path


def test_legacy_provider_moves_to_route_hint_without_confirming_route(tmp_path):
    path = legacy_store_with_events(tmp_path, [("s", "m", "anthropic", "Qwen/Qwen3")])

    migrated = SQLiteStore(str(path)).conn.execute(
        "SELECT model_raw, route_hint, route, model_canonical FROM events"
    ).fetchone()

    assert tuple(migrated) == ("Qwen/Qwen3", "anthropic", "local", "")


def test_historical_correction_is_applied_once(tmp_path):
    path = legacy_store_with_events(tmp_path, [
        ("s", "claude", "legacy", "claude-opus"),
        ("s", "chatgpt", "legacy", "ChatGPT-4o"),
        ("s", "router", "legacy", "openrouter/free"),
        ("s", "qwen", "legacy", "Qwen/Qwen3"),
    ])

    first = SQLiteStore(str(path))
    assert [tuple(row) for row in first.conn.execute(
        "SELECT model_raw, route_hint, route FROM events ORDER BY msg_id"
    )] == [
        ("ChatGPT-4o", "legacy", "openai"),
        ("claude-opus", "legacy", "anthropic"),
        ("Qwen/Qwen3", "legacy", "local"),
        ("openrouter/free", "legacy", "openrouter"),
    ]
    first.conn.close()

    second = SQLiteStore(str(path))
    assert [tuple(row) for row in second.conn.execute(
        "SELECT model_raw, route_hint, route FROM events ORDER BY msg_id"
    )] == [
        ("ChatGPT-4o", "legacy", "openai"),
        ("claude-opus", "legacy", "anthropic"),
        ("Qwen/Qwen3", "legacy", "local"),
        ("openrouter/free", "legacy", "openrouter"),
    ]


def test_resolution_changes_only_selected_session(tmp_path):
    store = SQLiteStore(str(tmp_path / "current.db"))
    store.conn.executemany(
        "INSERT INTO events (session_id, msg_id, provider, model, input_tokens, "
        "output_tokens, cache_creation_tokens, cache_read_tokens, timestamp, project, "
        "model_raw, route_hint, route, model_canonical) "
        "VALUES (?, ?, '', '', 1, 2, 0, 0, '2026-01-01T00:00:00+00:00', 'p', ?, '', 'unknown', '')",
        [("local-session", "m1", "Qwen/Qwen3"), ("router-session", "m2", "Qwen/Qwen3")],
    )
    store.conn.commit()

    store.resolve_events(
        session_id="local-session", route="local", model_canonical="Qwen/Qwen3-8B"
    )

    routes = dict(store.conn.execute("SELECT session_id, route FROM events"))
    assert routes == {"local-session": "local", "router-session": "unknown"}


def test_resolution_changes_only_selected_date_range(tmp_path):
    store = SQLiteStore(str(tmp_path / "current.db"))
    store.conn.executemany(
        "INSERT INTO events (session_id, msg_id, provider, model, input_tokens, "
        "output_tokens, cache_creation_tokens, cache_read_tokens, timestamp, project, "
        "model_raw, route_hint, route, model_canonical) "
        "VALUES ('s', ?, '', '', 1, 2, 0, 0, ?, 'p', 'Qwen/Qwen3', '', 'unknown', '')",
        [("before", "2026-01-01T00:00:00+00:00"), ("inside", "2026-02-01T00:00:00+00:00")],
    )
    store.conn.commit()

    store.resolve_events(
        since="2026-02-01T00:00:00+00:00",
        until="2026-02-01T23:59:59+00:00",
        route="openrouter",
        model_canonical="Qwen/Qwen3-8B",
    )

    routes = dict(store.conn.execute("SELECT msg_id, route FROM events"))
    assert routes == {"before": "unknown", "inside": "openrouter"}
