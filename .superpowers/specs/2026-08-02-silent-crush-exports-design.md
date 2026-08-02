# Silent OpenCode export logs

## Goal

Prevent successful `footprint-crush` exports from printing messages in the
OpenCode terminal UI.

## Cause

The server plugin writes success messages with `console.log` when a session
becomes idle and when its JSON export completes. OpenCode renders that output
in its terminal UI.

## Design

- Remove success-path `console.log` calls from `footprint-crush.js`.
- Keep existing `console.error` calls so export, ingest, and nudge failures
  remain diagnosable.
- Add a regression test that runs the idle-event export path and asserts that
  it produces no console output on success.
- Document that successful OpenCode exports are silent while failures remain
  logged.

## Scope

The export JSON format, ingestion command, TUI card, and failure behavior are
unchanged.

## Verification

Run the focused Node test and the repository test suite.
