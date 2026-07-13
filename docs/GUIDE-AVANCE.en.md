# Advanced Guide

This guide is intended for users comfortable with the command line who want
to install `ai-footprint` manually or understand its internal workings. For
everyday use (skills, one-line installation), see the
[user guide](GUIDE.md). For developing the project itself (code
architecture, database schema, tests), see [CONTRIBUTING.md](CONTRIBUTING.md).

## Manual installation

The one-line installer (see the [user guide](GUIDE.md#install)) remains
the recommended method: it detects your installed tools and wires
everything up automatically. The methods below only install the **CLI**,
without automatic wiring into Claude Code, Opencode, or Pi.

### Via Homebrew (macOS/Linux)

```bash
brew install hrenaud/tap/ai-footprint
```

Formula maintained on a personal tap (`hrenaud/homebrew-tap`) — equivalent
to `brew tap hrenaud/tap && brew install ai-footprint`. Update:
`brew upgrade ai-footprint`.

### Via PyPI

```bash
pip install ai-footprint
```

The `agent-footprint` package (the project's former name) also redirects to
`ai-footprint`. Update: `pip install --upgrade ai-footprint`.

### From source (dev)

```bash
git clone https://github.com/hrenaud/ai-footprint
cd ai-footprint
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Wiring manually after a brew/pip install

Without automatic wiring, it's up to you to trigger ingestion and display
the status line:

```bash
ai-footprint ingest       # run periodically (or via your own hook)
ai-footprint statusline   # wire into your tool's config
```

The skills (`/footprint-report`, etc.) additionally require the skill files
from the repository — not installed by brew/pip.

## Environment variables

Used by `install.sh` and `uninstall.sh`:

| Variable                 | Effect                                                      | Default                           |
| ------------------------ | ----------------------------------------------------------- | --------------------------------- |
| `AI_FOOTPRINT_DIR`       | Installation directory (clone + venv).                      | `~/.ai-footprint/src`             |
| `AI_FOOTPRINT_DB`        | Path to the SQLite database (impact history).               | `~/.ai-footprint/ai-footprint.db` |
| `AI_FOOTPRINT_REF`       | Git branch or tag to install (useful for testing a branch). | `main`                            |
| `AI_FOOTPRINT_NO_CLAUDE` | `=1` → does not modify `~/.claude/settings.json`.           | not set                           |
| `AI_FOOTPRINT_NO_INGEST` | `=1` → does not run the initial ingestion.                  | not set                           |
| `AI_FOOTPRINT_PURGE_DB`  | `=1` (uninstall) → also deletes the SQLite database.        | not set                           |

Example: install a test branch in an isolated directory, without touching
the production install or `settings.json`:

```bash
AI_FOOTPRINT_REF=my-branch AI_FOOTPRINT_DIR=/tmp/ai-footprint-test \
AI_FOOTPRINT_NO_CLAUDE=1 \
  curl -fsSL https://raw.githubusercontent.com/hrenaud/ai-footprint/main/install.sh | bash
```

## Complete uninstallation

The [uninstaller](GUIDE.md#uninstallation) keeps the SQLite database by
default. To delete it as well:

```bash
AI_FOOTPRINT_PURGE_DB=1 \
  curl -fsSL https://raw.githubusercontent.com/hrenaud/ai-footprint/main/uninstall.sh | bash
```

## Under the hood

### The CLI

Skills are just a layer on top of the CLI: you can use it directly.

```bash
ai-footprint ingest           # parse transcripts → SQLite database (~/.ai-footprint/ai-footprint.db)
ai-footprint report           # multi-criteria report (--since, --detail, --all-projects)
ai-footprint card             # shareable PNG card (--since, --theme, --lang, --out)
ai-footprint statusline       # compact line for the current session
ai-footprint resolve --list   # lists the uncovered models to resolve
ai-footprint resolve --set "provider/model=org/repo-hf"   # applies a mapping and recalculates
ai-footprint resolve --forget "provider/model"            # removes a mapping and recalculates
ai-footprint nudge --json     # nudge status (unproposed models, update available)
```

`ingest` summarizes the coverage obtained, for example:

```
80 events ingested · 33639/33709 measured · 70 not covered (retained, impact not estimated)
```

The "uncovered" ones are models outside the EcoLogits scope: the event is
retained but excluded from the totals (showing a false number would be
worse than a coverage gap). Many are internal `<synthetic>` placeholders (0
tokens, no real impact); the real third-party or recent models are resolved
with `ai-footprint resolve` (or `/footprint-resolve`). Full details:
[METHODOLOGY.md](METHODOLOGY.md).

### Multi-tool ingestion

`ai-footprint ingest` reads the session transcripts of each detected tool
(Claude Code, Opencode, Pi) and converts them into events in the SQLite
database. Ingestion is **idempotent**: replaying the same transcript
duplicates nothing. Each tool triggers ingestion its own way:

- **Claude Code**: a `Stop` hook ingests the transcript at the end of the
  session, and a `SessionStart` hook offers an update or the resolution of
  uncovered models at the start of the session, if relevant.
- **Opencode**: a plugin triggers ingestion on the same session lifecycle
  events.
- **Pi**: an extension does the same on its own session events.

### Statusline

The statusline displays the impact of the **current session**. The tool
passes the session ID to ai-footprint, which ingests the current transcript
and filters the totals on it. Run manually outside a session, it falls back
to the **global total** of the history:

```bash
~/.ai-footprint/src/scripts/statusline.sh
```

The installer never replaces a statusline already used by another tool — it
then displays the command to switch manually.

### Uncovered models and resolution

See [METHODOLOGY.md](METHODOLOGY.md) for details on what is measured and
why some models remain out of scope. `ai-footprint resolve` associates an
uncovered model with an equivalent Hugging Face repository, checks its
actual parameters, and recalculates the impacts.
