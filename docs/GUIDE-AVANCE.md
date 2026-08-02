# Guide avancé

Ce guide s'adresse aux utilisateurs à l'aise avec la ligne de commande qui
veulent installer `ai-footprint` manuellement ou comprendre son
fonctionnement interne. Pour l'usage courant (skills, installation en une
ligne), voir le [guide utilisateur](GUIDE.md). Pour le développement du
projet lui-même (architecture du code, schéma de base de données, tests),
voir [CONTRIBUTING.md](CONTRIBUTING.md).

## Installation manuelle

L'installeur en une ligne (voir le [guide utilisateur](GUIDE.md#installer))
reste la méthode recommandée : il détecte tes outils installés et câble tout
automatiquement. Les méthodes ci-dessous n'installent que la **CLI**, sans
câblage automatique dans Claude Code, Opencode, Pi ou Codex CLI.

### Via Homebrew (macOS/Linux)

```bash
brew install hrenaud/tap/ai-footprint
```

Formule maintenue sur un tap personnel (`hrenaud/homebrew-tap`) — équivalent
à `brew tap hrenaud/tap && brew install ai-footprint`. Mise à jour :
`brew upgrade ai-footprint`.

### Via PyPI

```bash
pip install ai-footprint
```

Le paquet `agent-footprint` (ancien nom du projet) redirige aussi vers
`ai-footprint`. Mise à jour : `pip install --upgrade ai-footprint`.

### Depuis les sources (dev)

```bash
git clone https://github.com/hrenaud/ai-footprint
cd ai-footprint
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Câbler manuellement après une installation brew/pip

Sans câblage automatique, c'est à toi de déclencher l'ingestion et
d'afficher la statusline :

```bash
ai-footprint ingest       # à lancer périodiquement (ou via ton propre hook)
ai-footprint statusline   # à brancher dans la config de ton outil
```

Les skills (`/footprint-report`, etc.) nécessitent en plus les fichiers de
skills du dépôt — non installés par brew/pip.

## Variables d'environnement

Utilisées par `install.sh` et `uninstall.sh` :

| Variable                 | Effet                                                           | Défaut                            |
| ------------------------ | --------------------------------------------------------------- | --------------------------------- |
| `AI_FOOTPRINT_DIR`       | Répertoire d'installation (clone + venv).                       | `~/.ai-footprint/src`             |
| `AI_FOOTPRINT_DB`        | Chemin de la base SQLite (historique d'impact).                 | `~/.ai-footprint/ai-footprint.db` |
| `AI_FOOTPRINT_REF`       | Branche ou tag git à installer (utile pour tester une branche). | `main`                            |
| `AI_FOOTPRINT_NO_CLAUDE` | `=1` → ne modifie pas `~/.claude/settings.json`.                | non défini                        |
| `AI_FOOTPRINT_NO_INGEST` | `=1` → n'exécute pas l'ingestion initiale.                      | non défini                        |
| `AI_FOOTPRINT_PURGE_DB`  | `=1` (désinstallation) → supprime aussi la base SQLite.         | non défini                        |

Exemple : installer une branche de test dans un répertoire isolé, sans
toucher à l'installation de production ni à `settings.json` :

```bash
curl -fsSL https://raw.githubusercontent.com/hrenaud/ai-footprint/main/install.sh | \
  AI_FOOTPRINT_REF=ma-branche AI_FOOTPRINT_DIR=/tmp/ai-footprint-test \
  AI_FOOTPRINT_NO_CLAUDE=1 bash
```

## Désinstallation complète

L'[uninstaller](GUIDE.md#desinstallation) conserve la base SQLite par
défaut. Pour la supprimer aussi :

```bash
AI_FOOTPRINT_PURGE_DB=1 \
  curl -fsSL https://raw.githubusercontent.com/hrenaud/ai-footprint/main/uninstall.sh | bash
```

## Sous le capot

### La CLI

Les skills ne sont qu'une couche au-dessus de la CLI : tu peux l'utiliser
directement.

```bash
ai-footprint ingest           # parse les transcripts → base SQLite (~/.ai-footprint/ai-footprint.db)
ai-footprint report           # rapport multi-critères (--since, --detail, --all-projects)
ai-footprint card             # card PNG partageable (--since, --theme, --lang, --out)
ai-footprint statusline       # ligne compacte pour la session courante
ai-footprint resolve --list   # liste les modèles non couverts à résoudre
ai-footprint resolve --set "provider/modele=org/repo-hf"   # applique un mapping et recalcule
ai-footprint resolve --forget "provider/modele"            # retire un mapping et recalcule
ai-footprint nudge --json     # état des nudges (modèles non proposés, mise à jour dispo)
```

`ingest` résume la couverture obtenue, par exemple :

```
80 events ingérés · 33639/33709 mesurés · 70 non couverts (conservés, impact non estimé)
```

Les « non couverts » sont des modèles hors périmètre EcoLogits : l'event est
conservé mais exclu des totaux (afficher un faux chiffre serait pire qu'un
trou de couverture). Beaucoup sont des placeholders internes `<synthetic>` (0
token, sans impact réel) ; les vrais modèles tiers ou récents se résolvent
avec `ai-footprint resolve` (ou `/footprint-resolve`). Détails complets :
[METHODOLOGY.md](METHODOLOGY.md).

### Ingestion multi-outils

`ai-footprint ingest` lit les transcripts de session de chaque outil détecté
(Claude Code, Opencode, Pi, Codex CLI) et les convertit en events dans la base
SQLite. L'ingestion est **idempotente** : rejouer un même transcript ne
duplique rien. Chaque outil déclenche l'ingestion à sa façon :

- **Claude Code** : un hook `Stop` ingère le transcript en fin de session, et
  un hook `SessionStart` propose en début de session une mise à jour ou la
  résolution des modèles non couverts, si pertinent.
- **Opencode** : un plugin déclenche l'ingestion sur les mêmes
  événements de cycle de vie de session.
- **Pi** : une extension fait de même sur ses propres événements de session.
- **Codex CLI** : pas de hook temps réel (le slot `notify` de `config.toml`
  peut être pris par un autre outil) — l'ingestion se fait par backfill, au
  moment de l'installation puis à chaque relance manuelle de
  `ai-footprint ingest --source-codex`.

### Statusline Claude Code

Claude Code affiche l'impact dans sa statusline. La statusline affiche l'impact de la **session en cours**.

L'outil transmet
l'identifiant de session à ai-footprint, qui ingère le transcript courant et
filtre les totaux dessus. Lancée manuellement hors session, elle retombe sur
le **total global** de l'historique :

```bash
~/.ai-footprint/src/scripts/statusline.sh
```

L'installeur ne remplace jamais une statusline déjà utilisée par un autre
outil — il affiche alors la commande pour basculer manuellement.

Chaque indicateur choisit automatiquement son unité (ex. eau en mL, cL ou L ;
énergie en mWh, Wh ou kWh ; CO2 en mgCO2eq, gCO2eq ou kgCO2eq) pour éviter les
« 0.000… » sur les petites sessions. Sans donnée, la statusline affiche une
ligne à 0 (jamais une ligne vide) pour rester rafraîchie par l'outil hôte.

Une ligne à 0 malgré des tokens réellement consommés a deux causes
possibles : (1) aucune donnée n'a été ingérée pour cette session, ou (2) le
modèle utilisé n'est pas couvert par EcoLogits — l'event est bien ingéré mais
`rows_for_report` l'exclut des totaux (`WHERE i.error IS NULL`), afficher un
faux chiffre étant pire qu'un trou de couverture. Pour distinguer ces deux cas,
la statusline de session ajoute un suffixe `· 🔢 N tok` quand
`tokens_for_session` (qui compte directement sur `events`, sans la jointure
`impacts`) renvoie un total non nul — un `🔢` présent avec le reste de la
ligne à 0 signale un modèle non couvert, son absence signale une absence
d'ingestion.

### Statusline TUI Opencode

Opencode affiche ses infos de statut dans le corps du panneau latéral de
session (`sidebar_content`), pas en pied d'écran comme les autres outils. Un
plugin dédié — `skills/footprint-crush/tui/` (sources), compilé en
`skills/footprint-crush/footprint-crush-tui.js` (bundle committé) — s'y
enregistre pour afficher la statusline ai-footprint à cet endroit.

L'installeur :

- copie le bundle dans `~/.config/opencode/plugins/footprint-crush-tui.js` et
  l'enregistre dans `~/.config/opencode/tui.json` ;
- installe un `node_modules` réel à côté (`~/.config/opencode/plugins/`) pour
  `@opentui/core`, `@opentui/solid` et `solid-js` via `npm install`.

Ce `node_modules` est nécessaire car ces trois librairies restent **external**
au bundle esbuild (cf. `skills/footprint-crush/tui/build.mjs`) : le renderer
universel Solid s'initialise par effet de bord au chargement du module et a
besoin d'une instance unique de ces libs — les bundler en dur casse ce
mécanisme (erreur `No renderer found` à l'exécution). Si `npm` est absent au
moment de l'installation, la statusline TUI ne s'affichera pas tant que ce
`node_modules` n'est pas créé manuellement (mêmes paquets/versions que
`skills/footprint-crush/tui/package.json`).

La carte, dépliée par défaut, est repliable avec un clic ou au clavier (Entrée
ou Espace après avoir reçu le focus). Son état est conservé entre les sessions.
Un clic affiche une notification de confirmation ; les bascules au clavier
restent silencieuses. Elle affiche la version installée, puis une ligne par
indicateur (🌍/💧/⚡) plutôt qu'une seule ligne inline, le panneau latéral étant
trop étroit pour la ligne complète utilisée par les autres outils (elle s'y
coupait au milieu d'une unité). Un avertissement de modèle extrapolé peut
compléter les indicateurs. Cet avertissement nomme le modèle récent et sa
version de repli, quel que soit son fournisseur (par exemple `gpt-5.6-terra`
avec les paramètres de `gpt-5.5`).

Opencode ≥1.18.9 tourne sur un binaire compilé Bun. Sous Bun, l'interop
CJS→ESM d'un module `module.exports = fonction` (fonction nue) fuite les
propriétés intrinsèques de cette fonction (`.length`, `.name`) comme de faux
exports nommés supplémentaires du module — contrairement à Node, où l'interop
ne produit que `{default: fonction}`. Le chargeur de plugins d'Opencode lit
d'abord `mod.default` en cherchant la forme V1 documentée `{server:
fonction}` ; si ce n'est pas un objet de cette forme (cas d'une fonction nue),
il retombe sur un chargement « legacy » qui itère _tous_ les exports du
module et exige que chacun soit soit une fonction, soit un objet `{server:
fonction}` — les faux exports `.length`/`.name` (un nombre et une chaîne) ne
satisfont ni l'un ni l'autre, d'où l'erreur `Plugin export is not a
function`. `footprint-crush.js` exporte donc directement la forme V1
`module.exports = { server: async ({client}) => {...} }`, lue par `mod.default`
sans jamais retomber sur le scan legacy — la fuite Bun devient sans effet.

Les exports de session et leur ingestion sont silencieux en cas de succès pour
ne pas perturber le TUI ; seules les erreurs du plugin sont journalisées.

Par ailleurs, Opencode/Bun scanne tous les `.js` à la **racine** de son
dossier plugins comme candidats plugin, même non déclarés dans
`opencode.json`/`tui.json` (un sous-dossier n'est pas scanné). La logique
testable (`ingestExport`) vit donc dans `lib/footprint-crush-lib.js` (et non à
la racine), requis via `require()` par `footprint-crush.js` mais jamais
lui-même un candidat plugin scanné — `install.sh` déploie
`footprint-crush.js` à la racine de `~/.config/opencode/plugins/` et
`footprint-crush-lib.js` dans son sous-dossier `lib/`.

Le prop `session_id` que le slot `sidebar_content` d'Opencode transmet à la
fonction enregistrée n'est pas toujours renseigné à l'exécution (constaté
empiriquement) : sans repli, `fetchStatusline` n'envoie alors aucun id de
session au binaire, qui calcule sur le **total global** de l'historique
(tous outils/modèles confondus) au lieu de la session en cours — d'où des
chiffres démesurés et un modèle affiché sans rapport avec celui réellement
utilisé. Le plugin retombe donc sur `api.route.current.params.sessionID`
(route de session courante) quand `session_id` est absent, comme le fait le
plugin de référence `opencode-subagent-statusline`
(`resolveSessionId` dans `skills/footprint-crush/tui/src/statusline-source.mjs`).

### Modèles non couverts et résolution

Voir [METHODOLOGY.md](METHODOLOGY.md) pour le détail de ce qui est mesuré et
pourquoi certains modèles restent hors périmètre. `ai-footprint resolve`
associe un modèle non couvert à un dépôt Hugging Face équivalent, vérifie ses
paramètres réels, et recalcule les impacts.
