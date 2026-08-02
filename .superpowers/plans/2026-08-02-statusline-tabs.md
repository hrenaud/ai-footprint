# Statusline Tabs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Present separate Claude Code and OpenCode statusline examples through accessible tabs on both landing pages.

**Architecture:** Keep the landing page static and bilingual. Extend the shared landing-page CSS and its existing JavaScript asset for the tab behaviour, while each language page supplies its translated text and correct relative asset paths. Rename the advanced guide's generic statusline heading to explicitly identify Claude Code, making it parallel to the existing OpenCode section, and state the same distinction concisely in the README.

**Tech Stack:** Static HTML, shared CSS, vanilla JavaScript, pytest, MkDocs build script.

## Global Constraints

- Modify both `docs/index.html` and `docs/fr/index.html` with equivalent structure and translated copy.
- Add no framework or dependency.
- The control uses ARIA tab semantics and supports pointer, Left/Right Arrow, Home, End, Enter, and Space interactions.
- Claude Code is the initially selected tab; the hidden OpenCode image uses `loading="lazy"`.
- Use descriptive image alternatives and explicit image dimensions.
- Rename the generic advanced-guide statusline heading to identify Claude Code; retain its existing detailed explanation and the OpenCode section.
- State concisely in `README.md` that Claude Code uses a statusline and OpenCode a sidebar card.
- Do not commit or push unless the user explicitly requests it.

---

### Task 1: Specify the bilingual statusline tabs in landing-page tests

**Files:**
- Modify: `tests/test_landing_page.py`
- Modify: `tests/test_docs_site.py`

**Interfaces:**
- Consumes: `README.md`, `docs/index.html`, `docs/fr/index.html`, `docs/GUIDE-AVANCE.md`, `docs/GUIDE-AVANCE.en.md`, `docs/assets/opencode-statusline.png`, and `docs/assets/script.js`.
- Produces: regression coverage for the shared tab structure, translated copy, lazy OpenCode asset, tab keyboard handler, explicit Claude Code guide headings, and the concise README distinction.

- [ ] **Step 1: Write the failing tests**

Add these imports and tests to `tests/test_landing_page.py` after the existing
asset checks:

```python
import pytest


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
    script = (DOCS_DIR / "assets" / "script.js").read_text(encoding="utf-8")

    assert "querySelectorAll('[role=\"tab\"]')" in script
    assert 'event.key === "ArrowLeft"' in script
    assert 'event.key === "ArrowRight"' in script
    assert 'event.key === "Home"' in script
    assert 'event.key === "End"' in script
    assert 'event.key === "Enter"' in script
    assert 'event.key === " "' in script
```

Add this test to `tests/test_docs_site.py` after the MkDocs configuration tests:

```python
def test_advanced_guides_name_the_claude_code_statusline():
    fr_guide = (DOCS_DIR / "GUIDE-AVANCE.md").read_text(encoding="utf-8")
    en_guide = (DOCS_DIR / "GUIDE-AVANCE.en.md").read_text(encoding="utf-8")

    assert "### Statusline Claude Code" in fr_guide
    assert "Claude Code affiche l'impact dans sa statusline" in fr_guide
    assert "### Claude Code statusline" in en_guide
    assert "Claude Code displays the impact in its statusline" in en_guide


def test_readme_distinguishes_the_claude_code_and_opencode_displays():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert "Dans Claude Code, l'impact s'affiche dans la statusline." in readme
    assert "Dans OpenCode, une carte dédiée s'affiche dans le panneau latéral." in readme
```

- [ ] **Step 2: Run the targeted test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_landing_page.py tests/test_docs_site.py -q`

Expected: FAIL because neither landing page has the tab roles or OpenCode asset,
the script has no tab keyboard handler, and the advanced guides use generic
statusline headings.

- [ ] **Step 3: Do not change production files in this task**

Keep the test failure as the red state for Task 2.

### Task 2: Add the OpenCode capture and accessible tab markup

**Files:**
- Create: `docs/assets/opencode-statusline.png`
- Modify: `docs/index.html:144-154`
- Modify: `docs/fr/index.html:155-168`
- Modify: `docs/GUIDE-AVANCE.md:140`
- Modify: `docs/GUIDE-AVANCE.en.md:134`
- Modify: `README.md:123`

**Interfaces:**
- Consumes: the OpenCode sidebar capture supplied by the user and the tests from Task 1.
- Produces: two structurally identical tab interfaces whose panel IDs and asset paths are used by the shared JavaScript, explicit Claude Code sections in both advanced guides, and a concise README distinction between both displays.

- [ ] **Step 1: Add the supplied image asset**

Save the supplied 310x115 OpenCode sidebar screenshot as
`docs/assets/opencode-statusline.png`. Preserve it as a PNG and do not upscale
it. Its visual content is the AI Footprint OpenCode card with a version label,
carbon, water, and energy ranges, plus a fallback-model warning.

- [ ] **Step 2: Replace the English Claude Code-only block**

Replace the `div.step.step-optional` in `docs/index.html` with this markup:

```html
<div class="step step-optional statusline-example">
  <span class="step-num">Statusline</span>
  <div class="statusline-tabs" role="tablist" aria-label="Statusline examples">
    <button
      id="claude-statusline-tab"
      class="statusline-tab"
      type="button"
      role="tab"
      aria-selected="true"
      aria-controls="claude-statusline-panel"
    >
      Claude Code
    </button>
    <button
      id="opencode-statusline-tab"
      class="statusline-tab"
      type="button"
      role="tab"
      aria-selected="false"
      aria-controls="opencode-statusline-panel"
      tabindex="-1"
    >
      OpenCode
    </button>
  </div>
  <div
    id="claude-statusline-panel"
    class="statusline-panel"
    role="tabpanel"
    aria-labelledby="claude-statusline-tab"
  >
    <p>See your impact in the Claude Code statusline, live, session after session.</p>
    <img
      class="statusline-preview"
      src="assets/statusline.png"
      alt="Claude Code statusline showing AI Footprint impact ranges during a session"
      width="1630"
      height="106"
    />
  </div>
  <div
    id="opencode-statusline-panel"
    class="statusline-panel"
    role="tabpanel"
    aria-labelledby="opencode-statusline-tab"
    hidden
  >
    <p>See your impact in the OpenCode statusline, live, session after session.</p>
    <img
      class="statusline-preview opencode-statusline-preview"
      src="assets/opencode-statusline.png"
      alt="OpenCode sidebar showing the AI Footprint version, impact ranges, and model fallback warning"
      width="310"
      height="115"
      loading="lazy"
    />
  </div>
</div>
```

- [ ] **Step 3: Replace the French Claude Code-only block**

Use the same IDs, roles, class names, and dimensions in `docs/fr/index.html`.
Set `aria-label="Exemples de statusline"`, change both image paths to
`../assets/...`, and use this translated copy:

```html
<p>Vois ton impact dans la statusline Claude Code, en direct, session apres session.</p>
<p>Vois ton impact dans la statusline OpenCode, en direct, session apres session.</p>
```

Use these alternative texts:

```html
alt="Statusline Claude Code montrant les fourchettes d'impact AI Footprint pendant une session"
alt="Panneau lateral OpenCode montrant la version AI Footprint, les fourchettes d'impact et un avertissement de repli de modele"
```

- [ ] **Step 4: Make the advanced guides explicitly name Claude Code**

In `docs/GUIDE-AVANCE.md`, replace the `### Statusline` heading with:

```markdown
### Statusline Claude Code

Claude Code affiche l'impact dans sa statusline. La statusline affiche l'impact de la **session en cours**.
```

In `docs/GUIDE-AVANCE.en.md`, replace the `### Statusline` heading with:

```markdown
### Claude Code statusline

Claude Code displays the impact in its statusline. The statusline displays the impact of the **current session**.
```

Keep all following paragraphs in place, including the session identifier,
manual command, unit, missing-data, and token diagnostic explanations.

- [ ] **Step 5: Add the concise README distinction**

In `README.md`, insert this paragraph immediately after `## Suivi en temps réel`
and before the existing sentence beginning `Une fois l'installation terminée`:

```markdown
Dans Claude Code, l'impact s'affiche dans la statusline. Dans OpenCode, une carte dédiée s'affiche dans le panneau latéral.
```

Do not add any implementation, configuration, or interaction detail: the
advanced guides remain the detailed reference.

- [ ] **Step 6: Run the targeted test to verify it still fails**

Run: `.venv/bin/python -m pytest tests/test_landing_page.py tests/test_docs_site.py -q`

Expected: FAIL only in `test_shared_script_handles_statusline_tab_keyboard_navigation`, because the markup, image, advanced-guide headings, and README distinction now exist but the tab interaction is not implemented.

### Task 3: Implement tab presentation and interaction in shared assets

**Files:**
- Modify: `docs/assets/style.css:229-236`
- Modify: `docs/assets/script.js:1-12`

**Interfaces:**
- Consumes: `.statusline-tabs`, `.statusline-tab`, `.statusline-panel`, and their ARIA IDs from Task 2.
- Produces: keyboard and pointer activation that synchronizes `aria-selected`, `tabindex`, and the panel `hidden` attribute.

- [ ] **Step 1: Add the CSS after the existing `.statusline-preview` rule**

```css
.statusline-tabs {
  display: flex;
  gap: 8px;
  margin: 16px 0;
}

.statusline-tab {
  appearance: none;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  background: var(--color-bg);
  color: var(--color-text);
  cursor: pointer;
  font: inherit;
  padding: 6px 12px;
}

.statusline-tab[aria-selected="true"] {
  background: var(--color-accent);
  border-color: var(--color-accent);
  color: #f6f9f7;
  font-weight: 700;
}

.statusline-tab:focus-visible {
  outline: 3px solid var(--color-text);
  outline-offset: 2px;
}

.opencode-statusline-preview {
  max-width: 310px;
}
```

The existing `.statusline-preview` rule keeps both images responsive. The
selected state changes background, border, weight, and text colour rather than
colour alone.

- [ ] **Step 2: Append the tab controller to `docs/assets/script.js`**

```js
document.querySelectorAll('[role="tablist"]').forEach((tabList) => {
  const tabs = [...tabList.querySelectorAll('[role="tab"]')];
  const activateTab = (tab) => {
    tabs.forEach((candidate) => {
      const selected = candidate === tab;
      const panel = document.getElementById(candidate.getAttribute("aria-controls"));
      candidate.setAttribute("aria-selected", String(selected));
      candidate.tabIndex = selected ? 0 : -1;
      panel.hidden = !selected;
    });
  };

  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => activateTab(tab));
    tab.addEventListener("keydown", (event) => {
      let nextIndex;
      if (event.key === "ArrowLeft") nextIndex = (index - 1 + tabs.length) % tabs.length;
      if (event.key === "ArrowRight") nextIndex = (index + 1) % tabs.length;
      if (event.key === "Home") nextIndex = 0;
      if (event.key === "End") nextIndex = tabs.length - 1;
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        activateTab(tab);
        return;
      }
      if (nextIndex === undefined) return;
      event.preventDefault();
      tabs[nextIndex].focus();
      activateTab(tabs[nextIndex]);
    });
  });
});
```

- [ ] **Step 3: Run the targeted tests to verify the green state**

Run: `.venv/bin/python -m pytest tests/test_landing_page.py tests/test_docs_site.py -q`

Expected: PASS.

- [ ] **Step 4: Inspect the diff without committing**

Run: `git diff --check && git diff -- docs/index.html docs/fr/index.html docs/assets/style.css docs/assets/script.js tests/test_landing_page.py`

Expected: no whitespace errors; only the planned landing-page, shared-asset, and test changes appear.

### Task 4: Build and manually verify the documentation site

**Files:**
- Modify: `scripts/build_docs.py:19-38`
- Modify: `tests/test_docs_site.py:181-203`
- Verify: `docs/index.html`
- Verify: `docs/fr/index.html`
- Verify: `docs/assets/opencode-statusline.png`
- Verify: `docs/assets/style.css`
- Verify: `docs/assets/script.js`

**Interfaces:**
- Consumes: completed implementation from Tasks 1-3.
- Produces: a clean generated documentation output and build and interaction evidence for the static landing page.

- [ ] **Step 1: Extend the failing build-output test**

In `test_build_script_syncs_output_into_docs_guide`, after the loop that
checks generated pages exist, add this assertion:

```python
        for html_path in guide_dir.rglob("*.html"):
            assert all(
                not line.endswith((" ", "\t"))
                for line in html_path.read_text(encoding="utf-8").splitlines()
            ), f"trailing whitespace in {html_path}"
```

Run: `uv run --extra dev python -m pytest tests/test_docs_site.py::test_build_script_syncs_output_into_docs_guide -q`

Expected: FAIL because MkDocs Material emits whitespace-only indentation in
some generated HTML navigation blocks.

- [ ] **Step 2: Normalize generated HTML in the build script**

Add this helper before `main` in `scripts/build_docs.py`:

```python
def _strip_trailing_whitespace(directory: Path) -> None:
    for html_path in directory.rglob("*.html"):
        lines = html_path.read_text(encoding="utf-8").splitlines()
        html_path.write_text(
            "\n".join(line.rstrip() for line in lines) + "\n", encoding="utf-8"
        )
```

Call `_strip_trailing_whitespace(Path(tmp))` immediately after the successful
`subprocess.run` and before replacing `docs/guide/`.

Run: `uv run --extra dev python -m pytest tests/test_docs_site.py::test_build_script_syncs_output_into_docs_guide -q`

Expected: PASS.

- [ ] **Step 3: Build the documentation output**

Run: `.venv/bin/python scripts/build_docs.py`

Expected: exits with status 0 and regenerates the committed `docs/guide/` output without altering either hand-written landing page.

- [ ] **Step 4: Run the full test suite**

Run: `.venv/bin/python -m pytest`

Expected: PASS with no failures.

- [ ] **Step 5: Manually verify the static landing pages**

Open `docs/index.html` and `docs/fr/index.html` at desktop and mobile widths.

Check each page:

1. Claude Code is selected on load and only its panel is visible.
2. Clicking OpenCode shows the OpenCode capture and hides Claude Code.
3. Left/Right Arrow, Home, End, Enter, and Space activate the expected tab from keyboard focus.
4. The focused tab has a visible outline and the selected tab has more than a colour-only distinction.
5. Both screenshots scale within the viewport without horizontal overflow.

- [ ] **Step 6: Inspect the final working tree without committing**

Run: `git status --short && git diff --check`

Expected: only the requested statusline tabs, their image asset, tests, and the approved design/plan artifacts are uncommitted; no whitespace errors.

## Self-Review

- Spec coverage: Tasks 1-4 cover both languages, both tools, source image,
  keyboard/pointer interaction, ARIA semantics, visual states, lazy loading,
  asset dimensions, unit coverage, build, and manual responsive verification.
- Placeholder scan: no placeholders, deferred choices, or unspecified file
  paths remain.
- Interface consistency: Task 2 defines the exact IDs, roles, classes, and
  `aria-controls` values consumed by Task 3 and asserted in Task 1.
