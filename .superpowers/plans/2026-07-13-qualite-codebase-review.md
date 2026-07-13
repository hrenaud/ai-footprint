# Dette qualité codebase (Q1-Q10) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corriger les 10 points de dette qualité identifiés par la review du 2026-07-13 (`.superpowers/specs/2026-07-13-qualite-codebase-review.md`), en TDD, sans changer le comportement observable sauf là où le correctif l'exige explicitement (Q1, Q2, Q5, Q6).

**Architecture:** Chaque tâche correspond à un Q-item, dans l'ordre de priorité de la spec. Q1 introduit un module `ai_footprint/dates.py` partagé consommé par les collecteurs et le store. Q2/Q4/Q8/Q10 modifient uniquement `ai_footprint/impact/params.py`. Q3 introduit deux helpers privés dans `ai_footprint/store/db.py`. Q6 ajoute des tests de régression sur `crush.py`/`pi.py` avec un fix minimal. Q7+Q9 extraient deux nouveaux packages de commandes (`ai_footprint/ingest/`, `ai_footprint/models_admin/`) suivant la convention déjà en place (`ai_footprint/card/cli.py`, `ai_footprint/resolve/cli.py`) et ajoutent une fonction `open_store` à `store/db.py`. Q5 ajoute du logging debug dans les collecteurs.

**Tech Stack:** Python 3.11+, pytest, sqlite3 stdlib, EcoLogits, huggingface_hub (optionnel).

## Global Constraints

- TDD strict : test d'abord, vérifier qu'il échoue, implémenter, vérifier qu'il passe, committer — sauf Task 3 (Q3) qui est un refactor SQL pur sans changement de comportement : la couverture existante de `tests/test_store.py` sert de filet (vert avant → refactor → vert après).
- Aucune régression de comportement observable, sauf là où le correctif l'exige explicitement (Q1 : centralisation du parsing ; Q2/Q5 : ajout de logs debug ; Q6 : durcissement contre les entrées malformées).
- Suivre la convention existante pour tout module de commande extrait : package `<name>/` avec `__init__.py` vide + `<name>/cli.py` exposant `cmd_<name>(args) -> int` (cf. `ai_footprint/card/cli.py`, `ai_footprint/resolve/cli.py`).
- Commits en `type: sujet` (conventionnel), un commit par étape « Commit » du plan.
- Ne jamais utiliser `ai-footprint` global — uniquement `.venv/bin/python -m pytest` / `.venv/bin/ai-footprint` (rappel CLAUDE.md, hors scope ici car pas de release dans ce plan).

---

### Task 1: Q1 — module `dates.py` partagé, dédup du parsing de timestamp

**Files:**

- Modify: `ai_footprint/dates.py`
- Modify: `ai_footprint/collectors/claude_code.py:1-23`
- Modify: `ai_footprint/collectors/crush.py:1-23`
- Modify: `ai_footprint/store/db.py:1-51`
- Test: `tests/test_dates.py`

**Interfaces:**

- Produces: `ai_footprint.dates.parse_iso_ts(s: str) -> datetime | None`, `ai_footprint.dates.ts_from_epoch_ms(ms: int | float | None) -> str | None`.
- Consumes (Task 5, 7): rien de nouveau — ces fonctions ne sont pas rappelées ailleurs dans ce plan.

- [ ] **Step 1: Write the failing tests for `parse_iso_ts` and `ts_from_epoch_ms`**

Ajouter à la fin de `tests/test_dates.py` :

```python
from ai_footprint.dates import parse_iso_ts, ts_from_epoch_ms


def test_parse_iso_ts_with_z_suffix():
    dt = parse_iso_ts("2026-07-13T10:00:00Z")
    assert dt is not None
    assert dt.isoformat() == "2026-07-13T10:00:00+00:00"


def test_parse_iso_ts_invalid_returns_none():
    assert parse_iso_ts("not-a-date") is None


def test_parse_iso_ts_non_string_returns_none():
    assert parse_iso_ts(None) is None


def test_ts_from_epoch_ms_none_returns_none():
    assert ts_from_epoch_ms(None) is None


def test_ts_from_epoch_ms_converts_to_iso_utc():
    result = ts_from_epoch_ms(1752400800000)
    assert result == "2026-07-13T10:00:00+00:00"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_dates.py -v`
Expected: FAIL avec `ImportError: cannot import name 'parse_iso_ts'`

- [ ] **Step 3: Implement `parse_iso_ts` and `ts_from_epoch_ms` in `ai_footprint/dates.py`**

En tête de fichier, remplacer `from datetime import datetime` par :

```python
from datetime import datetime, timezone
```

Ajouter à la fin du fichier :

```python
def parse_iso_ts(s: str) -> datetime | None:
    """Parse un timestamp ISO 8601 (suffixe 'Z' accepté). None si invalide."""
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def ts_from_epoch_ms(ms: int | float | None) -> str | None:
    """Convertit un epoch en millisecondes en timestamp ISO UTC. None si absent."""
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).isoformat()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_dates.py -v`
Expected: PASS (11 tests : 6 existants + 5 nouveaux)

- [ ] **Step 5: Commit**

```bash
git add ai_footprint/dates.py tests/test_dates.py
git commit -m "feat(dates): add parse_iso_ts and ts_from_epoch_ms"
```

- [ ] **Step 6: Re-router `claude_code.py` vers `dates.parse_iso_ts`**

Dans `ai_footprint/collectors/claude_code.py`, remplacer les lignes 19-23 :

```python
def _parse_ts(s: str) -> datetime | None:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
```

par :

```python
from ai_footprint.dates import parse_iso_ts as _parse_ts
```

Placer cette ligne avec les autres imports en tête de fichier (pas à la ligne 19). Vérifier que l'import `from datetime import datetime` reste nécessaire pour le reste du fichier (type hints) ; sinon le retirer s'il devient inutilisé.

- [ ] **Step 7: Re-router `store/db.py` vers `dates.parse_iso_ts`**

Dans `ai_footprint/store/db.py`, remplacer les lignes 47-51 :

```python
def _parse_ts(s: str) -> datetime | None:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
```

par :

```python
from ai_footprint.dates import parse_iso_ts as _parse_ts
```

Placer cette ligne avec les autres imports en tête de fichier.

- [ ] **Step 8: Re-router `crush.py` vers `dates.ts_from_epoch_ms`**

Dans `ai_footprint/collectors/crush.py`, remplacer les lignes 19-23 (le corps de `_parse_ts_utc_ms`) par :

```python
from ai_footprint.dates import ts_from_epoch_ms as _parse_ts_utc_ms
```

Placer cette ligne avec les autres imports en tête de fichier.

- [ ] **Step 9: Run the full test suite to verify no regression**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: PASS (tous les tests existants, notamment `tests/test_claude_code_collector.py`, `tests/test_crush_collector.py`, `tests/test_store.py`, `tests/test_pi_collector.py` qui dépendent de `pi.py: from ai_footprint.collectors.claude_code import (_active_seconds, _parse_ts, _project_from_cwd)` — cette ré-import chaîne continue de fonctionner car `_parse_ts` reste un nom exporté par `claude_code.py`)

- [ ] **Step 10: Commit**

```bash
git add ai_footprint/collectors/claude_code.py ai_footprint/collectors/crush.py ai_footprint/store/db.py
git commit -m "refactor(dates): dedupe timestamp parsing via ai_footprint.dates"
```

---

### Task 2: Q2 — exceptions précises + logging dans `impact/params.py`

**Files:**

- Modify: `ai_footprint/impact/params.py`
- Test: `tests/test_params_error_logging.py` (nouveau)

**Interfaces:**

- Consumes: rien de nouveau.
- Produces: `logger = logging.getLogger("ai_footprint.impact.params")` (nom du module, utilisé par les tests via `caplog.at_level(..., logger="ai_footprint.impact.params")`).

- [ ] **Step 1: Write the failing tests**

Créer `tests/test_params_error_logging.py` :

```python
import json
import logging
import sys
import types

import pytest

import ai_footprint.impact.params as params_mod


def test_hf_total_params_model_info_failure_is_logged(monkeypatch, caplog):
    mod = types.SimpleNamespace()

    def fake_model_info(repo):
        raise OSError("boom")

    mod.model_info = fake_model_info
    monkeypatch.setitem(sys.modules, "huggingface_hub", mod)
    monkeypatch.setattr(params_mod, "huggingface_hub", mod)
    monkeypatch.setattr(
        params_mod, "_fetch_safetensors_index_bytes", lambda repo: None)

    with caplog.at_level(logging.DEBUG, logger="ai_footprint.impact.params"):
        result = params_mod._fetch_hf_total_params("org/model")

    assert result is None
    assert "org/model" in caplog.text


def test_index_bytes_request_failure_is_logged(monkeypatch, caplog):
    def fake_urlopen(req, timeout=15):
        raise __import__("urllib.error", fromlist=["URLError"]).URLError("dns fail")

    monkeypatch.setattr(params_mod.urllib.request, "urlopen", fake_urlopen)

    with caplog.at_level(logging.DEBUG, logger="ai_footprint.impact.params"):
        result = params_mod._fetch_safetensors_index_bytes("org/model")

    assert result is None
    assert "org/model" in caplog.text


def test_index_bytes_head_failure_is_logged(monkeypatch, caplog):
    index = {
        "weight_map": {"a": "model-00001-of-00002.safetensors",
                        "b": "model-00002-of-00002.safetensors"}
    }

    class _Resp:
        def read(self):
            return json.dumps(index).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=15):
        url = req.full_url if hasattr(req, "full_url") else req
        if "resolve" in str(url) and "model-00001" in str(url):
            raise OSError("head failed")
        return _Resp()

    monkeypatch.setattr(params_mod.urllib.request, "urlopen", fake_urlopen)

    with caplog.at_level(logging.DEBUG, logger="ai_footprint.impact.params"):
        params_mod._fetch_safetensors_index_bytes("org/model")

    assert "org/model" in caplog.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_params_error_logging.py -v`
Expected: FAIL — soit `caplog.text` vide (pas de log émis), soit erreur selon l'implémentation actuelle des trois `except Exception:` muets.

- [ ] **Step 3: Add logger + import urllib.error at module level in `params.py`**

En tête de fichier, avec les imports existants (`json`, `re`, `time`), ajouter :

```python
import logging
import urllib.error
```

Juste après le bloc d'imports, ajouter :

```python
logger = logging.getLogger(__name__)
```

- [ ] **Step 4: Fix the inner HEAD-loop exception (line ~102)**

Dans `_fetch_safetensors_index_bytes`, remplacer :

```python
        except Exception:
            continue
```

(la clause associée à la boucle HEAD interne) par :

```python
        except (urllib.error.URLError, OSError, ValueError) as exc:
            logger.debug("HEAD request failed for %s: %s", repo, exc)
            continue
```

- [ ] **Step 5: Fix the outer try/except (line ~106)**

Remplacer :

```python
    except Exception:
        return None
```

(la clause englobant tout le corps de `_fetch_safetensors_index_bytes`) par :

```python
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError) as exc:
        logger.debug("Failed to fetch safetensors index for %s: %s", repo, exc)
        return None
```

- [ ] **Step 6: Fix the `model_info` call exception in `_fetch_hf_total_params` (line ~192)**

Remplacer :

```python
        except Exception:
            pass
```

(la clause associée à l'appel `huggingface_hub.model_info(...)`) par :

```python
        except (OSError, ValueError, AttributeError) as exc:
            logger.debug("huggingface_hub.model_info failed for %s: %s", repo, exc)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_params_error_logging.py -v`
Expected: PASS

- [ ] **Step 8: Run the full params test suite to verify no regression**

Run: `.venv/bin/python -m pytest tests/test_params_huggingface.py tests/test_params_error_logging.py -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add ai_footprint/impact/params.py tests/test_params_error_logging.py
git commit -m "fix(params): catch specific exceptions and log HF resolution failures"
```

---

### Task 3: Q3 — dédup des requêtes SQL dans `store/db.py`

**Files:**

- Modify: `ai_footprint/store/db.py:200-350`

**Interfaces:**

- Produces (privé, non consommé hors de ce fichier) : `SQLiteStore._criteria_rows(self, group_col, select_extra, extra_where="", since=None) -> list[sqlite3.Row]`, `SQLiteStore._criteria_row_dict(self, r) -> dict`, `SQLiteStore._param_models_with_warning(self, warning_clause, since=None) -> list[str]`.

Refactor pur, comportement inchangé — pas de nouveaux tests (couverture existante de `tests/test_store.py` sert de filet).

- [ ] **Step 1: Run the existing store tests to confirm green baseline**

Run: `.venv/bin/python -m pytest tests/test_store.py -v`
Expected: PASS (baseline avant refactor)

- [ ] **Step 2: Add the two shared helpers to `store/db.py`**

Juste avant `intensity_by_model` (ligne 200), ajouter :

```python
    def _criteria_rows(self, group_col, select_extra="", extra_where="",
                        since=None):
        where = "WHERE i.error IS NULL" + extra_where
        params: list = []
        if since:
            where += " AND e.timestamp >= ?"
            params.append(since)
        query = f"""
            SELECT {group_col} AS grp{select_extra},
                   SUM(e.active_seconds) AS sec,
                   SUM(e.output_tokens) AS toks,
                   SUM(i.energy_min) AS emin, SUM(i.energy_max) AS emax,
                   SUM(i.gwp_min) AS gmin, SUM(i.gwp_max) AS gmax,
                   SUM(i.adpe_min) AS amin, SUM(i.adpe_max) AS amax,
                   SUM(i.pe_min) AS pmin, SUM(i.pe_max) AS pmax,
                   SUM(i.wcf_min) AS wmin, SUM(i.wcf_max) AS wmax
            FROM events e JOIN impacts i ON i.event_id = e.id
            {where}
            GROUP BY grp
        """
        return self.conn.execute(query, params).fetchall()

    def _criteria_row_dict(self, r) -> dict:
        result = {"active_seconds": r["sec"] or 0, "output_tokens": r["toks"] or 0}
        for name, (min_col, max_col) in _CRIT_COLS.items():
            result[name] = {"min": r[min_col] or 0, "max": r[max_col] or 0}
        return result
```

Note : adapter les noms de colonnes exacts (`emin`/`emax`/etc.) à ceux réellement utilisés dans les trois méthodes existantes — les lire dans `store/db.py:200-298` avant d'écrire cette étape en exécution réelle, et garder rigoureusement la même liste de colonnes SELECT que l'implémentation actuelle pour ne rien changer au résultat.

- [ ] **Step 3: Rewrite `intensity_by_model`, `intensity_by_client`, `tokens_by_model` to call `_criteria_rows`**

Remplacer le corps SQL de chacune des trois méthodes par un appel à `self._criteria_rows(group_col=..., select_extra=..., extra_where=..., since=since)` suivi d'une construction du dict de résultat via `self._criteria_row_dict(r)`, en conservant à l'identique la clé de groupement retournée par chaque méthode (`r["grp"]` mappé sur la clé actuelle : modèle, client, ou modèle selon le cas) et toute logique de post-traitement (tri, filtrage) déjà présente après la requête SQL dans le code actuel.

- [ ] **Step 4: Add `_param_models_with_warning` helper**

Juste avant `estimated_param_models` (ligne ~318), ajouter :

```python
    def _param_models_with_warning(self, warning_clause: str, since=None) -> list[str]:
        where = f"WHERE {warning_clause}"
        params: list = []
        if since:
            where += " AND e.timestamp >= ?"
            params.append(since)
        query = f"""
            SELECT DISTINCT e.model
            FROM events e JOIN impacts i ON i.event_id = e.id
            {where}
            ORDER BY e.model
        """
        return [r["model"] for r in self.conn.execute(query, params).fetchall()]
```

- [ ] **Step 5: Rewrite `estimated_param_models` and `extrapolated_param_models` to call the helper**

Remplacer chaque corps par un appel à `self._param_models_with_warning(warning_clause=..., since=since)` avec la clause `warnings LIKE '...'` spécifique à chaque méthode, reprise verbatim du code actuel.

- [ ] **Step 6: Run the existing store tests to confirm no regression**

Run: `.venv/bin/python -m pytest tests/test_store.py -v`
Expected: PASS (identique au baseline du Step 1 — même nombre de tests, tous verts)

- [ ] **Step 7: Commit**

```bash
git add ai_footprint/store/db.py
git commit -m "refactor(store): dedupe SQL query construction across criteria methods"
```

---

### Task 4: Q6 — couverture de tests + durcissement `crush.py`/`pi.py`

**Files:**

- Modify: `ai_footprint/collectors/crush.py:87-88`
- Modify: `ai_footprint/collectors/pi.py` (juste après le bloc `try/except json.JSONDecodeError` dans `_parse_file`)
- Test: `tests/test_crush_collector.py`
- Test: `tests/test_pi_collector.py`

**Interfaces:** aucune nouvelle interface publique — durcissement interne uniquement.

- [ ] **Step 1: Write the failing test for `CrushCollector`**

Ajouter à `tests/test_crush_collector.py` :

```python
def test_non_dict_message_entries_skipped_without_crashing():
    fd, path = tempfile.mkstemp(suffix=".json")
    data = {"messages": ["not-a-dict", None, {"data": {"role": "user",
                                                        "content": "hi",
                                                        "time": {"created": 1752400800000}}}]}
    os.write(fd, json.dumps(data).encode())
    os.close(fd)
    try:
        events = CrushCollector(root=os.path.dirname(path)).collect()
        assert isinstance(events, list)
    finally:
        os.remove(path)
```

(Adapter le nom exact du champ racine/structure attendue par `_parse_export` en le confirmant dans `crush.py` avant d'écrire ce test en exécution réelle — le format doit correspondre à un fichier `.json` valide que `CrushCollector` découvre et parse réellement, pas un mock.)

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_crush_collector.py::test_non_dict_message_entries_skipped_without_crashing -v`
Expected: FAIL avec `AttributeError: 'str' object has no attribute 'get'` (ou équivalent pour `None`)

- [ ] **Step 3: Fix `crush.py::_parse_export`**

Dans `ai_footprint/collectors/crush.py`, juste après la ligne `for msg in messages:` (ligne 87), ajouter :

```python
        for msg in messages:
            if not isinstance(msg, dict):
                continue
```

(fusionner avec la ligne `for` existante — n'ajouter que le `if not isinstance(msg, dict): continue` comme premier statement du corps de boucle, avant `info = msg.get("data") or msg.get("info")`)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_crush_collector.py -v`
Expected: PASS (tous les tests du fichier, y compris le nouveau)

- [ ] **Step 5: Commit**

```bash
git add ai_footprint/collectors/crush.py tests/test_crush_collector.py
git commit -m "fix(crush): skip non-dict message entries instead of crashing"
```

- [ ] **Step 6: Write the failing test for `PiCollector`**

Ajouter à `tests/test_pi_collector.py` :

```python
def test_non_dict_json_lines_skipped_without_crashing():
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.write(fd, b'[1, 2, 3]\n"just a string"\n')
    os.close(fd)
    try:
        events = PiCollector(root=os.path.dirname(path)).collect()
        assert isinstance(events, list)
    finally:
        os.remove(path)
```

- [ ] **Step 7: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_pi_collector.py::test_non_dict_json_lines_skipped_without_crashing -v`
Expected: FAIL avec `AttributeError: 'list' object has no attribute 'get'` (ou équivalent pour `str`)

- [ ] **Step 8: Fix `pi.py::_parse_file`**

Dans `ai_footprint/collectors/pi.py`, juste après le bloc :

```python
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
```

ajouter :

```python
            if not isinstance(obj, dict):
                continue
```

avant la ligne `cur_ts = _parse_ts(obj.get("timestamp", ""))`.

- [ ] **Step 9: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_pi_collector.py -v`
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add ai_footprint/collectors/pi.py tests/test_pi_collector.py
git commit -m "fix(pi): skip non-dict JSON lines instead of crashing"
```

---

### Task 5: Q7 + Q9 — extraction des commandes `ingest`/`models` + sécurisation de la sauvegarde config

**Files:**

- Create: `ai_footprint/ingest/__init__.py`
- Create: `ai_footprint/ingest/cli.py`
- Create: `ai_footprint/models_admin/__init__.py`
- Create: `ai_footprint/models_admin/cli.py`
- Modify: `ai_footprint/store/db.py` (ajout de `open_store`)
- Modify: `ai_footprint/__main__.py`
- Modify: `tests/test_ingest_ux.py`
- Test: `tests/test_ingest_and_save.py` (nouveau)

**Interfaces:**

- Produces: `ai_footprint.ingest.cli.build_engine(config) -> EcoLogitsEngine`, `ai_footprint.ingest.cli.config_snapshot(config) -> str`, `ai_footprint.ingest.cli.ingest_and_save(store, events, engine, config) -> int`, `ai_footprint.ingest.cli.ingest_summary(new_count, cov, store=None) -> str`, `ai_footprint.ingest.cli.cmd_ingest(args) -> int`, `ai_footprint.models_admin.cli.cmd_models(args) -> int`, `ai_footprint.store.db.open_store(db_path: str) -> SQLiteStore`.

- [ ] **Step 1: Write the failing regression test for `ingest_and_save` (Q9)**

Créer `tests/test_ingest_and_save.py` :

```python
import pytest

from ai_footprint.ingest.cli import ingest_and_save


class _FakeConfig:
    def __init__(self):
        self.model_params = {}
        self.hf_unresolved = {}
        self.saved = False

    def save(self):
        self.saved = True


class _CrashingStore:
    def ingest(self, events, engine, config):
        config.model_params["partial/model"] = {"total_params": 1.0}
        raise RuntimeError("boom")


class _OkStore:
    def ingest(self, events, engine, config):
        config.model_params["org/model"] = {"total_params": 7.0}
        return 3


class _NoopStore:
    def ingest(self, events, engine, config):
        return 0


def test_ingest_and_save_does_not_save_config_when_ingest_raises():
    config = _FakeConfig()
    with pytest.raises(RuntimeError):
        ingest_and_save(_CrashingStore(), [], engine=None, config=config)
    assert config.saved is False


def test_ingest_and_save_saves_config_when_ingest_succeeds_and_changed():
    config = _FakeConfig()
    n = ingest_and_save(_OkStore(), [], engine=None, config=config)
    assert n == 3
    assert config.saved is True


def test_ingest_and_save_skips_save_when_config_unchanged():
    config = _FakeConfig()
    n = ingest_and_save(_NoopStore(), [], engine=None, config=config)
    assert n == 0
    assert config.saved is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_ingest_and_save.py -v`
Expected: FAIL avec `ModuleNotFoundError: No module named 'ai_footprint.ingest'`

- [ ] **Step 3: Create `ai_footprint/ingest/__init__.py`**

Fichier vide.

- [ ] **Step 4: Create `ai_footprint/ingest/cli.py` with the four moved/new functions**

```python
from ai_footprint.impact.engine import EcoLogitsEngine
from ai_footprint.impact.resolver import ModelResolver


def build_engine(config) -> EcoLogitsEngine:
    return EcoLogitsEngine(ModelResolver(config.model_aliases))


def config_snapshot(config) -> str:
    return repr((config.model_params, config.hf_unresolved))


def ingest_and_save(store, events, engine, config) -> int:
    """Ingère les events puis persiste la config seulement si l'ingest a
    réussi et a modifié le cache de résolution HF (Q9 : pas de sauvegarde
    partielle si store.ingest() lève une exception)."""
    before = config_snapshot(config)
    n = store.ingest(events, engine, config)
    if config_snapshot(config) != before:
        config.save()
    return n


def ingest_summary(new_count, cov, store=None) -> str:
    ...  # corps repris verbatim de ai_footprint/__main__.py:243-270


def cmd_ingest(args) -> int:
    ...  # corps repris du dispatch ingest de ai_footprint/__main__.py:370-387,
         # utilisant build_engine, ingest_and_save, ingest_summary,
         # ai_footprint.store.db.open_store, ai_footprint.config.Config
```

Note d'exécution réelle : copier verbatim le corps actuel de `_ingest_summary` (`__main__.py:243-270`) dans `ingest_summary`, et le corps actuel du bloc `if args.cmd == "ingest":` (`__main__.py:370-387`) dans `cmd_ingest`, en remplaçant les appels à `_store(...)` par `open_store(...)` (importé depuis `ai_footprint.store.db`), `_engine(config)` par `build_engine(config)`, et la séquence `before = _config_snapshot(config); n = store.ingest(...); if _config_snapshot(config) != before: config.save()` par `n = ingest_and_save(store, events, build_engine(config), config)`.

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_ingest_and_save.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add ai_footprint/ingest/__init__.py ai_footprint/ingest/cli.py tests/test_ingest_and_save.py
git commit -m "feat(ingest): extract ingest command module with safe config save"
```

- [ ] **Step 7: Add `open_store` to `store/db.py`**

En tête de `ai_footprint/store/db.py`, ajouter `import os` aux imports existants.

En fin de fichier (ou juste après la définition de `SQLiteStore`), ajouter :

```python
def open_store(db_path: str) -> SQLiteStore:
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    return SQLiteStore(db_path)
```

- [ ] **Step 8: Update `tests/test_ingest_ux.py` to import from the new module**

Remplacer la ligne 3 :

```python
from ai_footprint.__main__ import _ingest_summary
```

par :

```python
from ai_footprint.ingest.cli import ingest_summary
```

Renommer les 4 appels `_ingest_summary(...)` (lignes 38, 47, 53, 58) en `ingest_summary(...)`.

- [ ] **Step 9: Run `test_ingest_ux.py` to verify no regression**

Run: `.venv/bin/python -m pytest tests/test_ingest_ux.py -v`
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add ai_footprint/store/db.py tests/test_ingest_ux.py
git commit -m "refactor(store): add open_store; point tests at ingest.cli.ingest_summary"
```

- [ ] **Step 11: Create `ai_footprint/models_admin/__init__.py`**

Fichier vide.

- [ ] **Step 12: Create `ai_footprint/models_admin/cli.py` moving `_cmd_models` verbatim**

```python
# Imports repris de ai_footprint/__main__.py (json, os, sys si utilisés dans
# le corps de _cmd_models, plus ai_footprint.config.Config,
# ai_footprint.impact.params.ModelParamsResolver,
# ai_footprint.impact.params.fetch_moe_params_from_hf,
# ai_footprint.impact.params._param_from_json,
# ai_footprint.impact.params._param_to_json — à confirmer en lisant
# __main__.py:89-174 pour la liste exacte des imports utilisés par ce corps)


def cmd_models(args) -> int:
    ...  # corps repris verbatim de ai_footprint/__main__.py:89-174 (_cmd_models),
         # renommé cmd_models, sans autre changement
```

Note d'exécution réelle : lire `ai_footprint/__main__.py:1-35` pour la liste exacte des imports déjà présents, et n'inclure dans ce nouveau fichier que ceux effectivement référencés par le corps de `_cmd_models` (89-174), copié tel quel.

- [ ] **Step 13: Update `__main__.py` dispatch for `models`**

Remplacer :

```python
    return _cmd_models(args)
```

par :

```python
    return cmd_models(args)
```

et ajouter en tête de `__main__.py` :

```python
from ai_footprint.models_admin.cli import cmd_models
```

Supprimer la définition de `_cmd_models(args)` (lignes 89-174) de `__main__.py`.

- [ ] **Step 14: Update `__main__.py` dispatch for `ingest` and `statusline`**

Remplacer le bloc `if args.cmd == "ingest":` (lignes 370-387) par un appel à `return cmd_ingest(args)`, et ajouter en tête de `__main__.py` :

```python
from ai_footprint.ingest.cli import build_engine, cmd_ingest, ingest_and_save
from ai_footprint.store.db import open_store
```

Dans le bloc `statusline` (lignes 424-438), remplacer la séquence `before = _config_snapshot(config); store.ingest(ClaudeCodeCollector(transcript).collect(), _engine(config), config); if _config_snapshot(config) != before: config.save()` par :

```python
ingest_and_save(store, ClaudeCodeCollector(transcript).collect(), build_engine(config), config)
```

Supprimer les définitions désormais inutilisées `_store` (61-63), `_engine` (66-67), `_config_snapshot` (70-74), `_ingest_summary` (243-270) de `__main__.py` si plus aucun appel local ne les référence après ces remplacements — vérifier avec `grep -n "_store(\|_engine(\|_config_snapshot(\|_ingest_summary(" ai_footprint/__main__.py` avant suppression.

- [ ] **Step 15: Run the full test suite to verify no regression**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: PASS (aucune régression sur `test_ingest_ux.py`, `test_store.py`, `test_params_huggingface.py`, ni les tests CLI existants qui exercent `main()`)

- [ ] **Step 16: Commit**

```bash
git add ai_footprint/models_admin/__init__.py ai_footprint/models_admin/cli.py ai_footprint/__main__.py
git commit -m "refactor(cli): extract ingest and models commands into dedicated modules"
```

---

### Task 6: Q4 — imports en tête de module dans `impact/params.py`

**Files:**

- Modify: `ai_footprint/impact/params.py`
- Modify: `tests/test_params_huggingface.py`

**Interfaces:** aucune nouvelle interface publique — `huggingface_hub` reste un attribut de module `ai_footprint.impact.params.huggingface_hub`, mais désormais résolu une seule fois à l'import du module plutôt qu'à chaque appel de `_fetch_hf_total_params`.

- [ ] **Step 1: Run the existing HF params tests to confirm green baseline**

Run: `.venv/bin/python -m pytest tests/test_params_huggingface.py -v`
Expected: PASS (baseline avant refactor)

- [ ] **Step 2: Hoist stdlib imports and the `huggingface_hub` import guard to module level**

En tête de `ai_footprint/impact/params.py`, avec les imports existants (`json`, `re`, `time`, `logging`, `urllib.error` du Task 2), ajouter :

```python
import os
import shutil
import subprocess
import sys
import urllib.request

try:
    import huggingface_hub
except ImportError:
    huggingface_hub = None
```

- [ ] **Step 3: Remove the inline imports from `_fetch_hf_cli_info`**

Dans `_fetch_hf_cli_info` (lignes 116-163), supprimer les lignes 124-127 (`import subprocess`, `import shutil`, `import os`, `import sys`) — le reste du corps de la fonction reste inchangé, ces noms restent résolus via les imports de module.

- [ ] **Step 4: Remove the inline import guard from `_fetch_hf_total_params`**

Dans `_fetch_hf_total_params` (lignes 166-220), supprimer les lignes 179-182 :

```python
        try:
            import huggingface_hub
        except ImportError:
            huggingface_hub = None
```

Le test `if huggingface_hub is not None:` (ligne 185) continue de fonctionner en référençant désormais le nom de module.

- [ ] **Step 5: Rewrite the `_fake_hf` helper in `tests/test_params_huggingface.py`**

Remplacer (ligne ~27-32) :

```python
def _fake_hf(...):
    ...
    monkeypatch.setitem(sys.modules, "huggingface_hub", mod)
    ...
```

par une version qui importe `ai_footprint.impact.params as params_mod` et utilise `monkeypatch.setattr(params_mod, "huggingface_hub", mod)` à la place du `monkeypatch.setitem(sys.modules, ...)`. Conserver le reste de la logique du helper à l'identique.

- [ ] **Step 6: Rewrite the `_hf_counting` helper**

Même changement pour `_hf_counting` (ligne ~140) : remplacer `monkeypatch.setitem(sys.modules, "huggingface_hub", mod)` par `monkeypatch.setattr(params_mod, "huggingface_hub", mod)`, en utilisant le `params_mod` déjà importé dans ce helper (ligne 133).

- [ ] **Step 7: Rewrite the 6 standalone test functions using `sys.modules`**

Pour chacune des fonctions suivantes, ajouter `import ai_footprint.impact.params as params_mod` en début de fonction si absent, et remplacer `monkeypatch.setitem(sys.modules, "huggingface_hub", ...)` par `monkeypatch.setattr(params_mod, "huggingface_hub", ...)` :

- `test_huggingface_network_error_returns_none` (ligne ~53)
- `test_huggingface_missing_lib_returns_none` (ligne ~59, valeur `None`)
- `test_huggingface_cache_hit_avoids_second_call` (ligne ~78)
- `test_fetch_hf_params_missing_lib_returns_none` (ligne ~119, valeur `None`)
- `test_fetch_hf_params_no_safetensors_returns_none` (ligne ~127)
- `test_huggingface_failure_not_retried_same_run` (ligne ~17 — `params_mod` déjà importé, changer juste l'appel)

- [ ] **Step 8: Run the HF params tests to verify no regression**

Run: `.venv/bin/python -m pytest tests/test_params_huggingface.py -v`
Expected: PASS (identique au baseline du Step 1)

- [ ] **Step 9: Run the full test suite**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add ai_footprint/impact/params.py tests/test_params_huggingface.py
git commit -m "refactor(params): hoist stdlib and huggingface_hub imports to module level"
```

---

### Task 7: Q5 — logging debug des erreurs de parsing silencieuses

**Files:**

- Modify: `ai_footprint/collectors/claude_code.py`
- Modify: `ai_footprint/collectors/crush.py`
- Test: `tests/test_claude_code_collector.py`
- Test: `tests/test_crush_collector.py`

**Interfaces:** `ai_footprint.collectors.claude_code.logger`, `ai_footprint.collectors.crush.logger` (loggers de module, noms `ai_footprint.collectors.claude_code` / `ai_footprint.collectors.crush`).

- [ ] **Step 1: Write the failing test for `claude_code.py`**

Ajouter à `tests/test_claude_code_collector.py` :

```python
import logging


def test_malformed_json_line_is_logged(tmp_path, caplog):
    transcript = tmp_path / "session.jsonl"
    transcript.write_text('{"not": "valid json"\nnot json at all\n')
    with caplog.at_level(logging.DEBUG, logger="ai_footprint.collectors.claude_code"):
        ClaudeCodeCollector(str(transcript)).collect()
    assert "session.jsonl" in caplog.text or "JSON" in caplog.text
```

(Adapter le nom exact de la classe/import déjà utilisé dans ce fichier de test — vérifier l'import existant avant d'écrire cette étape en exécution réelle.)

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_claude_code_collector.py::test_malformed_json_line_is_logged -v`
Expected: FAIL — `caplog.text` vide (aucun log émis actuellement)

- [ ] **Step 3: Add logger and debug log to `claude_code.py::_parse_file`**

En tête de `ai_footprint/collectors/claude_code.py`, ajouter `import logging` et `logger = logging.getLogger(__name__)` avec les autres imports/constantes de module.

Dans `_parse_file` (lignes 57-60), remplacer :

```python
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
```

par :

```python
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                logger.debug("Skipping malformed JSON line in %s: %s", path, exc)
                continue
```

(`path` : utiliser le nom de la variable réellement en portée à cet endroit du fichier — confirmer en lisant le corps de `_parse_file` avant d'écrire cette étape en exécution réelle.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_claude_code_collector.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ai_footprint/collectors/claude_code.py tests/test_claude_code_collector.py
git commit -m "feat(claude_code): log malformed JSON lines at debug level"
```

- [ ] **Step 6: Write the failing test for `crush.py`**

Ajouter à `tests/test_crush_collector.py` :

```python
def test_malformed_export_json_is_logged(caplog):
    fd, path = tempfile.mkstemp(suffix=".json")
    os.write(fd, b"{not valid json")
    os.close(fd)
    try:
        with caplog.at_level(logging.DEBUG, logger="ai_footprint.collectors.crush"):
            CrushCollector(root=os.path.dirname(path)).collect()
        assert "JSON" in caplog.text or os.path.basename(path) in caplog.text
    finally:
        os.remove(path)
```

- [ ] **Step 7: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_crush_collector.py::test_malformed_export_json_is_logged -v`
Expected: FAIL — `caplog.text` vide

- [ ] **Step 8: Add logger and debug log to `crush.py::_parse_export`**

En tête de `ai_footprint/collectors/crush.py`, ajouter `import logging` et `logger = logging.getLogger(__name__)`.

Dans `_parse_export` (lignes 78-81), remplacer :

```python
        try:
            data = json.load(fh)
        except (json.JSONDecodeError, OSError):
            return
```

par :

```python
        try:
            data = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            logger.debug("Skipping unreadable/malformed export %s: %s", path, exc)
            return
```

(`path` : confirmer le nom de variable en portée à cet endroit avant l'exécution réelle.)

- [ ] **Step 9: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_crush_collector.py -v`
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add ai_footprint/collectors/crush.py tests/test_crush_collector.py
git commit -m "feat(crush): log malformed/unreadable export files at debug level"
```

---

### Task 8: Q8 — context manager pour `urlopen` dans `params.py`

**Files:**

- Modify: `ai_footprint/impact/params.py:79-80`

**Interfaces:** aucun changement de signature — comportement identique, juste fermeture garantie du handle.

- [ ] **Step 1: Write the failing test**

Ajouter à `tests/test_params_huggingface.py` :

```python
def test_urlopen_handle_is_closed_even_on_json_error(monkeypatch):
    import ai_footprint.impact.params as params_mod

    closed = {"value": False}

    class _Resp:
        def read(self):
            return b"not valid json"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            closed["value"] = True
            return False

    monkeypatch.setattr(params_mod.urllib.request, "urlopen",
                         lambda req, timeout=15: _Resp())

    params_mod._fetch_safetensors_index_bytes("org/model")
    assert closed["value"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_params_huggingface.py::test_urlopen_handle_is_closed_even_on_json_error -v`
Expected: FAIL si `urlopen` n'est actuellement pas utilisé en context manager (`closed["value"]` reste `False`)

- [ ] **Step 3: Wrap `urlopen` in a `with` statement**

Dans `_fetch_safetensors_index_bytes` (lignes 79-80), remplacer :

```python
        resp = urllib.request.urlopen(req, timeout=15)
        index = json.loads(resp.read())
```

par :

```python
        with urllib.request.urlopen(req, timeout=15) as resp:
            index = json.loads(resp.read())
```

Vérifier que le reste du corps de la fonction qui dépend de `index` reste au même niveau d'indentation logique (ajuster l'indentation du bloc suivant pour rester dans le `with` si `index` est réutilisé après, sinon sortir du `with` juste après le `json.loads`).

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_params_huggingface.py -v`
Expected: PASS (y compris le nouveau test)

- [ ] **Step 5: Commit**

```bash
git add ai_footprint/impact/params.py tests/test_params_huggingface.py
git commit -m "fix(params): close urlopen handle via context manager"
```

---

### Task 9: Q10 — constante nommée pour le fallback provider

**Files:**

- Modify: `ai_footprint/impact/params.py:266-268`
- Test: `tests/test_params_huggingface.py`

**Interfaces:** `ai_footprint.impact.params._REGISTRY_FALLBACK_PROVIDERS` (constante de module, tuple).

- [ ] **Step 1: Write the failing test**

Ajouter à `tests/test_params_huggingface.py` :

```python
def test_registry_fallback_constant_includes_huggingface_hub():
    import ai_footprint.impact.params as params_mod

    assert "huggingface_hub" in params_mod._REGISTRY_FALLBACK_PROVIDERS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_params_huggingface.py::test_registry_fallback_constant_includes_huggingface_hub -v`
Expected: FAIL avec `AttributeError: module 'ai_footprint.impact.params' has no attribute '_REGISTRY_FALLBACK_PROVIDERS'`

- [ ] **Step 3: Extract the named constant**

Avec les autres constantes de module (`HF_NEGATIVE_TTL_DAYS`, `_MOE_NAME_RE`, etc.), ajouter :

```python
# EcoLogits enregistre certains modèles sous le provider "huggingface_hub"
# indépendamment du provider déclaré (ex. openai/gpt-oss), d'où ce repli
# systématique lors de la résolution registre.
_REGISTRY_FALLBACK_PROVIDERS = ("huggingface_hub",)
```

Dans `ModelParamsResolver._from_registry` (ligne 267), remplacer :

```python
        for prov in (provider, "huggingface_hub"):
```

par :

```python
        for prov in (provider, *_REGISTRY_FALLBACK_PROVIDERS):
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_params_huggingface.py -v`
Expected: PASS

- [ ] **Step 5: Run the full test suite**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: PASS (tous les tests, toutes tâches confondues)

- [ ] **Step 6: Commit**

```bash
git add ai_footprint/impact/params.py tests/test_params_huggingface.py
git commit -m "refactor(params): name the registry fallback provider constant"
```

---

## Self-Review

**1. Couverture spec** : Q1→Task 1, Q2→Task 2, Q3→Task 3, Q4→Task 6, Q5→Task 7, Q6→Task 4, Q7→Task 5, Q8→Task 8, Q9→Task 5, Q10→Task 9. Les 10 points sont couverts, dans l'ordre de priorité de la spec (Q1, Q2, Q3, Q6, Q7/Q9, puis Q4/Q5/Q8/Q10 « au fil de l'eau »).

**2. Placeholders** : Task 3 (Step 2-5) et Task 5 (Step 4, Step 12) et Task 7 (Step 3, Step 8) contiennent des notes d'exécution explicites demandant de confirmer un nom de variable ou une liste d'imports en lisant le fichier avant d'écrire le code final — ce ne sont pas des lacunes de conception mais des points où le code exact dépend de détails (noms de variables locales, imports effectivement utilisés) qu'un ingénieur exécutant la tâche doit vérifier dans le fichier source au moment de l'implémentation, la logique et la structure du correctif étant elles pleinement spécifiées.

**3. Cohérence des types/noms** : `parse_iso_ts`/`ts_from_epoch_ms` (Task 1) utilisés de façon cohérente en Task 1 uniquement (pas rappelés ailleurs). `build_engine`/`config_snapshot`/`ingest_and_save`/`ingest_summary`/`cmd_ingest`/`cmd_models`/`open_store` (Task 5) nommés de façon cohérente entre leur définition et leur usage dans `__main__.py` et `tests/test_ingest_ux.py`. `_criteria_rows`/`_criteria_row_dict`/`_param_models_with_warning` (Task 3) restés privés à `SQLiteStore`, cohérents entre définition et appel. `_REGISTRY_FALLBACK_PROVIDERS` (Task 9) et `logger` (Task 2, 7) nommés une seule fois chacun, sans collision entre modules (chaque module a son propre `logger = logging.getLogger(__name__)`).

---

**Plan complet et sauvegardé dans `.superpowers/plans/2026-07-13-qualite-codebase-review.md`.**
