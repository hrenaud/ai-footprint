// build.mjs — Bundle tui.tsx en un seul fichier ESM committé :
// ../footprint-crush-tui.js. solid-js / @opentui/solid / @opentui/core
// restent external (non bundlés) : le renderer universel Solid s'initialise
// par effet de bord au chargement de ces modules et exige une instance
// unique — les bundler casse cette initialisation ("No renderer found" à
// l'exécution). install.sh installe un vrai node_modules à côté du plugin
// déployé pour que ces imports se résolvent normalement au chargement.

import { build } from "esbuild";
import { solidPlugin } from "esbuild-plugin-solid";

await build({
  entryPoints: ["src/tui.tsx"],
  bundle: true,
  format: "esm",
  platform: "node",
  target: "node18",
  outfile: "../footprint-crush-tui.js",
  external: ["@opentui/core", "@opentui/solid", "solid-js"],
  plugins: [
    solidPlugin({
      solid: { generate: "universal", moduleName: "@opentui/solid" },
    }),
  ],
});

console.log("footprint-crush-tui.js généré.");
