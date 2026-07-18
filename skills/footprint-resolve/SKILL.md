---
name: footprint-resolve
description: Résout les modèles « non couverts » d'ai-footprint (impact non estimé) en mappant leur nom vers un repo Hugging Face, récupère les paramètres et recalcule les impacts. À utiliser quand le rapport ai-footprint liste des modèles non couverts, ou via /footprint-resolve.
---

Résout les modèles à impact non estimé : tu fournis le mapping nom→repo Hugging Face (ta connaissance du monde), la CLI vérifie les paramètres sur HF et recalcule les impacts en base. Applique automatiquement puis présente un récap corrigeable.

## Localiser le binaire

```bash
AC="$(command -v ai-footprint || echo "$HOME/.ai-footprint/src/.venv/bin/ai-footprint")"
[ -x "$AC" ] || { echo "ai-footprint non installé."; exit 1; }
```

## Étapes

> **Entrée proactive** : ce skill peut désormais être invoqué automatiquement
> par `footprint-report`, `footprint-card`, ou par le nudge de démarrage de
> session (hook `SessionStart` Claude Code, event `session.created` OpenCode,
> event `session_start` Pi), en plus d'une invocation manuelle par
> l'utilisateur. Le comportement du skill est identique dans les deux cas.

1. **Lister les non couverts** : `"$AC" resolve --list --json`. Si la liste est vide, informer qu'il n'y a rien à résoudre et s'arrêter.

2. **Proposer un repo HF canonique pour chaque modèle**, à partir de l'identifiant brut. Retirer les suffixes de routeur (`:free`), les suffixes de date (`-YYYYMMDD`), corriger les noms d'organisation (ex. `z-ai` → `zai-org`, `openai/gpt-oss-120b:free` → `openai/gpt-oss-120b`). **Laisser de côté** les modèles propriétaires ou introuvables sur HF (ex. `poolside/…`) : ne pas inventer de repo.

   **Cas MoE** (Mixture-of-Experts) : si le modèle est un MoE (ex. `nemotron-3-super-120b-a12b`, `laguna-m.1`, séries Qwen3 `*-A3B`), le total HF (safetensors) **surestimerait ~10×** l'énergie, qu'EcoLogits calcule sur les params **actifs**. Ajouter `:<actifs>` (params actifs en milliards) au repo : le total reste HF, l'actif est ta valeur. L'indice est souvent dans le nom (`…120b-a12b` → ~12 Md actifs). Si l'actif n'est pas connu de façon fiable, traiter en dense (sans suffixe) et le signaler dans le récap.

2bis. **Secours : recherche web** — si aucun repo canonique n'est déductible de l'identifiant (modèle trop récent, id de routeur opaque type catalogue NVIDIA NIM) **et** que le runtime dispose d'un tool de recherche web : chercher la fiche du modèle (page Hugging Face, annonce de l'éditeur) pour retrouver le repo HF réel et, le cas échéant, l'actif MoE. Le web ne fournit que **le nom du repo** et **l'actif MoE** — ne jamais reprendre un _nombre de paramètres_ lu dans un article/blog : le total sera vérifié sur HF par la CLI. Si la fiche HF n'existe pas, le modèle **reste non couvert**. Sans tool web, laisser de côté (comportement normal).

2b. **Faire confirmer les mappings** avant d'écrire quoi que ce soit (ne pas appliquer d'office ; voir « Comment poser les questions » ci-dessous). Question header « Mappings », choix multiple : une option par modèle résolu, libellée `modèle → repo` (préciser « MoE, N Md actifs » le cas échéant), toutes pré-retenues. L'utilisateur retire ce qu'il refuse ; une saisie libre laisse corriger un repo à la main. N'appliquer à l'étape 3 **que** les mappings retenus. (S'il ne reste aucun modèle résolvable à proposer, informer et s'arrêter sans poser la question.)

3. **Appliquer les mappings retenus et recalculer** en une invocation (un seul recompute) :

```bash
"$AC" resolve \
  --set "anthropic/z-ai/glm-4.5-air:free=zai-org/GLM-4.5-Air" \
  --set "anthropic/openai/gpt-oss-120b:free=openai/gpt-oss-120b" \
  --set "nvidia/nemotron-3-super-120b-a12b=nvidia/Nemotron-...:12" \
  --list --json
```

`--set "P/M=repo"` récupère les params sur HF (dense, échec géré par item) ; `--set "P/M=repo:<actifs>"` déclare un MoE (total HF, actif saisi, `arch=moe`) ; le recompute est automatique quand la config change ; `--list --json` final montre ce qui reste non couvert.

4. **Présenter un récap** : pour chaque modèle — repo retenu, params (Md), succès/échec, et **la source si le mapping vient d'une recherche web** (URL de la fiche modèle d'où viennent le repo et l'actif). Lister les modèles laissés de côté (propriétaires/introuvables) et ceux dont le `--set` a échoué. Indiquer le delta de couverture (sortie « Recompute : X → Y »).

5. **Rappeler le revert** : un mapping douteux se retire avec
   `"$AC" resolve --forget "<provider>/<model>"` (retire l'entrée et recalcule).

## Garde-fous

- Le **total vient toujours de HF** (vérifiable) ; tu ne fournis que le nom du repo, jamais une taille inventée. Seul l'**actif d'un MoE** relève de ta connaissance (généralement lisible dans le nom, ex. `-a12b`) : en cas de doute, rester dense plutôt qu'inventer un actif.
- Un modèle sans repo HF réel reste non couvert — c'est honnête, ne pas forcer.
- **Recherche web (étape 2bis)** : elle ne sert qu'à trouver le _nom du repo_ (et l'_actif MoE_) — jamais un nombre de paramètres pris dans un article/blog. Repo inventé → la CLI répond `hf-unresolved` ; actif aberrant → `active-gt-total`. Citer la source dans le récap.
- Les placeholders `<synthetic>` n'apparaissent jamais ici (déjà exclus des non couverts).

## Comment poser les questions (indépendant de l'outil)

Cette skill peut tourner sous plusieurs agents (Claude Code, OpenCode, Pi…). Pose la confirmation avec le mécanisme interactif du runtime **s'il en a un**, sinon en texte :

- **Claude Code** : outil `AskUserQuestion` (intitulé, `header`, options ; « Other » ajouté d'office).
- **Codex** : utiliser `request_user_input` si l’outil est exposé par le runtime ; sinon, utiliser le repli texte numéroté ci-dessous et attendre la réponse avant de poursuivre.
- **OpenCode** : outil `question` (header, intitulé, liste d'options, réponse libre).
- **Pi** (earendil-works) : pas de tool natif (cœur = `read`/`bash`/`edit`/`write`) ; question structurée via extension (`pi-askuserquestion` / `pi-ask-user`), sinon repli texte ci-dessous.
- **Serveur/plateforme MCP** : elicitation MCP (`elicitation/create` avec un JSON schema).
- **Sinon** : présenter la liste des mappings proposés, **numérotée**, et **attendre** que l'utilisateur dise lesquels retenir.

Dans tous les cas : n'appliquer les `--set` qu'**après** confirmation ; ne jamais résoudre d'office un modèle que l'utilisateur n'a pas retenu.
