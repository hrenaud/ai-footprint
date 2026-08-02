# Silent OpenCode Export Logs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop successful ai-footprint OpenCode exports from printing log lines in the OpenCode terminal UI.

**Architecture:** Keep the existing session-idle flow unchanged: serialize the session, write its JSON export, then ingest it. Remove only success-path console output, while preserving `console.error` for operational failures. An integration-style Node test invokes the event hook with a temporary export directory and no-op executable to assert a successful export is silent.

**Tech Stack:** Node.js built-in test runner, CommonJS, OpenCode server plugin, Markdown documentation.

## Global Constraints

- Do not change the export JSON schema, ingestion command, TUI card, or nudge behavior.
- Successful exports must emit no `console.log` or `console.error` output.
- Existing errors remain visible through `console.error`.
- Do not add dependencies or persistent debug logs.

---

### Task 1: Silence Successful Exports

**Files:**
- Modify: `skills/footprint-crush/test/footprint-crush.test.js`
- Modify: `skills/footprint-crush/footprint-crush.js:51-100,191-203`
- Modify: `docs/GUIDE-AVANCE.md:170-203`

**Interfaces:**
- Consumes: `module.exports.server({ client })`, which returns `{ event({ event }) }`.
- Produces: the existing `session.idle` handler, without console output when export and ingestion succeed.

- [ ] **Step 1: Write the failing regression test**

Add this test to `skills/footprint-crush/test/footprint-crush.test.js`:

```js
test("session.idle: export successful remains silent", async () => {
  const os = require("node:os");
  const fs = require("node:fs");
  const path = require("node:path");
  const pluginPath = require.resolve("../footprint-crush.js");
  const home = fs.mkdtempSync(path.join(os.tmpdir(), "footprint-crush-"));
  const bin = path.join(home, "ai-footprint");
  const previousHome = process.env.HOME;
  const previousBin = process.env.AI_FOOTPRINT_BIN;
  const originalLog = console.log;
  const originalError = console.error;
  const output = [];

  fs.writeFileSync(bin, "#!/bin/sh\nexit 0\n");
  fs.chmodSync(bin, 0o755);
  process.env.HOME = home;
  process.env.AI_FOOTPRINT_BIN = bin;
  delete require.cache[pluginPath];
  const plugin = require("../footprint-crush.js");
  console.log = (...args) => output.push(args);
  console.error = (...args) => output.push(args);

  try {
    const hooks = await plugin.server({
      client: {
        session: {
          messages: async () => ({ data: [] }),
          get: async () => ({ data: { id: "ses_123" } }),
        },
      },
    });
    await hooks.event({
      event: { type: "session.idle", properties: { sessionID: "ses_123" } },
    });
    assert.deepEqual(output, []);
  } finally {
    console.log = originalLog;
    console.error = originalError;
    process.env.HOME = previousHome;
    process.env.AI_FOOTPRINT_BIN = previousBin;
    delete require.cache[pluginPath];
    fs.rmSync(home, { recursive: true, force: true });
  }
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `node --test skills/footprint-crush/test/footprint-crush.test.js`

Expected: FAIL because the event handler emits success messages through `console.log`.

- [ ] **Step 3: Remove only success-path logging**

Delete these calls from `skills/footprint-crush/footprint-crush.js`:

```js
console.log(`[footprint-crush] Exported session ${sessionId} → ${outPath}`);
```

```js
console.log(
  `[footprint-crush] Session idle: ${event.properties.sessionID} — export en cours...`,
);
```

Keep every `console.error` call unchanged.

- [ ] **Step 4: Document the intended TUI behavior**

Append this sentence to the OpenCode statusline section of `docs/GUIDE-AVANCE.md`:

```markdown
Les exports de session et leur ingestion sont silencieux en cas de succès pour
ne pas perturber le TUI ; seules les erreurs du plugin sont journalisées.
```

- [ ] **Step 5: Run the focused test to verify it passes**

Run: `node --test skills/footprint-crush/test/footprint-crush.test.js`

Expected: all tests pass.

- [ ] **Step 6: Run full verification**

Run: `node --test skills/footprint-crush/test/footprint-crush.test.js && npm test --prefix skills/footprint-crush/tui && .venv/bin/python -m pytest`

Expected: all Node and Python tests pass.

- [ ] **Step 7: Commit the fix**

```bash
git add skills/footprint-crush/footprint-crush.js skills/footprint-crush/test/footprint-crush.test.js docs/GUIDE-AVANCE.md .superpowers/specs/2026-08-02-silent-crush-exports-design.md .superpowers/plans/2026-08-02-silent-crush-exports.md
git commit -m "fix(opencode): silence successful export logs"
```
