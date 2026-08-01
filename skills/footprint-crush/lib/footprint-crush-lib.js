// footprint-crush-lib.js — Logique pure partagée par footprint-crush.js et ses
// tests. Isolée dans ce fichier (plutôt que des named exports sur
// footprint-crush.js) car Opencode ≥1.18.9 charge les plugins "legacy" en
// exigeant que CHAQUE export du module soit soit une fonction directement,
// soit un objet {server: fonction} (cf. getLegacyPlugins) : un named export
// supplémentaire comme `ingestExport` faisait échouer le chargement du
// plugin avec l'erreur "Plugin export is not a function".
//
// Ce fichier vit dans lib/ (et non à la racine de skills/footprint-crush/,
// ni du dossier plugins déployé) car Opencode/Bun scanne tous les .js à la
// RACINE de son dossier plugins comme candidats plugin, même non déclarés
// dans opencode.json/tui.json : placé à la racine, ce module ({ingestExport}
// sans forme de plugin valide) échouait lui aussi au chargement avec la même
// erreur. Un sous-dossier n'est pas scanné.
//
// Par ailleurs, module.exports = fonction seule ne suffit pas non plus sous
// Bun (runtime d'Opencode) : contrairement à Node, l'interop CJS→ESM de Bun
// expose les propriétés intrinsèques de la fonction (`.length`, `.name`)
// comme exports nommés supplémentaires du module — Opencode les rejette
// alors comme "exports" invalides. C'est pour ça que footprint-crush.js
// EXPORTE une fonction directement mais ne DOIT PLUS rien requérir d'un
// module voisin scanné : seul le require() vers lib/ (hors scan) évite le
// problème.

/**
 * Déclenche l'ingestion des exports Opencode dans la base ai-footprint.
 * L'export (`exportSession`) écrit seulement un fichier JSON sur disque : sans
 * cet appel, `ai-footprint statusline` ne voit jamais la session (les
 * chiffres restent à 0 même après plusieurs tours de conversation).
 *
 * @param {(bin: string, args: string[]) => Promise<{stdout: string, stderr: string}>} execFileImpl
 * @param {string} bin
 * @param {string} exportDir
 * @param {string} sessionId
 */
async function ingestExport(execFileImpl, bin, exportDir, sessionId) {
  try {
    await execFileImpl(bin, ["ingest", "--source-crush", exportDir]);
  } catch (err) {
    console.error(
      `[footprint-crush] Ingestion échouée pour ${sessionId}: ${err.message}`,
    );
  }
}

function toExportMessage(message, sessionId, sessionModel) {
  const info = message.info || message;
  const messageModel = info.model || {};
  const model =
    messageModel.id || messageModel.modelID
      ? messageModel
      : sessionModel || { id: "", providerID: "" };
  return {
    info: {
      role: info.role || "user",
      time: info.time || { created: 0 },
      agent: info.agent || "opencode",
      model,
      tokens: info.tokens || {
        input: 0,
        output: 0,
        reasoning: 0,
        cache: { read: 0, write: 0 },
      },
      cost: info.cost || 0,
      id: info.id || "",
      sessionID: info.sessionID || info.session_id || sessionId,
    },
    parts: (message.parts || []).map((part) => ({
      type: part.type || "text",
      text: part.text || "",
    })),
  };
}

module.exports = { ingestExport, toExportMessage };
