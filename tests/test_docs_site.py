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
    config = _mkdocs_config()
    excluded = config["exclude_docs"].splitlines()
    for entry in ["index.html", "fr/", "guide/"]:
        assert entry in excluded
    assert "assets/" not in excluded
    for asset in (DOCS_DIR / "assets").iterdir():
        assert f"assets/{asset.name}" in excluded


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


def test_mkdocs_config_declares_nav_translations_for_en_locale():
    config = _mkdocs_config()
    i18n_plugin = next(
        p["i18n"] for p in config["plugins"] if isinstance(p, dict) and "i18n" in p
    )
    en_locale = next(
        lang for lang in i18n_plugin["languages"] if lang["locale"] == "en"
    )
    assert en_locale.get("nav_translations") == NAV_TRANSLATIONS_EN


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
    finally:
        shutil.rmtree(guide_dir, ignore_errors=True)
        if guide_existed_before:
            shutil.copytree(backup, guide_dir)
