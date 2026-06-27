# agent-carbon — Design MVP

> Spec issu du brainstorming du 2026-06-27, à partir de `KICKOFF.md`.
> But : compteur d'impact **vendor-neutral** et **multi-critères** pour les outils d'IA agentique, qui **délègue le calcul d'impact à EcoLogits** au lieu de réécrire un modèle.

## Principe directeur

Le cœur est **vendor-neutral**. Tout ce qui est spécifique à un outil (Claude Code) ou à une cible de sortie (statusline) vit dans des **adaptateurs** branchés sur des interfaces stables. On n'écrit **aucun modèle d'impact** : EcoLogits s'en charge.

La philosophie d'incertitude est explicite : l'incertitude principale (facteur ~8, piloté par la région datacenter d'Anthropic non publiée) est **irréductible**. Un bon outil ne la masque pas, il l'**affiche en fourchette** (min/max). On ne produit jamais un chiffre unique de fausse précision.

## Décisions tranchées (brainstorming)

| #   | Décision               | Choix retenu                                                                                                                                                       |
| --- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1   | Périmètre MVP          | **Claude / Claude Code uniquement**, mais coutures d'extensibilité posées dès le départ (interface `Collector` + stubs) pour ajouter outils/modes **sans refacto** |
| 2   | Alimentation EcoLogits | **Offline** depuis tokens stockés ; mode `live` posé en placeholder                                                                                                |
| 3   | Source des données     | **JSONL** (source de vérité) → ingestion → **notre propre DB SQLite** → reporting ; démarrage propre, backfill `carbon.db` en placeholder                          |
| 4   | Inférence locale       | **Hors MVP**, module placeholder (`énergie_machine × grille FRA`, facteur Wh/token à fixer plus tard)                                                              |
| 5   | Sortie                 | **Rapport CLI + statusline**, branchés sur la DB                                                                                                                   |
| 6   | Langage                | **Tout Python** (EcoLogits est Python ; on parse du JSONL)                                                                                                         |

Paramètres validés : zone électrique par défaut **`USA`** (configurable, fourchette toujours affichée) ; granularité du rapport = **par modèle + par projet + total**, filtre `--since`.

## Pipeline

```
JSONL Claude Code (~/.claude/projects/**/*.jsonl)
   ↓  ClaudeCodeCollector (parse)
InferenceEvent[]   {provider, model, input/output/cache_creation/cache_read tokens, ts, project, session_id, msg_id}
   ↓  EcoLogitsEngine (offline, par zone élec)
ImpactRecord[]     {gwp, adpe, pe, energy, water} × {usage, embodied} × RangeValue(min/max/mean) + warnings
   ↓  SQLiteStore (ingestion idempotente)
notre DB SQLite
   ↓
report CLI  +  statusline
```

## Composants & coutures d'extensibilité

| Module        | MVP (réel)                                                                                   | Placeholder (extension sans refacto)                                                            |
| ------------- | -------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `collectors/` | `Collector` (ABC) + `ClaudeCodeCollector` (parse JSONL)                                      | `CodexCollector`, `PICollector`, `LocalInferenceCollector` → stubs levant `NotImplementedError` |
| `impact/`     | `EcoLogitsEngine.compute(event, zone)` — mode **offline**                                    | `compute_live()` posée en stub                                                                  |
| `store/`      | `SQLiteStore` : tables `events` + `impacts`, ingestion idempotente                           | `import_legacy(carbon_db_path)` stub (backfill `carbon.db`)                                     |
| `report/`     | commande `report` : tableau multi-critères + fourchettes, par modèle/projet/total, `--since` | export `--format md/json` en extension                                                          |
| `statusline/` | commande compacte lisant l'agrégat en DB                                                     | —                                                                                               |
| `config`      | `electricity_mix_zone` configurable (défaut `USA`)                                           | —                                                                                               |

### Interface `Collector` (contrat)

- **Rôle** : transformer une source spécifique à un outil en `InferenceEvent[]` normalisés.
- **Entrée** : chemin(s) de source (pour Claude Code : répertoire des JSONL).
- **Sortie** : itérable d'`InferenceEvent`.
- **Dépendances** : aucune sur l'impact ou le store (couplage faible).

### Modèle `InferenceEvent` (normalisé, neutre)

```
InferenceEvent
  provider            # "anthropic"
  model               # nom modèle exact issu du JSONL
  input_tokens
  output_tokens
  cache_creation_tokens
  cache_read_tokens
  timestamp           # ISO, UTC
  project             # dossier projet (dérivé du chemin JSONL)
  session_id
  msg_id              # identifiant message → clé d'idempotence
```

### `EcoLogitsEngine`

- **Rôle** : `compute(event, zone) -> ImpactRecord` via l'API **offline** d'EcoLogits.
- L'entrée offline pressentie est la fonction interne du type `llm_impacts(provider, model_name, output_token_count, request_latency, electricity_mix_zone)` + le _model registry_ (mapping `model_name → paramètres`). **À valider par le spike fondateur** (cf. tests) car semi-interne.
- **Sortie** : `ImpactRecord` reflétant `ImpactsOutput` d'EcoLogits — `energy` (kWh), `gwp` (kgCO₂eq), `adpe` (kgSbeq), `pe` (MJ), `wcf` (L), chacun en `.usage`/`.embodied`, valeurs `RangeValue(min/max/mean)`, plus `warnings`/`errors`.

## Modèle de données (notre schéma SQLite)

- **`events`** : une ligne par message d'inférence normalisé (conservée même après la purge JSONL ~30 j). Clé naturelle = `(session_id, msg_id)`.
- **`impacts`** : résultat EcoLogits par event — 5 critères × 2 phases × (min/max/mean) + warnings + zone élec + version EcoLogits utilisée.
- Séparation `events`/`impacts` volontaire : on peut **recalculer** les impacts (autre zone, nouvelle version EcoLogits) **sans re-parser** les JSONL.

## Flux d'ingestion (idempotent)

1. `ClaudeCodeCollector` lit les JSONL → `InferenceEvent[]`.
2. Pour chaque event non déjà présent (`(session_id, msg_id)`), insertion dans `events`.
3. `EcoLogitsEngine.compute` → insertion dans `impacts`.
4. Rejouer les mêmes JSONL ne crée aucun doublon (la purge 30 j n'efface donc pas l'historique déjà ingéré).

## Gestion d'erreurs

- **Modèle inconnu d'EcoLogits** : l'event est stocké, l'impact est `null` + warning loggé. Pas de crash.
- **Warnings EcoLogits** (ex. « architecture du modèle non divulguée » pour Claude) : conservés par record et affichés en note de bas de rapport.
- **Idempotence** : protège contre le double comptage en cas de ré-ingestion.

## Sortie

- **Rapport CLI** : tableau multi-critères (gwp/adpe/pe/énergie/eau) avec fourchettes **min–max**, dimensions **par modèle**, **par projet**, et **total global** ; filtre temporel `--since`. La zone élec et l'incertitude sont rappelées explicitement.
- **Statusline** : ligne compacte (adaptateur de sortie spécifique Claude Code) lisant l'agrégat déjà calculé en DB. Pas de hook live requis dans le MVP.

## Stratégie de test (TDD — tests écrits avant implémentation)

1. **Spike fondateur (bloquant)** : prouver que l'API offline EcoLogits renvoie un `ImpactsOutput` multi-critères + `RangeValue` pour un modèle Claude réel. Si l'API interne diffère de l'hypothèse, on l'ajuste **ici** avant toute autre brique.
2. `ClaudeCodeCollector` : fixture JSONL réelle (anonymisée) → `InferenceEvent[]` attendus, y compris dérivation du `project` depuis le chemin.
3. `SQLiteStore` : test d'ingestion idempotente (rejouer = aucun doublon) + recalcul d'impact sans re-parse.
4. `report` : snapshot du tableau CLI sur DB de test (par modèle / par projet / total).

## Hors MVP (assumé, posé en coutures)

Inférence locale (câblage + facteur Wh/token Apple Silicon), terminal utilisateur, backfill `carbon.db`, mode live, export fichier (md/json) — tous **posés en placeholders**, **aucun implémenté** dans le MVP.
