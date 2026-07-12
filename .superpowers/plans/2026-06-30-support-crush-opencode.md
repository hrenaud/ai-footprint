# Support Opencode/Crush Plan d'Implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter le support Opencode/Crush à agent-carbon avec ingestion automatique (plugin + backfill), conforme au spec `specs/2026-06-30-support-crush-opencode.md`.

**Architecture :** Pipeline complet :
1. **Plugin Opencode** installé à l'installation → écrit les exports JSON dans `~/.agent-carbon/crush-exports/`
2. **Backfill SQLite** au premier lancement → lit `~/.local/share/opencode/opencode.db`
3. **CrushCollector** (2 modes) → `InferenceEvent` → `carbon.db` (colonne `client="opencode"`)
4. **CLI `--source-crush`** → agrège les deux sources dans un seul `ingest`

**Tech Stack:** Python 3.12+, SQLite3, argparse. Zéro nouvelle dépendance.

## Global Constraints

- Zéro nouvelle dépendance externe (aucun `pip install` additionnel).
- `InferenceEvent` est un `dataclass(frozen=True)` : si un champ manque, retourner 0/vide, NE PAS CRÉER d'exception.
- `client = "opencode"` (la colonne `client` existe déjà dans `events`).
- Le collecteur ne produit QUE des messages `role == "assistant"` (comme ClaudeCodeCollector).
- Le temps actif est tronqué à 300 s (`_ACTIVE_CAP_SECONDS`) : delta > 300 → 0 (les hits lents ne comptent pas).
- Tests TDD : écrire le test AVANT le code. Chaque étape teste un comportement atomique.
- DRY : les helpers primitifs (`_project`, `_active`, `_ts`) peuvent être importés de `claude_code`.

---

### Task 0 : Installation du plugin Opencode/Crush

**Files à créer :**

- `~/.config/opencode/plugins/agent-carbon-crush.js` (ou via l'installateur)

**Rôle du plugin :**

Le plugin écoute `session.idle` (fin de session) via le SDK Opencode et écrit un fichier JSON export dans `~/.agent-carbon/crush-exports/<sessionId>.json`.

**Format du fichier exporté** (conforme au spec) :

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

**Installation :** L'installateur d'agent-carbon doit créer ce fichier à l'emplacement `~/.config/opencode/plugins/agent-carbon-crush.js` et vérifier qu'il est chargé par Opencode.

**Note :** Les champs `directory`, `slug`, `path`, `title`, `reasoning`, `cost` sont ignorés dans le mapping (voir Task 1 mapping).

---

### Task 1 : Collecteur Crush (exports JSON)

**Files :**

- Create : `agent_carbon/collectors/crush.py`
- Test : `tests/test_crush_collector.py`
- Fixture : `tests/fixtures/crush-export.json`

**Interfaces :**

- Consomme : `Collector.collect() -> Iterator[InferenceEvent]` (de `base.py`).
- Consomme : `ClaudeCodeCollector._project_from_cwd(cwd: str) -> str` (helper).
- Produit : une instance `CrushCollector(root: str)` dont `collect()` étend `Collector` et produit `InferenceEvent` à partir de JSON brut (format `opencode export`).

**Mapping Crush → InferenceEvent (format export) :**

| Champ crush (JSON export) | Champ InferenceEvent | Source JSON export |
|---|---|---|
| `info.model.providerID` | `provider` | `obj["info"]["model"]["providerID"]` |
| `info.model.modelID` | `model` | `obj["info"]["model"]["modelID"]` |
| `info.tokens.input` | `input_tokens` | `obj["info"]["tokens"]["input"]` |
| `info.tokens.output` | `output_tokens` | `obj["info"]["tokens"]["output"]` |
| `info.tokens.cache.read` | `cache_read_tokens` | `obj["info"]["tokens"]["cache"]["read"]` |
| `info.tokens.cache.write` | `cache_creation_tokens` | `obj["info"]["tokens"]["cache"]["write"]` |
| `info.time.created` (ms) | `timestamp` (ISO 8601) | `obj["info"]["time"]["created"]` |
| `info.directory` | `project` | basename `obj["info"]["directory"]` |
| `info.id` | `session_id` | `obj["info"]["id"]` |
| `msg.info.id` | `msg_id` | `msg["info"]["id"]` |
| `msg.info.sessionID` | `session_id` (fallback) | `msg["info"]["sessionID"]` |
| `time.completed - created` (ms) | `active_seconds` | delta (s) |
| *(fixe)* | `client` | `"opencode"` |

**Notes :**
- Pas de champ `reasoning_tokens` dans InferenceEvent (ignorer TOUJOURS, NE PAS lever d'exception).
- Les champs `directory`, `slug`, `path`, `title`, `reasoning`, `cost` (si présents) sont ignorés (non stockés).
- Le fichier peut avoir la structure `msg.data` ou `msg.info` (les deux formats sont acceptés).

- [ ] **Étape 1 : Écrire le test d'export JSON seul**

```python
# tests/test_crush_collector.py

from pathlib import Path

from agent_carbon.collectors.crush import CrushCollector
from agent_carbon.models import InferenceEvent

CRUSH_EXPORT = Path(__file__).parent / "fixtures/crush-export.json"


def test_parses_only_assistant_messages():
    """Seuls les messages assistant sont produits (user ignorés)."""
    events = list(CrushCollector(str(CRUSH_EXPORT)).collect())
    assert len(events) == 2  # 2 messages assistant dans le fixture


def test_event_fields_mapped_from_crush_export_structure():
    """Les champs InferenceEvent sont correctement mappés depuis le JSON export."""
    events = {e.msg_id: e for e in CrushCollector(str(CRUSH_EXPORT)).collect()}
    e = events["msg-1"]
    assert isinstance(e, InferenceEvent)
    assert e.provider == "anthropic"
    assert e.model == "claude-sonnet"
    assert e.input_tokens == 8427
    assert e.output_tokens == 287
    assert e.cache_creation_tokens == 7052
    assert e.cache_read_tokens == 8020
    assert e.project == "projA"  # basename de directory
    assert e.session_id == "sess-GH123"
    assert e.client == "opencode"
```

- [ ] **Étape 2 : Écrire le test des messages utilisateur ignorés + fichiers vides**

```python
def test_ignores_user_messages_and_empty_files():
    """Les messages user ne sont PAS produits. Les fichiers vides ne produisent rien."""
    fd, vide = tempfile.mkstemp(suffix=".json")
    os.write(fd, b"")
    os.close(fd)

    events = list(CrushCollector(vide).collect())
    assert events == []  # fichier vide → 0 events
    os.unlink(vide)

    fd, malformé = tempfile.mkstemp(suffix=".json")
    os.write(fd, b"not json {{{")
    os.close(fd)

    events = list(CrushCollector(malformé).collect())
    assert events == []  # JSON invalide → 0 events (ignore silencieusement)
    os.unlink(malformé)
```

- [ ] **Étape 3 : Écrire les tests d'edge cases (delta > 300s, champs manquants, clés `data`/`info`)**

```python
def test_active_seconds_capped_at_300():
    """Les deltas > 300s sont tronqués à 0 (pas de hits lents)."""
    # ... fixture avec time.created=0, time.completed=400000 → active_seconds=0.0

def test_missing_optional_fields_use_defaults():
    """Les champs optionnels absents utilisent 0 ou ''."""
    # ... fixture sans tokens/model/time → valeurs par défaut

def test_collect_from_directory_recursive():
    """Le collecteur trouve les exports JSON récursivement dans un répertoire."""
    # ... créér des fichiers dans sous-dossiers, vérifier qu'ils sont trouvés
```

- [ ] **Étape 4 : Implémenter `CrushCollector` (mode exports JSON)**

```python
import glob
import json
import os
from collections.abc import Iterator
from datetime import datetime, timezone

from agent_carbon.collectors.base import Collector
from agent_carbon.collectors.claude_code import (
    _project_from_cwd,
    _ACTIVE_CAP_SECONDS,
)
from agent_carbon.models import InferenceEvent


def _parse_ts_utc_ms(ms: int | float | None) -> str | None:
    """Convertit un timestamp Unix en ms en ISO 8601 UTC."""
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).isoformat()


def _safe_int(value: int | float | None) -> int:
    """Convertit une valeur en int, avec fallback 0 si None ou absente."""
    if value is None:
        return 0
    return int(value)


class CrushCollector(Collector):
    """Collecteur des exportations JSON d'Opencode/Crush (mode export).

    Lit les fichiers `*.json` dans `root` (format `opencode export`).
    """

    provider: str = ""  # Chaque event porte son propre provider
    client: str = "opencode"

    def __init__(self, root: str):
        self.root: str = os.path.expanduser(root)

    def collect(self) -> Iterator[InferenceEvent]:
        # `root` peut être un fichier unique (export d'une session) ou un répertoire
        # (tous les exports d'un dossier).
        if os.path.isfile(self.root):
            yield from self._parse_export(self.root)
            return

        pattern = os.path.join(self.root, "**", "*.json")
        for path in glob.glob(pattern, recursive=True):
            yield from self._parse_export(path)

    def _parse_export(self, path: str) -> Iterator[InferenceEvent]:
        """Parse un export JSON d'Opencode/Crash en InferenceEvent.
        Seuls les messages 'assistant' sont produits.
        """
        with open(path, encoding="utf-8") as fh:
            try:
                obj = json.load(fh)
            except (json.JSONDecodeError, OSError):
                return

        messages = obj.get("messages")
        if not isinstance(messages, list):
            return

        for msg in messages:
            info = msg.get("data") or msg.get("info")
            if not isinstance(info, dict):
                continue

            if info.get("role") != "assistant":
                continue

            # Modèle avec provider (de info.msg.info.model ou info.msg.info)
            raw_model = info.get("model") or {}
            provider = raw_model.get("providerID") or ""
            model = raw_model.get("modelID") or raw_model.get("id") or ""

            # Tokens (de info.msg.info.tokens ou info.msg.info)
            raw_tokens = info.get("tokens") or {}
            input_tokens = _safe_int(raw_tokens.get("input"))
            output_tokens = _safe_int(raw_tokens.get("output"))
            cache_read_tokens = _safe_int(raw_tokens.get("cache", {}).get("read"))
            cache_creation_tokens = _safe_int(raw_tokens.get("cache", {}).get("write"))

            # Timestamp (Unix ms → ISO 8601)
            ts_ms = info.get("time", {}).get("created")
            timestamp = _parse_ts_utc_ms(ts_ms)

            # Session (info.msg.info.sessionID ou info.msg.info.id)
            session_id = info.get("sessionID") or info.get("id") or ""
            # Fallback : info.session_id ou info.ID
            if not session_id:
                session_id = info.get("session_id") or info.get("ID") or ""
            # Fallback final : obj.info.id
            if not session_id:
                session_id = obj.get("info", {}).get("id", "")

            # Project (basename du directory)
            directory = info.get("directory") or obj.get("directory") or ""
            project = _project_from_cwd(directory)

            # Msg ID
            msg_id = info.get("id") or ""

            # Active secondes (delta)
            created_ms = info.get("time", {}).get("created")
            completed_ms = info.get("time", {}).get("completed")
            active_seconds = self._calc_active_seconds(created_ms, completed_ms)

            yield InferenceEvent(
                provider=provider,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_tokens=cache_read_tokens,
                cache_creation_tokens=cache_creation_tokens,
                timestamp=timestamp or "",
                project=project,
                session_id=session_id,
                msg_id=msg_id,
                active_seconds=active_seconds,
                client=self.client,
            )

    @staticmethod
    def _calc_active_seconds(created_ms: int | float | None, completed_ms: int | float | None) -> float:
        """Calcule le temps actif entre created et completed, tronqué à _ACTIVE_CAP_SECONDS."""
        if created_ms is None or completed_ms is None:
            return 0.0
        delta_s = (completed_ms - created_ms) / 1000.0
        if 0 < delta_s <= _ACTIVE_CAP_SECONDS:
            return delta_s
        return 0.0
```

- [ ] **Étape 5 : Run des tests unitaires**

```bash
$ pytest tests/test_crush_collector.py::test_parses_only_assistant_messages -v
```

Attendu : FAIL → `No module named 'agent_carbon.collectors.crush'`.

- [ ] **Étape 6 : Écrire l'implémentation (Task 4)**

Voir code ci-dessus.

- [ ] **Étape 7 : Run des tests unitaires**

```bash
$ pytest tests/test_crush_collector.py -v
```

Attendu : PASS → Tous les tests doivent passer.

- [ ] **Étape 8 : Commit**

```bash
$ git add agent_carbon/collectors/crush.py tests/test_crush_collector.py tests/fixtures/crush-export.json
$ git commit -m "feat: add CrushCollector for Opencode export JSON"
```

---

### Task 2 : Collecteur Crush (backfill SQLite)

**Files :**

- Modify : `agent_carbon/collectors/crush.py` (ajouter mode backfill)
- Test : `tests/test_crush_collector.py` (ajouté si backfill)
- Existing DB : `~/.local/share/opencode/opencode.db` (lecture seule)

**Interfaces :**

- Consomme : mêmes APIs que Task 1 (`Collector`, `InferenceEvent`).
- Produit : une instance `CrushCollector(backfill_db_path=...)` qui lit les sessions et messages directement de SQLite.

**Structure de la base Opencode (pour le backfill) :**

**Table `session`** :
- `id` : identifiant de session
- `title`, `directory`, `model` (JSON), `tokens_input`, `tokens_output`, `tokens_reasoning`, `tokens_cache_read`, `tokens_cache_write`
- `time_created`, `time_updated` (timestamps Unix ms)

**Table `message`** :
- `id`, `session_id`, `data` (JSON string avec `role`, `time`, `agent`, `model`, `tokens`)

**Mapping SQLite → InferenceEvent :**

| Champ crush DB | Champ InferenceEvent | Source |
|---|---|---|
| `session.id` | `session_id` | `session["id"]` |
| `session.directory` | `project` | basename `session["directory"]` |
| `session.model` (JSON) → `providerID` | `provider` | `json.loads(session["model"])["providerID"]` |
| `session.model` (JSON) → `id` | `model` | `json.loads(session["model"])["id"]` |
| `session.tokens_input` | `input_tokens` | `session["tokens_input"]` |
| `session.tokens_output` | `output_tokens` | `session["tokens_output"]` |
| `session.tokens_cache_read` | `cache_read_tokens` | `session["tokens_cache_read"]` |
| `session.tokens_cache_write` | `cache_creation_tokens` | `session["tokens_cache_write"]` |
| `session.time_created` (ms) | `timestamp` (ISO 8601) | `session["time_created"]` |
| `message.id` | `msg_id` | `message["id"]` |
| `message.session_id` | `session_id` (info) | `message["session_id"]` |
| `message.data` (JSON) → `role` | (ignore if != "assistant") | `json.loads(message["data"])["role"]` |
| `message.data` (JSON) → `model` | `provider`, `model` (fallback) | `json.loads(message["data"])["model"]` |
| `message.data` (JSON) → `tokens` | `input_tokens`, etc. (fallback) | `json.loads(message["data"])["tokens"]` |
| `message.data` (JSON) → `time.created` | `active_seconds` | delta depuis message précédent |

**Stratégie :** Pour chaque session, lire la table `session` (qui a `id`, `title`, `directory`, `model` (JSON), `tokens_input`, `tokens_output`, `tokens_cache_read`, `tokens_cache_write`, `time_created`, `time_updated`), puis pour chaque message de la table `message` associé à cette session, lire le JSON de la colonne `data` et vérifier le rôle.

- [ ] **Étape 1 : Écrire le test de backfill SQLite**

```python
def test_backfill_from_sqlite():
    """Le mode backfill lit les sessions et messages depuis une DB SQLite."""
    tmp_dir = Path(tempfile.mkdtemp())
    db_path = str(tmp_dir / "opencode.db")

    # Créer une DB de test avec la structure exacte de la BDD Opencode
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE session (
            id TEXT PRIMARY KEY,
            title TEXT,
            directory TEXT,
            model TEXT,
            tokens_input INTEGER,
            tokens_output INTEGER,
            tokens_cache_read INTEGER,
            tokens_cache_write INTEGER,
            tokens_reasoning INTEGER,
            time_created INTEGER,
            time_updated INTEGER
        );
        CREATE TABLE message (
            id TEXT,
            session_id TEXT,
            data TEXT
        );
    """)

    # Insérer une session
    conn.execute(
        "INSERT INTO session (id, title, directory, model, "
        "tokens_input, tokens_output, tokens_cache_read, tokens_cache_write, "
        "tokens_reasoning, time_created, time_updated) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "sess-GH123", "Fix bug XYZ", "/Users/me/DEV/projA",
            json.dumps({"id": "claude-sonnet", "providerID": "anthropic"}),
            8427, 287, 8020, 7052, 0,
            1719741600000, 1719742000000,
        ),
    )

    # Insérer un message assistant
    conn.execute(
        "INSERT INTO message (id, session_id, data) VALUES (?, ?, ?)",
        (
            "msg-1", "sess-GH123",
            json.dumps({
                "role": "assistant",
                "time": {"created": 1719741600000, "completed": 1719741630000},
                "model": {"id": "claude-sonnet", "providerID": "anthropic"},
                "tokens": {"input": 8427, "output": 287, "cache": {"read": 8020, "write": 7052}},
            }),
        ),
    )
    conn.commit()
    conn.close()

    # Test du collecteur
    events = list(CrushCollector(backfill_db_path=db_path).collect())
    assert len(events) == 1
    e = events[0]
    assert isinstance(e, InferenceEvent)
    assert e.provider == "anthropic"
    assert e.model == "claude-sonnet"
    assert e.input_tokens == 8427
    assert e.output_tokens == 287
    assert e.cache_creation_tokens == 7052
    assert e.cache_read_tokens == 8020
    assert e.session_id == "sess-GH123"
    assert e.project == "projA"
    assert e.client == "opencode"
```

- [ ] **Étape 2 : Écrire les tests supplémentaires (user ignorés, DB manquante, pas de messages, delta > 300s)**

```python
def test_backfill_ignores_user_messages():
    """Les messages user dans la DB ne sont pas produits."""
    # ... fixture avec 1 user + 1 assistant → 1 event

def test_backfill_missing_db_returns_empty():
    """Si la DB n'existe pas, le collecteur retourne []"""
    events = list(CrushCollector(backfill_db_path="/non/existent/path.db").collect())
    assert events == []

def test_backfill_no_messages_returns_empty():
    """Une session sans messages ne produit rien."""
    # ... fixture avec session sans messages

def test_backfill_active_seconds_capped():
    """Les deltas > 300s sont tronqués à 0 dans le mode backfill."""
    # ... fixture avec time.completed - time_created > 300000
```

- [ ] **Étape 3 : Implémenter le mode backfill dans `CrushCollector`**

Modifier `CrushCollector.__init__` pour accepter `backfill_db_path=None` et modifier `collect()` pour dispatcher selon le mode.

Ajouter une méthode `_backfill_from_db(self, db_path: str) -> Iterator[InferenceEvent]` qui :
1. Se connecte à la DB SQLite
2. Lit toutes les sessions (`SELECT * FROM session`)
3. Pour chaque session, extrait `id`, `directory`, `model` (JSON), `tokens_input`, `tokens_output`, `tokens_cache_read`, `tokens_cache_write`, `time_created`
4. Pour chaque message associé (`SELECT * FROM message WHERE session_id = ?`), extrait le JSON de la colonne `data`, vérifie le rôle, et extrait `id`, `session_id`, `model`, `tokens`, `time`

- [ ] **Étape 4 : Run des tests unitaires**

```bash
$ pytest tests/test_crush_collector.py -v
```

Attendu : PASS → Tous les tests (JSON + SQLite) doivent passer.

- [ ] **Étape 5 : Commit**

```bash
$ git add agent_carbon/collectors/crush.py
$ git commit -m "feat: add CrushCollector SQLite backfill mode"
```

---

### Task 3 : Intégration CLI — `agent-carbon ingest --source-crush`

**Files :**

- Modify : `agent_carbon/__main__.py` (ajouter l'argument `--source-crush`)

**Interfaces :**

- Consomme : `ClaudeCodeCollector` (déjà importé), `CrushCollector` (nouveau).
- Produit : `parser.add_argument("--source-crush", default=None)` dans `p_ing`

**Modification de `__main__.py` :**

```python
# 1. Ajouter l'import
from agent_carbon.collectors.crush import CrushCollector

# 2. Ajouter l'argument --source-crush dans le parser ingest
p_ing = sub.add_parser("ingest", help="parser les transcripts et calculer l'impact")
p_ing.add_argument("--source", default=_DEFAULT_SOURCE)
p_ing.add_argument("--source-crush", default=None,
                   help="directory d'exports JSON Opencode/Crash, ou chemin vers opencode.db (backfill SQLite)")
p_ing.add_argument("--db", default=_DEFAULT_DB)

# 3. Modifier le handler ingest
if args.cmd == "ingest":
    store = _store(args.db)
    if args.source_crush:
        # Détection du mode : si le chemin pointe vers une DB SQLite, backfill.
        if args.source_crush.endswith(".db"):
            events = CrushCollector(backfill_db_path=args.source_crush).collect()
        else:
            events = CrushCollector(root=args.source_crush).collect()
    else:
        events = ClaudeCodeCollector(args.source).collect()
    n = store.ingest(events, _engine(config), config)
    print(_ingest_summary(n, store.coverage()))
    return 0
```

**Note :** La détection du mode se fait par l'extension du chemin : si le chemin se termine par `.db`, on utilise le mode backfill SQLite, sinon on utilise le mode export JSON.

- [ ] **Étape 1 : Run des tests existants**

```bash
$ pytest tests/test_cli_end_to_end.py -v
```

Attendu : Tous les tests existants PASS.

- [ ] **Étape 2 : Commit**

```bash
$ git add agent_carbon/__main__.py
$ git commit -m "feat: add --source-crush to ingest command"
```

---

### Task 4 : Intégration dans l'installateur

**Files à modifier :**

- Script d'installation d'agent-carbon (fichier d'installation principal)

**Rôle :** L'installateur doit :

1. **Créer le plugin Opencode** : écrire le fichier `~/.config/opencode/plugins/agent-carbon-crush.js` qui écoute `session.idle` et écrit les exports dans `~/.agent-carbon/crush-exports/`.

2. **Backfill initial** : si `~/.local/share/opencode/opencode.db` existe, exécuter automatiquement `agent-carbon ingest --source-crush ~/.local/share/opencode/opencode.db` pour ingérer les sessions existantes.

3. **Vérifier que le plugin est chargé** : s'assurer qu'Opencode charge le plugin à chaque démarrage.

**Note :** Le backfill initial ne se fait qu'une fois. Les sessions futures sont collectées via le plugin.

---

## Plan global résumé

| Étape | Tâche | Fichiers |
|---|---|---|
| 0 | Plugin Opencode (installation) | `~/.config/opencode/plugins/agent-carbon-crush.js` |
| 1 | Collecteur Crush (exports JSON) | `agent_carbon/collectors/crush.py` (mode JSON) |
| 2 | Collecteur Crush (backfill SQLite) | `agent_carbon/collectors/crush.py` (mode SQLite) |
| 3 | CLI `--source-crush` | `agent_carbon/__main__.py` |
| 4 | Intégration installateur | Script d'installation |

## Self-Review

### 1. Coverage du spec

Ce plan couvre l'intégralité du spec `specs/2026-06-30-support-crush-opencode.md` :

- ✅ Collecteur générique (`CrushCollector`) hérité de `Collector`
- ✅ Mode export JSON (lecture de `~/.agent-carbon/crush-exports/`)
- ✅ Mode backfill SQLite (lecture de `~/.local/share/opencode/opencode.db`)
- ✅ Plugin Opencode installé automatiquement à l'installation
- ✅ Backfill initial au premier lancement
- ✅ CLI `--source-crush` pour les deux modes
- ✅ Mapping des champs conforme au format `opencode export` et à la structure de la BDD Opencode
- ✅ Gestion des erreurs silencieuse (pas d'exceptions levées)
- ✅ Tests TDD avec fixtures

### 2. Différences avec l'ancien plan

L'ancien plan omettait :
- Le plugin Opencode (Task 0)
- Le backfilling automatique à l'installation (Task 4)
- La structure exacte de la BDD Opencode (table `session` avec `id`, `directory`, `model` (JSON), `tokens_*`, `time_created`, `time_updated`)
- Le mapping correct des champs depuis les tables `session` et `message` de la BDD Opencode
- La détection du mode par extension `.db` dans la CLI

### 3. Next steps

- [ ] Implémenter Task 0 (plugin Opencode) dans l'installateur
- [ ] Valider la structure de la BDD Opencode locale (`~/.local/share/opencode/opencode.db`)
- [ ] Tester le backfill sur la base réelle

---

*Document créé : 2026-07-01. Basé sur `specs/2026-06-30-support-crush-opencode.md` et `comparaison-donnees-outils.md`.*
