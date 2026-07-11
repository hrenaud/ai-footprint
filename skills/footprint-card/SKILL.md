---
name: footprint-card
description: Génère une card PNG partageable (1080×1080) résumant l'empreinte environnementale des sessions d'IA — carbone (GWP) en héro + 4 critères avec jauges min–max + top projets — via ai-footprint. À utiliser quand l'utilisateur veut partager/exporter son empreinte en image, ou tape /footprint-card.
---

Lance `ai-footprint card` pour générer une image PNG résumant l'empreinte, puis indique à l'utilisateur où trouver le(s) fichier(s) exporté(s).

## Étapes

1. Localiser le binaire et rafraîchir la base (silencieux) :

```bash
AC="$(command -v ai-footprint || echo "$HOME/.ai-footprint/src/.venv/bin/ai-footprint")"
[ -x "$AC" ] || { echo "ai-footprint non installé. Installer : curl -fsSL https://raw.githubusercontent.com/hrenaud/ai-footprint/main/install.sh | bash"; exit 1; }
"$AC" ingest >/dev/null 2>&1 || true
```

2. **Poser les options à l'utilisateur** (voir « Comment poser les questions » ci-dessous), toujours — même s'il a passé des flags : dans ce cas, mets la valeur correspondante en première option « (Recommandé) ». Deux questions :

   - **Période** — header « Période ». Options : `Tout l'historique` (recommandé, pas de `--since`), `30 derniers jours`, `7 derniers jours`. L'« Other » automatique laisse saisir une date précise (`2026-06-27`, `27/06/2026`, `27/06/26` ou ISO 8601).
   - **Thème** — header « Thème ». Options : `Clair` (recommandé, défaut, pas de flag), `Sombre` (`--theme dark`), `Les deux` (`--theme both`).

3. **Construire les flags depuis les réponses**, puis lancer la génération. Pour une période relative, calculer la date de début :

```bash
# ex. « 7 derniers jours » : SINCE=$(python3 -c "import datetime;print(datetime.date.today()-datetime.timedelta(days=7))")
"$AC" card [FLAGS]
```

`[FLAGS]` = concaténation de : `--since <date>` (si période ≠ tout), `--theme dark|both` (si thème ≠ clair). Ne jamais inventer d'autres flags que ceux-ci.

4. Si Chrome/Chromium est introuvable, la commande échoue avec un message clair (`brew install --cask google-chrome` sur macOS, `apt install chromium` sur Linux) : relaie ce message à l'utilisateur sans l'interpréter.

5. Affiche le(s) chemin(s) PNG exporté(s) (imprimés par la commande, un par ligne — `~/.ai-footprint/exports/` par défaut), et rappelle en une phrase que chaque valeur est posée sur sa fourchette min–max (incertitude irréductible sur la région datacenter), pas une valeur unique.

## Comment poser les questions (indépendant de l'outil)

Cette skill peut tourner sous plusieurs agents (Claude Code, OpenCode, Pi…). Pose les questions avec le mécanisme interactif du runtime **s'il en a un**, sinon en texte :

- **Claude Code** : outil `AskUserQuestion` (intitulé, `header`, options ; « Other » ajouté d'office).
- **OpenCode** : outil `question` (header, intitulé, liste d'options, réponse libre).
- **Pi** (earendil-works) : pas de tool natif (cœur = `read`/`bash`/`edit`/`write`) ; question structurée via extension (`pi-askuserquestion` / `pi-ask-user`), sinon repli texte ci-dessous.
- **Serveur/plateforme MCP** : elicitation MCP (`elicitation/create` avec un JSON schema).
- **Sinon** (runtime sans tool dédié) : présenter chaque question en clair, options **numérotées**, et **attendre** la réponse avant de continuer.

Dans tous les cas : une option = une valeur exploitable, prévoir une saisie libre (« autre »), et ne **construire/lancer la commande qu'après** avoir reçu les réponses. Ne jamais deviner à la place de l'utilisateur ni exécuter avant réponse.

> **Piège JSON (`AskUserQuestion` & tools MCP)** : l'entrée doit être du JSON **pur**. Chaque `question`/`label`/`description` est une chaîne littérale **déjà assemblée** — pas de concaténation (`"a" + "b"`), pas d'expression, pas de backslash non échappé (`\` → `\\` ou `/`). Sinon l'appel échoue avec « Invalid tool parameters / could not be parsed as JSON ».
