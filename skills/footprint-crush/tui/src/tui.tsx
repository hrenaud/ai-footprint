// tui.tsx — Plugin TUI Opencode : affiche la statusline ai-footprint dans le
// slot sidebar_content (corps du panneau latéral de session — c'est là
// qu'Opencode affiche ses infos de statut, pas en bas de l'écran comme
// Claude Code ; le plugin de référence opencode-subagent-statusline
// enregistre ce même slot, avec `order: 90`, pour sa section "Subagents").
//
// Bundlé (esbuild + esbuild-plugin-solid, cf. build.mjs) en un seul fichier
// committé : ../footprint-crush-tui.js. @opentui/solid / @opentui/core /
// solid-js restent EXTERNAL au bundle (comme le plugin de référence
// sub-agent-statusline) : le renderer universel Solid s'initialise par effet
// de bord au chargement du module et a besoin d'une instance unique de ces
// libs — les bundler en dur casse ce mécanisme (erreur "No renderer found"
// à l'exécution, constatée empiriquement). install.sh installe donc un vrai
// node_modules à côté du plugin déployé pour que ces imports se résolvent
// normalement (cf. .superpowers/specs/…-opencode-tui-statusline.md).

import { execFile } from "node:child_process";
import { createRoot, createSignal, onCleanup, For } from "solid-js";
import {
  formatStatuslineLine,
  formatVersion,
  SIDEBAR_EXPANDED_KEY,
  isSidebarExpanded,
  sidebarToggleMessage,
  resolveBinPath,
  resolveDbPath,
  fetchStatusline,
  fetchVersion,
  resolveSessionId,
} from "./statusline-source.mjs";

const REFRESH_MS = 5000;

// execFile laisse le stdin de l'enfant ouvert (pipe non fermé) : le binaire
// ai-footprint, lisant tout stdin quand il n'est pas un TTY (pour le JSON du
// hook Claude Code), reste alors bloqué en attente d'un EOF qui n'arrive
// jamais si on n'écrit rien. On écrit le JSON (s'il y en a) puis on ferme
// stdin nous-mêmes pour éviter ce blocage.
function execFileWithStdin(bin, args, stdin) {
  return new Promise((resolve, reject) => {
    const child = execFile(bin, args, (err, stdout, stderr) => {
      if (err) reject(err);
      else resolve({ stdout, stderr });
    });
    if (stdin) child.stdin.write(stdin);
    child.stdin.end();
  });
}

function StatusFooter(props) {
  const [lines, setLines] = createSignal([]);
  const [expanded, setExpanded] = createSignal(
    isSidebarExpanded(props.api.kv.get(SIDEBAR_EXPANDED_KEY, true)),
  );
  const [version, setVersion] = createSignal("");
  const bin = resolveBinPath(process.env);

  fetchVersion(execFileWithStdin, bin).then(setVersion);

  function toggle(notify) {
    const nextExpanded = !expanded();
    setExpanded(nextExpanded);
    props.api.kv.set(SIDEBAR_EXPANDED_KEY, nextExpanded);
    if (notify) {
      props.api.ui.toast({
        variant: "info",
        message: sidebarToggleMessage(nextExpanded),
      });
    }
  }

  async function refresh() {
    const db = resolveDbPath(process.env);
    const sessionId = resolveSessionId(props.sessionId, props.api);
    const line = await fetchStatusline(execFileWithStdin, bin, db, sessionId);
    // Une ligne par indicateur (🌍/💧/⚡…) plutôt qu'une seule chaîne inline :
    // le panneau latéral d'Opencode est trop étroit pour la ligne complète,
    // qui s'y coupait au milieu d'une unité.
    setLines(
      line
        .split(" · ")
        .map(formatStatuslineLine)
        .filter(Boolean),
    );
  }

  refresh();
  const timer = setInterval(refresh, REFRESH_MS);
  onCleanup(() => clearInterval(timer));

  return (
    <box>
      <box
        focusable
        onMouseDown={() => toggle(true)}
        onKeyDown={(key) => {
          if (key.name === "return" || key.name === "space") toggle(false);
        }}
      >
        <box flexDirection="row">
          <text>{expanded() ? "▼" : "▶"} AI Footprint</text>
          {version() && (
            <text
              fg={props.theme.textMuted}
              opacity={0.7}
              selectable={false}
            >
              {` ${formatVersion(version())}`}
            </text>
          )}
        </box>
      </box>
      {expanded() && (
        <For each={lines()}>
          {(item) => <text>{item}</text>}
        </For>
      )}
    </box>
  );
}

export const id = "footprint-crush-tui";

export const tui = async (api) => {
  createRoot(() => {
    api.slots.register({
      order: 90,
      slots: {
        sidebar_content(ctx) {
          return (
            <StatusFooter
              sessionId={ctx.session_id}
              theme={ctx.theme.current}
              api={api}
            />
          );
        },
      },
    });
  });
};

export default { id, tui };
