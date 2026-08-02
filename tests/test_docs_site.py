import shutil
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = REPO_ROOT / "docs"
MKDOCS_CONFIG = REPO_ROOT / "mkdocs.yml"

SOURCE_DOCS = [
    "METHODOLOGY.md",
    "comparaison-donnees-outils.md",
    "publication-pypi.md",
    "checklist-nouvel-outil.md",
    "CONTRIBUTING.md",
    "GUIDE.md",
    "GUIDE-AVANCE.md",
]

# French nav title -> expected English nav title. Used both to check
# mkdocs.yml's nav_translations and to verify the built EN pages actually
# show translated titles (mkdocs derives <title> from the nav label).
NAV_TRANSLATIONS_EN = {
    "Accueil": "Home",
    "Guide utilisateur": "User guide",
    "Guide avancé": "Advanced guide",
    "Méthodologie": "Methodology",
    "Comparaison des outils": "Tool comparison",
    "Publication PyPI": "PyPI Publication",
    "Checklist nouvel outil": "New tool checklist",
    "Contribuer": "Contributing",
}


def _mkdocs_config() -> dict:
    return yaml.safe_load(MKDOCS_CONFIG.read_text(encoding="utf-8"))


def test_mkdocs_config_uses_docs_dir_as_source():
    config = _mkdocs_config()
    assert config["docs_dir"] == "docs"


def test_mkdocs_config_excludes_landing_pages_and_their_assets():
    # Landing-page assets are excluded file by file (not the whole "assets/"
    # dir): the material theme also writes its own CSS/JS under an "assets/"
    # dir in the output, and excluding the directory wholesale drops those
    # theme files too, leaving the built site unstyled.
    # favicon.svg is the one exception: it must stay out of exclude_docs so
    # mkdocs-material can actually find and copy it as the site favicon.
    config = _mkdocs_config()
    excluded = config["exclude_docs"].splitlines()
    for entry in ["index.html", "fr/", "guide/"]:
        assert entry in excluded
    assert "assets/" not in excluded
    assert "assets/favicon.svg" not in excluded
    for asset in (DOCS_DIR / "assets").iterdir():
        if asset.name == "favicon.svg":
            continue
        assert f"assets/{asset.name}" in excluded


def test_mkdocs_config_declares_favicon():
    config = _mkdocs_config()
    assert config["theme"]["favicon"] == "assets/favicon.svg"


def test_mkdocs_config_uses_material_theme_for_language_switcher():
    # mkdocs-static-i18n only auto-injects the contextual language switcher
    # link for the material theme (see mkdocs_static_i18n/reconfigure.py) —
    # readthedocs/mkdocs themes get no switcher UI at all.
    config = _mkdocs_config()
    assert config["theme"]["name"] == "material"
    assert "navigation.instant" not in config["theme"].get("features", [])


def test_mkdocs_config_declares_fr_and_en_locales():
    config = _mkdocs_config()
    i18n_plugin = next(
        p["i18n"] for p in config["plugins"] if isinstance(p, dict) and "i18n" in p
    )
    locales = {lang["locale"] for lang in i18n_plugin["languages"]}
    assert locales == {"fr", "en"}


def test_french_docs_explain_inference_routes_and_scoped_resolution():
    advanced = (DOCS_DIR / "GUIDE-AVANCE.md").read_text(encoding="utf-8")
    methodology = (DOCS_DIR / "METHODOLOGY.md").read_text(encoding="utf-8")
    contributing = (DOCS_DIR / "CONTRIBUTING.md").read_text(encoding="utf-8")

    assert "route_hint" in advanced
    assert "indicative" in advanced
    assert "--session ou --since" in advanced
    assert "migration historique ponctuelle" in advanced
    assert "ne se reproduit pas" in advanced
    assert "openrouter" in methodology
    assert "custom" in methodology
    assert "impact non estimé" in methodology
    assert "--route" in methodology
    assert "recalcul ciblé" in methodology
    assert "--recompute" in methodology
    assert "tous les events en erreur" in methodology
    assert "~/.ai-footprint/config.json" in advanced
    assert "ne persiste pas une version sœur" in advanced
    assert "EcoLogits est vérifié à nouveau pour chaque nouvel event" in advanced
    assert "model_raw" in contributing
    assert "model_canonical" in contributing
    assert "historical-routes-v1" in contributing
    assert "huggingface_hub>=1.8.0,<2" in contributing
    assert "model_info(repo, timeout=10)" in contributing


def test_mkdocs_config_declares_nav_translations_for_en_locale():
    config = _mkdocs_config()
    i18n_plugin = next(
        p["i18n"] for p in config["plugins"] if isinstance(p, dict) and "i18n" in p
    )
    en_locale = next(
        lang for lang in i18n_plugin["languages"] if lang["locale"] == "en"
    )
    assert en_locale.get("nav_translations") == NAV_TRANSLATIONS_EN


def test_advanced_guides_name_the_claude_code_statusline():
    fr_guide = (DOCS_DIR / "GUIDE-AVANCE.md").read_text(encoding="utf-8")
    en_guide = (DOCS_DIR / "GUIDE-AVANCE.en.md").read_text(encoding="utf-8")

    assert "### Statusline Claude Code" in fr_guide
    assert "Claude Code affiche l'impact dans sa statusline" in fr_guide
    assert "### Claude Code statusline" in en_guide
    assert "Claude Code displays the impact in its statusline" in en_guide


def test_english_docs_explain_confirmed_routes_and_registry_reselection():
    advanced = (DOCS_DIR / "GUIDE-AVANCE.en.md").read_text(encoding="utf-8")
    methodology = (DOCS_DIR / "METHODOLOGY.en.md").read_text(encoding="utf-8")
    french_methodology = (DOCS_DIR / "METHODOLOGY.md").read_text(encoding="utf-8")
    methodology_text = " ".join(methodology.split())

    assert "route_hint" in advanced
    assert "historical migration" in advanced
    assert "EcoLogits is checked again for every new event" in advanced
    assert "Exact EcoLogits registry" in methodology
    assert "Same-provider sibling version" in methodology
    assert "User-confirmed Hugging Face mapping" in methodology
    assert methodology.index("Exact EcoLogits registry") < methodology.index(
        "Same-provider sibling version"
    ) < methodology.index("User-confirmed Hugging Face mapping")
    assert "Registre EcoLogits exact" in french_methodology
    assert "Version sœur du même fournisseur" in french_methodology
    assert "Mapping Hugging Face confirmé par l'utilisateur" in french_methodology
    assert "The exact registry is checked first for every new event" in methodology_text


def test_readme_distinguishes_the_claude_code_and_opencode_displays():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert "Dans Claude Code, l'impact s'affiche dans la statusline." in readme
    assert "Dans OpenCode, une carte dédiée s'affiche dans le panneau latéral." in readme


def test_build_produces_translated_titles_and_homepage_for_en_locale(tmp_path):
    site_dir = tmp_path / "site"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "mkdocs",
            "build",
            "-f",
            str(MKDOCS_CONFIG),
            "-d",
            str(site_dir),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )

    guide_html = (site_dir / "en" / "GUIDE.html").read_text(encoding="utf-8")
    assert "<title>User guide - AI Footprint — Documentation</title>" in guide_html

    homepage_html = (site_dir / "en" / "index.html").read_text(encoding="utf-8")
    assert "<title>Home - AI Footprint — Documentation</title>" in homepage_html
    assert "Documentation ai-footprint" not in homepage_html


def test_build_copies_favicon_into_site(tmp_path):
    site_dir = tmp_path / "site"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "mkdocs",
            "build",
            "-f",
            str(MKDOCS_CONFIG),
            "-d",
            str(site_dir),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )

    assert (site_dir / "assets" / "favicon.svg").is_file()
    assert 'href="assets/favicon.svg"' in (site_dir / "index.html").read_text(
        encoding="utf-8"
    )


def test_build_produces_html_for_each_source_doc_in_both_locales(tmp_path):
    site_dir = tmp_path / "site"
    before = {
        path: path.read_bytes()
        for path in [DOCS_DIR / "index.html", DOCS_DIR / "fr" / "index.html"]
    }

    subprocess.run(
        [
            sys.executable,
            "-m",
            "mkdocs",
            "build",
            "-f",
            str(MKDOCS_CONFIG),
            "-d",
            str(site_dir),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )

    for name in SOURCE_DOCS:
        html_name = name.removesuffix(".md") + ".html"
        assert (site_dir / html_name).exists(), f"missing FR page for {name}"
        assert (site_dir / "en" / html_name).exists(), f"missing EN page for {name}"

    for path, content in before.items():
        assert path.read_bytes() == content, f"{path} was modified by the doc build"


def test_build_script_syncs_output_into_docs_guide(tmp_path, monkeypatch):
    guide_dir = DOCS_DIR / "guide"
    guide_existed_before = guide_dir.exists()
    backup = tmp_path / "guide-backup"
    if guide_existed_before:
        shutil.copytree(guide_dir, backup)

    try:
        subprocess.run(
            [sys.executable, "scripts/build_docs.py"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
        )

        for name in SOURCE_DOCS:
            html_name = name.removesuffix(".md") + ".html"
            assert (guide_dir / html_name).exists()
            assert (guide_dir / "en" / html_name).exists()

        for html_path in guide_dir.rglob("*.html"):
            assert all(
                not line.endswith((" ", "\t"))
                for line in html_path.read_text(encoding="utf-8").splitlines()
            ), f"trailing whitespace in {html_path}"
    finally:
        shutil.rmtree(guide_dir, ignore_errors=True)
        if guide_existed_before:
            shutil.copytree(backup, guide_dir)
