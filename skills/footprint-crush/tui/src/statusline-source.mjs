// statusline-source.mjs — Logique pure de résolution/appel du binaire
// ai-footprint pour la statusline TUI Opencode. Mêmes conventions que
// scripts/statusline.sh et footprint-crush.js (variables AI_FOOTPRINT_BIN /
// AI_FOOTPRINT_DB, fallback ~/.ai-footprint).

import path from "node:path";

export const SIDEBAR_EXPANDED_KEY = "footprint.sidebar.expanded";

export function isSidebarExpanded(value) {
  return value !== false;
}

export function sidebarToggleMessage(expanded) {
  return expanded ? "AI Footprint expanded" : "AI Footprint collapsed";
}

export function resolveBinPath(env) {
  const home = env.HOME || "~";
  return (
    env.AI_FOOTPRINT_BIN ||
    path.join(home, ".ai-footprint", "src", ".venv", "bin", "ai-footprint")
  );
}

export function resolveDbPath(env) {
  const home = env.HOME || "~";
  return (
    env.AI_FOOTPRINT_DB || path.join(home, ".ai-footprint", "ai-footprint.db")
  );
}

export function formatStatuslineLine(line) {
  return line.startsWith("🔢 ") ? "" : line;
}

export function formatVersion(version) {
  return version ? `v${version}` : "";
}

/**
 * @param {(bin: string, args: string[]) => Promise<{stdout: string}>} execFileImpl
 * @param {string} bin
 * @returns {Promise<string>} la version du binaire, ou "" en cas d'échec.
 */
export async function fetchVersion(execFileImpl, bin) {
  try {
    const { stdout } = await execFileImpl(bin, ["--version"]);
    return stdout.trim();
  } catch {
    return "";
  }
}

/**
 * Le prop `session_id` du slot `sidebar_content` d'Opencode n'est pas
 * toujours renseigné à l'exécution (constaté empiriquement) ; le plugin de
 * référence opencode-subagent-statusline retombe alors sur
 * `api.route.current.params.sessionID` (route de session courante). Sans
 * id résolu, `fetchStatusline` n'envoie aucun stdin et le binaire calcule
 * sur le total global de l'historique au lieu de la session en cours.
 * @param {string} [ctxSessionId] - `props.session_id` reçu par le slot.
 * @param {{route: {current: {name: string, params?: {sessionID?: string}}}}} api
 * @returns {string|undefined}
 */
export function resolveSessionId(ctxSessionId, api) {
  if (ctxSessionId) return ctxSessionId;
  const route = api?.route?.current;
  if (
    route?.name === "session" &&
    typeof route.params?.sessionID === "string"
  ) {
    return route.params.sessionID;
  }
  return undefined;
}

/**
 * @param {(bin: string, args: string[], stdin?: string) => Promise<{stdout: string}>} execFileImpl
 * @param {string} bin
 * @param {string} db
 * @param {string} [sessionId] - id de session Opencode courante ; transmis en
 *   JSON sur stdin comme le fait le hook Claude Code, pour que la statusline
 *   porte sur la session en cours plutôt que sur le total global.
 * @returns {Promise<string>} la ligne de statusline, ou "" en cas d'échec.
 */
export async function fetchStatusline(execFileImpl, bin, db, sessionId) {
  try {
    const stdin = sessionId
      ? JSON.stringify({ session_id: sessionId })
      : undefined;
    const { stdout } = await execFileImpl(
      bin,
      ["statusline", "--db", db],
      stdin,
    );
    return stdout.trim();
  } catch {
    return "";
  }
}
