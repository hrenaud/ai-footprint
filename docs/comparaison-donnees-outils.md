# Comparaison des données par outil

**Objectif** : Comparer les données disponibles dans les JSON/transcripts de chaque outil supporté par ai-footprint.

**Mise à jour** : Ce document est mis à jour à chaque nouvel outil ajouté.

---

## Légende

| Symbole | Signification                                   |
| ------- | ----------------------------------------------- |
| ✅      | Disponible dans cet outil                       |
| ❌      | Non disponible                                  |
| ⚠️      | Partiellement disponible (structure différente) |

---

## Tableau comparatif

| Champ                         | Claude Code (JSONL)           | Opencode (JSON)                    | Pi (JSONL)                                              | Usage dans ai-footprint                                     |
| ----------------------------- | ----------------------------- | ---------------------------------- | ------------------------------------------------------- | ----------------------------------------------------------- |
| **Identifiants**              |                               |                                    |                                                         |                                                             |
| `sessionId`                   | ✅                            | ✅ `session_id`                    | ✅ header `type:"session"`, `id`                        | Clé de jointure avec `sessions` table                       |
| `uuid` / `id`                 | ✅ `msg_id`                   | ✅ `message.id`                    | ✅ `message.id` (entrée `type:"message"`)               | Clé unique par message                                      |
| **Modèle**                    |                               |                                    |                                                         |                                                             |
| `model` (string)              | ✅ `"claude-opus-4-8"`        | ⚠️ `{providerID, modelID}`         | ✅ `message.model`                                      | Normalisé en `provider` + `model` dans `InferenceEvent`     |
| `provider`                    | ❌ (déduit de `model`)        | ✅ `model.providerID`              | ✅ `message.provider`                                   | Permet le lookup EcoLogits                                  |
| **Tokens**                    |                               |                                    |                                                         |                                                             |
| `input_tokens`                | ✅                            | ✅ `tokens.input`                  | ✅ `message.usage.input`                                | Calcul d'impact                                             |
| `output_tokens`               | ✅                            | ✅ `tokens.output`                 | ✅ `message.usage.output`                               | Calcul d'impact                                             |
| `cache_creation_input_tokens` | ✅                            | ⚠️ `tokens.cache.write`            | ✅ `message.usage.cacheWrite`                           | Calcul d'impact (cache)                                     |
| `cache_read_input_tokens`     | ✅                            | ⚠️ `tokens.cache.read`             | ✅ `message.usage.cacheRead`                            | Calcul d'impact (cache)                                     |
| `reasoning_tokens`            | ❌                            | ✅ `tokens.reasoning`              | ❌                                                      | À valider avec EcoLogits                                    |
| **Temps**                     |                               |                                    |                                                         |                                                             |
| `timestamp` (ISO 8601)        | ✅                            | ⚠️ Unix timestamp ms               | ✅ ISO 8601 natif                                       | Converti en ISO 8601 UTC                                    |
| `active_seconds` (delta)      | ✅ Calculé                    | ✅ `time.completed - time.created` | ✅ Calculé (delta entre timestamps successifs)          | Mesure du temps actif                                       |
| **Coût**                      |                               |                                    |                                                         |                                                             |
| `cost` (USD)                  | ❌ (non lu par le collecteur) | ✅ `cost` (BD + exports)           | ⚠️ `message.usage.cost.total` (présent mais non stocké) | **Non stocké** — pas de champ `cost` dans `InferenceEvent`  |
| `latency` (ms)                | ❌ (non lu par le collecteur) | ❌                                 | ❌                                                      | Non exploité actuellement                                   |
| **Métadonnées session**       |                               |                                    |                                                         |                                                             |
| `title`                       | ❌                            | ✅ `session.title`                 | ❌                                                      | **Non stocké** (note : à risquer)                           |
| `directory`                   | ✅ `cwd`                      | ✅ `session.directory`             | ✅ `session.cwd`                                        | Utilisé pour `project` (basename)                           |
| `slug`                        | ❌                            | ✅ `session.slug`                  | ❌                                                      | **Non stocké** (note : à risquer)                           |
| `path`                        | ❌                            | ✅ `session.path`                  | ❌                                                      | **Non stocké** (note : à risquer)                           |
| **Statut**                    |                               |                                    |                                                         |                                                             |
| `role` (user/assistant)       | ✅                            | ✅                                 | ✅ `message.role`                                       | Filtrage (seuls les assistant comptent)                     |
| `error`                       | ❌                            | ✅ `error.name`, `error.data`      | ❌                                                      | **Non stocké** — pas de champ `error` dans `InferenceEvent` |
| `archived`                    | ❌                            | ✅ `time_archived`                 | ❌                                                      | Non exploité actuellement                                   |
| **Collecte**                  |                               |                                    |                                                         |                                                             |
| Format de stockage            | JSONL (ligne par ligne)       | SQLite (BDD locale)                | JSONL (ligne par ligne)                                 | Collecteurs spécifiques par outil                           |
| Déclencheur                   | `hooks.Stop` (fin de session) | `session.idle` (plugin)            | `session_shutdown` (extension)                          | Installation automatique                                    |
| Backfilling                   | Lecture directe JSONL         | Lecture directe SQLite             | Lecture directe JSONL                                   | Scripts de backfilling spécifiques                          |

---

## Détails par outil

### Claude Code

**Sources disponibles** :

1. **Transcripts de session** : `~/.claude/projects/**/*.jsonl` — seule source
   effectivement lue par `ClaudeCodeCollector` (glob + parsing de tous les
   `**/*.jsonl`).

**Structure d'un event (transcript)** :

```json
{
  "type": "assistant",
  "message": {
    "model": "claude-opus-4-8",
    "usage": {
      "input_tokens": 8427,
      "output_tokens": 287,
      "cache_creation_input_tokens": 7052,
      "cache_read_input_tokens": 8020
    }
  },
  "sessionId": "sess-A",
  "uuid": "u1",
  "cwd": "/Users/me/DEV/projA",
  "timestamp": "2026-06-27T10:08:45.619Z"
}
```

**Collecteur** : `ClaudeCodeCollector` (lecture directe JSONL)

---

### Opencode

**Sources disponibles** :

1. **BDD locale** : `~/.local/share/opencode/opencode.db` (SQLite)
2. **Exports plugin** : `~/.ai-footprint/crush-exports/<sessionId>.json`
3. **SDK SSE** : `event.subscribe()` (temps réel)

**Structure d'une session (table `session`)** :

```json
{
  "id": "ses_120fa4dc7ffeSg6YofUeAPBX1P",
  "title": "New session - 2026-06-19T08:35:53.016Z",
  "directory": "/Users/renaudheluin/.agents",
  "model": "{\"id\":\"Qwen3.6-35B-A3B-4bit\",\"providerID\":\"myprovider\"}",
  "tokens_input": 145920,
  "tokens_output": 11950,
  "tokens_reasoning": 0,
  "tokens_cache_read": 0,
  "tokens_cache_write": 0,
  "time_created": 1781858206763,
  "time_updated": 1781858206763
}
```

**Structure d'un message (table `message`)** :

```json
{
  "id": "msg_edf05b24e001gD1yQMa8Rqwfpa",
  "session_id": "ses_120fa4dc7ffeSg6YofUeAPBX1P",
  "data": "{\"role\":\"assistant\",\"time\":{\"created\":1781858153054,\"completed\":1781858153428},\"model\":{\"providerID\":\"myprovider\",\"modelID\":\"Qwen3.6-35B-A3B-4bit\"},\"tokens\":{\"input\":0,\"output\":0,\"reasoning\":0,\"cache\":{\"read\":0,\"write\":0}},\"cost\":0}"
}
```

**Structure d'un export (plugin)** :

```json
{
  "info": {
    "id": "sess-abc123",
    "slug": "mon-projet",
    "directory": "/home/user/project",
    "model": { "id": "claude-sonnet-4-20250514", "providerID": "anthropic" },
    "tokens": {
      "input": 8427,
      "output": 287,
      "reasoning": 0,
      "cache": { "read": 8020, "write": 7052 }
    },
    "time": { "created": 1719741600000, "updated": 1719742500000 }
  },
  "messages": [
    {
      "info": {
        "id": "msg-1",
        "role": "assistant",
        "time": { "created": 1719741700000, "completed": 1719741800000 },
        "model": {
          "id": "claude-sonnet-4-20250514",
          "providerID": "anthropic"
        },
        "tokens": {
          "input": 8427,
          "output": 287,
          "reasoning": 0,
          "cache": { "read": 8020, "write": 7052 }
        },
        "cost": 0.00123
      }
    }
  ]
}
```

**Collecteur** : `CrushCollector` (backfilling BDD + lecture exports plugin)

---

### Pi

**Sources disponibles** :

1. **Transcripts de session** : `~/.pi/agent/sessions/--<cwd>--/<timestamp>_<uuid>.jsonl`

**Structure d'un fichier de session** (une entrée d'en-tête `type:"session"` puis des entrées `type:"message"`) :

```json
{"type":"session","id":"sess-A","timestamp":"2026-06-27T10:00:00.000Z","cwd":"/Users/me/DEV/projA"}
{"type":"message","id":"u1","timestamp":"2026-06-27T10:08:45.619Z","message":{"role":"assistant","provider":"anthropic","model":"claude-opus-4-8","usage":{"input":8427,"output":287,"cacheRead":8020,"cacheWrite":7052,"totalTokens":15786,"cost":{"total":0}}}}
```

**Collecteur** : `PiCollector` (lecture directe JSONL, root = répertoire ou fichier unique)

---

## Notes pour les futurs outils

Quand un nouvel outil est ajouté, mettre à jour :

1. Ce document (tableau comparatif)
2. Le collecteur correspondant dans `ai_footprint/collectors/`
3. Les tests dans `tests/test_<outil>_collector.py`

**Champs obligatoires à mapper dans `InferenceEvent`** :

- `provider` (string)
- `model` (string)
- `input_tokens` (int)
- `output_tokens` (int)
- `cache_creation_tokens` (int)
- `cache_read_tokens` (int)
- `timestamp` (ISO 8601 UTC)
- `project` (string, basename du directory)
- `session_id` (string)
- `msg_id` (string)

**Champs optionnels déjà mappés dans `InferenceEvent`** :

- `active_seconds` (float)
- `client` (string, identifie l'outil)

**Champs pas encore mappés** (présents chez au moins un outil, absents de
`InferenceEvent` — à ajouter si un besoin produit apparaît) :

- `reasoning_tokens` (int)
- `cost` (float, USD)
- `error` (string)

---

_Document créé le 2026-06-30, mis à jour le 2026-07-13. À mettre à jour à chaque nouvel outil ajouté._
