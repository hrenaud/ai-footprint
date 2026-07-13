# Comparing data across tools

**Goal**: Compare the data available in the JSON/transcripts of each tool
supported by ai-footprint.

**Update**: This document is updated every time a new tool is added.

---

## Legend

| Symbol | Meaning                                   |
| ------ | ----------------------------------------- |
| ✅     | Available in this tool                    |
| ❌     | Not available                             |
| ⚠️     | Partially available (different structure) |

---

## Comparison table

| Field                         | Claude Code (JSONL)            | Opencode (JSON)                    | Pi (JSONL)                                             | Usage in ai-footprint                                  |
| ----------------------------- | ------------------------------ | ---------------------------------- | ------------------------------------------------------ | ------------------------------------------------------ |
| **Identifiers**               |                                |                                    |                                                        |                                                        |
| `sessionId`                   | ✅                             | ✅ `session_id`                    | ✅ header `type:"session"`, `id`                       | Join key with the `sessions` table                     |
| `uuid` / `id`                 | ✅ `msg_id`                    | ✅ `message.id`                    | ✅ `message.id` (entry `type:"message"`)               | Unique key per message                                 |
| **Model**                     |                                |                                    |                                                        |                                                        |
| `model` (string)              | ✅ `"claude-opus-4-8"`         | ⚠️ `{providerID, modelID}`         | ✅ `message.model`                                     | Normalized to `provider` + `model` in `InferenceEvent` |
| `provider`                    | ❌ (inferred from `model`)     | ✅ `model.providerID`              | ✅ `message.provider`                                  | Allows the EcoLogits lookup                            |
| **Tokens**                    |                                |                                    |                                                        |                                                        |
| `input_tokens`                | ✅                             | ✅ `tokens.input`                  | ✅ `message.usage.input`                               | Impact calculation                                     |
| `output_tokens`               | ✅                             | ✅ `tokens.output`                 | ✅ `message.usage.output`                              | Impact calculation                                     |
| `cache_creation_input_tokens` | ✅                             | ⚠️ `tokens.cache.write`            | ✅ `message.usage.cacheWrite`                          | Impact calculation (cache)                             |
| `cache_read_input_tokens`     | ✅                             | ⚠️ `tokens.cache.read`             | ✅ `message.usage.cacheRead`                           | Impact calculation (cache)                             |
| `reasoning_tokens`            | ❌                             | ✅ `tokens.reasoning`              | ❌                                                     | To be validated with EcoLogits                         |
| **Time**                      |                                |                                    |                                                        |                                                        |
| `timestamp` (ISO 8601)        | ✅                             | ⚠️ Unix timestamp ms               | ✅ native ISO 8601                                     | Converted to ISO 8601 UTC                              |
| `active_seconds` (delta)      | ✅ Computed                    | ✅ `time.completed - time.created` | ✅ Computed (delta between consecutive timestamps)     | Active time measurement                                |
| **Cost**                      |                                |                                    |                                                        |                                                        |
| `cost` (USD)                  | ❌ (not read by the collector) | ✅ `cost` (DB + exports)           | ⚠️ `message.usage.cost.total` (present but not stored) | **Not stored** — no `cost` field in `InferenceEvent`   |
| `latency` (ms)                | ❌ (not read by the collector) | ❌                                 | ❌                                                     | Not currently used                                     |
| **Session metadata**          |                                |                                    |                                                        |                                                        |
| `title`                       | ❌                             | ✅ `session.title`                 | ❌                                                     | **Not stored** (note: to be reconsidered)              |
| `directory`                   | ✅ `cwd`                       | ✅ `session.directory`             | ✅ `session.cwd`                                       | Used for `project` (basename)                          |
| `slug`                        | ❌                             | ✅ `session.slug`                  | ❌                                                     | **Not stored** (note: to be reconsidered)              |
| `path`                        | ❌                             | ✅ `session.path`                  | ❌                                                     | **Not stored** (note: to be reconsidered)              |
| **Status**                    |                                |                                    |                                                        |                                                        |
| `role` (user/assistant)       | ✅                             | ✅                                 | ✅ `message.role`                                      | Filtering (only assistant messages count)              |
| `error`                       | ❌                             | ✅ `error.name`, `error.data`      | ❌                                                     | **Not stored** — no `error` field in `InferenceEvent`  |
| `archived`                    | ❌                             | ✅ `time_archived`                 | ❌                                                     | Not currently used                                     |
| **Collection**                |                                |                                    |                                                        |                                                        |
| Storage format                | JSONL (line by line)           | SQLite (local DB)                  | JSONL (line by line)                                   | Tool-specific collectors                               |
| Trigger                       | `hooks.Stop` (end of session)  | `session.idle` (plugin)            | `session_shutdown` (extension)                         | Automatic installation                                 |
| Backfilling                   | Direct JSONL read              | Direct SQLite read                 | Direct JSONL read                                      | Tool-specific backfilling scripts                      |

---

## Details per tool

### Claude Code

**Available sources**:

1. **Session transcripts**: `~/.claude/projects/**/*.jsonl` — the only
   source actually read by `ClaudeCodeCollector` (glob + parsing of all
   `**/*.jsonl` files).

**Structure of an event (transcript)**:

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

**Collector**: `ClaudeCodeCollector` (direct JSONL read)

---

### Opencode

**Available sources**:

1. **Local DB**: `~/.local/share/opencode/opencode.db` (SQLite)
2. **Plugin exports**: `~/.ai-footprint/crush-exports/<sessionId>.json`
3. **SSE SDK**: `event.subscribe()` (real time)

**Structure of a session (`session` table)**:

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

**Structure of a message (`message` table)**:

```json
{
  "id": "msg_edf05b24e001gD1yQMa8Rqwfpa",
  "session_id": "ses_120fa4dc7ffeSg6YofUeAPBX1P",
  "data": "{\"role\":\"assistant\",\"time\":{\"created\":1781858153054,\"completed\":1781858153428},\"model\":{\"providerID\":\"myprovider\",\"modelID\":\"Qwen3.6-35B-A3B-4bit\"},\"tokens\":{\"input\":0,\"output\":0,\"reasoning\":0,\"cache\":{\"read\":0,\"write\":0}},\"cost\":0}"
}
```

**Structure of a plugin export**:

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

**Collector**: `CrushCollector` (DB backfilling + plugin export reading)

---

### Pi

**Available sources**:

1. **Session transcripts**: `~/.pi/agent/sessions/--<cwd>--/<timestamp>_<uuid>.jsonl`

**Structure of a session file** (one `type:"session"` header entry, then
`type:"message"` entries):

```json
{"type":"session","id":"sess-A","timestamp":"2026-06-27T10:00:00.000Z","cwd":"/Users/me/DEV/projA"}
{"type":"message","id":"u1","timestamp":"2026-06-27T10:08:45.619Z","message":{"role":"assistant","provider":"anthropic","model":"claude-opus-4-8","usage":{"input":8427,"output":287,"cacheRead":8020,"cacheWrite":7052,"totalTokens":15786,"cost":{"total":0}}}}
```

**Collector**: `PiCollector` (direct JSONL read, root = directory or single
file)

---

## Notes for future tools

When a new tool is added, update:

1. This document (comparison table)
2. The corresponding collector in `ai_footprint/collectors/`
3. The tests in `tests/test_<tool>_collector.py`

**Required fields to map into `InferenceEvent`**:

- `provider` (string)
- `model` (string)
- `input_tokens` (int)
- `output_tokens` (int)
- `cache_creation_tokens` (int)
- `cache_read_tokens` (int)
- `timestamp` (ISO 8601 UTC)
- `project` (string, basename of the directory)
- `session_id` (string)
- `msg_id` (string)

**Optional fields already mapped in `InferenceEvent`**:

- `active_seconds` (float)
- `client` (string, identifies the tool)

**Fields not yet mapped** (present in at least one tool, absent from
`InferenceEvent` — to be added if a product need arises):

- `reasoning_tokens` (int)
- `cost` (float, USD)
- `error` (string)

---

_Document created on 2026-06-30, updated on 2026-07-13. To be updated with
each new tool added._
