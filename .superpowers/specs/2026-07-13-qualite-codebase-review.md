# Spec — dette qualité identifiée par la review du 2026-07-13

> Issue d'une review complète qualité + sécurité de la codebase (hors tests),
> menée via deux sous-agents (sécurité / qualité) sur `ai_footprint/`,
> `scripts/`, `skills/`. Aucune vulnérabilité de sécurité exploitable trouvée
> (subprocess en forme liste, SQL paramétré, pas de désérialisation dangereuse,
> pas de secret en dur) — ce document ne couvre donc que la qualité.
> Correctifs en TDD (tests d'abord), un point à la fois.

## Points forts (à préserver)

- Subprocess systématiquement en forme liste (jamais `shell=True`).
- SQL paramétré (`?`) partout dans `store/db.py`, jamais d'interpolation.
- Cascade de résolution offline-safe, aucune exception non gérée qui casse l'ingest.

## 🔴 Majeur

### Q1 — Duplication du parsing de timestamp (3 implémentations)

- **Constat** : trois fonctions quasi identiques parsent des timestamps ISO/epoch :
  `_parse_ts` (`ai_footprint/collectors/claude_code.py:19`), `_parse_ts`
  (`ai_footprint/store/db.py:47`), `_parse_ts_utc_ms`
  (`ai_footprint/collectors/crush.py:19`). Risque de divergence silencieuse si
  un format évolue dans un seul endroit.
- **Correctif attendu** : extraire un module partagé (ex. `ai_footprint/dates.py`)
  avec une fonction unique couvrant les formats nécessaires, et faire pointer
  les trois call-sites dessus.

### Q2 — Exceptions avalées sans trace dans la résolution HF

- **Constat** : `except Exception: continue` / `except Exception: return None`
  dans `ai_footprint/impact/params.py:102,106,192`. Un échec réseau, un JSON
  malformé ou un timeout HuggingFace sont indiscernables — impossible de
  diagnostiquer pourquoi une résolution de modèle échoue.
- **Correctif attendu** : catcher les types précis attendus
  (`urllib.error.URLError`, `json.JSONDecodeError`, `subprocess.TimeoutExpired`)
  et logger (`logger.debug`) le cas échéant plutôt que d'avaler silencieusement.

## 🟠 Moyen

### Q3 — Duplication de requêtes SQL dans `store/db.py`

- **Constat** : `intensity_by_model()`, `intensity_by_client()`,
  `tokens_by_model()` (`store/db.py:205-221,240-256,273-290`) répètent le même
  schéma JOIN + agrégation avec seulement colonnes/GROUP BY qui changent.
  Même chose entre `estimated_param_models()` et `extrapolated_param_models()`
  (lignes 321-334, 340-349).
- **Correctif attendu** : extraire un helper de construction de requête
  paramétrable par les colonnes/critères variables.

### Q4 — Imports différés dans le corps des fonctions (`impact/params.py`)

- **Constat** : `_fetch_hf_cli_info()` importe `subprocess`, `shutil`, `os`,
  `sys` localement (lignes 116-127) ; `_fetch_hf_total_params()` importe
  `huggingface_hub` localement (ligne 180). Dépendances masquées, analyse
  statique compliquée.
- **Correctif attendu** : remonter les imports stdlib en tête de module ; pour
  `huggingface_hub` (optionnel), garder un import différé mais documenté
  (try/except explicite en tête de module plutôt qu'inline dans la fonction).

### Q5 — Erreurs silencieuses dans les collecteurs

- **Constat** : `except json.JSONDecodeError: continue` sans log ni compteur
  dans `collectors/claude_code.py:50-81` et `collectors/crush.py:73-81`. Des
  lignes malformées sont perdues sans trace.
- **Correctif attendu** : logger en debug ou incrémenter un compteur de lignes
  ignorées, exposé au minimum en mode verbeux.

### Q6 — Trou de couverture de tests sur les collecteurs

- **Constat** : `collectors/pi.py` et `collectors/crush.py` (parsing JSONL/JSON
  avec logique de backfill) n'ont pas de tests dédiés couvrant les cas limites
  (JSON malformé, champs manquants, dérive de schéma).
- **Correctif attendu** : ajouter des tests unitaires ciblés (TDD : écrire le
  cas limite en échec d'abord) pour `PiCollector` et `CrushCollector`.

## 🟡 Mineur

### Q7 — `main()` et `_cmd_models()` trop longs

- **Constat** : `ai_footprint/__main__.py` — `main()` fait ~195 lignes
  (273-468), `_cmd_models()` 86 lignes (89-174) avec 3 scénarios imbriqués
  (dense/MoE/fallback).
- **Correctif attendu** : découper en modules `commands/*.py` par sous-commande ;
  `main()` devient un simple dispatcher.

### Q8 — Fuite potentielle de handle fichier

- **Constat** : `urllib.request.urlopen(req, timeout=15)`
  (`impact/params.py:79-80`) n'est pas dans un context manager ; si le parsing
  JSON qui suit échoue, le handle n'est jamais fermé.
- **Correctif attendu** : `with urllib.request.urlopen(...) as resp:`.

### Q9 — Mutation de config pendant l'ingest

- **Constat** : le cache de résolution HF est écrit dans
  `config.model_params` en cours d'ingest (`__main__.py:382-385`). Un crash
  partiel laisse un état de cache incohérent (certaines entrées ajoutées,
  d'autres non).
- **Correctif attendu** : différer l'écriture de config à la fin d'un ingest
  réussi, ou travailler sur une copie et ne committer qu'en cas de succès.

### Q10 — Fallback provider non documenté

- **Constat** : `ModelParamsResolver._from_registry()`
  (`impact/params.py:266-268`) tente `(provider, "huggingface_hub")` comme
  repli, couplage implicite aux internes du registre EcoLogits.
- **Correctif attendu** : documenter ce fallback en commentaire (pourquoi ce
  couple précis) ou l'extraire en constante nommée explicite.

## Priorisation proposée

1. Q1 (dates) — élimine un risque de divergence silencieuse, base pour Q5.
2. Q2 (exceptions avalées) — restaure la diagnosticabilité de la résolution HF.
3. Q3 (SQL dupliqué) — réduit la surface de maintenance de `store/db.py`.
4. Q6 (tests collecteurs) — sécurise les refactors à venir (Q1, Q5).
5. Q7 (découpage `main()`) — améliore la lisibilité, pas bloquant.
6. Q4, Q5, Q8, Q9, Q10 — au fil de l'eau, faible risque, faible effort.
