"""Contrat du renommage AI Footprint (spec 2026-07-09) : chemins par défaut,
nom de commande et garde de migration depuis l'ancienne base agent-carbon."""

import ai_footprint.__main__ as main_mod
from ai_footprint.config import DEFAULT_CONFIG_PATH


def test_default_db_path():
    assert main_mod._DEFAULT_DB.endswith("/.ai-footprint/ai-footprint.db")


def test_default_config_path():
    assert DEFAULT_CONFIG_PATH.endswith("/.ai-footprint/config.json")


def test_parser_prog_and_footer():
    assert "ai-footprint report --help" in main_mod._REPORT_FOOTER
    assert "/footprint-help" in main_mod._REPORT_FOOTER


def test_legacy_hint_when_old_db_only(tmp_path):
    """Ancienne base présente, nouvelle absente → message invitant à relancer
    install.sh (pas de migration silencieuse à l'exécution)."""
    legacy = tmp_path / ".agent-carbon" / "carbon.db"
    legacy.parent.mkdir()
    legacy.write_text("x")
    new = tmp_path / ".ai-footprint" / "ai-footprint.db"
    hint = main_mod._legacy_db_hint(str(new), str(legacy))
    assert hint is not None and "install.sh" in hint


def test_no_legacy_hint_when_new_db_exists(tmp_path):
    legacy = tmp_path / ".agent-carbon" / "carbon.db"
    legacy.parent.mkdir()
    legacy.write_text("x")
    new = tmp_path / ".ai-footprint" / "ai-footprint.db"
    new.parent.mkdir()
    new.write_text("x")
    assert main_mod._legacy_db_hint(str(new), str(legacy)) is None


def test_no_legacy_hint_when_no_old_db(tmp_path):
    new = tmp_path / ".ai-footprint" / "ai-footprint.db"
    legacy = tmp_path / ".agent-carbon" / "carbon.db"
    assert main_mod._legacy_db_hint(str(new), str(legacy)) is None
