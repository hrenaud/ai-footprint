import sys
import types
from ai_footprint.config import Config
from ai_footprint.resolve.cli import parse_mapping, set_mappings, forget, _print_set


def _fake_hf(total, monkeypatch):
    mod = types.ModuleType("huggingface_hub")
    info = types.SimpleNamespace(safetensors=types.SimpleNamespace(total=total))
    mod.model_info = lambda repo_id, **kw: info
    monkeypatch.setitem(sys.modules, "huggingface_hub", mod)


def test_parse_mapping_splits_on_first_equals():
    # Le « : » de la clé (glm:free, à gauche du =) ne doit pas être confondu
    # avec le séparateur d'actif MoE (côté repo, à droite du =).
    assert parse_mapping("anthropic/z-ai/glm:free=zai-org/GLM-4.5-Air") == (
        "anthropic/z-ai/glm:free", "zai-org/GLM-4.5-Air", None)


def test_parse_mapping_extracts_moe_active():
    # parse_mapping reste un découpeur pur : l'actif est renvoyé brut (str),
    # la conversion/validation float vit dans set_mappings.
    assert parse_mapping("nvidia/nemotron=org/repo:12") == (
        "nvidia/nemotron", "org/repo", "12")


def test_set_mappings_moe_uses_active_with_hf_total(monkeypatch):
    _fake_hf(123_600_000_000, monkeypatch)  # total HF = 123,6 Md
    cfg = Config()
    results = set_mappings(cfg, ["nvidia/nemotron=org/repo:12"])
    assert results[0]["ok"] is True
    entry = cfg.model_params["nvidia/nemotron"]
    assert entry["active"] == 12.0
    assert entry["total"] == 123.6
    assert entry["arch"] == "moe"
    assert entry["source"] == "resolve"


def test_print_set_shows_moe_couple(monkeypatch, capsys):
    _fake_hf(123_600_000_000, monkeypatch)
    results = set_mappings(Config(), ["nvidia/nemotron=org/repo:12"])
    _print_set(results, as_json=False)
    out = capsys.readouterr().out
    assert "MoE 12.0 actifs / 123.6 Md" in out


def test_set_mappings_moe_rejects_bad_active(monkeypatch):
    _fake_hf(123_600_000_000, monkeypatch)
    cfg = Config()
    results = set_mappings(cfg, ["nvidia/nemotron=org/repo:abc"])
    assert results[0]["ok"] is False
    assert results[0]["error"] == "active-format"
    assert "nvidia/nemotron" not in cfg.model_params


def test_set_mappings_moe_rejects_active_above_total(monkeypatch):
    _fake_hf(120_000_000_000, monkeypatch)  # total = 120 Md
    cfg = Config()
    results = set_mappings(cfg, ["nvidia/nemotron=org/repo:200"])  # actif > total
    assert results[0]["ok"] is False
    assert results[0]["error"] == "active-gt-total"
    assert "nvidia/nemotron" not in cfg.model_params


def test_set_mappings_writes_params_with_provenance(monkeypatch):
    _fake_hf(110_000_000_000, monkeypatch)
    cfg = Config()
    results = set_mappings(cfg, ["anthropic/glm:free=zai-org/GLM-4.5-Air"])
    assert results[0]["ok"] is True
    entry = cfg.model_params["anthropic/glm:free"]
    assert entry["total"] == 110.0
    assert entry["source"] == "resolve"
    assert entry["hf_repo"] == "zai-org/GLM-4.5-Air"


def test_set_mappings_reports_hf_failure(monkeypatch):
    monkeypatch.setitem(sys.modules, "huggingface_hub", None)  # HF indisponible
    cfg = Config()
    results = set_mappings(cfg, ["anthropic/foo=bar/baz"])
    assert results[0]["ok"] is False
    assert "anthropic/foo" not in cfg.model_params


def test_set_mappings_reports_bad_format():
    cfg = Config()
    results = set_mappings(cfg, ["pas-de-egal"])
    assert results[0]["ok"] is False
    assert results[0]["error"] == "format"


def test_forget_removes_entry():
    cfg = Config(model_params={"anthropic/glm:free": {"active": 110.0}})
    results = forget(cfg, ["anthropic/glm:free", "absent/xx"])
    assert results[0]["removed"] is True
    assert results[1]["removed"] is False
    assert "anthropic/glm:free" not in cfg.model_params
