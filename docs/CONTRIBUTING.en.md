# Contributing to ai-footprint

Technical guide: dev setup, conventions, code architecture, data schema, and
how to extend the project. For **how impact is calculated** (the exchanges
with EcoLogits, the methodology choices), see
[`METHODOLOGY.md`](METHODOLOGY.md).

## Setup

```bash
git clone https://github.com/hrenaud/ai-footprint
cd ai-footprint
python3 -m venv .venv
.venv/bin/pip install -e .        # installs ai-footprint + EcoLogits (tag 0.11.0)
.venv/bin/python -m pytest -q     # the suite must be green
```

Run the CLI in dev: `.venv/bin/python -m ai_footprint <command>`.

### Testing `install.sh` on a branch (before merging into `main`)

`install.sh` installs `main` by default, but accepts `AI_FOOTPRINT_REF` to
point at any branch or tag — useful to test a contribution under real
conditions (clone + venv + Claude Code hook) before merging:

```bash
AI_FOOTPRINT_REF=my-branch AI_FOOTPRINT_DIR=/tmp/ai-footprint-test \
  curl -fsSL https://raw.githubusercontent.com/hrenaud/ai-footprint/main/install.sh | bash
```

`AI_FOOTPRINT_DIR` avoids overwriting the current installation in
`~/.ai-footprint/src` during the test. See also `AI_FOOTPRINT_DB`,
`AI_FOOTPRINT_NO_CLAUDE`, `AI_FOOTPRINT_NO_INGEST` at the top of
`install.sh`.

To clean up a test installation:
`AI_FOOTPRINT_DIR=/tmp/ai-footprint-test AI_FOOTPRINT_PURGE_DB=1 bash uninstall.sh`
(`uninstall.sh` undoes everything `install.sh` sets up; it uses the same
`AI_FOOTPRINT_DIR` / `AI_FOOTPRINT_DB` variables, plus
`AI_FOOTPRINT_PURGE_DB=1` to also delete the database).

## Conventions

- **French** for code (comments, docstrings) and user-facing messages.
- **TDD**: write the test, watch it fail, implement, watch it pass, commit.
- **Semantic commits**: `feat:`, `fix:`, `docs:`, `refactor:`, `perf:`,
  `test:`, `chore:`.
- Never delete a file with `rm` — use `trash`.
- **Simplicity first** (YAGNI): the minimum code that solves the problem.
- EcoLogits parameters **in billions** everywhere (see METHODOLOGY).

## Architecture

```
JSONL Claude Code (~/.claude/projects/**/*.jsonl)
    ↓
ClaudeCodeCollector (parse, normalize, active time, client)
    ↓
InferenceEvent[]  (provider, model, tokens, timestamp, session, project, active_seconds, client)
    ↓
EcoLogitsEngine (offline, EcoLogits 0.11.0)
    ├─ recognized model → llm_impacts()
    └─ otherwise → ModelParamsResolver + compute_llm_impacts()
    ↓
ImpactRecord (5 criteria min/max, usage/embodied phases, warnings, error)
    ↓
SQLiteStore (idempotent; events / impacts / sessions / pending_models)
    ↓
CLI: report · statusline · resolve · models   (read the DB, never the JSONL)
```

### Modules (`ai_footprint/`)

| Module                      | Role                                                                                                                                                                                                               |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `collectors/claude_code.py` | parses JSONL → `InferenceEvent` (ignores non-`assistant`/without usage; derives project from `cwd`; estimates `active_seconds`; fills `client`). No prompt/response content is extracted.                          |
| `models.py`                 | `InferenceEvent` dataclass.                                                                                                                                                                                        |
| `impact/engine.py`          | `EcoLogitsEngine.compute()`: registry path vs. self-hosted fallback; `_extract_impacts` (totals/usage/embodied as min/max).                                                                                        |
| `impact/resolver.py`        | `ModelResolver`: name aliases (`Config.model_aliases`).                                                                                                                                                            |
| `impact/params.py`          | `ModelParamsResolver` (cascade registry→cache→HF→file) + `fetch_hf_params(repo)` (safetensors ÷ 1e9, offline-safe).                                                                                                |
| `store/db.py`               | `SQLiteStore`: idempotent ingestion, aggregations, recompute.                                                                                                                                                      |
| `report/cli.py`             | renders the report sections (5, plus a 6th, intensity per tool, if several tools are present). Also exposes `_central`/`_scale`/`_ranked_projects`, reused by `card/cli.py`.                                       |
| `card/cli.py`               | `card` subcommand: aggregates the totals (`build_card_data`), generates the HTML (`render_card_html` + `card/template.html`), renders the PNG via a local headless Chrome/Chromium (`render_png`, `_find_chrome`). |
| `resolve/cli.py`            | `resolve` subcommand (list/set/recompute/forget).                                                                                                                                                                  |
| `statusline/line.py`        | compact line.                                                                                                                                                                                                      |
| `dates.py`                  | `parse_since()` (normalizes `--since` dates).                                                                                                                                                                      |
| `config.py`                 | `Config` dataclass (JSON `~/.ai-footprint/config.json`).                                                                                                                                                           |
| `cache.py`                  | generic JSON cache throttled by TTL (`load_json_cache`/`save_json_cache`/`should_refresh`), reused by `tool_updates.py` and `nudge.py`.                                                                            |
| `nudge.py`                  | proactive proposals: `check_self_update` (ai-footprint update via GitHub tag), `check_uncovered_batch`/`mark_batch_prompted` (resolving uncovered models, batch silence).                                          |
| `__main__.py`               | argument parser + command dispatch.                                                                                                                                                                                |

### Database schema (`~/.ai-footprint/ai-footprint.db`)

`sqlite3`, `row_factory = Row`, additive migrations via `ALTER TABLE`.

```sql
CREATE TABLE events (
  session_id TEXT, msg_id TEXT,
  provider TEXT, model TEXT,
  input_tokens INTEGER, output_tokens INTEGER,
  cache_creation_tokens INTEGER, cache_read_tokens INTEGER,
  timestamp TEXT,                  -- ISO 8601
  project TEXT,                    -- derived from cwd
  active_seconds REAL DEFAULT 0,   -- estimated active time (intensity)
  client TEXT DEFAULT '',          -- source tool (claude-code…)
  PRIMARY KEY (session_id, msg_id)
);

CREATE TABLE impacts (
  session_id TEXT, msg_id TEXT,
  model_resolved TEXT, zone TEXT, methodology_version TEXT,
  energy_min REAL, energy_max REAL, gwp_min REAL, gwp_max REAL,
  adpe_min REAL, adpe_max REAL, pe_min REAL, pe_max REAL,
  wcf_min REAL, wcf_max REAL,
  breakdown_json TEXT,             -- {"usage": {...}, "embodied": {...}}
  warnings TEXT, error TEXT,       -- non-NULL error = uncovered
  PRIMARY KEY (session_id, msg_id)
);

CREATE TABLE sessions (session_id TEXT PRIMARY KEY, project TEXT, started_at TEXT, ended_at TEXT);
CREATE TABLE pending_models (provider TEXT, model TEXT, first_seen TEXT, occurrences INTEGER DEFAULT 0,
                             PRIMARY KEY (provider, model));
```

**Idempotence**: `INSERT OR IGNORE` on `(session_id, msg_id)`; re-ingestion
does not recompute the impact but backfills missing `active_seconds`/`client`.

**Key `SQLiteStore` methods** (readable filtered by `since`, lexicographic
comparison on `timestamp`):

- `rows_for_report(since, session_id)` — total / projects.
- `tokens_by_model(since)` — total tokens + central value & min/max bounds
  per criterion.
- `session_count(since)`, `first_session_started_at()`,
  `clients_covered(since)` — used by the card (sub-hero, period label,
  covered tools).
- `intensity_by_model(since)` — active hours, tok/h, impact/h (events with
  time > 0).
- `uncovered_by_model(since)` — uncovered models (excluding `<synthetic>`).
- `uncovered_keys()` — uncovered `(provider, model)` pairs (excluding
  `<synthetic>`), without a `since` filter; used by `resolve --retry-hf` and
  by `ai_footprint/nudge.py`.
- `coverage()` — `{total, measured, uncovered}`.
- `recompute_errors(engine, config)` — recomputes events in `error` →
  `{before, after}`.
- `mark_model_events_error(provider, model, error)` — puts a model back into
  error state (matching `(session_id, msg_id)`) to revert a mapping.

### Separation of events / impacts

`events` = normalized raw source (immutable). `impacts` = calculation
result (depends on the engine + zone + params). This allows
**recalculating** without re-parsing the JSONL.

### Card PNG: headless Chrome rather than Playwright

The HTML → PNG rendering of `ai-footprint card` drives an **already
installed local Chrome/Chromium** as a subprocess (`--headless=new
--screenshot=...`), not Playwright: zero new Python dependency, doesn't add
weight to the default installation (the statusline's `Stop` hook doesn't
need a browser). `card/cli.py::_find_chrome()` detects the binary
(`CHROME_BIN`, common macOS paths, then `PATH`); if absent, the command
fails cleanly with install instructions rather than crashing.

## Tests

`tests/` (pytest). Useful conventions:

- **Deterministic offline**: to force a Hugging Face lookup to fail without
  network, use a model name containing `:` (rejected by HF validation
  before any network call). For the success path, **mock**
  `huggingface_hub.model_info` via
  `monkeypatch.setitem(sys.modules, "huggingface_hub", fake)` (see
  `test_params_huggingface.py`).
- **Temporary config** in CLI tests: monkeypatch `Config.load`/`Config.save`
  to a `tmp_path` path (see `test_cli_models.py`).

Run: `.venv/bin/python -m pytest -q`.

## Documentation site (docs/guide)

The Markdown files in `docs/` (`METHODOLOGY.md`,
`comparaison-donnees-outils.md`, `publication-pypi.md`,
`checklist-nouvel-outil.md`) are converted to HTML via **MkDocs** (+
`mkdocs-static-i18n`), independently of the landing pages
(`docs/index.html`, `docs/fr/index.html`) which remain hand-written.

- Config: `mkdocs.yml` (`docs_dir: docs`, `exclude_docs` excludes the
  landing pages/assets so MkDocs only touches the `.md` files).
- Bilingual: FR is the default locale (current content), `/en/` is ready to
  host translations (`file.en.md`) — as long as they don't exist, `/en/`
  shows the FR content (`mkdocs-static-i18n` fallback).
- GitHub Pages serves `docs/` as-is (no server-side build): after any
  change to one of the Markdown files, regenerate and **commit** the
  result:

  ```bash
  .venv/bin/python scripts/build_docs.py
  ```

  The script builds into a temporary folder then replaces `docs/guide/`
  (the temporary `.mkdocs-build/` folder is gitignored).

## Extending

- **New collector** (a tool other than Claude Code): implement a collector
  that emits `InferenceEvent`s (filling in `provider`/`client`), on the
  model of `ClaudeCodeCollector`. The rest of the pipeline is neutral with
  respect to the source. Full checklist to follow for each integration:
  [`checklist-nouvel-outil.md`](checklist-nouvel-outil.md).
- **New skill**: add `skills/<name>/SKILL.md` (frontmatter
  `name`/`description`). The installer deploys it via a symlink into
  `~/.claude/skills/`.
- **Model resolution**: the cascade lives in `impact/params.py`; the
  deterministic `resolve` CLI (HF + recompute) in `resolve/cli.py`; the
  name→repo mapping (judgment call) in the `/footprint-resolve` skill. HF
  failures are memoized (in-memory negative cache + persisted in
  `config.json`, 7-day TTL); `resolve --retry-hf` purges this cache and
  retries the cascade on the uncovered models. Params estimated from file
  size carry provenance warnings (`params-bytes-per-param:<n>`,
  `params-range-unknown-dtype`) and are flagged in the report.

## Technical backlog

See
[`.superpowers/specs/2026-07-02-qualite-lecture-resolution-design.md`](../.superpowers/specs/2026-07-02-qualite-lecture-resolution-design.md):
data-reading and model-resolution quality fixes (HF negative cache, 4-bit
estimation…), and the "WebSearch step" evolution in the resolution
cascade. `resolve --set "P/M=repo:<active>"` handles MoE models.

## Release

A release bumps the semantic version, generates the CHANGELOG, and creates
the tag.

**Always with the local venv binary** (`.venv/bin/ai-footprint`), never the
global `ai-footprint` command: the latter runs the code of the installed
clone (`~/.ai-footprint/src`) and would commit/tag there instead of the dev
repo you're working in.

```bash
.venv/bin/ai-footprint release bump <patch|minor|major> [--no-push]
```

- `patch`: backward-compatible fixes
- `minor`: backward-compatible new features
- `major`: incompatible changes

The process:

1. Checks that the tree is clean, that we're on `main`, and that the target
   tag doesn't already exist.
2. Computes the new version (e.g. `0.1.0` → `0.2.0`).
3. Generates the CHANGELOG between the last `v*` tag and HEAD from the
   conventional commits (`feat:`, `fix:`, etc.).
4. Bumps `pyproject.toml` + `ai_footprint/__init__.py`.
5. Prepends the new block into `CHANGELOG.md`.
6. Commits `chore(release): X.Y.Z` + tags `vX.Y.Z`.
7. **Pushes `origin main --tags` by default** (`--no-push` option to skip
   it).

Evidence: the `tests/test_release.py` tests (31 tests) cover the full
cycle.

> **Note**: before the first `v*` tag, the CHANGELOG is maintained manually
> (the "Pre-versioning" section). After the first release, it is entirely
> auto-generated.

## Dependency watch (ecologits, huggingface_hub)

A GitHub Actions workflow (`.github/workflows/check-tool-updates.yml`,
weekly cron + manual trigger) compares the versions pinned in
`pyproject.toml` (ecologits pinned exactly, huggingface_hub) against the
latest versions published on PyPI (via `ai_footprint/tool_updates.py`) and
opens an issue if a new version exists.

**No automatic bump**: ecologits is pinned to an exact PyPI version because
a minor `0.x` bump can break the calculation cascade, and the installed
tool shares its database with the dev repo (see § Two codebases, one
base) — a silent bump would be risky. The issue is just a reminder; the
bump is done by hand in `pyproject.toml` after testing.

In addition to the weekly cron, a **`SessionStart` hook local to the dev
repo** (`.claude/settings.json`, _not_ the global `~/.claude/settings.json`
installed by `install.sh`) runs `ai-footprint tool-updates-check` on every
Claude Code session start in this project, and displays a message if an
ecologits/huggingface_hub update is available. The network check is cached
for 24h (`.claude/tool-updates-cache.json`, gitignored) so it doesn't slow
down every session start. This logic is tested in
`tests/test_tool_updates.py` (`session_start_notice`, `should_refresh`,
`load_cache`).

> **Not to be confused with the global `SessionStart` hook** added by
> `install.sh` for end-user nudges (`ai-footprint nudge --claude-hook`, see
> `ai_footprint/nudge.py`): that one is **internal to the dev repo**
> (`.claude/settings.json`, not installed for end users) and is used to
> alert ai-footprint maintainers about new ecologits/huggingface_hub
> releases — an entirely different topic from the nudges aimed at
> ai-footprint's end users.

## Out of current scope (seams laid down)

Third-party collectors (Codex, local inference) as stubs; `compute_live()`
(real-time instrumentation) and `import_legacy()` not implemented; CSV/JSON
export and workstation energy are out of scope.
