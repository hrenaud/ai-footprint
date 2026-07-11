import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date, datetime

from ai_footprint.impact.engine import CRITERIA
from ai_footprint.report.cli import _central, _ranked_projects, _scale

_MONTHS_FR = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]

# Ordre d'affichage des 4 tuiles (hors héro GWP), comme la maquette.
_TILE_CRITERIA = ("wcf", "energy", "adpe", "pe")

_LABELS = {
    "fr": {
        "hero_label": "Mon empreinte IA — carbone (GWP)",
        "hero_mid": "~ valeur centrale",
        "tile": {"wcf": "Eau", "energy": "Énergie", "adpe": "ADPe", "pe": "Énergie primaire"},
        "projects_title": "Projets les plus impactants — GWP",
        "footer_tools": "estimations EcoLogits · fourchettes min–max",
    },
    "en": {
        "hero_label": "My AI footprint — carbon (GWP)",
        "hero_mid": "~ central value",
        "tile": {"wcf": "Water", "energy": "Energy", "adpe": "ADPe", "pe": "Primary energy"},
        "projects_title": "Most impactful projects — GWP",
        "footer_tools": "EcoLogits estimates · min–max ranges",
    },
}

_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "template.html")


def _fmt_fr(s: str) -> str:
    return s.replace(".", ",")


def _fmt_tokens(n: float) -> str:
    if n >= 1e9:
        return f"{_fmt_fr(f'{n / 1e9:.1f}')} Md tokens"
    if n >= 1e3:
        return f"{n / 1e3:.0f} k tokens"
    return f"{n:.0f} tokens"


def _period_label(since: str | None, first_session: str | None) -> str:
    ts = since or first_session
    if not ts:
        return ""
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return f"depuis {_MONTHS_FR[dt.month - 1]} {dt.year}"


def _gauge(lo: float, hi: float) -> dict:
    """Positions % sur une échelle 0 → hi×1,1 (le max ne colle pas au bord)."""
    if hi <= 0:
        return {"fill_left": 0.0, "fill_right": 100.0, "tick_left": 0.0}
    scale = hi * 1.1
    fill_left = lo / scale * 100
    fill_right = 100 - hi / scale * 100
    tick_left = (lo + hi) / 2 / scale * 100
    return {
        "fill_left": round(fill_left, 1),
        "fill_right": round(fill_right, 1),
        "tick_left": round(tick_left, 1),
    }


def _pretty_unit(unit: str) -> str:
    """« kgCO2eq » → « kg CO₂eq », « mgSbeq » → « mg Sbeq » (mockup : espace +
    subscript avant le suffixe « eq »)."""
    m = re.match(r"^([a-zµ]+)(CO2eq|Sbeq)$", unit)
    if not m:
        return unit
    prefix, base = m.groups()
    return f"{prefix} {base.replace('CO2eq', 'CO₂eq')}"


def _bound(value: float) -> str:
    return _fmt_fr(f"{value:.3g}")


def build_card_data(store, since: str | None = None) -> dict:
    rows = store.rows_for_report(since)
    totals = {c: [0.0, 0.0] for c in CRITERIA}
    for row in rows:
        for c in CRITERIA:
            totals[c][0] += row[f"{c}_min"]
            totals[c][1] += row[f"{c}_max"]

    period = _period_label(since, store.first_session_started_at())
    sessions = store.session_count(since)
    tokens = sum(r["tokens"] for r in store.tokens_by_model(since))
    clients = store.clients_covered(since)

    gwp_lo, gwp_hi = totals["gwp"]
    factor, unit = 1.0, "kgCO2eq"  # héro toujours en kg (métrique vitrine, cf. maquette)
    hero = {
        "value": _fmt_fr(_central(gwp_lo, gwp_hi, factor)),
        "unit": _pretty_unit(unit),
        "sub": f"{sessions} sessions · {_fmt_tokens(tokens)} · {', '.join(clients)}",
        "bound_min": f"min {_bound(gwp_lo * factor)}",
        "bound_max": f"max {_bound(gwp_hi * factor)}",
        **_gauge(gwp_lo * factor, gwp_hi * factor),
    }

    tiles = []
    for crit in _TILE_CRITERIA:
        lo, hi = totals[crit]
        cfactor, cunit = _scale(hi or 1.0, crit)
        tiles.append({
            "criterion": crit,
            "value": _fmt_fr(_central(lo, hi, cfactor)),
            "unit": _pretty_unit(cunit),
            "bound_min": _bound(lo * cfactor),
            "bound_max": _bound(hi * cfactor),
            **_gauge(lo * cfactor, hi * cfactor),
        })

    ranked = _ranked_projects(rows)
    top = ranked[:3]
    total_mid = (gwp_lo + gwp_hi) / 2 or 1.0
    top_mid = ((top[0][1][0] + top[0][1][1]) / 2 or 1.0) if top else 1.0
    projects = []
    for name, (plo, phi) in top:
        mid = (plo + phi) / 2
        projects.append({
            "name": name,
            "value": _fmt_fr(_central(plo, phi, factor)) + f" {unit.replace('kgCO2eq', 'kg').replace('gCO2eq', 'g').replace('mgCO2eq', 'mg')}",
            "share": round(mid / total_mid * 100),
            "bar_width": round(mid / top_mid * 100),
        })

    return {
        "period": period,
        "footer_date": date.today().isoformat(),
        "hero": hero,
        "tiles": tiles,
        "projects": projects,
    }


def _range_html(fill_left: float, fill_right: float, tick_left: float,
                bound_min: str, bound_max: str, mid: str | None = None) -> str:
    mid_html = f'<span class="mid">{mid}</span>' if mid else ""
    return (
        '<div class="range">'
        '<div class="range-track">'
        f'<div class="range-fill" style="left:{fill_left}%; right:{fill_right}%"></div>'
        f'<div class="range-tick" style="left:{tick_left}%"></div>'
        "</div>"
        '<div class="range-bounds mono">'
        f"<span>{bound_min}</span>{mid_html}<span>{bound_max}</span>"
        "</div>"
        "</div>"
    )


def _tiles_html(tiles: list[dict], lang: str) -> str:
    labels = _LABELS[lang]["tile"]
    out = []
    for t in tiles:
        out.append(
            '<div class="tile">'
            f'<div class="tile-label mono">{labels[t["criterion"]]}</div>'
            f'<div class="tile-value">{t["value"]}<small>{t["unit"]}</small></div>'
            + _range_html(t["fill_left"], t["fill_right"], t["tick_left"],
                          t["bound_min"], t["bound_max"])
            + "</div>"
        )
    return "".join(out)


def _projects_html(projects: list[dict]) -> str:
    out = []
    for p in projects:
        width = p["bar_width"]
        out.append(
            '<div class="proj">'
            f'<div class="proj-name">{p["name"]}</div>'
            '<div class="proj-bar-slot">'
            f'<div class="proj-bar" style="width:{width}%"></div>'
            "</div>"
            f'<div class="proj-val mono"><b>{p["value"]}</b> · {p["share"]} %</div>'
            "</div>"
        )
    return "".join(out)


def render_card_html(data: dict, theme: str = "light", lang: str = "fr") -> str:
    with open(_TEMPLATE_PATH, encoding="utf-8") as f:
        template = f.read()

    labels = _LABELS[lang]
    hero = data["hero"]
    theme_style = (
        ".card--dark {\n"
        "    --surface: #171c1a;\n"
        "    --panel: #1d2420;\n"
        "    --ink: #f2f5f2;\n"
        "    --sec: #9fada5;\n"
        "    --muted: #75837b;\n"
        "    --accent: #1fb47f;\n"
        "    --accent-hi: #43d99e;\n"
        "    --hairline: #2a332e;\n"
        "  }"
        if theme == "dark" else ""
    )
    replacements = {
        "{{THEME_STYLE}}": theme_style,
        "{{THEME_CLASS}}": " card--dark" if theme == "dark" else "",
        "{{PERIOD}}": f'{data["period"]} · {data["footer_date"]}',
        "{{HERO_LABEL}}": labels["hero_label"],
        "{{HERO_VALUE}}": hero["value"],
        "{{HERO_UNIT}}": hero["unit"],
        "{{HERO_SUB}}": hero["sub"],
        "{{HERO_RANGE}}": _range_html(
            hero["fill_left"], hero["fill_right"], hero["tick_left"],
            hero["bound_min"], hero["bound_max"], mid=labels["hero_mid"]),
        "{{TILES_HTML}}": _tiles_html(data["tiles"], lang),
        "{{PROJECTS_TITLE}}": labels["projects_title"],
        "{{PROJECTS_HTML}}": _projects_html(data["projects"]),
        "{{FOOTER_TOOLS}}": labels["footer_tools"],
        "{{FOOTER_REPO}}": "github.com/hrenaud/ai-footprint",
    }
    for placeholder, value in replacements.items():
        template = template.replace(placeholder, str(value))
    return template


def _find_chrome() -> str | None:
    env = os.environ.get("CHROME_BIN")
    if env and os.path.exists(env):
        return env
    for path in (
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ):
        if os.path.exists(path):
            return path
    for name in ("google-chrome", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return found
    return None


def render_png(html: str, out_path: str, chrome_bin: str) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html)
        tmp_path = f.name
    try:
        subprocess.run(
            [chrome_bin, "--headless=new", f"--screenshot={out_path}",
             "--window-size=1080,1080", "--force-device-scale-factor=2",
             "--hide-scrollbars", "--default-background-color=00000000",
             f"file://{tmp_path}"],
            check=True, capture_output=True,
        )
    finally:
        os.unlink(tmp_path)


def cmd_card(args) -> int:
    from ai_footprint.store.db import SQLiteStore

    os.makedirs(os.path.dirname(os.path.abspath(args.db)), exist_ok=True)
    store = SQLiteStore(args.db)

    themes = ("light", "dark") if args.theme == "both" else (args.theme,)
    langs = ("fr", "en") if args.lang == "both" else (args.lang,)

    chrome_bin = _find_chrome()
    if chrome_bin is None:
        print(
            "Chrome/Chromium introuvable — installe-le pour générer la card :\n"
            "  macOS : brew install --cask google-chrome\n"
            "  Linux : apt install chromium",
            file=sys.stderr,
        )
        return 1

    data = build_card_data(store, args.since)
    out_dir = os.path.expanduser(args.out)
    os.makedirs(out_dir, exist_ok=True)

    today = date.today().isoformat()
    exported = []
    for theme in themes:
        for lang in langs:
            html = render_card_html(data, theme=theme, lang=lang)
            theme_part = "" if theme == "light" else f"-{theme}"
            filename = f"ai-footprint{theme_part}-{lang}-{today}.png"
            out_path = os.path.join(out_dir, filename)
            render_png(html, out_path, chrome_bin)
            exported.append(out_path)

    for path in exported:
        print(path)
    return 0
