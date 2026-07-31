// src/tui.tsx
import { insert as _$insert } from "@opentui/solid";
import { createComponent as _$createComponent } from "@opentui/solid";
import { setProp as _$setProp } from "@opentui/solid";
import { createElement as _$createElement } from "@opentui/solid";
import { execFile } from "node:child_process";
import { createRoot, createSignal, onCleanup, For } from "solid-js";

// src/statusline-source.mjs
import path from "node:path";
function resolveBinPath(env) {
  const home = env.HOME || "~";
  return env.AI_FOOTPRINT_BIN || path.join(home, ".ai-footprint", "src", ".venv", "bin", "ai-footprint");
}
function resolveDbPath(env) {
  const home = env.HOME || "~";
  return env.AI_FOOTPRINT_DB || path.join(home, ".ai-footprint", "ai-footprint.db");
}
function resolveSessionId(ctxSessionId, api) {
  if (ctxSessionId) return ctxSessionId;
  const route = api?.route?.current;
  if (route?.name === "session" && typeof route.params?.sessionID === "string") {
    return route.params.sessionID;
  }
  return void 0;
}
async function fetchStatusline(execFileImpl, bin, db, sessionId) {
  try {
    const stdin = sessionId ? JSON.stringify({ session_id: sessionId }) : void 0;
    const { stdout } = await execFileImpl(
      bin,
      ["statusline", "--db", db],
      stdin
    );
    return stdout.trim();
  } catch {
    return "";
  }
}

// src/tui.tsx
var REFRESH_MS = 5e3;
function execFileWithStdin(bin, args, stdin) {
  return new Promise((resolve, reject) => {
    const child = execFile(bin, args, (err, stdout, stderr) => {
      if (err) reject(err);
      else resolve({
        stdout,
        stderr
      });
    });
    if (stdin) child.stdin.write(stdin);
    child.stdin.end();
  });
}
function StatusFooter(props) {
  const [lines, setLines] = createSignal([]);
  async function refresh() {
    const bin = resolveBinPath(process.env);
    const db = resolveDbPath(process.env);
    const sessionId = resolveSessionId(props.sessionId, props.api);
    const line = await fetchStatusline(execFileWithStdin, bin, db, sessionId);
    setLines(line.split(" \xB7 ").filter(Boolean));
  }
  refresh();
  const timer = setInterval(refresh, REFRESH_MS);
  onCleanup(() => clearInterval(timer));
  return (() => {
    var _el$ = _$createElement("box");
    _$setProp(_el$, "title", "AI Footprint");
    _$setProp(_el$, "border", true);
    _$setProp(_el$, "padding", 1);
    _$insert(_el$, _$createComponent(For, {
      get each() {
        return lines();
      },
      children: (item) => (() => {
        var _el$2 = _$createElement("text");
        _$insert(_el$2, item);
        return _el$2;
      })()
    }));
    return _el$;
  })();
}
var id = "footprint-crush-tui";
var tui = async (api) => {
  createRoot(() => {
    api.slots.register({
      order: 90,
      slots: {
        sidebar_content(props) {
          return _$createComponent(StatusFooter, {
            get sessionId() {
              return props.session_id;
            },
            api
          });
        }
      }
    });
  });
};
var tui_default = {
  id,
  tui
};
export {
  tui_default as default,
  id,
  tui
};
