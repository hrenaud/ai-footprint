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
4. Temporary token diagnostic, labelled `🔢 Tokens :`.
5. Optional fallback-model warning as the final line, for example
   `≈ sonnet-5 inconnu, params sonnet-4`.

The warning is emitted as the final ` · `-separated statusline segment. This
keeps the Claude Code statusline informative and lets the OpenCode card render
it as its final line without TUI-specific parsing.

## Version

The TUI queries the local ai-footprint binary for its version once when the
component mounts. It does not run this command during the five-second metric
refresh cycle.

## Verification

- Unit tests cover statusline segmentation for the optional model warning.
- The TUI source test covers the one-time version lookup helper.
- The TUI bundle builds successfully.
- Manual OpenCode test confirms that the header is expanded initially and that
  tokens and the optional warning are displayed as separate lines.
