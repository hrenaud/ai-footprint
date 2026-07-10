---
name: footprint-config
description: Régler la configuration d'ai-footprint — zone du mix électrique, PUE et WUE de l'hébergement auto-hébergé. À utiliser quand l'utilisateur veut changer sa localisation/mix ou les hypothèses d'infrastructure.
---

# footprint-config

Réglages persistés dans `~/.ai-footprint/config.json`.

## Champs

- `electricity_mix_zone` : code ISO-3 (ex. `FRA`, `DEU`, `USA`). `null` = détecté au prochain `report` interactif.
- `datacenter_pue` : plage `{min, max}` (défaut `1.1`–`1.5`). Plus bas = poste local ; plus haut = datacenter on-prem.
- `datacenter_wue` : litres d'eau par kWh (défaut `0`, local sans refroidissement eau).

## Procédure

1. Lire `~/.ai-footprint/config.json` (créer avec les défauts s'il est absent) pour connaître les valeurs actuelles.

2. **Demander quoi changer** (voir « Comment poser les questions » ci-dessous ; ne pas attendre que l'utilisateur saisisse les valeurs de lui-même) :

   - **Q1 — quel(s) réglage(s) ?** header « Réglage », `multiSelect: true`. Options : `Zone du mix électrique`, `PUE (datacenter)`, `WUE (eau)`. Indiquer la valeur actuelle dans la description de chaque option.

   - Puis une question par réglage choisi (mettre la valeur actuelle en première option « (Recommandé) » ; l'« Other » automatique laisse saisir une valeur libre) :
     - **Zone** — header « Zone ». Options : `FRA` (France, mix bas carbone), `USA`, `DEU`, `Détecter automatiquement` (→ laisser `null`, la détection locale se fait au prochain `report` interactif). Other = autre code ISO-3.
     - **PUE** — header « PUE ». Options : `Poste local (1.0–1.1)`, `Datacenter efficace (1.1–1.3)`, `Datacenter standard (1.1–1.5)`. Other = plage `min–max` sur mesure.
     - **WUE** — header « WUE ». Options : `0 — local, pas de refroidissement eau`, `1.8 — datacenter refroidi à l'eau`. Other = valeur en L/kWh.

3. Écrire le JSON mis à jour (préserver les autres champs, **notamment `model_params`**). Pour le PUE, écrire `{"min": …, "max": …}`. Pour « Détecter automatiquement », mettre `electricity_mix_zone` à `null`.

4. Confirmer les valeurs enregistrées.

Ne jamais toucher `model_params` (cache des modèles auto-hébergés, géré par `ai-footprint models`).

## Comment poser les questions (indépendant de l'outil)

Cette skill peut tourner sous plusieurs agents (Claude Code, OpenCode, Pi…). Pose les questions avec le mécanisme interactif du runtime **s'il en a un**, sinon en texte :

- **Claude Code** : outil `AskUserQuestion` (intitulé, `header`, options ; « Other » ajouté d'office).
- **OpenCode** : outil `question` (header, intitulé, liste d'options, réponse libre).
- **Pi** (earendil-works) : pas de tool natif (cœur = `read`/`bash`/`edit`/`write`) ; question structurée via extension (`pi-askuserquestion` / `pi-ask-user`), sinon repli texte ci-dessous.
- **Serveur/plateforme MCP** : elicitation MCP (`elicitation/create` avec un JSON schema).
- **Sinon** : présenter chaque question en clair, options **numérotées**, et **attendre** la réponse.

Dans tous les cas : une option = une valeur exploitable, prévoir une saisie libre (« autre »), et n'écrire la config qu'**après** avoir reçu les réponses.
