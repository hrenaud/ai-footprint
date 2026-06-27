# agent-carbon — Kickoff / handoff

> Brief de démarrage rédigé depuis une session `mcp-nr` après analyse critique de **claude-carbon**.
> But : repartir d'un projet propre, **vendor-neutral** et **multi-critères**, en s'appuyant sur **EcoLogits** comme moteur d'impact plutôt que de réécrire (mal) la modélisation.
> Prochaine étape : ouvrir une session **ici** et lancer le skill `brainstorming` pour cadrer le MVP (voir « Décisions à trancher »).

## Pourquoi ce projet existe

`claude-carbon` (`gwittebolle/claude-carbon`, MIT) est un **compteur d'inférence opérationnelle, mono-critère (CO₂), soudé à Claude Code**. Audit mené sur la base réelle (`~/.claude/claude-carbon/carbon.db`, 702 sessions). Conclusions :

### Les 9 trous, réordonnés par gravité

| #   | Trou                                                                                                   | Effet                 | EcoLogits le règle ?      |
| --- | ------------------------------------------------------------------------------------------------------ | --------------------- | ------------------------- |
| 1   | `cache_read_factor = 0.08` deviné (90 % des tokens en _nombre_, mais ~3 % de l'énergie réelle ici)     | ×3 (faible chez nous) | absorbé dans ranges       |
| 2   | Facteurs **extrapolés du prix** (Opus=3×Sonnet, Fable=2×Opus) ; seul Sonnet mesuré                     | ×3                    | ✅ basé sur taille modèle |
| 3   | **Batching / utilisation GPU** non modélisé                                                            | ×2–10                 | absorbé dans ranges       |
| 4   | **Embodied / fabrication** (puces, HBM, châssis, bâtiment)                                             | +20–50 %              | ✅ phase `embodied`       |
| 5   | **Mix datacenter figé** à 287 gCO₂e/kWh (région AWS réelle inconnue)                                   | ×0,1–2                | ✅ `electricity_mix_zone` |
| 6   | Couverture : purge transcripts 30 j + lignes legacy `methodology_version 1` figées                     | biais ↓               | côté collecte (à nous)    |
| 7   | **Eau** (onsite WUE stocké mais jamais calculé + offsite production élec)                              | indicateur séparé     | ✅ `wcf` (L)              |
| 8   | **ADP / métaux** + mono-critère                                                                        | indicateurs séparés   | ✅ `adpe`, `pe`           |
| 9   | Inférence **locale** exclue (ou facturée ×1000 avec facteurs Claude) ; **terminal** utilisateur absent | mineur à moyen        | ❌ à traiter à part       |

### Le chiffre « 100 kg » est de la fausse précision

Recalcul propre des sessions Claude (tokens × facteurs actuels) : **central ~87 kg** (la valeur stockée 80,5 kg diffère à cause des lignes legacy sonnet → trou #6).
Fourchette défendable en faisant varier mix + cache_read :

| Scénario | Hypothèses                     | Total       |
| -------- | ------------------------------ | ----------- |
| Bas      | grille ~50 g/kWh + cache 0,05  | **~15 kg**  |
| Central  | 287 g/kWh + cache 0,08         | **~87 kg**  |
| Haut     | grille ~400 g/kWh + cache 0,15 | **~125 kg** |

→ **facteur ~8**, piloté quasi entièrement par la région datacenter d'Anthropic (non publiée). L'incertitude est **irréductible** : un bon outil ne la supprime pas, il l'**affiche en fourchette**.

## Décision d'architecture

Séparer ce que `claude-carbon` confond :

```
[A] COLLECTE   (spécifique par outil)     ← Claude Code, Codex, PI, Hermes…
       ↓  {provider, modèle, tokens in/out/cache, timestamp, projet}
[B] MODÉLISATION D'IMPACT  (agnostique)   ← EcoLogits
       ↓  {gwp, adpe, pe, énergie, eau} × {usage, embodied} × [min,max]
[C] STOCKAGE + REPORTING                   ← à nous (DB + rapport)
```

- **[B] = EcoLogits** (`/mlco2/ecologits`, GenAI Impact, lignée Boavizta, réputation High). Multi-provider (`openai`, `anthropic`, `mistralai`, `google`, `huggingface`…), multi-critères, multi-phases, **RangeValue (min/max/mean) natif**, mix configurable par zone ISO (`FRA`, `USA`, `WOR`…). On n'écrit PAS de modèle d'impact.
- **[A]** = petits collecteurs/parsers, un par outil. C'est la seule vraie valeur à écrire.
- **[C]** = DB + rapport (peut s'inspirer de l'UX de claude-carbon).

### Ce qui reste à NOUS (EcoLogits ne couvre pas)

- **Inférence locale** (ex. qwen sur Mac Apple Silicon) : EcoLogits suppose un datacenter. À modéliser à part = `énergie_Mac × grille FRA` (~56 g/kWh). Ordre de grandeur mesuré : tout le local historique ≈ **~20 g** (vs 30 kg facturés à tort par claude-carbon).
- **Terminal utilisateur** (le Mac pendant un appel cloud) : ~0,25 kg sur tout l'historique → minime mais réel, absent partout.
- **Entraînement / dév modèle** : inconnu, amorti, hors périmètre (comme EcoLogits).

## Détails techniques utiles

- EcoLogits s'utilise nativement en **instrumentation live** (`EcoLogits.init(providers=[...])` puis appels via le SDK). Pour nous il faut l'alimenter depuis des **tokens stockés** (Claude Code ne passe pas par notre SDK) → vérifier l'API d'impact « offline » (model name + token counts) lors du brainstorming.
- Données de réf claude-carbon : DB `~/.claude/claude-carbon/carbon.db` (table `sessions`, colonnes `input_tokens` [inclut cache_write], `cache_creation_tokens`, `cache_read_tokens`, `output_tokens`, `model`, `co2_grams`, `excluded`, `methodology_version`). Repo `~/code/claude-carbon` (lire `METHODOLOGY.md`).
- Pour modèles fermés (Claude), EcoLogits **estime** les paramètres → incertitude réelle mais bornée et documentée (≠ proxy tarifaire).

## Décisions à trancher (pour le brainstorming)

1. **Périmètre MVP** : quel(s) outil(s) en collecte d'abord ? (Claude Code seul pour valider la chaîne, ou direct multi-outils ?)
2. **Alimentation EcoLogits** : live vs offline depuis tokens stockés — quelle API exacte ?
3. **Reprise de l'existant** : on relit la DB claude-carbon (lecture seule, pérenne) ou on repart de zéro sur les transcripts JSONL ?
4. **Cas local** : module séparé `local_inference` (élec machine × grille locale) — quel facteur Wh/token pour Apple Silicon ?
5. **Sortie** : rapport multi-critères + fourchettes — quel format (CLI ? statusline ? export) ?
6. **Langage** : EcoLogits = Python → tout en Python, ou collecteurs séparés ?

## Statut

- [x] Audit claude-carbon + inventaire des trous
- [x] Décision : EcoLogits comme moteur d'impact
- [x] Archi [A]/[B]/[C] posée
- [ ] Brainstorming MVP (à faire ici, session dédiée)
- [ ] Setup projet (Python, deps, EcoLogits)
- [ ] Premier collecteur
