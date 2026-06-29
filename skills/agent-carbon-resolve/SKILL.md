---
name: agent-carbon-resolve
description: Résout les modèles « non couverts » d'agent-carbon (impact non estimé) en mappant leur nom vers un repo Hugging Face, récupère les paramètres et recalcule les impacts. À utiliser quand le rapport agent-carbon liste des modèles non couverts, ou via /agent-carbon-resolve.
---

Résout les modèles à impact non estimé : tu fournis le mapping nom→repo Hugging Face (ta connaissance du monde), la CLI vérifie les paramètres sur HF et recalcule les impacts en base. Applique automatiquement puis présente un récap corrigeable.

## Localiser le binaire

```bash
AC="$(command -v agent-carbon || echo "$HOME/.agent-carbon/src/.venv/bin/agent-carbon")"
[ -x "$AC" ] || { echo "agent-carbon non installé."; exit 1; }
```

## Étapes

1. **Lister les non couverts** : `"$AC" resolve --list --json`. Si la liste est vide, informer qu'il n'y a rien à résoudre et s'arrêter.

2. **Proposer un repo HF canonique pour chaque modèle**, à partir de l'identifiant brut. Retirer les suffixes de routeur (`:free`), les suffixes de date (`-YYYYMMDD`), corriger les noms d'organisation (ex. `z-ai` → `zai-org`, `openai/gpt-oss-120b:free` → `openai/gpt-oss-120b`). **Laisser de côté** les modèles propriétaires ou introuvables sur HF (ex. `poolside/…`) : ne pas inventer de repo.

   **Cas MoE** (Mixture-of-Experts) : si le modèle est un MoE (ex. `nemotron-3-super-120b-a12b`, `laguna-m.1`, séries Qwen3 `*-A3B`), le total HF (safetensors) **surestimerait ~10×** l'énergie, qu'EcoLogits calcule sur les params **actifs**. Ajouter `:<actifs>` (params actifs en milliards) au repo : le total reste HF, l'actif est ta valeur. L'indice est souvent dans le nom (`…120b-a12b` → ~12 Md actifs). Si l'actif n'est pas connu de façon fiable, traiter en dense (sans suffixe) et le signaler dans le récap.

3. **Appliquer le mapping et recalculer** en une invocation (un seul recompute) :

```bash
"$AC" resolve \
  --set "anthropic/z-ai/glm-4.5-air:free=zai-org/GLM-4.5-Air" \
  --set "anthropic/openai/gpt-oss-120b:free=openai/gpt-oss-120b" \
  --set "nvidia/nemotron-3-super-120b-a12b=nvidia/Nemotron-...:12" \
  --list --json
```

`--set "P/M=repo"` récupère les params sur HF (dense, échec géré par item) ; `--set "P/M=repo:<actifs>"` déclare un MoE (total HF, actif saisi, `arch=moe`) ; le recompute est automatique quand la config change ; `--list --json` final montre ce qui reste non couvert.

4. **Présenter un récap** : pour chaque modèle — repo retenu, params (Md), succès/échec. Lister les modèles laissés de côté (propriétaires/introuvables) et ceux dont le `--set` a échoué. Indiquer le delta de couverture (sortie « Recompute : X → Y »).

5. **Rappeler le revert** : un mapping douteux se retire avec
   `"$AC" resolve --forget "<provider>/<model>"` (retire l'entrée et recalcule).

## Garde-fous

- Le **total vient toujours de HF** (vérifiable) ; tu ne fournis que le nom du repo, jamais une taille inventée. Seul l'**actif d'un MoE** relève de ta connaissance (généralement lisible dans le nom, ex. `-a12b`) : en cas de doute, rester dense plutôt qu'inventer un actif.
- Un modèle sans repo HF réel reste non couvert — c'est honnête, ne pas forcer.
- Les placeholders `<synthetic>` n'apparaissent jamais ici (déjà exclus des non couverts).
