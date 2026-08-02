import io
import json
import sys
import types
from contextlib import redirect_stdout
from types import SimpleNamespace
from ai_footprint import __main__ as cli
from ai_footprint.config import Config
from ai_footprint.impact.engine import EcoLogitsEngine
from ai_footprint.impact.resolver import ModelResolver
from ai_footprint.models import InferenceEvent
from ai_footprint.store.db import SQLiteStore


def _engine():
    return EcoLogitsEngine(ModelResolver({}))


def _fake_hf(total, monkeypatch):
    import ai_footprint.impact.params as params_mod
    mod = types.ModuleType("huggingface_hub")
    info = types.SimpleNamespace(safetensors=types.SimpleNamespace(total=total))
    mod.model_info = lambda repo_id, **kw: info
    monkeypatch.setattr(params_mod, "huggingface_hub", mod)


def _patch_config(monkeypatch, path):
    original_load = Config.load.__func__
    original_save = Config.save
    def load(cls, p=None):
        return original_load(cls, p or path)
    def save(self, p=None):
        return original_save(self, p or path)
    monkeypatch.setattr(Config, "load", classmethod(load))
    monkeypatch.setattr(Config, "save", save)


def _ingest_error_event(db):
    s = SQLiteStore(db)
    s.ingest([InferenceEvent("ollama", "x:y", 100, 200, 0, 0,
               "2026-06-27T10:00:00.000Z", "p", "s", "u1",
               route="unknown")],
             _engine(), Config(electricity_mix_zone="FRA"))
    return s


def test_resolve_list_json(tmp_path, monkeypatch):
    db = str(tmp_path / "c.db")
    _patch_config(monkeypatch, str(tmp_path / "config.json"))
    _ingest_error_event(db)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cli.main(["resolve", "--db", db, "--list", "--json"])
    assert rc == 0
    data = json.loads(buf.getvalue())
    assert data[0]["model_raw"] == "x:y"
    assert data[0]["session_id"] == "s"
    assert data[0]["tokens"] == 300


def test_resolve_local_session_recomputes_only_selected_events(tmp_path, monkeypatch):
    db = str(tmp_path / "c.db")
    config_path = str(tmp_path / "config.json")
    Config(electricity_mix_zone="FRA").save(config_path)
    _patch_config(monkeypatch, config_path)
    _ingest_error_event(db)
    assert SQLiteStore(db).coverage()["uncovered"] == 1
    _fake_hf(7_000_000_000, monkeypatch)
    with redirect_stdout(io.StringIO()):
        rc = cli.main([
            "resolve", "--db", db, "--session", "s", "--route", "local",
            "--model", "Org/Repo", "--repo", "Org/Repo",
            "--active-params", "3", "--total-params", "7",
        ])
    assert rc == 0
    assert SQLiteStore(db).coverage()["uncovered"] == 0
    reloaded = Config.load(config_path)
    assert reloaded.model_params["local/Org/Repo"]["source"] == "resolve"
    assert reloaded.model_params["local/Org/Repo"]["active"] == 3.0


def test_resolve_rejects_invalid_local_params_without_changing_rows(tmp_path, monkeypatch, capsys):
    db = str(tmp_path / "c.db")
    _patch_config(monkeypatch, str(tmp_path / "config.json"))
    _ingest_error_event(db)
    rc = cli.main([
        "resolve", "--db", db, "--session", "s", "--route", "local",
        "--model", "Org/Repo", "--active-params", "8", "--total-params", "7",
    ])
    assert rc == 2
    assert "active-params: must not exceed total-params" in capsys.readouterr().err
    row = SQLiteStore(db).conn.execute("SELECT route FROM events").fetchone()
    assert row["route"] == "unknown"


def test_resolve_rejects_invalid_route_without_changing_rows(tmp_path, monkeypatch, capsys):
    from ai_footprint.resolve.cli import cmd_resolve

    db = str(tmp_path / "c.db")
    _patch_config(monkeypatch, str(tmp_path / "config.json"))
    _ingest_error_event(db)
    args = SimpleNamespace(
        db=db, since=None, list=False, json=False, set=[], forget=[], recompute=False,
        retry_hf=False, route="invalid", model="Org/Repo", session="s", repo=None,
        active_params=None, total_params=None,
    )
    assert cmd_resolve(args) == 2
    assert "route: must be" in capsys.readouterr().err
    row = SQLiteStore(db).conn.execute("SELECT route FROM events").fetchone()
    assert row["route"] == "unknown"


def test_legacy_mapping_does_not_confirm_an_unknown_route(tmp_path, monkeypatch):
    db = str(tmp_path / "c.db")
    config_path = str(tmp_path / "config.json")
    Config(electricity_mix_zone="FRA").save(config_path)
    _patch_config(monkeypatch, config_path)
    _ingest_error_event(db)
    _fake_hf(7_000_000_000, monkeypatch)
    with redirect_stdout(io.StringIO()):
        cli.main(["resolve", "--db", db, "--set", "ollama/x:y=Org/Repo"])
    assert SQLiteStore(db).coverage()["uncovered"] == 1
    row = SQLiteStore(db).conn.execute("SELECT route FROM events").fetchone()
    assert row["route"] == "unknown"


def test_legacy_mapping_never_confirms_unrelated_unknown_rows(tmp_path, monkeypatch):
    db = str(tmp_path / "c.db")
    config_path = str(tmp_path / "config.json")
    Config(electricity_mix_zone="FRA").save(config_path)
    _patch_config(monkeypatch, config_path)

    # Ingère deux modèles non couverts
    store = SQLiteStore(db)
    store.ingest([
        InferenceEvent("ollama", "ModelA", 100, 200, 0, 0,
                       "2026-06-27T10:00:00.000Z", "p", "s1", "mA1"),
        InferenceEvent("ollama", "ModelA", 100, 200, 0, 0,
                       "2026-06-27T10:01:00.000Z", "p", "s2", "mA2"),
        InferenceEvent("ollama", "ModelB", 100, 200, 0, 0,
                       "2026-06-27T10:02:00.000Z", "p", "s1", "mA2"),
    ], _engine(), Config(electricity_mix_zone="FRA"))
    assert store.coverage()["uncovered"] == 3  # tous en erreur

    # Mock HF pour le --set
    _fake_hf(7_000_000_000, monkeypatch)

    # Legacy mappings do not turn route hints into confirmed routes.
    with redirect_stdout(io.StringIO()):
        cli.main(["resolve", "--db", db, "--set", "ollama/ModelA=Org/RepoA"])
    with redirect_stdout(io.StringIO()):
        cli.main(["resolve", "--db", db, "--set", "ollama/ModelB=Org/RepoB"])
    assert SQLiteStore(db).coverage()["uncovered"] == 3
    assert {row["route"] for row in SQLiteStore(db).conn.execute("SELECT route FROM events")} == {"unknown"}


def test_retry_hf_does_not_estimate_unknown_routes(tmp_path, monkeypatch):
    """No automatic fallback may confirm an unknown route."""
    import json as _json
    from types import SimpleNamespace
    import ai_footprint.impact.params as params_mod
    from ai_footprint.impact.params import ParamsResult
    from ai_footprint.config import Config
    from ai_footprint.resolve.cli import cmd_resolve
    from ai_footprint.store.db import SQLiteStore

    db = str(tmp_path / "t.db")
    store = SQLiteStore(db)
    store.conn.execute(
        "INSERT INTO events (session_id, msg_id, provider, model, input_tokens, output_tokens, "
        "cache_creation_tokens, cache_read_tokens, timestamp, project, active_seconds, client, "
        "model_raw, route_hint) VALUES ('s1','m1','ollama','org/nouveau',1,2,0,0,"
        "'2026-07-02T00:00:00+00:00','p',0,'','org/nouveau','ollama')")
    store.conn.execute(
        "INSERT INTO impacts VALUES ('s1','m1','org/nouveau','WOR','v',"
        "NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,"
        "'{}','[]','model-params-unresolved')")
    store.conn.commit()
    store.conn.close()

    # Config isolée (ne pas toucher ~/.ai-footprint) + HF factice qui réussit
    cfg = Config(electricity_mix_zone="WOR",
                 hf_unresolved={"ollama/org/nouveau": "2026-07-02T00:00:00+00:00"})
    monkeypatch.setattr(Config, "load", classmethod(lambda cls, path=None: cfg))
    monkeypatch.setattr(Config, "save", lambda self, path=None: None)
    monkeypatch.setattr(params_mod, "fetch_hf_params",
                        lambda repo: ParamsResult(active=7.0, total=7.0,
                                                  arch="dense", source="huggingface"))

    args = SimpleNamespace(db=db, since=None, list=False, json=False,
                           set=[], forget=[], recompute=False, retry_hf=True)
    assert cmd_resolve(args) == 0
    assert "ollama/org/nouveau" not in cfg.hf_unresolved  # purgé avant retente
    check = SQLiteStore(db)
    assert check.coverage()["uncovered"] == 1
