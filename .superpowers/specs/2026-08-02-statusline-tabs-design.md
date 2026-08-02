# Statusline Tabs on the Landing Page

## Goal

Replace the landing page's Claude Code-only statusline example with one
accessible `Statusline` example that lets visitors switch between Claude Code
and OpenCode.

## Scope

- Update both hand-written landing pages:
  - `docs/index.html` (English)
  - `docs/fr/index.html` (French)
- Replace the existing optional Claude Code statusline block in `#how-it-works`.
- Add `docs/assets/opencode-statusline.png` from the provided 310x115 OpenCode
  sidebar capture.
- Make the advanced guides symmetrical by naming the existing generic
  statusline section after Claude Code in both languages.
- Add a short README sentence that distinguishes the Claude Code statusline
  from the OpenCode sidebar card.
- Extend the existing shared stylesheet and JavaScript only; add no dependency
  or framework.

## Interface

The replacement block contains:

1. A `Statusline` label, translated to `Statusline` in French as well.
2. A tab list with `Claude Code` and `OpenCode` buttons.
3. Two associated panels, each with a tool-specific sentence and screenshot.

Claude Code is selected on initial load. Selecting a tab displays only its
panel. The English copy is:

- `See your impact in the Claude Code statusline, live, session after session.`
- `See your impact in the OpenCode statusline, live, session after session.`

The French copy is:

- `Vois ton impact dans la statusline Claude Code, en direct, session apres session.`
- `Vois ton impact dans la statusline OpenCode, en direct, session apres session.`

The existing `statusline.png` remains the Claude Code screenshot.
`opencode-statusline.png` illustrates the OpenCode sidebar card, including the
installed version, the greenhouse-gas, water, and energy ranges, and an
uncovered-model fallback warning.

## Advanced Guides

Rename the generic statusline section immediately preceding the existing
OpenCode section so the guide explicitly distinguishes the two integrations:

- `docs/GUIDE-AVANCE.md`: `### Statusline Claude Code`; state that Claude Code
  displays the impact in its statusline.
- `docs/GUIDE-AVANCE.en.md`: `### Claude Code statusline`; state that Claude
  Code displays the impact in its statusline.

Keep the existing session-scoping, unit-selection, missing-data, and token
diagnostic explanations under these renamed headings. The existing OpenCode
sections remain unchanged.

## README

Under `## Suivi en temps réel`, add one concise sentence before the shared
session-impact explanation: `Dans Claude Code, l'impact s'affiche dans la
statusline. Dans OpenCode, une carte dédiée s'affiche dans le panneau latéral.`
This introduces the two displays without duplicating their advanced-guide
behaviour or installation details.

## Accessibility

- Use buttons in an element with `role="tablist"`; each button has `role="tab"`,
  `aria-selected`, and `aria-controls`.
- Each panel has `role="tabpanel"` and is associated to its button with
  `aria-labelledby`; the inactive panel uses `hidden`.
- The existing shared script handles click, Left/Right Arrow, Home, and End so
  keyboard users can activate and move between tabs.
- Visible focus styling and a non-colour-only selected state are required.
- The screenshots get descriptive, tool-specific alternative text. The content
  is a screenshot of a product display, so the alt summarizes its purpose
  rather than transcribing every metric.

## Eco-design

- Reuse the shared CSS and existing JavaScript asset; no new request is needed
  for code.
- Load only the initially visible screenshot. The OpenCode screenshot receives
  `loading="lazy"` so it is fetched only when useful to the visitor.
- Declare image dimensions to avoid layout shifts.
- The documentation build removes trailing whitespace from generated HTML so its
  committed output passes `git diff --check` across MkDocs Material versions.

## Verification

- Extend `tests/test_landing_page.py` to require the two tab labels, both
  tool-specific text strings, accessible tab markup, and each image reference
  on the English and French pages.
- Run `.venv/bin/python -m pytest tests/test_landing_page.py`.
- Run `.venv/bin/python scripts/build_docs.py` and the complete
  `.venv/bin/python -m pytest` suite.
- Verify that generated HTML contains no trailing whitespace.
- Manually verify at desktop and mobile widths that only the active panel is
  visible, the tabs can be operated with mouse and keyboard, focus is visible,
  and both language pages show the correct image paths.
