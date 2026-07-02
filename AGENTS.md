# agent-carbon — instructions projet

Compteur d'impact environnemental multi-critères pour les sessions d'IA, via

**EcoLogits** (aucune modélisation réécrite). Voir le README pour le produit.

## Documentation (à tenir à jour)

| Fichier                                                                                                                                          | Public / rôle                                                          |
| ------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------- |
| [README.md](README.md)                                                                                                                           | utilisateurs (non développeurs)                                        |
| [CONTRIBUTING.md](CONTRIBUTING.md)                                                                                                               | développeurs : architecture, schéma DB, dev, tests                     |
| [docs/METHODOLOGY.md](docs/METHODOLOGY.md)                                                                                                       | comprendre comment les impacts sont calculés (échanges EcoLogits)      |
| [CHANGELOG.md](CHANGELOG.md)                                                                                                                     | journal des évolutions                                                 |
| [docs/comparaison-donnees-outils.md](docs/comparaison-donnees-outils.md)                                                                         | comparatifs des informations des outils                                |
| [docs/superpowers/specs/2026-07-02-qualite-lecture-resolution-design.md](docs/superpowers/specs/2026-07-02-qualite-lecture-resolution-design.md) | backlog technique : audit qualité lecture données & résolution modèles |

> **À chaque tâche terminée : mettre à jour la doc concernée.** Ne pas toucher au
> CHANGELOG à la main : `agent-carbon release bump` le génère automatiquement
> depuis les commits conventionnels au moment de la release (cf. § Réaliser une
> release).

## Rappels projet

- **Tests** : `.venv/bin/python -m pytest` (TDD ; voir CONTRIBUTING).
- **Deux codebases, une base** : le repo dev **et** le clone installé

  `~/.agent-carbon/src` (qui fournit le binaire `agent-carbon` et les skills)

  partagent la base `~/.agent-carbon/carbon.db`. Après un changement de code ou de

  skill mergé sur `main`, **créer un tag de release** (`agent-carbon release bump

  <patch|minor|major>`) puis **relancer le script d'install**

  (`curl -fsSL https://raw.githubusercontent.com/hrenaud/agent-carbon/main/install.sh | bash`)

  pour que le binaire et les skills installés soient à jour.

- **`~/.agent-carbon/src` est read-only pour l'agent.** Ce clone n'est jamais une
  cible de travail : ni commande git (`commit`, `push`, `reset`, `pull`, `fetch`,
  `tag -d`…), ni édition de fichier, ni exécution de `release bump` dessus. Tout le
  travail git (commit, push, `release bump`, tag) se fait **ici, dans le repo dev**
  — avec le binaire du venv **local** (`.venv/bin/agent-carbon`, jamais
  `agent-carbon` global, qui pointe vers ce clone et y commiterait/taggerait à sa
  place). La seule opération autorisée sur ce clone est sa **réinstallation
  complète** via `install.sh` (voir ci-dessus), une fois le repo dev poussé et
  taggé — jamais une correction manuelle, même pour "réparer" un état incohérent.

- **Paramètres EcoLogits en milliards** partout (piège récurrent — cf. METHODOLOGY).

## Réaliser une release

**Toujours passer par l'outil, jamais à la main** (il bump `pyproject.toml` **et**
`agent_carbon/__init__.py`, génère le CHANGELOG depuis les commits conventionnels,
crée le commit `chore(release): X.Y.Z` + tag `vX.Y.Z`, puis push `origin main --tags`) :

```bash
.venv/bin/agent-carbon release bump <patch|minor|major>   # --no-push pour ne pas pousser
```

- **Toujours le binaire du venv local** (`.venv/bin/agent-carbon`), jamais la
  commande globale `agent-carbon` — celle-ci pointe vers le clone installé
  (`~/.agent-carbon/src`) et y ferait le commit/tag au lieu du repo dev (cf. §
  Rappels projet).
- `patch` : corrections backward-compatibles · `minor` : nouvelles features
  backward-compatibles · `major` : changements incompatibles.
- Prérequis : arbre propre, sur `main`, tag cible inexistant.
- Après le push, **relancer le script d'install** (voir ci-dessus) pour aligner le
  clone installé.
- Détail complet du process : cf. CONTRIBUTING (§ Release).
