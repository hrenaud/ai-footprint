/**
 * agent-carbon-pi.ts — Extension Pi pour agent-carbon.
 *
 * Écoute la fin de session (session_shutdown) et lance une ingestion
 * idempotente des transcripts JSONL de Pi (~/.pi/agent/sessions).
 *
 * Installation : placée dans ~/.pi/agent/extensions/ par install.sh.
 * Documentation extensions Pi : https://pi.dev/
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import os from "node:os";
import path from "node:path";

const AC_BIN =
  process.env.AGENT_CARBON_BIN ||
  path.join(
    os.homedir(),
    ".agent-carbon",
    "src",
    ".venv",
    "bin",
    "agent-carbon",
  );
const DB_PATH =
  process.env.AGENT_CARBON_DB ||
  path.join(os.homedir(), ".agent-carbon", "carbon.db");
const SOURCE_PI = path.join(os.homedir(), ".pi", "agent", "sessions");

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
        `agent-carbon: ingestion échouée (${stderr.trim()})`,
        "warning",
      );
    }
  });
}
