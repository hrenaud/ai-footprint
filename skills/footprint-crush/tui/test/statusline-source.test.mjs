import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  resolveBinPath,
  resolveDbPath,
  formatStatuslineLine,
  formatVersion,
  fetchVersion,
  fetchStatusline,
  resolveSessionId,
  SIDEBAR_EXPANDED_KEY,
  isSidebarExpanded,
  sidebarToggleMessage,
} from "../src/statusline-source.mjs";

test("sidebar_content: utilise les props du slot pour l'id de session", () => {
  const source = readFileSync(new URL("../src/tui.tsx", import.meta.url), "utf8");

  assert.match(
    source,
    /sidebar_content\(ctx, props\)[\s\S]*?sessionId=\{props\.session_id\}[\s\S]*?theme=\{ctx\.theme\.current\}/,
  );
});

test("formatStatuslineLine: masque le diagnostic de tokens", () => {
  assert.equal(formatStatuslineLine("🔢 8 300 tok"), "");
});

test("formatStatuslineLine: conserve la note de modele", () => {
  assert.equal(
    formatStatuslineLine("≈ sonnet-5 inconnu, params sonnet-4"),
    "≈ sonnet-5 inconnu, params sonnet-4",
  );
});

test("formatVersion: ajoute le prefixe v a la version semantique", () => {
  assert.equal(formatVersion("1.8.0"), "v1.8.0");
});

test("sidebar state: utilise la cle de preference persistante", () => {
  assert.equal(SIDEBAR_EXPANDED_KEY, "footprint.sidebar.expanded");
});

test("sidebar state: reste deplié sauf si la preference vaut false", () => {
  assert.equal(isSidebarExpanded(undefined), true);
  assert.equal(isSidebarExpanded(false), false);
});

test("sidebar state: fournit le message de confirmation adapte", () => {
  assert.equal(sidebarToggleMessage(true), "AI Footprint expanded");
  assert.equal(sidebarToggleMessage(false), "AI Footprint collapsed");
});

test("resolveBinPath: utilise AI_FOOTPRINT_BIN si défini", () => {
  const env = { AI_FOOTPRINT_BIN: "/custom/ai-footprint", HOME: "/home/x" };
  assert.equal(resolveBinPath(env), "/custom/ai-footprint");
});

test("resolveBinPath: sinon retombe sur ~/.ai-footprint/src/.venv/bin/ai-footprint", () => {
  const env = { HOME: "/home/x" };
  assert.equal(
    resolveBinPath(env),
    "/home/x/.ai-footprint/src/.venv/bin/ai-footprint",
  );
});

test("resolveDbPath: utilise AI_FOOTPRINT_DB si défini", () => {
  const env = { AI_FOOTPRINT_DB: "/custom/db.sqlite", HOME: "/home/x" };
  assert.equal(resolveDbPath(env), "/custom/db.sqlite");
});

test("resolveDbPath: sinon retombe sur ~/.ai-footprint/ai-footprint.db", () => {
  const env = { HOME: "/home/x" };
  assert.equal(resolveDbPath(env), "/home/x/.ai-footprint/ai-footprint.db");
});

test("fetchVersion: retourne la version du binaire", async () => {
  const version = await fetchVersion(
    async (bin, args) => {
      assert.equal(bin, "/bin/ai-footprint");
      assert.deepEqual(args, ["--version"]);
      return { stdout: "1.8.0\n" };
    },
    "/bin/ai-footprint",
  );
  assert.equal(version, "1.8.0");
});

test("fetchVersion: retourne une chaîne vide si le binaire échoue", async () => {
  const version = await fetchVersion(async () => {
    throw new Error("boom");
  }, "/bin/ai-footprint");
  assert.equal(version, "");
});

test("fetchStatusline: retourne le stdout du binaire (trimmé)", async () => {
  const fakeExecFile = async (bin, args, stdin) => {
    assert.equal(bin, "/bin/ai-footprint");
    assert.deepEqual(args, ["statusline", "--db", "/db/path"]);
    assert.equal(stdin, undefined);
    return { stdout: "🌍 0.12 gCO2eq\n" };
  };
  const line = await fetchStatusline(
    fakeExecFile,
    "/bin/ai-footprint",
    "/db/path",
  );
  assert.equal(line, "🌍 0.12 gCO2eq");
});

test("fetchStatusline: transmet l'id de session en JSON sur stdin (comme le hook Claude Code)", async () => {
  const fakeExecFile = async (bin, args, stdin) => {
    assert.deepEqual(args, ["statusline", "--db", "/db/path"]);
    assert.deepEqual(JSON.parse(stdin), { session_id: "ses_123" });
    return { stdout: "🌍 0.12 gCO2eq\n" };
  };
  const line = await fetchStatusline(
    fakeExecFile,
    "/bin/ai-footprint",
    "/db/path",
    "ses_123",
  );
  assert.equal(line, "🌍 0.12 gCO2eq");
});

test("resolveSessionId: utilise l'id fourni par le slot si présent", () => {
  const api = {
    route: { current: { name: "session", params: { sessionID: "route_id" } } },
  };
  assert.equal(resolveSessionId("ctx_id", api), "ctx_id");
});

test("resolveSessionId: retombe sur api.route.current.params.sessionID si l'id du slot est absent (cas observé en pratique : le slot sidebar_content ne reçoit pas toujours session_id)", () => {
  const api = {
    route: { current: { name: "session", params: { sessionID: "route_id" } } },
  };
  assert.equal(resolveSessionId(undefined, api), "route_id");
});

test("resolveSessionId: retourne undefined si aucune source n'a d'id (route hors session, ex. écran d'accueil)", () => {
  const api = { route: { current: { name: "home" } } };
  assert.equal(resolveSessionId(undefined, api), undefined);
});

test("fetchStatusline: retourne une chaîne vide si le binaire échoue", async () => {
  const fakeExecFile = async () => {
    throw new Error("boom");
  };
  const line = await fetchStatusline(
    fakeExecFile,
    "/bin/ai-footprint",
    "/db/path",
  );
  assert.equal(line, "");
});
