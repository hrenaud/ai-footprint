# Design — Propositions proactives de resolve & auto-update ai-footprint

Date : 2026-07-12

## Problème

ai-footprint calcule les impacts **une seule fois, à l'ingestion**, et ne les
recalcule jamais automatiquement (cf. `docs/METHODOLOGY.md` § Reproductibilité).
Deux dérives silencieuses en découlent pour un utilisateur non technique qui ne
consulte pas activement ses impacts :

1. Des modèles non couverts s'accumulent sans que l'utilisateur sache qu'un
   `footprint-resolve` peut les débloquer (le seul signal actuel est un texte
   statique, non interactif, dans la sortie de `footprint-report`, et **rien**
   dans `footprint-card`).
2. ai-footprint lui-même peut avoir une nouvelle version (facteurs d'impact mis
   à jour, nouveaux modèles couverts) sans que l'utilisateur en soit informé —
   aucun mécanisme n'existe aujourd'hui pour le signaler côté utilisateur final
   (le seul mécanisme existant, `tool_updates.py`, est **interne**, à
   destination des mainteneurs, pour ecologits/huggingface_hub).

## Objectif

À chaque démarrage de session (Claude Code, OpenCode, Pi), proposer
explicitement — jamais silencieusement — à l'utilisateur :

- de mettre à jour ai-footprint si une nouvelle version existe sur GitHub ;
- de lancer `footprint-resolve` s'il existe des modèles non couverts jamais
  proposés à l'utilisateur.

`footprint-report` et `footprint-card` posent la même question avant de
produire leur sortie, sans redite si elle a déjà été posée dans la session.

**Hors périmètre** : mise à jour automatique sans confirmation, notification
en dehors d'une session (email, cron), gestion fine des conflits multi-session
concurrents.

## Architecture

### État persistant (config)

Nouveau champ dans `~/.ai-footprint/config.json` :

```json
"resolve_prompt_state": { "prompted_keys": ["provider/model", "..."] }
```

Un modèle non couvert n'est proposé qu'une fois : dès qu'il apparaît dans
`prompted_keys`, il ne redéclenche plus de proposition (« silence par lot »),
jusqu'à ce qu'un modèle **différent** apparaisse en non-couvert.

### Réutilisation (pas de nouveau module parallèle)

- **Cache TTL** : extraction d'un helper générique
  (`load_json_cache`/`save_json_cache`/`should_refresh`, signature `**fields`)
  à partir de l'existant dans `ai_footprint/tool_updates.py`. `tool_updates.py`
  est refactoré pour l'utiliser (pas de réécriture de sa logique métier :
  comparaison de versions PyPI vs pins `pyproject.toml`, inchangée).
- **Liste des non-couverts** : `ai_footprint/nudge.py` appelle la même
  fonction interne que `resolve --list` (extraite si actuellement inline dans
  `ai_footprint/resolve/cli.py:cmd_resolve`), pas de nouvelle requête store.

### Nouveau : `ai_footprint/nudge.py`

- `check_self_update(config) -> {"current": str, "latest": str} | None` —
  compare `ai_footprint.__version__` au tag GitHub le plus récent
  (`git ls-remote --tags https://github.com/hrenaud/ai-footprint`), throttlé
  24h via le cache générique (clé `self_update_check`, même TTL que
  `tool_updates.py`).
- `check_uncovered_batch(store, config) -> list[str]` — clés non couvertes
  (hors `<synthetic>`) absentes de `prompted_keys`.
- `mark_batch_prompted(config, store)` — fusionne le lot non couvert **actuel**
  dans `prompted_keys` et sauvegarde la config.

### Nouvelle commande CLI

```
ai-footprint nudge --json           # {"update_available": {...}|null, "uncovered_new": [...]}
ai-footprint nudge --mark-prompted  # clôt le lot courant
```

Offline-safe : toute erreur réseau (`git ls-remote` échoue) → `update_available: null`,
pas de blocage.

## Flux (identique dans son principe pour les 3 outils)

1. Au démarrage de session, appel de `ai-footprint nudge --json`.
2. Si `update_available` : proposer la mise à jour seule d'abord.
   - Accepté → exécuter `curl -fsSL .../install.sh | bash` (idempotent),
     afficher le résultat, puis **ré-appeler** `nudge --json` (le registre
     EcoLogits embarqué a pu changer) avant de passer à l'étape 3.
   - Échec de l'install → afficher l'erreur brute, ne pas enchaîner sur le
     resolve, ne pas marquer de lot comme traité (on retentera à la session
     suivante).
3. Si `uncovered_new` non vide : proposer `footprint-resolve`.
4. Dès qu'une proposition de resolve a été **posée** (acceptée ou refusée) :
   `ai-footprint nudge --mark-prompted`.

`footprint-report`/`footprint-card` exécutent la même étape 3 avant de produire
leur sortie (remplace le message statique actuel / l'absence de message pour
`footprint-card`) — sans redite si le lot a déjà été clos dans la session
(`prompted_keys` déjà à jour).

## Points d'accroche par outil

Recherche menée via Context7 et la documentation officielle de chaque outil
(pas d'essai en aveugle) :

| Outil           | Event                                                                                                                                                                   | Mécanisme de proposition                                                                                                                                                                                                                                                                                   |
| --------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Claude Code** | hook `SessionStart` (nouveau, à ajouter dans `install.sh` à côté de `statusLine`/`Stop`)                                                                                | le hook exécute `ai-footprint nudge --json` et injecte le résultat + une instruction dans le contexte additionnel retourné ; l'agent lit l'instruction et appelle lui-même `AskUserQuestion`                                                                                                               |
| **OpenCode**    | hook `event` avec `event.type === "session.created"` (documenté à côté de `session.idle`, déjà utilisé par `footprint-crush.js`) — **pas d'API UI directe côté plugin** | le plugin injecte un message dans la session via le SDK client (à préciser en implémentation : méthode `client.session.*` équivalente à un `chat.message`/prompt) ; l'agent le lit et appelle son outil `question`                                                                                         |
| **Pi**          | événement `session_start` (`reason: "startup"\|"reload"\|"new"\|"resume"\|"fork"`)                                                                                      | **l'extension pose la question elle-même**, sans passer par le LLM, via `ctx.ui.confirm()`/`ctx.ui.select()` (API de base `@earendil-works/pi-coding-agent`, déjà utilisée par `footprint-pi.ts`) ; si acceptée, `pi.sendUserMessage()` déclenche un tour d'agent qui invoque le skill `footprint-resolve` |

**Validé — aucune extension/MCP supplémentaire requise pour Pi** : `ctx.ui`,
`pi.sendUserMessage`/`sendMessage` et `session_start` font partie de l'API de
base de l'extension déjà installée par `install.sh`
(`~/.pi/agent/extensions/footprint-pi.ts`). Ces méthodes UI sont des no-ops en
mode print/JSON (`ctx.hasUI === false`), déjà géré par le pattern existant
dans le fichier (`if (ctx.hasUI)`), donc pas de régression en mode non
interactif.

## Gestion d'erreurs

- **Réseau indisponible** (`git ls-remote`, appel GitHub) : `check_self_update`
  retourne `None` silencieusement, aucun blocage de session (même comportement
  offline-safe que `tool_updates.session_start_check`).
- **Cache corrompu/absent** : traité comme « jamais vérifié » →
  `should_refresh` renvoie `True`.
- **Échec de `install.sh`** : voir flux étape 2, pas de marquage, retry à la
  session suivante.
- **`mark-prompted` appelé sans réponse effective de l'utilisateur** (ex.
  timeout outil) : non géré spécifiquement — le lot est considéré clos ; s'il
  réapparaît identique à la session suivante, il n'est pas reproposé (accepté,
  cohérent avec le principe de silence par lot).

## Tests

- `ai_footprint/nudge.py` : tests unitaires purs (comparaison de versions,
  calcul du lot non couvert vs `prompted_keys`, throttle TTL réutilisé) —
  suivant le pattern déjà en place pour `tool_updates.py`.
- CLI `nudge --json`/`--mark-prompted` : test d'intégration sur une DB de test
  avec des events non couverts connus.
- Hooks/plugins (Claude Code, OpenCode, Pi) : pas de couverture automatisée
  possible pour l'injection UI elle-même (dépend du runtime de chaque outil) —
  vérification manuelle documentée dans le plan d'implémentation.

## Documentation à mettre à jour (implémentation)

- `docs/METHODOLOGY.md` : mentionner que le recalcul (`resolve --forget` +
  `recompute_errors`) peut désormais être proposé proactivement.
- `skills/footprint-report/SKILL.md`, `skills/footprint-card/SKILL.md`,
  `skills/footprint-resolve/SKILL.md` : nouvelle étape de proposition avant le
  flux existant.
- `CONTRIBUTING.md` : documenter `ai_footprint/nudge.py`, la commande
  `nudge`, le nouveau hook `SessionStart`/`session.created`/`session_start`.
- `CHANGELOG.md` : généré automatiquement à la release, ne pas éditer à la
  main (cf. AGENTS.md).
