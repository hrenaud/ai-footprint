# Support Opencode/Crush dans agent-carbon

**Date** : 2026-06-30  
**Statut** : ✅ Validé (2026-07-01) — cohérent avec `comparaison-donnees-outils.md` → [plan](../plans/2026-06-30-support-crush-opencode.md)
**Déclencheur** : Ajouter le support d'Opencode (renommé "Crush" chez Charm) à agent-carbon

---

## Contexte

Agent-carbon supporte actuellement **Claude Code** via la lecture de transcripts JSONL (`~/.claude/projects/**/*.jsonl`). On veut étendre le support à **Opencode**, rebranded **Crush** (charmbracelet/crush).

### Ce qu'est Crush/Opencode

- CLI TUI en Go (existant sous `~/.local/share/crush/crush.db` ou `~/.local/share/opencode/opencode.db`)
- Sessions stockées en SQLite
- Commande `opencode export <sessionID>` pour exporter une session en JSON
- Système de plugins TypeScript/JS (extensible)
- SDK avec streaming SSE (`event.subscribe()`)

### Données exportées par `opencode export`

Structure JSON avec :
- `info` : `{ id, slug, projectID, directory, path, title, agent, model: {id, providerID}, version, tokens: {input, output, reasoning, cache: {read, write}}, time: {created, updated} }`
- `messages` : tableau de messages avec `info: {role, time, agent, model, tokens, cost, id, sessionID}` et `parts: [{type, text, ...}]`

---

## Architecture : collecte unifiée via une seule BDD

**Principe fondamental** : on ne cloisonne pas les impacts par outil. Tout est centralisé dans une seule BDD SQLite (`~/.agent-carbon/carbon.db`).

```
Sources multiples (Claude Code, Crush/Opencode, ...)
         │
         ▼
  Collecteur par outil (polymorphique)
         │
         ▼
  InferenceEvent (format normalisé unique)
         │
         ▼
  SQLiteStore (stockage unique)
         │
         ▼
  EcoLogitsEngine (calculs d'impact)
         │
         ▼
  ModelResolver (reconnaissance des modèles)
         │
         ▼
  Rapports (multi-critères)
```

Ce qui **est spécifique à chaque outil** :
- **Le déclencheur** : comment on détecte qu'il faut collecter (hook Claude Code, plugin Opencode/Crush, etc.)
- **Les données/formats** : la forme brute du JSONL vs le JSON de `opencode export`

Ce qui **est commun et ne doit pas être dupliqué** :
- **La BDD** : une seule `carbon.db` avec les colonnes `provider`, `client`, `model`, `session_id`, etc. (colonne `client` déjà existante pour identifier la source)
- **Les calculs d'impact** : `EcoLogitsEngine.compute()` fonctionne sur `InferenceEvent` générique
- **La reconnaissance des modèles** : `ModelResolver` fait son lookup sur `provider/model` génériques
- **Les rapports** : `rows_for_report()`, `tokens_by_model()`, `intensity_by_model()` interrogent la même table `events`

---

## Comparaison Claude Code vs Crush/Opencode

| Aspect | Claude Code | Crush/Opencode |
|---|---|---|
| **Stockage** | JSONL ligne par ligne | SQLite (`~/.local/share/.../db`) |
| **Format** | Ligne par ligne | Session globale + messages |
| **Tokens** | `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens` | `input`, `output`, `reasoning`, `cache: {read, write}` |
| **Model** | String simple (ex: `claude-opus-4-8`) | `{ providerID, modelID }` (ex: `omlx/Ornith-1.0-35B-mlx-4bit`) |
| **Timestamps** | ISO 8601 | Unix timestamp ms |
| **Événement fin de session** | `hooks.Stop` (Shell script) | `session.idle` (Plugin TypeScript/JS) |
| **Export** | N/A (lecture directe) | `opencode export <sessionID>` (JSON) |

---

## Stratégie d'intégration : plugin installé à l'installation

**Approche retenue** : un plugin Opencode/Crush est installé automatiquement lors de l'installation d'agent-carbon (comme on installe déjà le hook Claude Code).

### Pipeline complet (sessions futures)

```
Utilisateur lance opencode/crush
         │
         ▼
  Plugin Opencode écoute session.idle
         │
         ▼  (SDK : client.session.get + session.messages)
  Écrit ~/.agent-carbon/crush-exports/<id>.json
         │
         ▼
  agent-carbon ingest
         │
         ▼  (CrushCollector)
  InferenceEvent → carbon.db (colonne client="opencode") → EcoLogits → rapport
```

### Fichier exporté (format `opencode export`)

```json
{
  "info": {
    "id": "sess-abc123",
    "slug": "mon-projet",
    "projectID": "...",
    "directory": "/home/user/project",
    "path": "/home/user/project/session-abc123",
    "title": "Fix bug XYZ",
    "agent": "opencode",
    "model": { "id": "claude-sonnet-4-20250514", "providerID": "anthropic" },
    "version": 1,
    "tokens": { "input": 8427, "output": 287, "reasoning": 0, "cache": { "read": 8020, "write": 7052 } },
    "time": { "created": 1719741600000, "updated": 1719742500000 }
  },
  "messages": [
    {
      "info": {
        "role": "user",
        "time": 1719741600000,
        "agent": "opencode",
        "model": { "id": "claude-sonnet-4-20250514", "providerID": "anthropic" },
        "tokens": { "input": 100, "output": 0, "reasoning": 0, "cache": { "read": 0, "write": 0 } },
        "cost": 0.001,
        "id": "msg-1",
        "sessionID": "sess-abc123"
      },
      "parts": [{ "type": "text", "text": "Hello!" }]
    }
  ]
}
```

### Plugin à installer

**Emplacement** : `~/.config/opencode/plugins/agent-carbon-crush.js`

**Fonctionnalités** :
- Écoute `session.idle` (fin de session) via le système de plugins OpenCode/Anomaly
- Récupère les messages via le SDK (`client.session.messages()`)
- Écrit un fichier JSON dans `~/.agent-carbon/crush-exports/<sessionId>.json`

---

## Backfilling : collecte des sessions EXISTANTES

**Problématique** : comment ingérer les sessions Crush/Opencode qui ont été produites AVANT l'installation d'agent-carbon ?

### Structure de la BDD locale Opencode/CRUSH

La base `~/.local/share/opencode/opencode.db` (ou `~/.local/share/crush/crush.db`) contient :

**Table `session`** :
- `id` : identifiant de session
- `title`, `directory`, `model` (JSON), `tokens_input`, `tokens_output`, `tokens_reasoning`, `tokens_cache_read`, `tokens_cache_write`
- `time_created`, `time_updated` (timestamps Unix ms)

**Table `message`** :
- `id`, `session_id`, `data` (JSON avec `role`, `time`, `agent`, `model`, `tokens`)

### Stratégie de backfilling

Créer un mécanisme de backfilling automatique qui :
1. Détecte la présence de la BDD Opencode/CRUSH locale
2. Lit les sessions et messages existants
3. Génère des `InferenceEvent` avec `client="opencode"` (colonne existante dans carbon.db)
4. Les ingère dans `carbon.db` sans dupliquer les calculs d'impact

### Deux phases de collecte

| Phase | Mécanisme | Objectif |
|---|---|---|
| **Backfilling** (une fois) | Lecture directe de `~/.local/share/opencode/opencode.db` | Ingestion des sessions EXISTANTES avant installation |
| **Plugin** (continu) | Écriture dans `~/.agent-carbon/crush-exports/` | Collecte des sessions FUTURES après installation |

Les deux phases convergent dans la même BDD `carbon.db` avec la colonne `client` qui identifie la source.

---

## Questions en suspens — Réponses validées

1. **Le champ `reasoning` dans les tokens est-il pertinent pour le calcul d'impact ?**  
   → **Non, ignoré en V1.** `InferenceEvent` n'a pas de champ `reasoning_tokens` et `EcoLogitsEngine` ne l'utilise pas.  
   Planifié pour une future extension (Q6+).

2. **Comment mapper `providerID`/`modelID` vers les modèles connus d'EcoLogits ?**  
   → La chaîne de résolution existe déjà dans EcoLogits. Pour les modèles self-hosted (ex: `omlx/Ornith-1.0-35B-mlx-4bit`), le registry est interrogé via `fetch_hf_params()` ou `fetch_moe_params_from_hf()`. Pas de travail supplémentaire nécessaire.

3. **Faut-il un skill dédié `/agent-carbon-crush` ou intégrer dans le existing `agent-carbon-report` ?**  
   → **Intégrer dans le skill existant `agent-carbon-report`.** Pas de skill dédié. Les données Opencode apparaîtront naturellement dans les rapports existants via la colonne `client="opencode"`.

4. **Quand implémenter le backfilling ?**  
   → **À la première exécution de `agent-carbon ingest --source-crush <path>`.** Soit manuellement, soit automatiquement via `install.sh` si la DB locale existe. Le code CLI est déjà en place ; seul le câblage dans l'installateur manque.

---

## Prochaines étapes (validées)

1. **Plugin Opencode installé automatiquement** — déjà implémenté dans le plan (Task 0) :
   - Créer `~/.config/opencode/plugins/agent-carbon-crush.js` qui écoute `session.idle`
   - Écrire les exports de session dans `~/.agent-carbon/crush-exports/<sessionId>.json`

2. **Collecteur Crush (JSON + SQLite)** — déjà implémenté dans le plan (Tasks 1-2) :
   - Module `agent_carbon/collectors/crush.py` (2 modes : exports JSON et backfill SQLite)
   - Testé avec `tests/test_crush_collector.py`

3. **Intégration CLI `--source-crush`** — déjà implémentée dans le plan (Task 3) :
   - CLI `agent-carbon ingest --source-crush <path>` supporte les deux modes
   - Détection automatique par extension `.db`

4. **Intégration dans l'installateur** — à implémenter (Task 4) :
   - Câbler le plugin Opencode dans `install.sh`
   - Exécuter automatiquement le backfill initial si `~/.local/share/opencode/opencode.db` existe
   - Vérifier que le plugin est chargé par Opencode à chaque démarrage

---

## Références

- [Crush GitHub](https://github.com/charmbracelet/crush) (ex-opencode-ai/opencode)
- [Crush Hooks Doc](https://github.com/charmbracelet/crush/blob/main/docs/hooks/README.md)
- [OpenCode Plugins Doc](https://opencode.ai/docs/plugins/)
- [OpenCode SDK Doc](https://opencode.ai/docs/sdk/)
- [Article Dev.to sur les hooks Crush](https://dev.to/einarcesar/does-opencode-support-hooks-a-complete-guide-to-extensibility-k3p)
- Code source existant : `agent_carbon/collectors/claude_code.py` (à utiliser comme référence)
- BDD locale existante : `~/.local/share/opencode/opencode.db`

---

*Spec en cours de brainstorming. En attente de validation utilisateur avant toute implémentation.*
