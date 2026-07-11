import re
import struct
from datetime import date

import pytest

from ai_footprint.card.cli import (
    _find_chrome,
    _fmt_fr,
    _fmt_tokens,
    _gauge,
    _period_label,
    build_card_data,
    render_card_html,
    render_png,
)
from ai_footprint.config import Config
from ai_footprint.impact.engine import EcoLogitsEngine
from ai_footprint.impact.resolver import ModelResolver
from ai_footprint.models import InferenceEvent
from ai_footprint.store.db import SQLiteStore


def _engine():
    return EcoLogitsEngine(ModelResolver({}))


def test_fmt_fr_converts_dot_to_comma():
    assert _fmt_fr("~13.2") == "~13,2"
    assert _fmt_fr("9.7–16.6") == "9,7–16,6"
    assert _fmt_fr("≈0") == "≈0"  # pas de point à convertir


def test_fmt_tokens_billions():
    assert _fmt_tokens(4.1e9) == "4,1 Md tokens"


def test_fmt_tokens_thousands():
    assert _fmt_tokens(566_000) == "566 k tokens"


def test_fmt_tokens_small():
    assert _fmt_tokens(820) == "820 tokens"


def test_period_label_uses_since_when_provided():
    assert _period_label("2026-06-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00") == "depuis juin 2026"


def test_period_label_falls_back_to_first_session():
    assert _period_label(None, "2026-05-15T00:00:00+00:00") == "depuis mai 2026"


def test_period_label_empty_without_data():
    assert _period_label(None, None) == ""


def test_gauge_matches_mockup_hero_positions():
    g = _gauge(9.7, 16.6)
    assert g["fill_left"] == pytest.approx(53.1, abs=0.2)
    assert g["fill_right"] == pytest.approx(9.1, abs=0.2)
    assert g["tick_left"] == pytest.approx(72.0, abs=0.3)


def test_gauge_handles_zero_range():
    g = _gauge(0.0, 0.0)
    assert g == {"fill_left": 0.0, "fill_right": 100.0, "tick_left": 0.0}


def _seed_store(tmp_path):
    store = SQLiteStore(str(tmp_path / "c.db"))
    events = [
        InferenceEvent("anthropic", "claude-opus-4-8", 1000, 5000, 0, 0,
                       "2026-05-10T10:00:00.000Z", "agent-carbon", "sess-A", "u1",
                       client="claude-code"),
        InferenceEvent("anthropic", "claude-opus-4-8", 1000, 5000, 0, 0,
                       "2026-06-15T10:00:00.000Z", "mcp-nr", "sess-B", "u2",
                       client="opencode"),
        InferenceEvent("anthropic", "claude-opus-4-8", 1000, 5000, 0, 0,
                       "2026-06-20T10:00:00.000Z", "immobilier", "sess-C", "u3",
                       client="claude-code"),
    ]
    store.ingest(events, _engine(), Config())
    return store


def test_build_card_data_structure(tmp_path):
    store = _seed_store(tmp_path)
    data = build_card_data(store, since=None)

    assert data["period"] == "depuis mai 2026"
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", data["footer_date"])
    assert data["footer_date"] == date.today().isoformat()

    hero = data["hero"]
    assert hero["value"].startswith("~")
    assert hero["unit"] == "kg CO₂eq"
    assert "sessions" in hero["sub"]
    assert "tokens" in hero["sub"]
    for key in ("fill_left", "fill_right", "tick_left"):
        assert isinstance(hero[key], float)
    assert "min" in hero["bound_min"] or hero["bound_min"] != ""
    assert hero["bound_max"] != ""

    tiles = data["tiles"]
    assert [t["criterion"] for t in tiles] == ["wcf", "energy", "adpe", "pe"]
    for t in tiles:
        assert t["value"].startswith("~") or t["value"] == "≈0"
        assert t["unit"]
        assert isinstance(t["fill_left"], float)

    projects = data["projects"]
    assert 1 <= len(projects) <= 3
    names = [p["name"] for p in projects]
    assert names == sorted(names, key=lambda n: names.index(n))  # ordre stable
    for p in projects:
        assert p["value"].startswith("~")
        assert 0 <= p["share"] <= 100
        assert 0 <= p["bar_width"] <= 100


def test_build_card_data_since_filters_and_labels_period(tmp_path):
    store = _seed_store(tmp_path)
    data = build_card_data(store, since="2026-06-01T00:00:00+00:00")
    assert data["period"] == "depuis juin 2026"
    names = {p["name"] for p in data["projects"]}
    assert "agent-carbon" not in names  # événement de mai exclu par --since


_MINIMAL_DATA = {
    "period": "depuis mai 2026",
    "footer_date": "2026-07-10",
    "hero": {
        "value": "~13,2", "unit": "kg CO₂eq", "sub": "190 sessions · 4,1 Md tokens · claude-code, opencode",
        "fill_left": 53.1, "fill_right": 9.1, "tick_left": 72.0,
        "bound_min": "min 9,7", "bound_max": "max 16,6",
    },
    "tiles": [
        {"criterion": "wcf", "value": "~161", "unit": "L",
         "fill_left": 41.0, "fill_right": 9.1, "tick_left": 66.0,
         "bound_min": "99,5", "bound_max": "222"},
        {"criterion": "energy", "value": "~41,5", "unit": "kWh",
         "fill_left": 50.0, "fill_right": 9.1, "tick_left": 70.0,
         "bound_min": "29,4", "bound_max": "53,6"},
        {"criterion": "adpe", "value": "~59,8", "unit": "mg Sbeq",
         "fill_left": 87.0, "fill_right": 9.1, "tick_left": 89.0,
         "bound_min": "58,5", "bound_max": "61"},
        {"criterion": "pe", "value": "~410", "unit": "MJ",
         "fill_left": 51.0, "fill_right": 9.1, "tick_left": 71.0,
         "bound_min": "294", "bound_max": "527"},
    ],
    "projects": [
        {"name": "agent-carbon", "value": "~3,1 kg", "share": 24, "bar_width": 100},
        {"name": "mcp-nr", "value": "~2,7 kg", "share": 21, "bar_width": 87},
    ],
}


def test_render_card_html_resolves_all_placeholders():
    html = render_card_html(_MINIMAL_DATA, theme="light", lang="fr")
    assert "{{" not in html
    assert "}}" not in html
    assert "card--dark" not in html
    assert "ai <span>footprint</span>" in html
    assert "Eau" in html
    assert "agent-carbon" in html


def test_render_card_html_dark_theme_adds_class():
    html = render_card_html(_MINIMAL_DATA, theme="dark", lang="fr")
    assert "card--dark" in html


def test_render_card_html_lang_en_translates_static_labels():
    html = render_card_html(_MINIMAL_DATA, theme="light", lang="en")
    assert "Water" in html
    assert "Eau" not in html or "Water" in html


@pytest.mark.skipif(_find_chrome() is None, reason="Chrome/Chromium introuvable")
def test_render_png_produces_correctly_sized_file(tmp_path):
    html = render_card_html(_MINIMAL_DATA, theme="light", lang="fr")
    out_path = tmp_path / "card.png"
    render_png(html, str(out_path), _find_chrome())
    assert out_path.exists()
    with open(out_path, "rb") as f:
        header = f.read(24)
    width, height = struct.unpack(">II", header[16:24])
    assert (width, height) == (2160, 2160)
