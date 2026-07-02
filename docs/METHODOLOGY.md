# Méthodologie — comment l'impact est évalué

agent-carbon **ne réécrit aucun modèle d'impact**. Il collecte les métadonnées
d'usage (tokens, modèle, horodatage) et délègue tout le calcul environnemental à
**[EcoLogits](https://github.com/mlco2/ecologits)** (moteur offline, multi-critères,
multi-phases). Ce document décrit ce qu'on envoie à EcoLogits, ce qu'on en reçoit,
et les choix de méthodologie (avec leurs limites).

## Pourquoi EcoLogits

L'audit de `claude-carbon` (mono-critère CO₂, facteurs dérivés du **prix**) a montré
les limites d'une modélisation maison. agent-carbon s'appuie sur EcoLogits :

- **multi-critères** (5 critères, pas seulement le CO₂) ;
- **multi-phases** (usage + fabrication) ;
- **offline** (aucune donnée envoyée sur le réseau pour le calcul) ;
- **maintenu et revu** par une communauté spécialisée.

## Les échanges avec EcoLogits

Pour **chaque message d'inférence** (un appel modèle dans un transcript), agent-carbon
fait un calcul. Deux chemins selon que le modèle est connu d'EcoLogits ou non.

### Ce qu'on envoie

| Donnée                 | Source                                                                        | Remarque                                              |
| ---------------------- | ----------------------------------------------------------------------------- | ----------------------------------------------------- |
| `provider`             | transcript (défaut `anthropic`)                                               | identifie le fournisseur                              |
| `model_name`           | transcript, après application des alias                                       | ex. `claude-opus-4-8`                                 |
| `output_token_count`   | usage du message                                                              | **seuls les tokens de sortie** alimentent le calcul   |
| `request_latency`      | **estimée** : `output_tokens / throughput_tok_s` (défaut 50 tok/s, min 0,5 s) | influe sur la part « énergie au repos » du datacenter |
| `electricity_mix_zone` | config (défaut USA, configurable)                                             | mix électrique du datacenter                          |

Pour un **modèle auto-hébergé / non reconnu**, on fournit en plus les **paramètres
du modèle** (actif/total, en milliards), le **PUE** (plage 1.1–1.5 par défaut) et le
**WUE** du datacenter.

### Ce qu'on reçoit

Pour chaque message, EcoLogits renvoie les **5 critères**, chacun en **fourchette
`(min, max)`**, répartis en deux **phases** :

| Critère  | Unité    | Quoi                                          |
| -------- | -------- | --------------------------------------------- |
| `energy` | kWh      | énergie consommée                             |
| `gwp`    | kg CO₂eq | réchauffement global                          |
| `adpe`   | kg Sbeq  | épuisement des ressources abiotiques (métaux) |
| `pe`     | MJ       | énergie primaire                              |
| `wcf`    | L        | empreinte eau                                 |

- **usage** : l'inférence elle-même.
- **embodied** : la fabrication/amortissement du matériel (gwp, adpe, pe).

agent-carbon stocke ces fourchettes telles quelles (table `impacts`), avec la
version de méthodologie utilisée. Le rapport agrège ensuite par total / projet /
modèle, et affiche une **valeur centrale `~`** (moyenne des bornes) accompagnée de la
**plage min–max**.

### Les deux chemins de calcul

1. **Modèle reconnu EcoLogits** → `llm_impacts()` (le registre EcoLogits porte déjà
   l'architecture et les paramètres du modèle).
2. **Modèle inconnu** → on résout les paramètres (voir plus bas) puis on appelle
   `compute_llm_impacts()` directement, avec le mix électrique de la zone et la plage
   PUE. La plage PUE (min/max) génère la fourchette min/max des résultats.

## Choix méthodologiques (et pourquoi)

- **Tokens de sortie uniquement.** Le coût d'inférence dominant est la génération.
  Les tokens d'entrée et de cache **ne sont pas** comptés dans l'impact (ils sont
  toutefois affichés dans « tokens utilisés », pour la transparence). C'est une
  approximation assumée, alignée sur EcoLogits.
- **Latence estimée.** Le transcript ne donne pas la durée réelle de l'appel ; on
  l'estime via un débit (`throughput_tok_s`). Approximation, configurable.
- **Fourchettes min–max, jamais un point.** L'incertitude est **irréductible** :
  - la **région datacenter** d'Anthropic (donc son mix électrique réel) est inconnue ;
  - le **PUE** d'un datacenter varie (plage 1.1–1.5).
    On documente cette incertitude plutôt que de la dissimuler derrière un chiffre
    faussement précis. La valeur centrale `~` n'est qu'un repère.
- **Zone électrique configurable.** Défaut USA ; réglable (ex. FRA) via
  `/agent-carbon-config`. Elle change fortement le GWP (le mix varie d'un facteur
  ~10 entre pays).

## Modèles auto-hébergés et tiers

Beaucoup de modèles ne sont pas dans le registre EcoLogits (inférence locale, modèles
open-weight, routeurs tiers). Pour estimer leur impact, il faut leurs **paramètres**.
agent-carbon les résout en cascade :

1. **Registre EcoLogits** (si finalement reconnu) — gère dense et **MoE** (actif/total).
2. **Cache config** (`~/.agent-carbon/config.json`) — params déclarés ou résolus
   précédemment, avec provenance (`source`, `hf_repo`).
3. **Hugging Face** — nombre de paramètres lu depuis les métadonnées safetensors
   (`total ÷ 1e9`, en **milliards**). Offline-safe : tout échec ⇒ non résolu.
4. **Sinon** — le modèle reste **non couvert** (impact non estimé), mis en file
   d'attente.

**Actif vs total (MoE).** Pour un Mixture-of-Experts, l'énergie dépend des paramètres
**actifs** par token (≪ total). Confondre actif et total surestime fortement l'énergie
(observé ~10× sur des modèles 120–225 Md). Le couple correct `(actif, total)` donne
une estimation honnête. _(Limite actuelle : la résolution automatique via Hugging Face
suppose « dense » ; un couple MoE se déclare à la main — cf. backlog.)_

> **Unité (piège récurrent)** : les paramètres EcoLogits sont **en milliards**
> partout. `safetensors.total` (compte brut) est divisé par `1e9`.

## Lire les chiffres : couverture

La sortie d'`ingest` (et le rapport) distingue :

- **mesurés** — impact estimé par EcoLogits.
- **non couverts** — modèle hors périmètre : l'event est **conservé** mais son impact
  n'est **pas** estimé (afficher un faux chiffre serait pire) et il est **exclu des
  totaux**. Deux familles :
  - les placeholders internes `<synthetic>` de Claude Code (0 token, aucune inférence
    réelle) — non couvrables par nature, exclus du rapport ;
  - les vrais modèles tiers/auto-hébergés non résolus — **résolubles** vers un repo
    Hugging Face via `agent-carbon resolve` (skill `/agent-carbon-resolve`).

La résolution d'un modèle déclenche un **recalcul** des impacts déjà en base
(`resolve --recompute`), sans re-parser les transcripts.

## Reproductibilité

Chaque impact stocke sa `methodology_version`
(`engine=…;ecologits=…`). On peut ainsi recalculer après une mise à jour d'EcoLogits
et comparer les résultats anciens/nouveaux.

## Estimation des paramètres des modèles auto-hébergés

Quand un modèle n'est ni dans le registre EcoLogits ni doté de metadata
safetensors, ses paramètres sont **estimés depuis la taille des fichiers** du
repo Hugging Face. Le dtype (octets/param) est déduit du nom du repo
(`-4bit` → 0.5, `-int8` → 1, `-fp16`/`-bf16` → 2, `-fp32` → 4) ; s'il est
indétectable, on produit une **fourchette** (0.5–2 octets/param, soit un
rapport 1:4 sur les params) plutôt qu'une valeur unique. Ces estimations
portent un warning de provenance en base et les modèles concernés sont
signalés dans le rapport (« Params estimés depuis la taille des fichiers »).

## Limites assumées

- Impact piloté par les **tokens de sortie** (entrée/cache non comptés).
- **Région datacenter inconnue** → fourchettes ; défaut mix USA (configurable).
- **Latence estimée**, pas mesurée.
- **Inférence locale / énergie du poste de travail** : hors périmètre (seule
  l'inférence est modélisée, pas la consommation de la machine de l'utilisateur).
- **MoE auto-résolu en dense** par le tier Hugging Face (le couple actif/total se
  déclare manuellement pour l'instant).

## Références

- EcoLogits — https://github.com/mlco2/ecologits
- CodeCarbon — https://github.com/mlco2/codecarbon
- claude-carbon — audit d'origine et UX de reporting
