# Design — `agent-carbon-resolve` : résolution des modèles non couverts

> Date : 2026-06-29. Statut : validé, prêt pour le plan d'implémentation.
> Lié : `docs/TODO-self-hosted-models.md` (chaîne de résolution params, recompute),
> section « Modèles non couverts » du rapport (`render_uncovered`).

## Problème

Le rapport liste désormais les **modèles non couverts** (impact non estimé faute de
paramètres connus d'EcoLogits) avec leurs tokens générés, et invite à lancer
`agent-carbon-resolve`. Cette commande n'existe pas encore.

Les modèles concernés sont des modèles tiers routés sous un identifiant brut
(ex. `z-ai/glm-4.5-air:free`) que la chaîne Hugging Face existante **ne peut pas**
résoudre tel quel : le suffixe `:free`, les suffixes de date (`-YYYYMMDD`) et les
renommages d'organisation (`z-ai` → `zai-org`) en font des identifiants de repo HF
invalides. Le mapping `nom brut → repo HF canonique` relève de la connaissance du
monde (force d'un LLM) ; la récupération des paramètres (`repo → params`) doit
rester déterministe et vérifiable (métadonnées safetensors HF).

De plus, résoudre un modèle ne sert à rien si les impacts **déjà en base** ne sont
pas recalculés. L'ingestion est idempotente par `msg_id` : relancer `ingest` ne
recalcule pas les events existants. La primitive de recompute n'existe aujourd'hui
que sous forme de script jetable (cf. TODO).

## Principe directeur

Séparer ce que le LLM fait bien de ce qui doit rester vérifiable :

- **Mapping nom → repo HF** : assuré par le LLM (skill).
- **Repo → paramètres** : déterministe, via HF safetensors (CLI).
- **Recompute des impacts** : déterministe (CLI).

Un modèle dont aucun repo HF réel n'est trouvable (ex. `poolside` propriétaire)
**reste non couvert**, honnêtement, plutôt que de se voir attribuer une taille
inventée.

## Architecture

Approche retenue : **primitives CLI fines + skill orchestrateur**.

### A. Sous-commande CLI `agent-carbon resolve`

Actions atomiques, déterministes, testables sans LLM :

| Action                                             | Effet                                                                                                                                                                                    |
| -------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--list [--json]`                                  | Liste les modèles non couverts + tokens générés (réutilise `store.uncovered_by_model`). `--json` pour consommation par le skill.                                                         |
| `--set "<provider>/<model>=<hf_repo>"` (répétable) | Récupère les params sur HF pour `<hf_repo>`, les persiste sous la clé `<provider>/<model>`. Échec géré par item (repo invalide, pas de safetensors, réseau) sans interrompre les autres. |
| `--recompute`                                      | Recalcule les impacts de **tous** les events en erreur (`impacts.error IS NOT NULL`), affiche le delta de couverture (avant/après).                                                      |
| `--forget "<provider>/<model>"` (répétable)        | Retire l'entrée de `model_params` puis recompute → le modèle repasse non couvert. Chemin de revert pour la revue.                                                                        |

`--set` et `--recompute` sont des étapes distinctes : le skill fait N `--set` puis
**un seul** `--recompute` (efficace ; les modèles mappés résolvent alors via le
cache, sans réseau).

Sortie : `--list` et `--set` supportent `--json` (le skill parse) ; `--recompute`
et `--forget` impriment un résumé humain que le skill relaie.

### B. Récupération des paramètres + persistance

- Extraire de `agent_carbon/impact/params.py` un helper
  **`fetch_hf_params(repo: str) -> ParamsResult | None`** : partie `repo → params`
  (`safetensors.total ÷ 1e9`, `arch="dense"`, warning `moe-assumed-dense`),
  offline-safe (lib absente, réseau, 404, `:` invalide → `None`, jamais d'exception).
- `ModelParamsResolver._from_huggingface` existant **réutilise** ce helper
  (model = nom du modèle). `resolve --set` l'appelle avec un repo **arbitraire**
  (≠ nom du modèle).
- Persistance dans **`config.model_params`** (pas de second fichier), entrée
  enrichie d'une provenance :

```json
"anthropic/z-ai/glm-4.5-air:free": {
  "active": 110.4, "total": 110.4, "arch": "dense",
  "source": "resolve", "hf_repo": "zai-org/GLM-4.5-Air"
}
```

`ModelParamsResolver._from_cache` lit déjà `active`/`total`/`arch` ; les clés
`source` et `hf_repo` sont de la provenance (ignorées par le resolver, utilisées
pour la revue/le revert). Aucun changement de schéma (`model_params` est
`dict[str, dict]`).

### C. Recompute (nouvelle méthode store)

`SQLiteStore.recompute_errors(engine, config) -> dict` :

1. Sélectionne les events joints à un impact où `error IS NOT NULL`.
2. Reconstruit l'`InferenceEvent` depuis la ligne `events`.
3. Rappelle `engine.compute(event, config)`.
4. `INSERT OR REPLACE` via `_store_impact`.
5. Retourne `{"before": <n_uncovered_avant>, "after": <n_uncovered_après>}`.

`coverage()` et le rapport se mettent à jour seuls (ils lisent la table `impacts`).
Les `<synthetic>` (0 token) restent en erreur — attendu. Les modèles mappés
résolvent via le cache (pas de réseau) ; les non-mappés retentent HF (timeout 10 s
déjà en place) et restent en erreur s'ils échouent.

### D. Skill `/agent-carbon-resolve`

Le LLM dans la boucle, niveau d'automatisation **« auto + revue après coup »** :

1. `agent-carbon resolve --list --json` → modèles non couverts + tokens. Si vide :
   informer qu'il n'y a rien à résoudre, s'arrêter.
2. Pour chaque modèle, **le LLM propose le repo HF canonique** (connaissance du
   monde). Il **laisse** ceux qu'il ne sait pas mapper (propriétaires, introuvables)
   et les signale.
3. `agent-carbon resolve --set "<k>=<repo>" …` pour tous les mappings proposés → HF
   vérifie et persiste les params.
4. `agent-carbon resolve --recompute` → delta de couverture.
5. **Récap** : tableau modèle → repo → params (Md) → tokens désormais couverts ;
   liste des échecs (`--set` raté) et des non-mappés ; rappel de
   `agent-carbon resolve --forget "<k>"` pour annuler un mapping douteux.

Le skill applique automatiquement (étapes 3–4) puis présente le récap corrigeable
(étape 5) — pas de confirmation préalable, conformément au choix validé.

### E. Mise à jour du rapport

La CTA de `render_uncovered` pointe vers **le skill `/agent-carbon-resolve`** (la
résolution exige le LLM pour le mapping de noms), et non un binaire seul.

## Composants modifiés / créés

- `agent_carbon/impact/params.py` : extraction de `fetch_hf_params(repo)`.
- `agent_carbon/store/db.py` : `recompute_errors(engine, config)`.
- `agent_carbon/resolve/cli.py` (nouveau module) : logique des actions `resolve`
  (`list` / `set` / `recompute` / `forget`), séparée de `__main__` pour rester
  focalisée et testable.
- `agent_carbon/__main__.py` : sous-parseur `resolve` câblé aux actions.
- `agent_carbon/report/cli.py` : CTA `render_uncovered` → `/agent-carbon-resolve`.
- `skills/agent-carbon-resolve/SKILL.md` (nouveau) + déploiement (installeur).

## Gestion des erreurs

- `--set` repo invalide / pas de safetensors / réseau → ligne d'échec par item,
  les autres items continuent ; code de sortie 0 (le skill lit les échecs).
- `huggingface_hub` absent → `fetch_hf_params` renvoie `None` proprement.
- Mapping erroné persisté → `--forget` le retire et recompute (revert).
- `--recompute` sans aucun event en erreur → delta `{before:0, after:0}`, message
  neutre.

## Tests (TDD)

- `fetch_hf_params` : repo invalide (`:` → HFValidationError, offline) → `None` ;
  happy-path via **mock** de `huggingface_hub.model_info` (safetensors total fixe)
  → params attendus (`total/1e9`).
- `recompute_errors` : modèle inconnu en erreur → ajout des params en config →
  recompute → couvert (`error None`, `gwp>0`) ; un `<synthetic>` reste en erreur.
- CLI `resolve --set` / `--forget` / `--recompute` via `main(argv)` sur DB et
  config temporaires (injection de config alignée sur `tests/test_cli_models.py`).
- `--list --json` : structure JSON attendue (modèles + tokens), respecte `--since`
  si fourni.

## Hors périmètre (YAGNI)

- Nettoyage déterministe automatique des noms (`:free`, suffixes date) sans LLM :
  écarté pour l'instant (le mapping passe par le skill). Réintroductible plus tard
  si un usage purement CLI le justifie.
- Saisie du couple MoE `(actif, total)` à la résolution : `fetch_hf_params` suppose
  dense (`moe-assumed-dense`) ; l'affinage MoE reste le sujet de la « Suite 2 » du
  TODO, indépendant.
