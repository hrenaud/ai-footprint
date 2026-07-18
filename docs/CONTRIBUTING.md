# Contribuer à ai-footprint

Guide technique : mise en place dev, conventions, architecture du code, schéma de
données, et comment étendre le projet. Pour **comment l'impact est calculé** (les
échanges avec EcoLogits, les choix de méthodologie), voir
[`METHODOLOGY.md`](METHODOLOGY.md).

## Mise en place

```bash
git clone https://github.com/hrenaud/ai-footprint
cd ai-footprint
python3 -m venv .venv
.venv/bin/pip install -e .        # installe ai-footprint + EcoLogits (tag 0.11.0)
.venv/bin/python -m pytest -q     # la suite doit être verte
```

Lancer la CLI en dev : `.venv/bin/python -m ai_footprint <commande>`.

### Tester `install.sh` sur une branche (avant merge sur `main`)

`install.sh` installe par défaut `main`, mais accepte `AI_FOOTPRINT_REF` pour
pointer sur n'importe quelle branche ou tag — utile pour tester une contribution
en conditions réelles (clone + venv + hook Claude Code) avant de merger :

```bash
AI_FOOTPRINT_REF=ma-branche AI_FOOTPRINT_DIR=/tmp/ai-footprint-test \
  curl -fsSL https://raw.githubusercontent.com/hrenaud/ai-footprint/main/install.sh | bash
```

`AI_FOOTPRINT_DIR` évite d'écraser l'installation courante dans
`~/.ai-footprint/src` pendant le test. Voir aussi `AI_FOOTPRINT_DB`,
`AI_FOOTPRINT_NO_CLAUDE`, `AI_FOOTPRINT_NO_INGEST` en tête d'`install.sh`.

Pour nettoyer une installation de test : `AI_FOOTPRINT_DIR=/tmp/ai-footprint-test
AI_FOOTPRINT_PURGE_DB=1 bash uninstall.sh` (`uninstall.sh` défait tout ce que
`install.sh` met en place ; utilise les mêmes variables `AI_FOOTPRINT_DIR` /
`AI_FOOTPRINT_DB`, plus `AI_FOOTPRINT_PURGE_DB=1` pour aussi supprimer la base).

## Conventions

- **Français** pour le code (commentaires, docstrings) et les messages utilisateur.
- **TDD** : écrire le test, le voir échouer, implémenter, le voir passer, committer.
- **Commits sémantiques** : `feat:`, `fix:`, `docs:`, `refactor:`, `perf:`, `test:`,
  `chore:`.
- Ne jamais supprimer un fichier avec `rm` — utiliser `trash`.
- **Simplicité d'abord** (YAGNI) : le minimum de code qui résout le problème.
- Paramètres EcoLogits **en milliards** partout (cf. METHODOLOGY).

## Architecture

```
JSONL Claude Code (~/.claude/projects/**/*.jsonl)
    ↓
ClaudeCodeCollector (parse, normalise, temps actif, client)
    ↓
InferenceEvent[]  (provider, model, tokens, timestamp, session, projet, active_seconds, client)
    ↓
EcoLogitsEngine (offline, EcoLogits 0.11.0)
    ├─ modèle reconnu → llm_impacts()
    └─ sinon → ModelParamsResolver + compute_llm_impacts()
    ↓
ImpactRecord (5 critères min/max, phases usage/embodied, warnings, error)
    ↓
SQLiteStore (idempotent ; events / impacts / sessions / pending_models)
    ↓
CLI : report · statusline · resolve · models   (lisent la DB, jamais les JSONL)
```

### Modules (`ai_footprint/`)

| Module                      | Rôle                                                                                                                                                                                                     |
| --------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `collectors/claude_code.py` | parse les JSONL → `InferenceEvent` (ignore non-`assistant`/sans usage ; dérive projet du `cwd` ; estime `active_seconds` ; renseigne `client`). Aucun contenu de prompt/réponse extrait.                 |
| `models.py`                 | dataclass `InferenceEvent`.                                                                                                                                                                              |
| `impact/engine.py`          | `EcoLogitsEngine.compute()` : chemin registre vs fallback auto-hébergé ; `_extract_impacts` (totals/usage/embodied en min/max).                                                                          |
| `impact/resolver.py`        | `ModelResolver` : alias de noms (`Config.model_aliases`).                                                                                                                                                |
| `impact/params.py`          | `ModelParamsResolver` (cascade registre→cache→HF→file) + `fetch_hf_params(repo)` (safetensors ÷ 1e9, offline-safe).                                                                                      |
| `store/db.py`               | `SQLiteStore` : ingestion idempotente, agrégations, recompute.                                                                                                                                           |
| `report/cli.py`             | rendu des sections du rapport (5 + une 6ᵉ, intensité par outil, si plusieurs outils sont présents). Expose aussi `_central`/`_scale`/`_ranked_projects`, réutilisés par `card/cli.py`.                   |
| `card/cli.py`               | sous-commande `card` : agrège les totaux (`build_card_data`), génère le HTML (`render_card_html` + `card/template.html`), rend le PNG via Chrome/Chromium headless local (`render_png`, `_find_chrome`). |
| `resolve/cli.py`            | sous-commande `resolve` (list/set/recompute/forget).                                                                                                                                                     |
| `statusline/line.py`        | ligne compacte.                                                                                                                                                                                          |
| `dates.py`                  | `parse_since()` (normalise les dates `--since`).                                                                                                                                                         |
| `config.py`                 | dataclass `Config` (JSON `~/.ai-footprint/config.json`).                                                                                                                                                 |
| `cache.py`                  | cache JSON générique throttlé par TTL (`load_json_cache`/`save_json_cache`/`should_refresh`), réutilisé par `tool_updates.py` et `nudge.py`.                                                             |
| `nudge.py`                  | propositions proactives : `check_self_update` (mise à jour ai-footprint via tag GitHub), `check_uncovered_batch`/`mark_batch_prompted` (resolve des modèles non couverts, silence par lot).              |
| `__main__.py`               | parseur d'arguments + dispatch des commandes.                                                                                                                                                            |

### Schéma de la base (`~/.ai-footprint/ai-footprint.db`)

`sqlite3`, `row_factory = Row`, migrations additives par `ALTER TABLE`.

```sql
CREATE TABLE events (
  session_id TEXT, msg_id TEXT,
  provider TEXT, model TEXT,
  input_tokens INTEGER, output_tokens INTEGER,
  cache_creation_tokens INTEGER, cache_read_tokens INTEGER,
  timestamp TEXT,                  -- ISO 8601
  project TEXT,                    -- dérivé du cwd
  active_seconds REAL DEFAULT 0,   -- temps actif estimé (intensité)
  client TEXT DEFAULT '',          -- outil source (claude-code…)
  PRIMARY KEY (session_id, msg_id)
);

CREATE TABLE impacts (
  session_id TEXT, msg_id TEXT,
  model_resolved TEXT, zone TEXT, methodology_version TEXT,
  energy_min REAL, energy_max REAL, gwp_min REAL, gwp_max REAL,
  adpe_min REAL, adpe_max REAL, pe_min REAL, pe_max REAL,
  wcf_min REAL, wcf_max REAL,
  breakdown_json TEXT,             -- {"usage": {...}, "embodied": {...}}
  warnings TEXT, error TEXT,       -- error non NULL = non couvert
  PRIMARY KEY (session_id, msg_id)
);

CREATE TABLE sessions (session_id TEXT PRIMARY KEY, project TEXT, started_at TEXT, ended_at TEXT);
CREATE TABLE pending_models (provider TEXT, model TEXT, first_seen TEXT, occurrences INTEGER DEFAULT 0,
                             PRIMARY KEY (provider, model));
```

**Idempotence** : `INSERT OR IGNORE` sur `(session_id, msg_id)` ; la ré-ingestion ne
recalcule pas l'impact mais rétro-remplit `active_seconds`/`client` manquants.

**Méthodes clés de `SQLiteStore`** (lecture filtrable par `since`, comparaison
lexicographique sur `timestamp`) :

- `rows_for_report(since, session_id)` — total / projets.
- `tokens_by_model(since)` — tokens totaux + centrale & bornes min/max par critère.
- `session_count(since)`, `first_session_started_at()`, `clients_covered(since)` —
  utilisées par la card (sous-héro, libellé de période, outils couverts).
- `intensity_by_model(since)` — heures actives, tok/h, impact/h (events à temps > 0).
- `uncovered_by_model(since)` — modèles non couverts (hors `<synthetic>`).
- `uncovered_keys()` — couples `(provider, model)` non couverts (hors `<synthetic>`), sans filtre `since` ; utilisée par `resolve --retry-hf` et par `ai_footprint/nudge.py`.
- `coverage()` — `{total, measured, uncovered}`.
- `recompute_errors(engine, config)` — recalcule les events en `error` → `{before, after}`.
- `mark_model_events_error(provider, model, error)` — repasse un modèle en erreur
  (appariement `(session_id, msg_id)`) pour un revert de mapping.

### Séparation events / impacts

`events` = source brute normalisée (immuable). `impacts` = résultat du calcul (dépend
du moteur + zone + params). Permet de **recalculer** sans re-parser les JSONL.

### Card PNG : Chrome headless plutôt que Playwright

Le rendu HTML → PNG de `ai-footprint card` pilote un **Chrome/Chromium local déjà
installé** en subprocess (`--headless=new --screenshot=...`), pas Playwright : zéro
nouvelle dépendance Python, n'alourdit pas l'installation par défaut (le hook Stop
de la statusline n'a pas besoin d'un navigateur). `card/cli.py::_find_chrome()`
détecte le binaire (`CHROME_BIN`, chemins macOS usuels, puis `PATH`) ; si absent,
la commande échoue proprement avec l'instruction d'installation plutôt que de
planter.

## Tests

`tests/` (pytest). Conventions utiles :

- **Offline déterministe** : pour forcer l'échec d'un lookup Hugging Face sans réseau,
  utiliser un nom de modèle contenant `:` (rejeté par la validation HF avant tout
  appel réseau). Pour le chemin succès, **mocker** `huggingface_hub.model_info` via
  `monkeypatch.setitem(sys.modules, "huggingface_hub", fake)` (cf. `test_params_huggingface.py`).
- **Config temporaire** dans les tests CLI : monkeypatch `Config.load`/`Config.save`
  vers un chemin `tmp_path` (cf. `test_cli_models.py`).

Lancer : `.venv/bin/python -m pytest -q`.

## Site de documentation (docs/guide)

Les Markdown de `docs/` (`METHODOLOGY.md`, `comparaison-donnees-outils.md`,
`publication-pypi.md`, `checklist-nouvel-outil.md`) sont convertis en HTML via
**MkDocs** (+ `mkdocs-static-i18n`), indépendamment des landing pages
(`docs/index.html`, `docs/fr/index.html`) qui restent écrites à la main.

- Config : `mkdocs.yml` (`docs_dir: docs`, `exclude_docs` exclut les landing
  pages/assets pour que MkDocs ne touche qu'aux `.md`).
- Bilingue : FR est la locale par défaut (contenu actuel), `/en/` est prêt à
  accueillir des traductions (`fichier.en.md`) — tant qu'elles n'existent pas,
  `/en/` affiche le contenu FR (fallback `mkdocs-static-i18n`).
- GitHub Pages sert `docs/` tel quel (pas de build serveur) : après toute
  modification d'un des Markdown, régénérer et **commiter** le résultat :

  ```bash
  .venv/bin/python scripts/build_docs.py
  ```

  Le script build dans un dossier temporaire puis remplace `docs/guide/`
  (le dossier temporaire `.mkdocs-build/` est gitignore).

## Étendre

- **Nouveau collecteur** (autre outil que Claude Code) : implémenter un collecteur qui
  émet des `InferenceEvent` (renseigner `provider`/`client`), sur le modèle de
  `ClaudeCodeCollector`. Le reste du pipeline est neutre vis-à-vis de la source.
  Checklist complète à suivre à chaque intégration :
  [`checklist-nouvel-outil.md`](checklist-nouvel-outil.md).
- **Nouveau skill** : ajouter `skills/<nom>/SKILL.md` (frontmatter `name`/`description`).
  L'installeur le déploie par symlink dans `~/.claude/skills/`.
- **Résolution de modèles** : la cascade vit dans `impact/params.py` ; la CLI
  `resolve` (déterministe : HF + recompute) dans `resolve/cli.py` ; le mapping
  nom→repo (jugement) dans le skill `/footprint-resolve`. Les échecs HF sont
  mémorisés (cache négatif en mémoire + persisté dans `config.json`, TTL 7 jours) ;
  `resolve --retry-hf` purge ce cache et retente la cascade sur les non couverts.
  Les params estimés depuis la taille des fichiers portent des warnings de
  provenance (`params-bytes-per-param:<n>`, `params-range-unknown-dtype`) et sont
  signalés dans le rapport.

## Backlog technique

Voir [`.superpowers/specs/2026-07-02-qualite-lecture-resolution-design.md`](../.superpowers/specs/2026-07-02-qualite-lecture-resolution-design.md) :
correctifs qualité de la lecture des données et de la résolution des modèles
(cache négatif HF, estimation 4-bit…), et l'évolution « étape WebSearch » dans la
cascade de résolution. `resolve --set "P/M=repo:<actifs>"` gère les MoE.

## Release

Un release bump la version sémantique, génère le CHANGELOG et crée le tag.

**Toujours avec le binaire du venv local** (`.venv/bin/ai-footprint`), jamais la
commande globale `ai-footprint` : celle-ci exécute le code du clone installé
(`~/.ai-footprint/src`) et y ferait le commit/tag au lieu du repo dev où tu
travailles.

```bash
.venv/bin/ai-footprint release bump <patch|minor|major> [--no-push]
```

- `patch` : corrections backward-compatible
- `minor` : nouvelles fonctionnalités backward-compatibles
- `major` : changements incompatibles

Le process :

1. Vérifie que l'arbre est propre, qu'on est sur `main`, et que le tag cible n'existe pas.
2. Calcule la nouvelle version (ex. `0.1.0` → `0.2.0`).
3. Génère le CHANGELOG entre le dernier tag `v*` et HEAD en exploitant les commits conventionnels (`feat:`, `fix:`, etc.).
4. Bump `pyproject.toml` + `ai_footprint/__init__.py`.
5. Prepend le nouveau bloc dans `CHANGELOG.md`.
6. Commit `chore(release): X.Y.Z` + tag `vX.Y.Z`.
7. **Push `origin main --tags` par défaut** (option `--no-push` pour skipper).

Preuve : les tests `tests/test_release.py` (31 tests) couvrent le cycle complet.

> **Note** : avant le premier tag `v*`, le CHANGELOG est maintenu manuellement (section « Pré-versioning »). Après le premier release, il est entièrement auto-généré.

## Veille des dépendances (ecologits, huggingface_hub)

Un workflow GitHub Actions (`.github/workflows/check-tool-updates.yml`, cron
hebdomadaire + déclenchement manuel) compare les versions pinnées dans
`pyproject.toml` (ecologits épinglé en exact, huggingface_hub) aux dernières
versions publiées sur PyPI (via `ai_footprint/tool_updates.py`) et
ouvre une issue si une nouvelle version existe.

**Aucun bump automatique** : ecologits est épinglé sur une version PyPI exacte car un
bump mineur en `0.x` peut casser la cascade de calcul, et l'outil installé
partage sa base avec le repo dev (cf. § Deux codebases, une base) — un bump
silencieux serait risqué. L'issue sert juste de rappel ; le bump se fait à la
main dans `pyproject.toml` après test.

En complément du cron hebdomadaire, un hook **`SessionStart` local au repo dev**
(`.claude/settings.json`, _pas_ le `~/.claude/settings.json` global installé par
`install.sh`) lance `ai-footprint tool-updates-check` à chaque démarrage de
session Claude Code dans ce projet, et affiche un message si une mise à jour
ecologits/huggingface_hub est disponible. La vérification réseau est mise en
cache 24h (`.claude/tool-updates-cache.json`, ignoré par git) pour ne pas
ralentir chaque démarrage de session. Logique testée dans
`tests/test_tool_updates.py` (`session_start_notice`, `should_refresh`,
`load_cache`).

> **À ne pas confondre avec le hook `SessionStart` global** ajouté par
> `install.sh` pour les nudges utilisateur (`ai-footprint nudge --claude-hook`,
> cf. `ai_footprint/nudge.py`) : celui-ci est **interne au repo dev**
> (`.claude/settings.json`, non installé chez les utilisateurs finaux) et sert
> à alerter les mainteneurs d'ai-footprint sur les nouvelles versions
> d'ecologits/huggingface_hub — un sujet entièrement différent des nudges
> destinés aux utilisateurs finaux d'ai-footprint.

## Hors périmètre actuel (coutures posées)

Collecteur inférence locale en stub ; `compute_live()` (instrumentation
temps réel) et `import_legacy()` non implémentés ; export CSV/JSON et énergie du poste
de travail hors périmètre.
