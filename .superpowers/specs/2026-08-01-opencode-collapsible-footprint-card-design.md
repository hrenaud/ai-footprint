# OpenCode Collapsible Footprint Card

## Goal

Replace the space-consuming bordered AI Footprint sidebar card with an
expandable section that exposes the installed ai-footprint version and makes
session diagnostics readable.

## Interaction

- The section starts expanded for every OpenCode session.
- Its header is `▼ AI Footprint v<version>` when expanded and
  `▶ AI Footprint v<version>` when collapsed.
- Clicking the header toggles the section.
- When the header has focus, Enter and Space toggle it as well.
- The collapse state is local to the current TUI instance and is not persisted.

## Content

When expanded, render one compact line for each statusline segment, without a
border or padding:

1. Carbon impact.
2. Water consumption.
3. Energy consumption.
4. Optional fallback-model warning as the final line, for example
   `≈ sonnet-5 inconnu, params sonnet-4`.

The warning is emitted as the final ` · `-separated statusline segment. This
keeps the Claude Code statusline informative and lets the OpenCode card render
it as its final line without TUI-specific parsing.

## Version

The TUI queries the local ai-footprint binary for its version once when the
component mounts. It renders the version in grey after `AI Footprint` and does
not run this command during the five-second metric refresh cycle.

## Model Attribution

Impact is calculated per assistant response, not from a session-wide model.

- Claude Code transcripts already contain the selected model on every assistant
  message; a model change in one session must therefore produce events with
  distinct models.
- OpenCode stores the selected provider and model on the preceding user
  message while the following assistant message contains the token usage. The
  exporter and SQLite backfill must carry that latest selected model forward to
  the next assistant message. They must not use the session-level model as a
  fallback for earlier responses, because it can be the model selected later
  in the session.

## Verification

- Unit tests cover statusline segmentation for the optional model warning.
- The TUI source test covers the one-time version lookup helper.
- Collector tests cover a session that changes model before a later assistant
  response for both Claude Code and OpenCode.
- The TUI bundle builds successfully.
- Manual OpenCode test confirms that the header is expanded initially and that
  tokens and the optional warning are displayed as separate lines.
