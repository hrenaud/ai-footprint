# AI Footprint

**Connaître l'empreinte environnementale de tes sessions d'IA.** AI Footprint (`ai-footprint`) lit les
transcripts de Claude Code, Opencode et Pi, estime l'impact de chaque réponse
générée, et te le restitue sous forme de rapport et de suivi en temps réel —
directement dans l'outil que tu utilises déjà.

Le calcul n'est pas réinventé : il est délégué à **[EcoLogits](https://github.com/mlco2/ecologits)**,
un moteur reconnu, **offline** et **multi-critères**.

## Ce qu'on mesure

Pas seulement le CO₂. Cinq critères, chacun donné en **fourchette** (pas un faux
chiffre précis — voir « Pourquoi des fourchettes ») :

|     | Critère     | Ce que ça représente                       |
| --- | ----------- | ------------------------------------------ |
| 🌍  | **GWP**     | gaz à effet de serre (kg CO₂eq)            |
| 💧  | **Eau**     | eau consommée (L)                          |
| ⛏   | **ADPe**    | épuisement des métaux/ressources (kg Sbeq) |
| ⚡  | **Énergie** | électricité (kWh)                          |
| 🔥  | **PE**      | énergie primaire (MJ)                      |

> **Pourquoi des fourchettes ?** La région exacte des datacenters d'Anthropic (donc
> leur mix électrique) est inconnue, et le rendement d'un datacenter (PUE) varie. Cette
> incertitude est **irréductible** : on l'affiche (min–max + valeur centrale `~`)
> plutôt que de la cacher. Détails : [docs/METHODOLOGY.md](docs/METHODOLOGY.md).

## Installation

### Rapide (une ligne)

```bash
curl -fsSL https://raw.githubusercontent.com/hrenaud/ai-footprint/main/install.sh | bash
```

L'installeur détecte Python ≥ 3.10, installe ai-footprint + EcoLogits, expose la
commande `ai-footprint`, déploie les skills et câble le suivi (statusline +
ingestion) pour chaque outil détecté sur ta machine — Claude Code, Opencode
(plugin) et Pi (extension) — et fait un backfill initial de leurs sessions
locales. **Redémarre ton outil** ensuite pour activer les skills.

Options d'installation (variables d'environnement) et détails complets : voir le
[guide avancé](docs/GUIDE-AVANCE.md).

### Via Homebrew (macOS/Linux)

```bash
brew install hrenaud/tap/ai-footprint
```

### Via PyPI

```bash
pip install ai-footprint
```

> **Homebrew et PyPI n'installent que la CLI** (`ai-footprint`), sans câblage
> automatique dans ton outil (pas de statusline, pas d'ingestion, pas de
> skills). Pour l'intégration complète, utilise l'installeur rapide
> ci-dessus, ou câble-la toi-même — voir le
> [guide avancé](docs/GUIDE-AVANCE.md).

### Manuelle (dev)

Python ≥ 3.10, puis depuis un clone du dépôt : `pip install -e .`.

### Désinstallation

```bash
curl -fsSL https://raw.githubusercontent.com/hrenaud/ai-footprint/main/uninstall.sh | bash
```

Retire le binaire, les skills, le câblage dans chaque outil (statusline + hook
d'ingestion Claude Code, plugin Opencode, extension Pi) et le répertoire source.
**La base `ai-footprint.db` (historique d'impact) est conservée par défaut** —
ajoute `AI_FOOTPRINT_PURGE_DB=1` avant la commande pour la supprimer aussi.

## Utilisation — via les skills (recommandé)

C'est la façon recommandée d'utiliser ai-footprint : tape la commande slash,
ou demande simplement en langage naturel (les skills se déclenchent aussi sur
des formulations comme « mon impact » ou « mon empreinte CO₂ ») :

| Skill                    | À quoi ça sert                                                                                | Exemple                                             |
| ------------------------ | --------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| **`/footprint-report`**  | Ton rapport d'impact complet.                                                                 | « mon impact », « mon empreinte CO₂ »               |
| **`/footprint-card`**    | Une card PNG partageable (1080×1080) résumant ton empreinte.                                  | « exporte mon empreinte en image »                  |
| **`/footprint-resolve`** | Estimer l'impact de modèles tiers/locaux non reconnus (les associe à un modèle Hugging Face). | quand le rapport liste des « modèles non couverts » |
| **`/footprint-config`**  | Régler ta zone électrique (ex. France) et les paramètres datacenter.                          | « configure ma zone élec »                          |
| **`/footprint-help`**    | Aide : toutes les commandes et options.                                                       | « comment utiliser ai-footprint »                   |

Le rapport a cinq sections : **impact total**, **projets les plus impactants**,
**tokens & impact par modèle**, **modèles non couverts**, et **intensité par modèle**
(impact par heure de travail — révèle qu'à débit égal, Opus émet bien plus que Haiku).
Une sixième section, **intensité par outil**, apparaît automatiquement dès que tes
données couvrent plusieurs outils (Claude Code, Opencode, Pi…) — elle révèle
quel outil consomme le plus de tokens et a les impacts les plus forts, à débit égal.

Options utiles du rapport : `--since 2026-06-27` (ou `27/06/26`) pour une période,
`--detail` pour les fourchettes min–max par modèle/projet, `--all-projects` pour la
liste complète. `/footprint-help` (ou `ai-footprint report --help`) les liste toutes.

### Card partageable

`/footprint-card` exporte une image PNG 1080×1080 résumant ton empreinte : le
carbone (GWP) en héro, les 4 autres critères (eau, énergie, ADPe, énergie primaire)
en tuiles, et le top 3 des projets les plus impactants. Chaque valeur est posée sur
sa fourchette min–max via une jauge à marqueur central — la signature visuelle du
projet, pour ne jamais présenter un chiffre unique trompeur.

Nécessite Chrome ou Chromium installé localement (rendu HTML → PNG en headless,
aucune dépendance Python supplémentaire). Options : `--since`, `--theme
light|dark|both` (défaut `light`), `--lang fr|en|both` (défaut `both`), `--out`
(défaut `~/.ai-footprint/exports/`).

## Suivi en temps réel

Une fois l'installation terminée, ton outil affiche en continu l'impact de la
**session en cours** (l'outil transmet la session ; ai-footprint ingère le
transcript courant et filtre dessus). En lancement manuel, hors session, ça
retombe sur le **total global** :

```bash
~/.ai-footprint/src/scripts/statusline.sh   # ⚡ 18.9–33.5 kWh · 🌍 7.93–13.5 kgCO2e · 💧 61.3–134 L
```

L'installeur ne remplace jamais une statusline déjà utilisée par un autre
outil — il affiche alors la commande pour basculer manuellement.

Un préfixe `≈` (suivi d'un rappel entre parenthèses, ex. `sonnet-5 inconnu, params
sonnet-4`) signale que la session utilise un modèle trop récent pour le registre
EcoLogits : l'impact affiché est un **repère provisoire**, extrapolé des paramètres
officiels de la version sœur nommée — voir
[docs/METHODOLOGY.md](docs/METHODOLOGY.md#modeles-anthropic-trop-recents-pour-le-registre-ecologits).

## En ligne de commande (sous le capot)

Les skills appellent simplement la CLI ; tu peux l'utiliser directement :

```bash
ai-footprint ingest      # parse les transcripts → base SQLite (~/.ai-footprint/ai-footprint.db)
ai-footprint report      # rapport multi-critères (--since, --detail, --all-projects)
ai-footprint card        # card PNG partageable (--since, --theme, --lang, --out)
ai-footprint statusline   # ligne compacte
ai-footprint resolve --list   # modèles non couverts à résoudre
```

`ingest` résume la couverture, p. ex. :

```
80 events ingérés · 33639/33709 mesurés · 70 non couverts (conservés, impact non estimé)
```

Les « non couverts » sont des modèles hors périmètre EcoLogits — l'event est conservé
mais exclu des totaux (afficher un faux chiffre serait pire). Beaucoup sont des
placeholders internes `<synthetic>` (0 token) ; les vrais modèles tiers se résolvent
avec `/footprint-resolve`. Voir [docs/METHODOLOGY.md](docs/METHODOLOGY.md).

## Pour aller plus loin

- **[docs/GUIDE.md](docs/GUIDE.md)** — mode d'emploi détaillé : installation,
  désinstallation, usage complet des skills et de la CLI.
- **[docs/GUIDE-AVANCE.md](docs/GUIDE-AVANCE.md)** — installation manuelle
  (Homebrew, PyPI, sources), variables d'environnement, fonctionnement interne.
- **[docs/METHODOLOGY.md](docs/METHODOLOGY.md)** — comment l'impact est évalué : les
  échanges avec EcoLogits, les choix de méthodologie et leurs limites.
- **[docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)** — côté technique : architecture, schéma de
  données, mise en place dev et comment étendre le projet.

## Sources d'inspiration

- **EcoLogits** (`mlco2/ecologits`) — le moteur d'impact (offline, multi-critères/phases).
- **claude-carbon** — audit d'origine et UX de reporting.
- **CodeCarbon** — tracker offline, zone électrique par code pays.
- **thirsty-llm** — approche offline-first et fourchettes (on en rejette le modèle
  prix-proxy, remplacé par EcoLogits).
