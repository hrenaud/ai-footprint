# Architecture technique

## Pipeline général

```
JSONL Claude Code
    ↓
ClaudeCodeCollector (parse, normalise)
    ↓
InferenceEvent[] (provider, model, tokens, timestamp, session, projet)
    ↓
EcoLogitsEngine (offline, via EcoLogits 0.11.0)
    ↓
ImpactRecord (5 critères min/max, phases, métadonnées)
    ↓
SQLiteStore (idempotent)
    ↓
CLI Report / Statusline
```

## Collecte (ClaudeCodeCollector)

**Source** : `~/.claude/projects/**/*.jsonl` (par défaut ; configurable avec `--source`)

**Traitement** :

1. Énumère tous les fichiers JSONL récursivement.
2. Pour chaque ligne JSON :
   - Ignore les non-assistant (`type != "assistant"`).
   - Ignore les messages sans usage (`message.usage` absent).
   - Extrait : `model`, `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, `timestamp`, `cwd`, `sessionId`, `uuid`.
   - Dérive le projet du `cwd` (dernier segment du chemin).
   - Normalise en `InferenceEvent`.

**Confidentialité** : aucun contenu de prompt ou de réponse n'est extrait — seules les métadonnées et usage.

**Provider** : hardcodé à `"anthropic"` (extensible en future collecteur pour CodexCollector, etc.).

## Impact (EcoLogitsEngine)

**Principes** :

- Offline : appel à `ecologits.tracers.utils.llm_impacts()` sans réseau.
- Output tokens only : seul `output_token_count` alimente le calcul.
- Latence estimée : `output_tokens / throughput_tok_s` (défaut 50 tok/s), min 0.5s.
- Fourchettes : chaque critère retourne `(min, max)` pour capturer l'incertitude.

**5 critères** (CRITERIA) :

1. **energy** — consommation énergétique (kWh)
2. **gwp** — Global Warming Potential (kg CO₂ eq)
3. **adpe** — Abiotic Depletion Potential for Elements (kg Sb eq)
4. **pe** — Primary Energy (MJ)
5. **wcf** — Water Consumption Footprint (m³)

**Phases** :

- **usage** : énergie et impacts lors de l'inférence.
- **embodied** : impact de fabrication/déploiement (gwp, adpe, pe ; energy embarquée agrégée dans usage).

**ModelResolver** :

- Mappe un modèle reçu vers un modèle reconnu par EcoLogits.
- Table d'alias configurable via `Config.model_aliases` (dictionnaire YAML).
- Signale les alias appliqués dans `ImpactRecord.warnings` (code : `alias:ancien->nouveau`).

**Méthodologie** :

```python
methodology_version = f"engine={ENGINE_VERSION};ecologits={ecologits.__version__}"
```

Stockée par record → reproductibilité garantie pour recalculs ou audits.

## Stockage (SQLiteStore)

**Base de données** : `~/.agent-carbon/carbon.db` (par défaut ; configurable avec `--db`)

**Schéma** :

### Table `events` (brutes, normalisées)

```sql
CREATE TABLE events (
  session_id TEXT,
  msg_id TEXT,
  provider TEXT,           -- "anthropic"
  model TEXT,              -- modèle reçu du transcript
  input_tokens INTEGER,
  output_tokens INTEGER,
  cache_creation_tokens INTEGER,
  cache_read_tokens INTEGER,
  timestamp TEXT,          -- ISO 8601
  project TEXT,            -- dérivé du cwd
  PRIMARY KEY (session_id, msg_id)
);
```

### Table `impacts` (résultats du calcul)

```sql
CREATE TABLE impacts (
  session_id TEXT,
  msg_id TEXT,
  model_resolved TEXT,     -- après ModelResolver
  zone TEXT,               -- électricité mix (ex. "NL")
  methodology_version TEXT,
  energy_min REAL, energy_max REAL,
  gwp_min REAL, gwp_max REAL,
  adpe_min REAL, adpe_max REAL,
  pe_min REAL, pe_max REAL,
  wcf_min REAL, wcf_max REAL,
  breakdown_json TEXT,     -- {"usage": {...}, "embodied": {...}}
  warnings TEXT,           -- JSON array de codes (alias, etc.)
  error TEXT,              -- code erreur si calcul échoué
  PRIMARY KEY (session_id, msg_id)
);
```

### Table `sessions` (agrégation)

```sql
CREATE TABLE sessions (
  session_id TEXT PRIMARY KEY,
  project TEXT,
  started_at TEXT,         -- timestamp min des events
  ended_at TEXT            -- timestamp max des events
);
```

**Idempotence** :

- Clé primaire `(session_id, msg_id)` sur events et impacts.
- `INSERT OR IGNORE` → réingestion sûre sans doublons.
- Mises à jour `started_at`/`ended_at` dans sessions pour couvrir la plage temporelle.

**Séparation events/impacts** :

- Events = source brute normalisée.
- Impacts = résultat du calcul (dépend du moteur EcoLogits + zone).
- Permet recalcul sans re-parsing des JSONL.

## Restitution

### Report (`agent-carbon report`)

- Agrège les impacts par `--by [model|project|total]`.
- Affiche les fourchettes min–max par critère.
- Filtre optionnel `--since ISO8601` sur `events.timestamp`.
- Lit uniquement la DB (jamais les JSONL).

### Statusline (`agent-carbon statusline`)

- Sortie une seule ligne compacte (total tous critères, ordre défini).
- Format prêt pour intégration dans `~/.claude/settings.json` (statusLine config).
- Lit la DB, pas les JSONL.

## Incertitude & méthodologie

**Traçabilité** :

- Chaque impact record stocke `methodology_version`.
- Permets de :
  - Identifier quelle version d'EcoLogits a calculé l'impact.
  - Relancer des recalculs avec une version ultérieure.
  - Comparer impacts anciens/nouveaux (avant/après upgrade EcoLogits).

**Fourchettes** :

- Toutes les valeurs sont stockées et affichées en (min, max).
- L'incertitude provient de la région datacenter et du mix électrique.
- Aucune réduction arbitraire à un point.

**Warnings** :

- JSON array stockée dans `impacts.warnings`.
- Codes connus : `alias:ancien->nouveau` (alias appliqué).
- Extensible : EcoLogits ajoute ses warnings d'incertitude.

**Errors** :

- Si `llm_impacts()` échoue → `impacts.error` contient le code erreur.
- L'event est toujours inséré (immuable), l'impact reste vide.
- Report/statusline ignore les erreurs (`WHERE error IS NULL`).

## Configuration

### Config (YAML)

Fichier `agent_carbon/config.py` + `~/.agent-carbon/config.yaml` (futur) :

```python
# Défauts
throughput_tok_s = 50             # tokens/s pour estimer la latence
electricity_mix_zone = "NL"       # zone élec (pays des datacenters)
model_aliases = {...}            # table d'alias modèles
```

### Ingest

- `--source` (défaut `~/.claude/projects`) : racine des transcripts.
- `--db` (défaut `~/.agent-carbon/carbon.db`) : chemin DB SQLite.

### Report

- `--db` : chemin DB.
- `--by` : agrégation (model|project|total), défaut model.
- `--since` : ISO 8601 (ex. "2026-06-26T00:00:00Z"), optionnel.

### Statusline

- `--db` : chemin DB.

## Hors MVP (placeholders et coutures)

**Posés, non implémentés** :

- `CodexCollector` (stub) : futur collecteur Codex.
- `LocalInferenceCollector` (stub) : futur collecteur inférence locale.
- `import_legacy()` : backfill depuis `carbon.db` ancien.
- `compute_live()` : mode live (instrumentation SDK temps réel).
- Énergie du poste de travail : hors périmètre.
- Eau (wcf) : à recevoir via release PyPI future.
- Export fichier (CSV, JSON) : futur.

**Après MVP** :

1. Brancher statusline dans `~/.claude/settings.json` :

   ```json
   {
     "statusLine": "agent-carbon statusline --db ~/.agent-carbon/carbon.db"
   }
   ```

2. Planifier l'ingest (hook ou cron) pour synchronisation avant purge des JSONL :

   ```bash
   agent-carbon ingest --source ~/.claude/projects --db ~/.agent-carbon/carbon.db
   ```

3. Suivi de version EcoLogits (GitHub Action ou notification) : monitorer `mlco2/ecologits` pour releases mineures, tester compatibilité, notifier la maintenance.

## Références

- EcoLogits : https://github.com/mlco2/ecologits
- CodeCarbon : https://github.com/mlco2/codecarbon
- claude-carbon : audit original et UX reporting
