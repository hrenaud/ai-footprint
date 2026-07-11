from pathlib import Path

import pytest

from ai_footprint.__main__ import main
from ai_footprint.card.cli import _find_chrome

FIXTURES = Path(__file__).parent / "fixtures"


def test_ingest_then_report(tmp_path, capsys):
    db = str(tmp_path / "ai-footprint.db")
    rc = main(["ingest", "--source", str(FIXTURES), "--db", db])
    assert rc == 0
    out = capsys.readouterr().out
    assert "3 events" in out  # sample.jsonl (2) + active.jsonl (1)

    rc = main(["report", "--db", db])
    assert rc == 0
    out = capsys.readouterr().out
    assert "opus-4-8" in out  # présent dans la section Intensité
    assert "GWP" in out
    assert "--help" in out             # pied de rapport : rappel des options
    assert "/footprint-help" in out  # renvoi au skill d'aide


def test_report_detail_flag_shows_minmax(tmp_path, capsys):
    db = str(tmp_path / "ai-footprint.db")
    main(["ingest", "--source", str(FIXTURES), "--db", db])
    capsys.readouterr()
    # vue compacte par défaut : titres « (~ central) »
    main(["report", "--db", db])
    assert "(~ central)" in capsys.readouterr().out
    # --detail et son alias --detailed basculent les tableaux par modèle en min–max
    for flag in ("--detail", "--detailed"):
        rc = main(["report", "--db", db, flag])
        assert rc == 0
        out = capsys.readouterr().out
        assert "(min–max)" in out
        assert "(~ central)" not in out


def test_ingest_is_idempotent_via_cli(tmp_path, capsys):
    db = str(tmp_path / "ai-footprint.db")
    main(["ingest", "--source", str(FIXTURES), "--db", db])
    capsys.readouterr()
    main(["ingest", "--source", str(FIXTURES), "--db", db])
    assert "0 events" in capsys.readouterr().out


def test_statusline_runs(tmp_path, capsys):
    db = str(tmp_path / "ai-footprint.db")
    main(["ingest", "--source", str(FIXTURES), "--db", db])
    capsys.readouterr()
    rc = main(["statusline", "--db", db])
    assert rc == 0
    assert "kWh" in capsys.readouterr().out


@pytest.mark.skipif(_find_chrome() is None, reason="Chrome/Chromium introuvable")
def test_card_runs(tmp_path, capsys):
    db = str(tmp_path / "ai-footprint.db")
    out_dir = tmp_path / "exports"
    main(["ingest", "--source", str(FIXTURES), "--db", db])
    capsys.readouterr()
    rc = main(["card", "--db", db, "--out", str(out_dir), "--lang", "fr", "--theme", "light"])
    assert rc == 0
    paths = capsys.readouterr().out.strip().splitlines()
    assert len(paths) == 1
    assert Path(paths[0]).exists()
