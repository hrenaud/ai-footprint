import re
from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parents[1] / "docs"

REQUIRED_IDS_IN_ORDER = [
    "nav",
    "hero",
    "multi-tools",
    "how-it-works",
    "criteria",
    "why-ranges",
    "footer",
]

TAG_WITH_ID_RE = re.compile(r'<(?:header|section|footer) id="([a-z-]+)"')


def _section_ids(html_path: Path) -> list[str]:
    text = html_path.read_text(encoding="utf-8")
    return TAG_WITH_ID_RE.findall(text)


def test_en_page_has_required_sections_in_order():
    ids = _section_ids(DOCS_DIR / "index.html")
    assert ids == REQUIRED_IDS_IN_ORDER


def test_fr_page_has_required_sections_in_order():
    ids = _section_ids(DOCS_DIR / "fr" / "index.html")
    assert ids == REQUIRED_IDS_IN_ORDER


def test_en_page_links_to_fr_page():
    text = (DOCS_DIR / "index.html").read_text(encoding="utf-8")
    assert 'href="fr/index.html"' in text


def test_fr_page_links_to_en_page():
    text = (DOCS_DIR / "fr" / "index.html").read_text(encoding="utf-8")
    assert 'href="../index.html"' in text


def test_en_page_mentions_ecologits_with_link():
    text = (DOCS_DIR / "index.html").read_text(encoding="utf-8")
    assert "EcoLogits" in text
    assert "https://github.com/mlco2/ecologits" in text


def test_fr_page_mentions_ecologits_with_link():
    text = (DOCS_DIR / "fr" / "index.html").read_text(encoding="utf-8")
    assert "EcoLogits" in text
    assert "https://github.com/mlco2/ecologits" in text


def test_en_page_references_shared_stylesheet():
    text = (DOCS_DIR / "index.html").read_text(encoding="utf-8")
    assert 'href="assets/style.css"' in text


def test_fr_page_references_shared_stylesheet():
    text = (DOCS_DIR / "fr" / "index.html").read_text(encoding="utf-8")
    assert 'href="../assets/style.css"' in text


def test_en_page_has_install_one_liner():
    text = (DOCS_DIR / "index.html").read_text(encoding="utf-8")
    assert (
        "curl -fsSL https://raw.githubusercontent.com/hrenaud/ai-footprint/main/install.sh | bash"
        in text
    )


def test_fr_page_has_install_one_liner():
    text = (DOCS_DIR / "fr" / "index.html").read_text(encoding="utf-8")
    assert (
        "curl -fsSL https://raw.githubusercontent.com/hrenaud/ai-footprint/main/install.sh | bash"
        in text
    )


def test_stylesheet_asset_exists():
    assert (DOCS_DIR / "assets" / "style.css").is_file()


def test_tool_logo_assets_exist():
    assert (DOCS_DIR / "assets" / "logo-claude.svg").is_file()
    assert (DOCS_DIR / "assets" / "logo-opencode.png").is_file()
    assert (DOCS_DIR / "assets" / "logo-pi.svg").is_file()


def test_en_page_multi_tools_has_logos():
    text = (DOCS_DIR / "index.html").read_text(encoding="utf-8")
    assert 'src="assets/logo-claude.svg"' in text
    assert 'src="assets/logo-opencode.png"' in text
    assert 'src="assets/logo-pi.svg"' in text


def test_fr_page_multi_tools_has_logos():
    text = (DOCS_DIR / "fr" / "index.html").read_text(encoding="utf-8")
    assert 'src="../assets/logo-claude.svg"' in text
    assert 'src="../assets/logo-opencode.png"' in text
    assert 'src="../assets/logo-pi.svg"' in text


def test_script_asset_exists():
    assert (DOCS_DIR / "assets" / "script.js").is_file()


def test_en_page_has_clickable_install_command_before_steps():
    text = (DOCS_DIR / "index.html").read_text(encoding="utf-8")
    assert 'src="assets/script.js"' in text
    assert 'id="install-cmd"' in text
    assert "copy-btn" not in text
    assert "install-cmd-wrap" in text
    assert "copy-feedback" in text
    assert text.index('id="install-cmd"') < text.index('class="steps"')


def test_fr_page_has_clickable_install_command_before_steps():
    text = (DOCS_DIR / "fr" / "index.html").read_text(encoding="utf-8")
    assert 'src="../assets/script.js"' in text
    assert 'id="install-cmd"' in text
    assert "copy-btn" not in text
    assert "install-cmd-wrap" in text
    assert "copy-feedback" in text
    assert text.index('id="install-cmd"') < text.index('class="steps"')
