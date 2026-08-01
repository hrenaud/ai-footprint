const test = require("node:test");
const assert = require("node:assert/strict");
const {
  ingestExport,
  toExportMessage,
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

test("toExportMessage: utilise le modele de session si le message ne le renseigne pas", () => {
  const result = toExportMessage({
    info: {
      role: "assistant",
      model: { id: "", providerID: "" },
      tokens: { input: 28049, output: 19, cache: { read: 0, write: 0 } },
    },
    parts: [],
  }, "ses_123", { id: "claude-sonnet-4", providerID: "anthropic" });

  assert.deepEqual(result.info.model, {
    id: "claude-sonnet-4",
    providerID: "anthropic",
  });
});
