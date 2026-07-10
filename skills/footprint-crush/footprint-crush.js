// footprint-crush.js — Plugin Opencode pour ai-footprint.
//
// Ce plugin écoute la fin de session (session.idle) et écrit les exports de
// session dans ~/.ai-footprint/crush-exports/<sessionId>.json pour ingestion
// automatique par ai-footprint.
//
// Installation : placé dans ~/.config/opencode/plugins/
// Documentation : https://opencode.ai/docs/plugins/

const fs = require("fs");
const path = require("path");

// Répertoire de sortie des exports (créé si nécessaire).
const EXPORT_DIR = path.join(
  process.env.HOME || "~",
  ".ai-footprint",
  "crush-exports"
);

async function ensureExportDir() {
  await fs.promises.mkdir(EXPORT_DIR, { recursive: true });
}

/**
 * Écrit un export de session au format Opencode/Crush.
 *
 * @param {import("@opencode-ai/sdk").Client} client — client SDK Opencode
 * @param {string} sessionId — identifiant de la session
 */
async function exportSession(client, sessionId) {
  await ensureExportDir();

  try {
    // Récupérer les messages de la session via le SDK.
    const messages = await client.session.messages(sessionId);

    // Construire la structure JSON exportée (format `opencode export`).
    const session = await client.session.get(sessionId);
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

    // Écrire dans crush-exports/<sessionId>.json.
    const outPath = path.join(EXPORT_DIR, `${sessionId}.json`);
    await fs.promises.writeFile(outPath, JSON.stringify(obj, null, 2), {
      encoding: "utf-8",
    });
    console.log(
      `[footprint-crush] Exported session ${sessionId} → ${outPath}`
    );
  } catch (err) {
    console.error(
      `[footprint-crush] Failed to export session ${sessionId}: ${err.message}`
    );
  }
}

/**
 * Plugin Opencode qui écoute session.idle et écrit les exports.
 */
module.exports = {
  name: "footprint-crush",
  description: "Exporte les sessions Opencode/Crush pour ai-footprint.",
  version: "1.0.0",

  /**
   * Configuration du plugin.
   * @param {import("@opencode-ai/plugin").PluginContext} context
   */
  register(context) {
    const client = context.client;

    // Écouter session.idle (fin de session) via le SDK.
    client.on("session.idle", async (sessionId) => {
      console.log(
        `[footprint-crush] Session idle: ${sessionId} — export en cours...`
      );
      await exportSession(client, sessionId);
    });

    // Fallback : si session.idle n'existe pas, utiliser event.subscribe().
    if (client.event && typeof client.event.subscribe === "function") {
      client.event.subscribe("session.idle", (sessionId) => {
        exportSession(client, sessionId);
      });
    }
  },
};
