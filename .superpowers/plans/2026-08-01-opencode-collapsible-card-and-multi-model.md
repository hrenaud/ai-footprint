# OpenCode Collapsible Card And Multi-Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve per-response model attribution across model changes and render a compact, expandable OpenCode impact section.

**Architecture:** OpenCode model attribution is normalized from each assistant message's `providerID` and `modelID`, falling back only through its parent message chain, never the session-wide model. The shared statusline emits independently splittable segments. The TUI reads the CLI version once, renders a compact expandable header, and maps the token segment to its temporary diagnostic label.

**Tech Stack:** Python 3.11, argparse, SQLite, Node.js test runner, TypeScript/Solid.js, OpenTUI, esbuild.

## Global Constraints

- Keep the existing five-second metric refresh; the version command runs only once per TUI mount.
- The OpenCode section starts expanded, has no border or padding, and does not persist its collapse state.
- Preserve provider and model per assistant response across model or provider changes in one session.
- Never infer a historical response model from the final session model.
- The model-fallback note is the final statusline segment and final expanded-card line.
- The token line is temporary and labelled `🔢 Tokens :`.

---

### Task 1: Preserve Per-Response Models

**Files:**
- Modify: `skills/footprint-crush/lib/footprint-crush-lib.js`
- Modify: `skills/footprint-crush/footprint-crush.js`
- Modify: `ai_footprint/collectors/crush.py`
- Modify: `skills/footprint-crush/test/footprint-crush.test.js`
- Modify: `tests/test_crush_collector.py`
- Modify: `tests/test_claude_code_collector.py`

**Interfaces:**
- Produces: `toExportMessages(messages, sessionId)` returning export-format messages with a model for every resolvable assistant response.
- Consumes: OpenCode `message.info.model`, `message.info.modelID`, `message.info.providerID`, and `message.info.parentID`.
- Produces: `CrushCollector` events using message-level `model` or top-level `modelID`/`providerID`; session-level model is not used for an earlier response.

- [ ] **Step 1: Write failing Node tests for a changed OpenCode model**

```js
test("toExportMessages: conserve le modele de chaque reponse", () => {
  const messages = [
    { info: { id: "user_1", role: "user", model: { modelID: "model-a", providerID: "provider-a" } } },
    { info: { id: "assistant_1", parentID: "user_1", role: "assistant", tokens: { input: 10, output: 1 } } },
    { info: { id: "user_2", role: "user", model: { modelID: "model-b", providerID: "provider-b" } } },
    { info: { id: "assistant_2", parentID: "user_2", role: "assistant", tokens: { input: 20, output: 2 } } },
  ];
  const result = toExportMessages(messages, "ses_123");
  assert.deepEqual(result[1].info.model, { id: "model-a", providerID: "provider-a" });
  assert.deepEqual(result[3].info.model, { id: "model-b", providerID: "provider-b" });
});
```

- [ ] **Step 2: Run the Node test and verify it fails**

Run: `node --test skills/footprint-crush/test/footprint-crush.test.js`

Expected: FAIL because `toExportMessages` is not exported.

- [ ] **Step 3: Write failing Python tests for direct OpenCode assistant metadata and Claude Code model changes**

Add a Crush SQLite fixture with two assistant records using top-level `providerID` / `modelID`, distinct providers and models, and assert both event pairs. Add a Claude JSONL fixture with two assistant records whose `message.model` values differ and assert both models.

- [ ] **Step 4: Implement model normalization without a session fallback**

```js
function toModel(info) {
  const model = info.model || {};
  return {
    id: model.id || model.modelID || info.modelID || "",
    providerID: model.providerID || info.providerID || "",
  };
}

function toExportMessages(messages, sessionId) {
  const models = new Map();
  return messages.map((message) => {
    const info = message.info || message;
    const model = toModel(info);
    if (model.id) models.set(info.id, model);
    return toExportMessage(message, sessionId, model.id ? model : models.get(info.parentID));
  });
}
```

Use `toExportMessages(messages, sessionId)` from `exportSession`. In the Python backfill, prefer `data["modelID"]` / `data["providerID"]` when `data["model"]` is absent; follow `parentID` through parsed messages only when direct metadata is absent. Do not use `session["model"]` as a fallback for an assistant response.

- [ ] **Step 5: Run focused tests and verify they pass**

Run: `node --test skills/footprint-crush/test/footprint-crush.test.js && .venv/bin/python -m pytest tests/test_crush_collector.py tests/test_claude_code_collector.py`

Expected: all Node and Python tests pass.

- [ ] **Step 6: Commit**

```bash
git add skills/footprint-crush ai_footprint/collectors/crush.py tests/test_crush_collector.py tests/test_claude_code_collector.py
git commit -m "fix(opencode): preserve model changes per response"
```

### Task 2: Expose Version And Split The Fallback Note

**Files:**
- Modify: `ai_footprint/__main__.py`
- Modify: `ai_footprint/statusline/line.py`
- Modify: `tests/test_statusline.py`
- Modify: `skills/footprint-crush/tui/src/statusline-source.mjs`
- Modify: `skills/footprint-crush/tui/test/statusline-source.test.mjs`

**Interfaces:**
- Produces: `ai-footprint --version` printing `__version__`.
- Produces: `fetchVersion(execFileImpl, bin)` returning a trimmed version or an empty string.
- Produces: `render_statusline()` with `≈ <unknown model>, params <fallback>` as the final ` · ` segment.

- [ ] **Step 1: Write failing tests for version and final warning position**

```python
def test_render_statusline_places_extrapolated_note_last():
    line = render_statusline(rows, tokens=42)
    assert line.endswith("≈ sonnet-5 inconnu, params sonnet-4")
```

```js
test("fetchVersion: retourne la version du binaire", async () => {
  const version = await fetchVersion(async () => ({ stdout: "1.8.0\n" }), "/bin/ai-footprint");
  assert.equal(version, "1.8.0");
});
```

- [ ] **Step 2: Run focused tests and verify they fail**

Run: `.venv/bin/python -m pytest tests/test_statusline.py && npm test --prefix skills/footprint-crush/tui`

Expected: warning ordering and `fetchVersion` expectations fail.

- [ ] **Step 3: Implement the minimal transport changes**

Add argparse's standard `--version` action using `ai_footprint.__version__`. Change statusline construction to append `· 🔢 … tok` and then `· ≈ …` when present. Add `fetchVersion()` that calls `execFileImpl(bin, ["--version"])`, returns trimmed stdout, and returns `""` on failure.

- [ ] **Step 4: Run focused tests and verify they pass**

Run: `.venv/bin/python -m pytest tests/test_statusline.py && npm test --prefix skills/footprint-crush/tui`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add ai_footprint/__main__.py ai_footprint/statusline/line.py tests/test_statusline.py skills/footprint-crush/tui/src/statusline-source.mjs skills/footprint-crush/tui/test/statusline-source.test.mjs
git commit -m "feat(statusline): expose version and fallback note"
```

### Task 3: Render The Compact Expandable TUI Card

**Files:**
- Modify: `skills/footprint-crush/tui/src/tui.tsx`
- Regenerate: `skills/footprint-crush/footprint-crush-tui.js`
- Modify: `docs/GUIDE-AVANCE.md`
- Modify: `docs/GUIDE-AVANCE.en.md`

**Interfaces:**
- Consumes: `fetchStatusline()` and `fetchVersion()` from `statusline-source.mjs`.
- Produces: an initially-expanded, borderless OpenTUI section with a togglable header.

- [ ] **Step 1: Add failing TUI source tests for line labels**

```js
test("formatStatuslineLine: labelle temporairement les tokens", () => {
  assert.equal(formatStatuslineLine("🔢 8 300 tok"), "🔢 Tokens : 8 300 tok");
});

test("formatStatuslineLine: conserve la note de modele", () => {
  assert.equal(formatStatuslineLine("≈ sonnet-5 inconnu, params sonnet-4"), "≈ sonnet-5 inconnu, params sonnet-4");
});
```

- [ ] **Step 2: Run the TUI test and verify it fails**

Run: `npm test --prefix skills/footprint-crush/tui`

Expected: FAIL because `formatStatuslineLine` is not exported.

- [ ] **Step 3: Implement the expandable section**

Use Solid signals `expanded` (initial `true`) and `version` (initial `""`). Call `fetchVersion()` once during component initialization. Replace the bordered `<box>` with a header `<box>` that uses `onMouseDown` and `onKeyDown` to toggle, renders `▼` / `▶`, and conditionally renders the formatted statusline lines below it. Do not set initial focus. Retain the existing five-second `refresh()` interval.

- [ ] **Step 4: Build and verify the generated plugin**

Run: `npm test --prefix skills/footprint-crush/tui && npm run build --prefix skills/footprint-crush/tui`

Expected: tests pass and `skills/footprint-crush/footprint-crush-tui.js` changes.

- [ ] **Step 5: Document the temporary diagnostic**

Add a short OpenCode section to both advanced guides: the expandable sidebar shows the installed version, temporary token count, and an optional extrapolated-model warning.

- [ ] **Step 6: Run full verification and commit**

Run: `node --test skills/footprint-crush/test/footprint-crush.test.js && npm test --prefix skills/footprint-crush/tui && .venv/bin/python -m pytest`

```bash
git add skills/footprint-crush/tui docs/GUIDE-AVANCE.md docs/GUIDE-AVANCE.en.md
git commit -m "feat(opencode): add collapsible footprint sidebar"
```

### Task 4: Remove The Token Diagnostic

**Files:**
- Modify: `skills/footprint-crush/tui/src/tui.tsx`
- Modify: `skills/footprint-crush/tui/src/statusline-source.mjs`
- Modify: `skills/footprint-crush/tui/test/statusline-source.test.mjs`
- Regenerate: `skills/footprint-crush/footprint-crush-tui.js`
- Modify: `docs/GUIDE-AVANCE.md`
- Modify: `docs/GUIDE-AVANCE.en.md`

**Interfaces:**
- Produces: `formatStatuslineLine(line)` returning an empty string for the
  temporary token segment and preserving impact and fallback-model segments.

- [ ] **Step 1: Write the failing source test**

```js
test("formatStatuslineLine: masque le diagnostic de tokens", () => {
  assert.equal(formatStatuslineLine("🔢 8 300 tok"), "");
});
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `npm test --prefix skills/footprint-crush/tui`

Expected: FAIL because the formatter still labels the token segment.

- [ ] **Step 3: Implement the compact header and filtered lines**

Render the header title and its version in separate text nodes. Give only the
version text `fg="gray"`. Make `formatStatuslineLine()` return an empty string
for the `🔢 ` segment and filter empty formatted lines before rendering the
expanded list. Keep click and keyboard collapse handling unchanged.

- [ ] **Step 4: Run tests and rebuild the bundle**

Run: `npm test --prefix skills/footprint-crush/tui && npm run build --prefix skills/footprint-crush/tui`

Expected: tests pass and `skills/footprint-crush/footprint-crush-tui.js` is regenerated.

- [ ] **Step 5: Update guides and commit**

Remove wording that identifies the token label as temporary from both advanced
guides, retain the version and extrapolated-model warning documentation, then:

```bash
git add skills/footprint-crush/tui docs/GUIDE-AVANCE.md docs/GUIDE-AVANCE.en.md
git commit -m "refactor(opencode): hide token diagnostic"
```
