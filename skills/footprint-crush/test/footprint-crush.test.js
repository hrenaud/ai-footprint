const test = require("node:test");
const assert = require("node:assert/strict");
const {
  ingestExport,
  toExportMessage,
  toExportMessages,
} = require("../lib/footprint-crush-lib.js");

test("ingestExport: appelle `ai-footprint ingest --source-crush <dir>`", async () => {
  let called;
  const fakeExecFile = async (bin, args) => {
    called = { bin, args };
    return { stdout: "", stderr: "" };
  };
  await ingestExport(
    fakeExecFile,
    "/bin/ai-footprint",
    "/exports/dir",
    "ses_123",
  );
  assert.equal(called.bin, "/bin/ai-footprint");
  assert.deepEqual(called.args, ["ingest", "--source-crush", "/exports/dir"]);
});

test("ingestExport: n'échoue pas (avale l'erreur) si l'ingestion plante", async () => {
  const fakeExecFile = async () => {
    throw new Error("boom");
  };
  await assert.doesNotReject(
    ingestExport(fakeExecFile, "/bin/ai-footprint", "/exports/dir", "ses_123"),
  );
});

test("session.idle: export successful remains silent", async () => {
  const os = require("node:os");
  const fs = require("node:fs");
  const path = require("node:path");
  const pluginPath = require.resolve("../footprint-crush.js");
  const home = fs.mkdtempSync(path.join(os.tmpdir(), "footprint-crush-"));
  const bin = path.join(home, "ai-footprint");
  const previousHome = process.env.HOME;
  const previousBin = process.env.AI_FOOTPRINT_BIN;
  const hadHome = Object.hasOwn(process.env, "HOME");
  const hadBin = Object.hasOwn(process.env, "AI_FOOTPRINT_BIN");
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
    if (hadHome) process.env.HOME = previousHome;
    else delete process.env.HOME;
    if (hadBin) process.env.AI_FOOTPRINT_BIN = previousBin;
    else delete process.env.AI_FOOTPRINT_BIN;
    delete require.cache[pluginPath];
    fs.rmSync(home, { recursive: true, force: true });
  }
});

test("toExportMessage: lit les metadonnees depuis info", () => {
  const result = toExportMessage({
    info: {
      role: "assistant",
      time: { created: 1, completed: 2 },
      agent: "build",
      model: { id: "Qwen3.6-35B-A3B-4bit", providerID: "omlx" },
      tokens: {
        input: 28049,
        output: 19,
        reasoning: 0,
        cache: { read: 12288, write: 0 },
      },
      cost: 0,
      id: "msg_123",
      sessionID: "ses_123",
    },
    parts: [{ type: "text", text: "OK" }],
  }, "ses_123");

  assert.deepEqual(result, {
    info: {
      role: "assistant",
      time: { created: 1, completed: 2 },
      agent: "build",
      model: { id: "Qwen3.6-35B-A3B-4bit", providerID: "omlx" },
      tokens: {
        input: 28049,
        output: 19,
        reasoning: 0,
        cache: { read: 12288, write: 0 },
      },
      cost: 0,
      id: "msg_123",
      sessionID: "ses_123",
    },
    parts: [{ type: "text", text: "OK" }],
  });
});

test("toExportMessage: ne reutilise pas le modele final de session", () => {
  const result = toExportMessage({
    info: {
      role: "assistant",
      model: { id: "", providerID: "" },
      tokens: { input: 28049, output: 19, cache: { read: 0, write: 0 } },
    },
    parts: [],
  }, "ses_123");

  assert.deepEqual(result.info.model, {
    id: "",
    providerID: "",
  });
});

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

test("toExportMessages: remonte toute la chaine parentID pour trouver le modele", () => {
  const messages = [
    { info: { id: "user_1", role: "user", model: { modelID: "model-a", providerID: "provider-a" } } },
    { info: { id: "assistant_1", parentID: "user_1", role: "assistant" } },
    { info: { id: "assistant_2", parentID: "assistant_1", role: "assistant", tokens: { input: 10, output: 1 } } },
  ];

  const result = toExportMessages(messages, "ses_123");

  assert.deepEqual(result[2].info.model, { id: "model-a", providerID: "provider-a" });
});
