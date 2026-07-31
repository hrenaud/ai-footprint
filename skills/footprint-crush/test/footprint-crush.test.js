const test = require("node:test");
const assert = require("node:assert/strict");
const { ingestExport } = require("../lib/footprint-crush-lib.js");

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
