import io
from contextlib import redirect_stdout
from agent_carbon.store.db import SQLiteStore
from agent_carbon import __main__ as cli


def test_models_command_lists_pending(tmp_path, monkeypatch):
    db = str(tmp_path / "c.db")
    s = SQLiteStore(db)
    s.add_pending("ollama", "qwen2.5:7b", "2026-06-29T10:00:00Z")
    # stdin non-TTY → pas de question, simple listing
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cli.main(["models", "--db", db])
    out = buf.getvalue()
    assert rc == 0
    assert "qwen2.5:7b" in out
