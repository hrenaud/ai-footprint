// footprint-crush.js — Plugin Opencode pour ai-footprint.
//
// Écoute deux événements de session :
//   - session.created : propose une mise à jour ai-footprint et/ou un
//     resolve des modèles non couverts jamais proposés (cf.
//     .superpowers/specs/2026-07-12-nudges-resolve-maj.md).
//   - session.idle    : écrit un export JSON de la session dans
//     ~/.ai-footprint/crush-exports/<sessionId>.json pour ingestion.
//
// Installation : copié dans ~/.config/opencode/plugins/ par install.sh.
// Documentation : https://opencode.ai/docs/plugins/

const fs = require("fs");
const path = require("path");
const { execFile } = require("child_process");
const { promisify } = require("util");

const execFileAsync = promisify(execFile);

const EXPORT_DIR = path.join(
  process.env.HOME || "~",
  ".ai-footprint",
  "crush-exports",
);
const AC_BIN =
  process.env.AI_FOOTPRINT_BIN ||
  path.join(
    process.env.HOME || "~",
    ".ai-footprint",
    "src",
    ".venv",
    "bin",
    "ai-footprint",
  );

async function ensureExportDir() {
  await fs.promises.mkdir(EXPORT_DIR, { recursive: true });
}

/**
 * Écrit un export de session au format Opencode/Crush.
 *
 * @param {import("@opencode-ai/sdk").OpencodeClient} client — client SDK Opencode
 * @param {string} sessionId — identifiant de la session
 */
async function exportSession(client, sessionId) {
  await ensureExportDir();

  try {
    const { data: messages } = await client.session.messages({
      path: { id: sessionId },
    });
    const { data: session } = await client.session.get({
      path: { id: sessionId },
    });
    const obj = {
      info: {
        id: session.id || sessionId,
        slug: session.slug || "",
        projectID: session.project_id || "",
        directory: session.directory || "",
        path: session.path || "",
        title: session.title || "",
        agent: session.agent || "opencode",
        model: session.model || { id: "", providerID: "" },
        version: session.version || 1,
        tokens: session.tokens
          ? {
              input: session.tokens.input || 0,
              output: session.tokens.output || 0,
              reasoning: session.tokens.reasoning || 0,
              cache: {
                read: session.tokens.cache?.read || 0,
                write: session.tokens.cache?.write || 0,
              },
            }
          : { input: 0, output: 0, reasoning: 0, cache: { read: 0, write: 0 } },
        time: {
          created: session.time_created || 0,
          updated: session.time_updated || 0,
        },
      },
      messages: (messages || []).map((msg) => ({
        info: {
          role: msg.role || "user",
          time: msg.time || { created: 0 },
          agent: msg.agent || "opencode",
          model: msg.model || { id: "", providerID: "" },
          tokens: msg.tokens || {
            input: 0,
            output: 0,
            reasoning: 0,
            cache: { read: 0, write: 0 },
          },
          cost: msg.cost || 0,
          id: msg.id || "",
          sessionID: msg.session_id || sessionId,
        },
        parts: (msg.parts || []).map((p) => ({
          type: p.type || "text",
          text: p.text || "",
        })),
      })),
    };

    const outPath = path.join(EXPORT_DIR, `${sessionId}.json`);
    await fs.promises.writeFile(outPath, JSON.stringify(obj, null, 2), {
      encoding: "utf-8",
    });
    console.log(`[footprint-crush] Exported session ${sessionId} → ${outPath}`);
  } catch (err) {
    console.error(
      `[footprint-crush] Failed to export session ${sessionId}: ${err.message}`,
    );
  }
}

/**
 * Propose une mise à jour ai-footprint et/ou un resolve des modèles non
 * couverts jamais proposés, en injectant un message dans la session.
 *
 * @param {import("@opencode-ai/sdk").OpencodeClient} client
 * @param {string} sessionId
 */
async function maybeNudge(client, sessionId) {
  let stdout;
  try {
    ({ stdout } = await execFileAsync(AC_BIN, ["nudge", "--json"]));
  } catch (err) {
    console.error(`[footprint-crush] nudge check failed: ${err.message}`);
    return;
  }

  let result;
  try {
    result = JSON.parse(stdout);
  } catch (err) {
    console.error(`[footprint-crush] nudge output invalide: ${err.message}`);
    return;
  }

  const { update_available: updateAvailable, uncovered_new: uncoveredNew } =
    result;
  if (!updateAvailable && (!uncoveredNew || uncoveredNew.length === 0)) {
    return;
  }

  const lines = [];
  if (updateAvailable) {
    lines.push(
      `ai-footprint : mise à jour disponible (${updateAvailable.current} → ` +
        `${updateAvailable.latest}). Propose à l'utilisateur (outil question) de ` +
        "lancer l'installeur (curl -fsSL https://raw.githubusercontent.com/hrenaud/" +
        "ai-footprint/main/install.sh | bash) avant toute autre action liée à ai-footprint.",
    );
  }
  if (uncoveredNew && uncoveredNew.length > 0) {
    lines.push(
      `ai-footprint : ${uncoveredNew.length} modèle(s) non couvert(s) jamais ` +
        `proposés (${uncoveredNew.join(", ")}). Propose à l'utilisateur (outil ` +
        "question) de lancer le skill /footprint-resolve, puis exécute " +
        "`ai-footprint nudge --mark-prompted` que la réponse soit oui ou non.",
    );
  }

  try {
    await client.session.prompt({
      path: { id: sessionId },
      body: {
        noReply: false,
        parts: [{ type: "text", text: lines.join("\n") }],
      },
    });
  } catch (err) {
    console.error(
      `[footprint-crush] injection du nudge échouée: ${err.message}`,
    );
  }
}

/**
 * Plugin Opencode : exporte les sessions terminées et propose resolve/maj
 * au démarrage.
 *
 * @param {{ client: import("@opencode-ai/sdk").OpencodeClient }} input
 */
module.exports.FootprintCrush = async ({ client }) => {
  return {
    event: async ({ event }) => {
      if (event.type === "session.idle") {
        console.log(
          `[footprint-crush] Session idle: ${event.properties.sessionID} — export en cours...`,
        );
        await exportSession(client, event.properties.sessionID);
      }
      if (event.type === "session.created") {
        await maybeNudge(client, event.properties.sessionID);
      }
    },
  };
};
