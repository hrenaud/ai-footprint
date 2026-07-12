# Landing page AI Footprint (EN + FR) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a bilingual (EN/FR) static landing page under `docs/` (GitHub
Pages, no build step) that presents AI Footprint to non-developer visitors and
converts them to install (`curl … | bash`) or doc reading.

**Architecture:** Pure static HTML + one shared CSS file. `docs/index.html`
(EN, root) and `docs/fr/index.html` (FR) share identical section structure
(`<header id="nav">`, five `<section id="…">`, `<footer id="footer">`) and both
link to `docs/assets/style.css`. No JS, no templating, no framework. A pytest
file enforces structural parity between the two languages (same section ids,
same order, both link to EcoLogits, both link to the other language, both
reference the shared stylesheet) so a future edit to one language that forgets
the other fails CI-style locally.

**Tech Stack:** HTML5, CSS3 (flexbox/grid, no preprocessor), Python stdlib
`re` for the parity test (no new dependency), pytest (already in the project).

## Global Constraints

- Hosting: GitHub Pages, `/docs` folder on `main`, no `gh-pages` branch, no
  build pipeline.
- No framework, no static site generator, no JS build step, no new Python
  dependency (use stdlib only for the test).
- `docs/index.html` = English, at the docs root. `docs/fr/index.html` =
  French.
- Shared assets (CSS) live in `docs/assets/`, referenced by both languages.
- Section order (identical in both languages): nav → hero → how-it-works →
  criteria → why-ranges → multi-tools → footer.
- Hero: qualitative statement, no precise number up front. EN: "Every prompt
  has a cost — invisible, but real." FR: "Chaque prompt a un coût — invisible,
  mais réel." Trust badge under the subtitle links to
  `https://github.com/mlco2/ecologits`.
- Install one-liner:
  `curl -fsSL https://raw.githubusercontent.com/hrenaud/ai-footprint/main/install.sh | bash`.
- Doc link (nav + footer): `https://github.com/hrenaud/ai-footprint/blob/main/CONTRIBUTING.md`.
- GitHub repo link: `https://github.com/hrenaud/ai-footprint`.
- Methodology link (why-ranges section):
  `https://github.com/hrenaud/ai-footprint/blob/main/docs/METHODOLOGY.md`.
- License: AGPL-3.0-or-later (footer credit).
- Visual preview slot in hero: use a static CSS placeholder box (no real
  media production — out of scope per spec).
- Language switch must work round-trip: EN page links to `fr/index.html`, FR
  page links to `../index.html` (and `../assets/style.css` for the
  stylesheet).
- No analytics/tracking of any kind.

---

### Task 1: Structural parity test (EN/FR contract)

**Files:**

- Create: `tests/test_landing_page.py`

**Interfaces:**

- Consumes: `docs/index.html`, `docs/fr/index.html`, `docs/assets/style.css`
  (created in Tasks 2–3; this task's tests fail until then).
- Produces: the section-id contract later tasks must satisfy — `<header
id="nav">`, `<section id="hero">`, `<section id="how-it-works">`, `<section
id="criteria">`, `<section id="why-ranges">`, `<section id="multi-tools">`,
  `<footer id="footer">`, in that exact order, in both language files.

- [ ] **Step 1: Write the failing test**

```python
import re
from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parents[1] / "docs"

REQUIRED_IDS_IN_ORDER = [
    "nav",
    "hero",
    "how-it-works",
    "criteria",
    "why-ranges",
    "multi-tools",
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_landing_page.py -v`
Expected: FAIL — all tests error/fail with `FileNotFoundError` (no
`docs/index.html`, `docs/fr/index.html`, or `docs/assets/style.css` yet).

- [ ] **Step 3: Commit**

```bash
git add tests/test_landing_page.py
git commit -m "test: add EN/FR structural parity contract for landing page"
```

---

### Task 2: Shared stylesheet + English landing page

**Files:**

- Create: `docs/assets/style.css`
- Create: `docs/index.html`

**Interfaces:**

- Consumes: the section-id contract from Task 1
  (`nav`/`hero`/`how-it-works`/`criteria`/`why-ranges`/`multi-tools`/`footer`).
- Produces: `docs/assets/style.css` classes reused verbatim by Task 3's FR
  page: `.nav`, `.nav-links`, `.btn`, `.btn-primary`, `.btn-secondary`,
  `.badge-trust`, `.hero`, `.hero-preview`, `.steps`, `.step`, `.criteria-grid`,
  `.criterion-card`, `.why-ranges`, `.tools-list`, `.footer`,
  `.footer-links`. Task 3 must link `../assets/style.css` and reuse these
  exact class names so both pages render identically.

- [ ] **Step 1: Write `docs/assets/style.css`**

```css
:root {
  --color-bg: #0b1210;
  --color-bg-alt: #101a17;
  --color-text: #e8f0ec;
  --color-text-muted: #9fb3aa;
  --color-accent: #4ade80;
  --color-accent-dark: #16a34a;
  --color-border: #22332c;
  --radius: 8px;
  --max-width: 960px;
  font-size: 16px;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  background: var(--color-bg);
  color: var(--color-text);
  font-family:
    -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  line-height: 1.6;
}

a {
  color: var(--color-accent);
}

.wrap {
  max-width: var(--max-width);
  margin: 0 auto;
  padding: 0 24px;
}

/* Nav */
.nav {
  border-bottom: 1px solid var(--color-border);
  padding: 16px 0;
}

.nav .wrap {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}

.nav-brand {
  font-weight: 700;
  font-size: 1.1rem;
  text-decoration: none;
  color: var(--color-text);
}

.nav-links {
  display: flex;
  gap: 20px;
  list-style: none;
  margin: 0;
  padding: 0;
}

.nav-links a {
  text-decoration: none;
  color: var(--color-text-muted);
}

.nav-links a:hover {
  color: var(--color-accent);
}

/* Buttons */
.btn {
  display: inline-block;
  padding: 10px 20px;
  border-radius: var(--radius);
  text-decoration: none;
  font-weight: 600;
  border: 1px solid transparent;
}

.btn-primary {
  background: var(--color-accent);
  color: #06210f;
}

.btn-secondary {
  background: transparent;
  color: var(--color-text);
  border-color: var(--color-border);
}

/* Hero */
.hero {
  padding: 64px 0 48px;
  text-align: center;
}

.hero h1 {
  font-size: 2.2rem;
  margin: 0 0 16px;
}

.hero .subtitle {
  color: var(--color-text-muted);
  max-width: 640px;
  margin: 0 auto 20px;
}

.badge-trust {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  font-size: 0.85rem;
  color: var(--color-text-muted);
  text-decoration: none;
  margin-bottom: 28px;
}

.badge-trust:hover {
  border-color: var(--color-accent);
}

.hero-ctas {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-bottom: 32px;
  flex-wrap: wrap;
}

.hero-preview {
  max-width: 720px;
  margin: 0 auto;
  border: 1px dashed var(--color-border);
  border-radius: var(--radius);
  padding: 48px 24px;
  color: var(--color-text-muted);
  background: var(--color-bg-alt);
}

/* Sections */
section,
footer {
  padding: 48px 0;
  border-top: 1px solid var(--color-border);
}

section h2 {
  font-size: 1.6rem;
  text-align: center;
  margin: 0 0 32px;
}

/* How it works */
.steps {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 24px;
}

.step {
  background: var(--color-bg-alt);
  border-radius: var(--radius);
  padding: 20px;
}

.step .step-num {
  color: var(--color-accent);
  font-weight: 700;
  font-size: 0.85rem;
}

.step code {
  display: block;
  background: #06100b;
  padding: 8px;
  border-radius: 4px;
  font-size: 0.8rem;
  overflow-x: auto;
  margin-top: 8px;
}

/* Criteria */
.criteria-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 20px;
}

.criterion-card {
  background: var(--color-bg-alt);
  border-radius: var(--radius);
  padding: 20px;
  text-align: center;
}

.criterion-card .criterion-icon {
  font-size: 1.8rem;
  display: block;
  margin-bottom: 8px;
}

/* Why ranges */
.why-ranges p {
  max-width: 720px;
  margin: 0 auto 16px;
}

.why-ranges .links {
  text-align: center;
  margin-top: 24px;
}

/* Multi-tools */
.tools-list {
  display: flex;
  gap: 16px;
  justify-content: center;
  flex-wrap: wrap;
  list-style: none;
  padding: 0;
  margin: 0;
}

.tools-list li {
  background: var(--color-bg-alt);
  border-radius: var(--radius);
  padding: 12px 20px;
}

/* Footer */
.footer {
  text-align: center;
  color: var(--color-text-muted);
  font-size: 0.9rem;
}

.footer-links {
  display: flex;
  gap: 20px;
  justify-content: center;
  list-style: none;
  padding: 0;
  margin: 16px 0 0;
}

.footer-links a {
  color: var(--color-text-muted);
  text-decoration: none;
}

.footer-links a:hover {
  color: var(--color-accent);
}
```

- [ ] **Step 2: Write `docs/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>
      AI Footprint — measure the environmental cost of your AI sessions
    </title>
    <meta
      name="description"
      content="AI Footprint measures the environmental impact (CO2, water, energy, rare metals) of your Claude Code, OpenCode and Pi sessions, honestly — powered by EcoLogits."
    />
    <link rel="stylesheet" href="assets/style.css" />
  </head>
  <body>
    <header id="nav" class="nav">
      <div class="wrap">
        <a class="nav-brand" href="index.html">AI Footprint</a>
        <ul class="nav-links">
          <li>
            <a
              href="https://github.com/hrenaud/ai-footprint/blob/main/CONTRIBUTING.md"
              >Docs</a
            >
          </li>
          <li><a href="https://github.com/hrenaud/ai-footprint">GitHub</a></li>
          <li><a href="fr/index.html">FR</a></li>
        </ul>
      </div>
    </header>

    <section id="hero" class="hero">
      <div class="wrap">
        <h1>Every prompt has a cost — invisible, but real.</h1>
        <p class="subtitle">
          AI Footprint measures 5 environmental criteria of your AI coding
          sessions — greenhouse gases, water, energy, rare-metal depletion — and
          reports them as honest ranges, never a fake precise number.
        </p>
        <a class="badge-trust" href="https://github.com/mlco2/ecologits"
          >Calculated with EcoLogits — recognized open-source engine, offline,
          no invented numbers</a
        >
        <div class="hero-ctas">
          <a class="btn btn-primary" href="#how-it-works">Install</a>
          <a
            class="btn btn-secondary"
            href="https://github.com/hrenaud/ai-footprint/blob/main/CONTRIBUTING.md"
            >See the docs</a
          >
        </div>
        <div class="hero-preview">
          Statusline &amp; report preview coming soon
        </div>
      </div>
    </section>

    <section id="how-it-works">
      <div class="wrap">
        <h2>How it works</h2>
        <div class="steps">
          <div class="step">
            <span class="step-num">STEP 1</span>
            <p>Install with a single command — no configuration.</p>
            <code
              >curl -fsSL
              https://raw.githubusercontent.com/hrenaud/ai-footprint/main/install.sh
              | bash</code
            >
          </div>
          <div class="step">
            <span class="step-num">STEP 2</span>
            <p>Use Claude Code, OpenCode or Pi exactly as you already do.</p>
          </div>
          <div class="step">
            <span class="step-num">STEP 3</span>
            <p>
              See your impact in the statusline, live, session after session.
            </p>
          </div>
          <div class="step">
            <span class="step-num">STEP 4</span>
            <p>
              Run a full report anytime for a detailed breakdown by project and
              model.
            </p>
          </div>
        </div>
      </div>
    </section>

    <section id="criteria">
      <div class="wrap">
        <h2>5 criteria measured</h2>
        <div class="criteria-grid">
          <div class="criterion-card">
            <span class="criterion-icon">🌍</span>
            <h3>GWP</h3>
            <p>Greenhouse gases emitted, in CO2 equivalent.</p>
          </div>
          <div class="criterion-card">
            <span class="criterion-icon">💧</span>
            <h3>Water</h3>
            <p>Water consumed to cool the datacenters running the model.</p>
          </div>
          <div class="criterion-card">
            <span class="criterion-icon">⛏</span>
            <h3>ADPe</h3>
            <p>
              Depletion of rare mineral resources used to build the hardware.
            </p>
          </div>
          <div class="criterion-card">
            <span class="criterion-icon">⚡</span>
            <h3>Energy</h3>
            <p>Electricity consumed by the servers to answer your request.</p>
          </div>
          <div class="criterion-card">
            <span class="criterion-icon">🔥</span>
            <h3>PE</h3>
            <p>Primary energy required, upstream of electricity generation.</p>
          </div>
        </div>
      </div>
    </section>

    <section id="why-ranges" class="why-ranges">
      <div class="wrap">
        <h2>Why ranges, not a single number</h2>
        <p>
          The exact region of the datacenter answering your request is unknown,
          and its energy efficiency (PUE) varies widely. Any tool claiming a
          single precise figure is hiding that uncertainty — or making it up.
        </p>
        <p>
          AI Footprint doesn't reinvent the modeling: it delegates every
          calculation to <strong>EcoLogits</strong>, a recognized open-source
          engine already used by other projects in the community — verifiable,
          not a proprietary black box.
        </p>
        <div class="links">
          <a
            href="https://github.com/hrenaud/ai-footprint/blob/main/docs/METHODOLOGY.md"
            >Read the methodology</a
          >
          &nbsp;·&nbsp;
          <a href="https://github.com/mlco2/ecologits">EcoLogits on GitHub</a>
        </div>
      </div>
    </section>

    <section id="multi-tools">
      <div class="wrap">
        <h2>Works with your tools</h2>
        <ul class="tools-list">
          <li>Claude Code</li>
          <li>OpenCode / CRUSH</li>
          <li>Pi</li>
        </ul>
      </div>
    </section>

    <footer id="footer" class="footer">
      <div class="wrap">
        <p>
          AI Footprint is licensed under AGPL-3.0-or-later. Calculations powered
          by <a href="https://github.com/mlco2/ecologits">EcoLogits</a>.
        </p>
        <ul class="footer-links">
          <li><a href="https://github.com/hrenaud/ai-footprint">GitHub</a></li>
          <li>
            <a
              href="https://github.com/hrenaud/ai-footprint/blob/main/CONTRIBUTING.md"
              >Docs</a
            >
          </li>
          <li><a href="fr/index.html">FR</a></li>
        </ul>
      </div>
    </footer>
  </body>
</html>
```

- [ ] **Step 3: Run EN-scoped tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_landing_page.py -v -k "en_page or stylesheet_asset_exists"`
Expected: PASS (7 tests: 5 `test_en_page_*` + `test_stylesheet_asset_exists`;
note `test_fr_page_links_to_en_page` also matches `-k en_page` by substring
and will still fail — that's expected, it belongs to Task 3).

To scope precisely, instead run:
`.venv/bin/python -m pytest tests/test_landing_page.py -v -k "(en_page and not fr_page) or stylesheet_asset_exists"`
Expected: PASS, 0 failures.

- [ ] **Step 4: Commit**

```bash
git add docs/assets/style.css docs/index.html
git commit -m "feat: add English landing page"
```

---

### Task 3: French landing page

**Files:**

- Create: `docs/fr/index.html`

**Interfaces:**

- Consumes: `docs/assets/style.css` class names from Task 2 (`.nav`,
  `.nav-links`, `.btn`, `.btn-primary`, `.btn-secondary`, `.badge-trust`,
  `.hero`, `.hero-preview`, `.steps`, `.step`, `.criteria-grid`,
  `.criterion-card`, `.why-ranges`, `.tools-list`, `.footer`,
  `.footer-links`), referenced via `../assets/style.css`.
- Produces: nothing consumed by later tasks (Task 4 only runs tests/checks).

- [ ] **Step 1: Write `docs/fr/index.html`**

```html
<!DOCTYPE html>
<html lang="fr">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>
      AI Footprint — mesure l'impact environnemental de tes sessions d'IA
    </title>
    <meta
      name="description"
      content="AI Footprint mesure l'impact environnemental (CO2, eau, énergie, métaux rares) de tes sessions Claude Code, OpenCode et Pi, honnêtement — propulsé par EcoLogits."
    />
    <link rel="stylesheet" href="../assets/style.css" />
  </head>
  <body>
    <header id="nav" class="nav">
      <div class="wrap">
        <a class="nav-brand" href="index.html">AI Footprint</a>
        <ul class="nav-links">
          <li>
            <a
              href="https://github.com/hrenaud/ai-footprint/blob/main/CONTRIBUTING.md"
              >Doc</a
            >
          </li>
          <li><a href="https://github.com/hrenaud/ai-footprint">GitHub</a></li>
          <li><a href="../index.html">EN</a></li>
        </ul>
      </div>
    </header>

    <section id="hero" class="hero">
      <div class="wrap">
        <h1>Chaque prompt a un coût — invisible, mais réel.</h1>
        <p class="subtitle">
          AI Footprint mesure 5 critères environnementaux de tes sessions d'IA —
          gaz à effet de serre, eau, énergie, épuisement des métaux rares — et
          les affiche sous forme de fourchettes honnêtes, jamais un faux chiffre
          précis.
        </p>
        <a class="badge-trust" href="https://github.com/mlco2/ecologits"
          >Calculé avec EcoLogits — moteur open source reconnu, offline, aucun
          chiffre inventé</a
        >
        <div class="hero-ctas">
          <a class="btn btn-primary" href="#how-it-works">Installer</a>
          <a
            class="btn btn-secondary"
            href="https://github.com/hrenaud/ai-footprint/blob/main/CONTRIBUTING.md"
            >Voir la doc</a
          >
        </div>
        <div class="hero-preview">Aperçu statusline &amp; rapport à venir</div>
      </div>
    </section>

    <section id="how-it-works">
      <div class="wrap">
        <h2>Comment ça marche</h2>
        <div class="steps">
          <div class="step">
            <span class="step-num">ÉTAPE 1</span>
            <p>Installe en une seule commande — zéro configuration.</p>
            <code
              >curl -fsSL
              https://raw.githubusercontent.com/hrenaud/ai-footprint/main/install.sh
              | bash</code
            >
          </div>
          <div class="step">
            <span class="step-num">ÉTAPE 2</span>
            <p>
              Utilise Claude Code, OpenCode ou Pi exactement comme d'habitude.
            </p>
          </div>
          <div class="step">
            <span class="step-num">ÉTAPE 3</span>
            <p>
              Vois ton impact dans la statusline, en direct, session après
              session.
            </p>
          </div>
          <div class="step">
            <span class="step-num">ÉTAPE 4</span>
            <p>
              Lance un rapport complet à tout moment pour un détail par projet
              et par modèle.
            </p>
          </div>
        </div>
      </div>
    </section>

    <section id="criteria">
      <div class="wrap">
        <h2>5 critères mesurés</h2>
        <div class="criteria-grid">
          <div class="criterion-card">
            <span class="criterion-icon">🌍</span>
            <h3>GWP</h3>
            <p>Gaz à effet de serre émis, en équivalent CO2.</p>
          </div>
          <div class="criterion-card">
            <span class="criterion-icon">💧</span>
            <h3>Eau</h3>
            <p>
              Eau consommée pour refroidir les datacenters qui font tourner le
              modèle.
            </p>
          </div>
          <div class="criterion-card">
            <span class="criterion-icon">⛏</span>
            <h3>ADPe</h3>
            <p>
              Épuisement des ressources minérales rares utilisées pour fabriquer
              le matériel.
            </p>
          </div>
          <div class="criterion-card">
            <span class="criterion-icon">⚡</span>
            <h3>Énergie</h3>
            <p>
              Électricité consommée par les serveurs pour répondre à ta requête.
            </p>
          </div>
          <div class="criterion-card">
            <span class="criterion-icon">🔥</span>
            <h3>PE</h3>
            <p>
              Énergie primaire nécessaire, en amont de la production
              d'électricité.
            </p>
          </div>
        </div>
      </div>
    </section>

    <section id="why-ranges" class="why-ranges">
      <div class="wrap">
        <h2>Pourquoi des fourchettes, pas un chiffre unique</h2>
        <p>
          La région exacte du datacenter qui répond à ta requête est inconnue,
          et son efficacité énergétique (PUE) varie fortement. Tout outil qui
          affiche un chiffre précis unique masque cette incertitude — ou
          l'invente.
        </p>
        <p>
          AI Footprint ne réinvente pas la modélisation : il délègue chaque
          calcul à <strong>EcoLogits</strong>, un moteur open source reconnu,
          déjà utilisé par d'autres projets de la communauté — vérifiable, pas
          une boîte noire propriétaire.
        </p>
        <div class="links">
          <a
            href="https://github.com/hrenaud/ai-footprint/blob/main/docs/METHODOLOGY.md"
            >Lire la méthodologie</a
          >
          &nbsp;·&nbsp;
          <a href="https://github.com/mlco2/ecologits">EcoLogits sur GitHub</a>
        </div>
      </div>
    </section>

    <section id="multi-tools">
      <div class="wrap">
        <h2>Compatible avec tes outils</h2>
        <ul class="tools-list">
          <li>Claude Code</li>
          <li>OpenCode / CRUSH</li>
          <li>Pi</li>
        </ul>
      </div>
    </section>

    <footer id="footer" class="footer">
      <div class="wrap">
        <p>
          AI Footprint est sous licence AGPL-3.0-or-later. Calculs propulsés par
          <a href="https://github.com/mlco2/ecologits">EcoLogits</a>.
        </p>
        <ul class="footer-links">
          <li><a href="https://github.com/hrenaud/ai-footprint">GitHub</a></li>
          <li>
            <a
              href="https://github.com/hrenaud/ai-footprint/blob/main/CONTRIBUTING.md"
              >Doc</a
            >
          </li>
          <li><a href="../index.html">EN</a></li>
        </ul>
      </div>
    </footer>
  </body>
</html>
```

- [ ] **Step 2: Run the full test suite**

Run: `.venv/bin/python -m pytest tests/test_landing_page.py -v`
Expected: PASS, 11/11 tests green.

- [ ] **Step 3: Commit**

```bash
git add docs/fr/index.html
git commit -m "feat: add French landing page"
```

---

### Task 4: Manual visual verification

**Files:** none (no code changes — verification only).

**Interfaces:**

- Consumes: `docs/index.html`, `docs/fr/index.html`, `docs/assets/style.css`
  from Tasks 2–3.
- Produces: nothing — this task's output is a pass/fail confirmation.

- [ ] **Step 1: Serve the docs folder locally**

```bash
cd docs && python3 -m http.server 8000
```

- [ ] **Step 2: Open both pages in a browser and check the golden path**

Open `http://localhost:8000/` and `http://localhost:8000/fr/`. Confirm for
each:

- All 7 sections render in order with visible content (no missing images
  breaking layout — the hero preview is a text placeholder box, not an
  `<img>`).
- The "Installer"/"Install" primary CTA scrolls to `#how-it-works`.
- The EcoLogits trust badge link opens `https://github.com/mlco2/ecologits`.
- The FR↔EN language links round-trip correctly (EN → `fr/index.html` → EN
  `../index.html` lands back on the original page, same for footer links).
- The GitHub and CONTRIBUTING.md links point to valid `https://github.com/hrenaud/ai-footprint...` URLs.
- No horizontal scroll or broken layout at narrow widths (resize the browser
  window to ~375px).

- [ ] **Step 3: Stop the local server**

Press `Ctrl+C` in the terminal running `http.server`.

- [ ] **Step 4: Run the full test suite one final time**

Run: `.venv/bin/python -m pytest tests/test_landing_page.py -v`
Expected: PASS, 11/11 tests green — confirms no regression from manual
inspection (no files should have changed in this task).

No commit for this task — it is verification only, not a code change.
