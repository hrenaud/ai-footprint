# Renommage en AI Footprint — spec

**Date** : 2026-07-09 · **Statut** : validé (nom), à implémenter

## Décision

Le produit **agent-carbon** est renommé **AI Footprint** :

- **Nom produit** : AI Footprint
- **Nom technique** (package PyPI, binaire, repo GitHub) : `ai-footprint`
- **Paquet coquille** : `agent-footprint` est publié sur PyPI comme coquille
  (paquet vide dépendant de `ai-footprint`) pour verrouiller le nom alternatif
  et rediriger les installations erronées.
- **Base de données** : `carbon.db` → `ai-footprint.db`
- **Skills** : préfixe simplifié `footprint-*`

### Pourquoi ce nom

- « Footprint » (empreinte) est le seul terme anglais qui couvre d'office le
  multi-critères (carbon/water/material footprint) sans énumérer — l'outil
  mesure GWP, énergie, eau et ADPe, « carbon » sous-vendait.
- « AI » plutôt que « agent » : audience grand public (cible du README),
  pérennité si l'outil couvre un jour des usages non-agentiques, meilleure
  découvrabilité (« AI footprint » est ce que les gens cherchent).
- Grammaticalement correct (juxtaposition nom + nom, singulier générique
  idiomatique pour un nom de produit).

### Disponibilité vérifiée (2026-07-09)

| Registre                | `ai-footprint`              | `agent-footprint` |
| ----------------------- | --------------------------- | ----------------- |
| PyPI                    | ✅ libre                    | ✅ libre          |
| GitHub (homonyme exact) | ⚠️ quelques repos morts ≤5★ | ✅ aucun          |
| Homebrew (core + cask)  | ✅ libre                    | ✅ libre          |

Noms éliminés : `agent-impact` et `ecotrace` (pris sur PyPI), `ai-impacts`
(collision avec aiimpacts.org, organisation de recherche connue).

## Périmètre du renommage

### 1. Code et packaging (repo dev)

| Élément                     | Avant                                         | Après                                                |
| --------------------------- | --------------------------------------------- | ---------------------------------------------------- |
| `pyproject.toml` `name`     | `agent-carbon`                                | `ai-footprint`                                       |
| Package Python              | `agent_carbon/`                               | `ai_footprint/`                                      |
| Binaire (`project.scripts`) | `agent-carbon`                                | `ai-footprint`                                       |
| Repo GitHub                 | `hrenaud/agent-carbon`                        | `hrenaud/ai-footprint` (redirection auto par GitHub) |
| Dossier d'install           | `~/.agent-carbon/`                            | `~/.ai-footprint/`                                   |
| Base SQLite                 | `~/.agent-carbon/carbon.db`                   | `~/.ai-footprint/ai-footprint.db`                    |
| Variables d'env             | `AGENT_CARBON_*`                              | `AI_FOOTPRINT_*`                                     |
| Défaut codé en dur          | `agent_carbon/__main__.py:35` (`_DEFAULT_DB`) | à mettre à jour                                      |

Fichiers touchés (recensement `grep carbon.db` / `agent-carbon`) :
`pyproject.toml`, `agent_carbon/` (package entier), `install.sh`,
`uninstall.sh`, `scripts/statusline.sh`, `tests/`, `README.md`,
`CONTRIBUTING.md`, `AGENTS.md`/`CLAUDE.md`, `docs/METHODOLOGY.md`,
`.github/` (workflows), hooks `settings.json` de Claude Code (câblés par
install.sh : hook Stop `ingest`, statusline).

### 2. Skills → `footprint-*`

| Avant                  | Après               |
| ---------------------- | ------------------- |
| `agent-carbon-config`  | `footprint-config`  |
| `agent-carbon-crush`   | `footprint-crush`   |
| `agent-carbon-help`    | `footprint-help`    |
| `agent-carbon-pi`      | `footprint-pi`      |
| `agent-carbon-report`  | `footprint-report`  |
| `agent-carbon-resolve` | `footprint-resolve` |

- Renommer les dossiers `skills/*` et les références internes
  (`SKILL.md`, mentions `/agent-carbon-help` et `/agent-carbon-resolve` dans
  `__main__.py`, doc).
- `install.sh` : supprimer les anciens symlinks `~/.claude/skills/agent-carbon-*`
  avant de créer les nouveaux (sinon skills fantômes).
- Note : `carbon-report` et `carbon-card` dans `~/.agents/skills`
  appartiennent au projet **claude-carbon** — **hors périmètre, on n'y touche
  pas**.

### 3. Migration de la base (point critique)

⚠️ `carbon.db` est partagée entre le repo dev **et** le clone installé
(`~/.agent-carbon/src`) dont le hook Stop écrit dedans à chaque fin de session.
Ordre impératif :

1. Le nouveau code (dev) sait lire le nouveau chemin **et** migrer l'ancien.
2. Merge + release + réinstallation via `install.sh` **dans la même fenêtre**,
   pour que le hook Stop installé pointe vite sur le nouveau chemin.
3. `install.sh` migre : si `~/.agent-carbon/carbon.db` existe et pas
   `~/.ai-footprint/ai-footprint.db` → déplacer le fichier (simple `mv`,
   schéma inchangé), puis laisser l'ancien dossier à `uninstall.sh` legacy.
4. Garder une garde dans le code : si l'ancienne base existe encore et pas la
   nouvelle, message clair invitant à relancer `install.sh` (pas de migration
   silencieuse à l'exécution).

Aucune migration de **schéma** : seul le chemin du fichier change.

### 4. Publication PyPI

Objectif : `pip install ai-footprint` fonctionne, et le nom `agent-footprint`
est verrouillé.

1. **Compte & sécurité** : compte PyPI + **Trusted Publishing** (OIDC GitHub
   Actions, pas de token longue durée).
2. **Workflow release** : job GitHub Actions déclenché sur tag `v*` :
   `python -m build` puis `pypa/gh-action-pypi-publish`. S'insère dans le flux
   existant `agent-carbon release bump` (le tag poussé déclenche la publication).
3. **Contrainte à lever** : la dépendance EcoLogits est une **URL git directe**
   (`ecologits @ git+https://…@0.11.0`) — **interdite sur PyPI**. Passer à
   `ecologits==0.11.0` (publié sur PyPI) ; vérifier que la version PyPI
   correspond au tag git utilisé (données `models.json` incluses).
4. **Paquet coquille `agent-footprint`** : mini-projet (un `pyproject.toml`,
   pas de code) avec `dependencies = ["ai-footprint"]`, README « ce paquet
   redirige vers ai-footprint », publié une fois manuellement. Hébergé dans un
   sous-dossier `packaging/agent-footprint/` du repo.
5. L'installation « produit » (hooks + skills + base) reste `install.sh` ;
   PyPI installe la CLI seule. Le README doit distinguer les deux.

### 5. Homebrew — tap personnel

Homebrew-core exige la notoriété (30 j, étoiles, releases) → pas maintenant.
La voie : un **tap personnel**.

1. Créer le repo `hrenaud/homebrew-tap` avec `Formula/ai-footprint.rb`.
2. Formule Python standard : `include Language::Python::Virtualenv`,
   `depends_on "python@3.12"`, ressources pip générées par
   `brew update-python-resources` (nécessite le point 4.3 : dépendances PyPI
   propres, pas d'URL git).
3. `url` = tarball GitHub du tag (`.../archive/refs/tags/vX.Y.Z.tar.gz`) +
   `sha256`.
4. Installation : `brew tap hrenaud/tap && brew install ai-footprint`.
5. Mise à jour de la formule à chaque release (bump url + sha256) — étape à
   ajouter au process de release (automatisable plus tard via workflow).
6. Candidature homebrew-core seulement si le projet décolle.

## Plan d'exécution ordonné

1. **Renommage code** (branche dédiée) : package `agent_carbon` → `ai_footprint`,
   pyproject, binaire, env vars, chemins par défaut, skills `footprint-*`,
   install.sh/uninstall.sh (avec migration db + purge anciens symlinks), doc.
   → vérif : tests verts (`.venv/bin/python -m pytest`), install.sh en dry-run
   sur dossier temporaire (`AI_FOOTPRINT_DIR`/`AI_FOOTPRINT_DB` custom).
2. **Dépendance EcoLogits** : passage à la version PyPI.
   → vérif : tests verts, impacts identiques sur un rapport de référence.
3. **Renommage repo GitHub** `agent-carbon` → `ai-footprint` (Settings →
   Rename ; redirections automatiques clones/URLs). Mettre à jour l'URL du
   `curl … install.sh` dans README/CLAUDE.md.
4. **Release** (`.venv/bin/agent-carbon release bump major` — changement
   incompatible : binaire, chemins, noms de skills) + **réinstallation**
   `install.sh` → le clone installé et la base migrent.
   → vérif : `ai-footprint report` fonctionne, hook Stop ingère dans
   `ai-footprint.db`, skills `/footprint-*` visibles.
5. **PyPI** : Trusted Publishing + workflow ; publier `ai-footprint` puis la
   coquille `agent-footprint`.
   → vérif : `pip install ai-footprint` dans un venv jetable.
6. **Homebrew tap** : repo `homebrew-tap` + formule.
   → vérif : `brew install hrenaud/tap/ai-footprint` sur machine locale.

## Arbitrages actés (2026-07-09)

- **Aucun alias transitoire `agent-carbon`** : le binaire, les env vars et les
  skills à l'ancien nom disparaissent (release major, uninstall/reinstall
  propre).
- **Périmètre = cette codebase uniquement** : les skills `carbon-report` et
  `carbon-card` appartiennent au projet claude-carbon et ne sont pas touchés.
- **Toute la documentation est mise à jour** dans le même passage : README,
  CONTRIBUTING, AGENTS.md/CLAUDE.md, docs/METHODOLOGY.md,
  docs/comparaison-donnees-outils.md, ainsi que les mémoires agent mentionnant
  la commande de release (`ai-footprint release bump`).
