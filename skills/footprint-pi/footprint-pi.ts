/**
 * footprint-pi.ts — Extension Pi pour ai-footprint.
 *
 * Écoute deux événements :
 *   - session_shutdown : lance une ingestion idempotente des transcripts
 *     JSONL de Pi (~/.pi/agent/sessions).
 *   - session_start : propose une mise à jour ai-footprint et/ou un resolve
 *     des modèles non couverts jamais proposés (cf.
 *     .superpowers/specs/2026-07-12-nudges-resolve-maj.md).
 *
 * Installation : placée dans ~/.pi/agent/extensions/ par install.sh.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import os from "node:os";
import path from "node:path";

const AC_BIN =
  process.env.AI_FOOTPRINT_BIN ||
  path.join(
    os.homedir(),
    ".ai-footprint",
    "src",
    ".venv",
    "bin",
    "ai-footprint",
  );
const DB_PATH =
  process.env.AI_FOOTPRINT_DB ||
  path.join(os.homedir(), ".ai-footprint", "carbon.db");
const SOURCE_PI = path.join(os.homedir(), ".pi", "agent", "sessions");

interface NudgeResult {
  update_available: { current: string; latest: string } | null;
  uncovered_new: string[];
}

export default function (pi: ExtensionAPI) {
  pi.on("session_shutdown", async (_event, ctx) => {
    const { code, stderr } = await pi.exec(AC_BIN, [
      "ingest",
      "--db",
      DB_PATH,
      "--source-pi",
      SOURCE_PI,
    ]);

    if (code !== 0 && ctx.hasUI) {
      ctx.ui.notify(
        `ai-footprint: ingestion échouée (${stderr.trim()})`,
        "warning",
      );
    }
  });

  pi.on("session_start", async (_event, ctx) => {
    if (!ctx.hasUI) {
      return;
    }

    const checkNudge = async (): Promise<NudgeResult | null> => {
      const { code, stdout } = await pi.exec(AC_BIN, [
        "nudge",
        "--db",
        DB_PATH,
        "--json",
      ]);
      if (code !== 0) {
        return null;
      }
      try {
        return JSON.parse(stdout) as NudgeResult;
      } catch {
        return null;
      }
    };

    let result = await checkNudge();
    if (!result) {
      return;
    }

    if (result.update_available) {
      const { current, latest } = result.update_available;
      const accept = await ctx.ui.confirm(
        `ai-footprint : mise à jour disponible (${current} → ${latest}). ` +
          "Lancer l'installeur maintenant ?",
      );
      if (!accept) {
        return;
      }
      const { code: installCode, stderr } = await pi.exec("bash", [
        "-c",
        "curl -fsSL https://raw.githubusercontent.com/hrenaud/ai-footprint/main/install.sh | bash",
      ]);
      if (installCode !== 0) {
        ctx.ui.notify(
          `ai-footprint: mise à jour échouée (${stderr.trim()})`,
          "warning",
        );
        return;
      }
      await pi.exec(AC_BIN, ["resolve", "--db", DB_PATH, "--retry-hf"]);
      await pi.exec(AC_BIN, ["nudge", "--db", DB_PATH, "--reset-prompted"]);
      result = await checkNudge();
      if (!result) {
        return;
      }
    }

    if (result.uncovered_new.length === 0) {
      return;
    }

    const accept = await ctx.ui.confirm(
      `ai-footprint : ${result.uncovered_new.length} modèle(s) non couvert(s) ` +
        `jamais proposés (${result.uncovered_new.join(", ")}). ` +
        "Lancer /footprint-resolve maintenant ?",
    );
    await pi.exec(AC_BIN, ["nudge", "--db", DB_PATH, "--mark-prompted"]);
    if (accept) {
      pi.sendUserMessage("/footprint-resolve");
    }
  });
}
