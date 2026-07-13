# Checklist: Integrate a new tool (AI client)

To be followed with each addition of an event source (Claude Code, Opencode/Crush, a future Codex-type client, etc.). Complete technical reference: see [CONTRIBUTING.md](CONTRIBUTING.md) (architecture, DB schema, conventions).

## 1. Collector (`ai_footprint/collectors/`)

- [ ] Implement a class inheriting from the ABC `Collector` (`base.py`): attributes `provider` / `client`, method `collect() -> Iterator[InferenceEvent]`.
      Choose the closest reference model according to the data source:
  - transcript file (JSONL…) → refer to `claude_code.py`.
  - export JSON + backfill SQLite → inspired by `crush.py` (deterministic synthetic IDs via SHA1 to avoid primary key collisions).
- [ ] Derive the `project` from the `cwd` if available; estimate `active_seconds`; ignore events without usage tokens.
- [ ] Never extract content from prompt/response — only the metadata necessary for impact calculation.

## 2. Tests (TDD — before implementation)

- [ ] Unit tests of the collector (fixtures representative of the source format, edge cases: unused event, missing cwd, duplicates/idempotence).
- [ ] End-to-end ingestion test (`SQLiteStore.ingest`) if the input format significantly differs from the existing collectors.
- [ ] `.venv/bin/python -m pytest -q` green before continuing.

## 3. CLI Wiring (`ai_footprint/__main__.py`)

- [ ] Register the new collector (option `--source-<tool>` if relevant, see `--source-crush`).

## 4. `install.sh`

- [ ] Detect the tool (`command -v <tool>`).
- [ ] Initial backfill if a local database/export already exists.
- [ ] Tool-specific wiring (hook, plugin, config) if the tool exposes an extension mechanism — see Opencode/Crush section (plugin `.js` + registration in `opencode.json`) for an example.
- [ ] Never overwrite a config/statusline already taken by another tool (see existing logic for `statusLine` in the Claude Code wiring).

## 5. Skill (`skills/`)

- [ ] If the tool has a clean conversational UX, add `skills/ai-footprint-<tool>/SKILL.md` (frontmatter `name`/`description`).
      The installer automatically deploys it via symlink.

## 6. Documentation

- [ ] `README.md`: mention the new tool if it changes user usage (installation, automatic detection).
- [ ] `CONTRIBUTING.md`: update the architecture diagram / the module table if the new collector introduces a different pattern.
- [ ] `docs/comparaison-donnees-outils.md`: add the tool to the comparison of available formats/data.
- [ ] `docs/METHODOLOGY.md`: only if the tool introduces a nuance in impact calculation (e.g., self-hosted models, different tokenization).

## 7. Final Verification

- [ ] Complete test suite is green.
- [ ] Manual end-to-end test of an `install.sh` (ideally via `AI_FOOTPRINT_REF=<branch>` on a test directory, see CONTRIBUTING § Test `install.sh` on a branch) confirming that detection, backfill, and wiring work without touching the configs of another tool.
- [ ] Release (`ai-footprint release bump <patch|minor>`) once merged into `main`, then rerun the install script (see § Two codebases, one base in AGENTS.md).
