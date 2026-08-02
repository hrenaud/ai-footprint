import re
import subprocess
from pathlib import Path

import pytest

DOCS_DIR = Path(__file__).resolve().parents[1] / "docs"

REQUIRED_IDS_IN_ORDER = [
    "nav",
    "hero",
    "multi-tools",
    "models",
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


def test_favicon_asset_exists():
    assert (DOCS_DIR / "assets" / "favicon.svg").is_file()


def test_en_page_references_favicon():
    text = (DOCS_DIR / "index.html").read_text(encoding="utf-8")
    assert '<link rel="icon" type="image/svg+xml" href="assets/favicon.svg" />' in text


def test_fr_page_references_favicon():
    text = (DOCS_DIR / "fr" / "index.html").read_text(encoding="utf-8")
    assert (
        '<link rel="icon" type="image/svg+xml" href="../assets/favicon.svg" />'
        in text
    )


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


@pytest.mark.parametrize(
    ("page", "claude_copy", "opencode_copy", "asset_prefix"),
    [
        (
            DOCS_DIR / "index.html",
            "See your impact in the Claude Code statusline, live, session after session.",
            "See your impact in the OpenCode statusline, live, session after session.",
            "assets/",
        ),
        (
            DOCS_DIR / "fr" / "index.html",
            "Vois ton impact dans la statusline Claude Code, en direct, session apres session.",
            "Vois ton impact dans la statusline OpenCode, en direct, session apres session.",
            "../assets/",
        ),
    ],
)
def test_landing_page_has_accessible_statusline_tabs(
    page: Path, claude_copy: str, opencode_copy: str, asset_prefix: str
):
    text = page.read_text(encoding="utf-8")

    assert 'role="tablist"' in text
    assert 'role="tab"' in text
    assert 'aria-controls="claude-statusline-panel"' in text
    assert 'aria-controls="opencode-statusline-panel"' in text
    assert 'role="tabpanel"' in text
    assert 'id="opencode-statusline-panel"' in text
    assert "hidden" in text
    assert claude_copy in text
    assert opencode_copy in text
    assert f'src="{asset_prefix}statusline.png"' in text
    assert f'src="{asset_prefix}opencode-statusline.png"' in text
    assert 'loading="lazy"' in text


def test_opencode_statusline_asset_exists():
    assert (DOCS_DIR / "assets" / "opencode-statusline.png").is_file()


def test_shared_script_handles_statusline_tab_keyboard_navigation():
    script_path = DOCS_DIR / "assets" / "script.js"
    test_script = r"""
const fs = require("fs");
const vm = require("vm");

class Element {
  constructor(id) {
    this.id = id;
    this.attributes = {};
    this.listeners = {};
    this.hidden = false;
    this.tabIndex = 0;
    this.focused = false;
  }
  addEventListener(type, listener) {
    (this.listeners[type] ??= []).push(listener);
  }
  dispatch(type, event = {}) {
    for (const listener of this.listeners[type] ?? []) listener(event);
  }
  getAttribute(name) {
    return this.attributes[name];
  }
  setAttribute(name, value) {
    this.attributes[name] = value;
  }
  focus() {
    tabs.forEach((tab) => (tab.focused = false));
    this.focused = true;
  }
}

const claude = new Element("claude-tab");
const opencode = new Element("opencode-tab");
const claudePanel = new Element("claude-statusline-panel");
const opencodePanel = new Element("opencode-statusline-panel");
const tabs = [claude, opencode];
claude.setAttribute("aria-controls", claudePanel.id);
opencode.setAttribute("aria-controls", opencodePanel.id);
const tabList = { querySelectorAll: () => tabs };
const document = {
  querySelectorAll: (selector) => {
    if (selector === ".install-cmd-wrap") return [];
    if (selector === '[role="tablist"]') return [tabList];
    throw new Error(`unexpected selector: ${selector}`);
  },
  getElementById: (id) => ({
    [claudePanel.id]: claudePanel,
    [opencodePanel.id]: opencodePanel,
  })[id],
};

vm.runInNewContext(fs.readFileSync(process.argv[1], "utf8"), { document });

function key(tab, value) {
  let prevented = false;
  tab.dispatch("keydown", { key: value, preventDefault: () => (prevented = true) });
  if (!prevented) throw new Error(`${value} did not prevent its default action`);
}

function state(selected, focused) {
  for (const tab of tabs) {
    const isSelected = tab === selected;
    if (tab.getAttribute("aria-selected") !== String(isSelected)) throw new Error("aria-selected");
    if (tab.tabIndex !== (isSelected ? 0 : -1)) throw new Error("tabIndex");
    if (document.getElementById(tab.getAttribute("aria-controls")).hidden === isSelected) throw new Error("panel hidden");
    if (tab.focused !== (tab === focused)) throw new Error("focus");
  }
}

claude.dispatch("click");
state(claude, null);
key(claude, "ArrowLeft");
state(opencode, opencode);
key(opencode, "ArrowRight");
state(claude, claude);
key(opencode, "Home");
state(claude, claude);
key(claude, "End");
state(opencode, opencode);
key(claude, "Enter");
state(claude, opencode);
key(opencode, " ");
state(opencode, opencode);
"""

    result = subprocess.run(
        ["node", "-e", test_script, str(script_path)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_selected_statusline_tab_uses_dark_accent_token():
    stylesheet = (DOCS_DIR / "assets" / "style.css").read_text(encoding="utf-8")
    selected_tab = re.search(
        r'\.statusline-tab\[aria-selected="true"\] \{(?P<rules>.*?)\n\}',
        stylesheet,
        re.DOTALL,
    )

    assert selected_tab is not None
    assert "background: var(--color-accent-dark);" in selected_tab["rules"]
    assert "border-color: var(--color-accent-dark);" in selected_tab["rules"]
