# Guide avancé

Ce guide s'adresse aux utilisateurs à l'aise avec la ligne de commande qui
veulent installer `ai-footprint` manuellement ou comprendre son
fonctionnement interne. Pour l'usage courant (skills, installation en une
ligne), voir le [guide utilisateur](GUIDE.md). Pour le développement du
projet lui-même (architecture du code, schéma de base de données, tests),
voir [CONTRIBUTING.md](CONTRIBUTING.md).

## Installation manuelle

L'installeur en une ligne (voir le [guide utilisateur](GUIDE.md#installer))
reste la méthode recommandée : il détecte tes outils installés et câble tout
automatiquement. Les méthodes ci-dessous n'installent que la **CLI**, sans
câblage automatique dans Claude Code, Opencode ou Pi.

### Via Homebrew (macOS/Linux)

```bash
brew install hrenaud/tap/ai-footprint
```

Formule maintenue sur un tap personnel (`hrenaud/homebrew-tap`) — équivalent
à `brew tap hrenaud/tap && brew install ai-footprint`. Mise à jour :
`brew upgrade ai-footprint`.

### Via PyPI

```bash
pip install ai-footprint
```

Le paquet `agent-footprint` (ancien nom du projet) redirige aussi vers
`ai-footprint`. Mise à jour : `pip install --upgrade ai-footprint`.

### Depuis les sources (dev)

```bash
git clone https://github.com/hrenaud/ai-footprint
cd ai-footprint
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Câbler manuellement après une installation brew/pip

Sans câblage automatique, c'est à toi de déclencher l'ingestion et
d'afficher la statusline :

```bash
ai-footprint ingest       # à lancer périodiquement (ou via ton propre hook)
ai-footprint statusline   # à brancher dans la config de ton outil
```

Les skills (`/footprint-report`, etc.) nécessitent en plus les fichiers de
skills du dépôt — non installés par brew/pip.

## Variables d'environnement

Utilisées par `install.sh` et `uninstall.sh` :

| Variable                 | Effet                                                           | Défaut                            |
| ------------------------ | --------------------------------------------------------------- | --------------------------------- |
| `AI_FOOTPRINT_DIR`       | Répertoire d'installation (clone + venv).                       | `~/.ai-footprint/src`             |
| `AI_FOOTPRINT_DB`        | Chemin de la base SQLite (historique d'impact).                 | `~/.ai-footprint/ai-footprint.db` |
| `AI_FOOTPRINT_REF`       | Branche ou tag git à installer (utile pour tester une branche). | `main`                            |
| `AI_FOOTPRINT_NO_CLAUDE` | `=1` → ne modifie pas `~/.claude/settings.json`.                | non défini                        |
| `AI_FOOTPRINT_NO_INGEST` | `=1` → n'exécute pas l'ingestion initiale.                      | non défini                        |
| `AI_FOOTPRINT_PURGE_DB`  | `=1` (désinstallation) → supprime aussi la base SQLite.         | non défini                        |

Exemple : installer une branche de test dans un répertoire isolé, sans
toucher à l'installation de production ni à `settings.json` :

```bash
AI_FOOTPRINT_REF=ma-branche AI_FOOTPRINT_DIR=/tmp/ai-footprint-test \
AI_FOOTPRINT_NO_CLAUDE=1 \
  curl -fsSL https://raw.githubusercontent.com/hrenaud/ai-footprint/main/install.sh | bash
```

## Désinstallation complète

L'[uninstaller](GUIDE.md#desinstallation) conserve la base SQLite par
défaut. Pour la supprimer aussi :

```bash
AI_FOOTPRINT_PURGE_DB=1 \
  curl -fsSL https://raw.githubusercontent.com/hrenaud/ai-footprint/main/uninstall.sh | bash
```

## Sous le capot

### La CLI

Les skills ne sont qu'une couche au-dessus de la CLI : tu peux l'utiliser
directement.

```bash
ai-footprint ingest           # parse les transcripts → base SQLite (~/.ai-footprint/ai-footprint.db)
ai-footprint report           # rapport multi-critères (--since, --detail, --all-projects)
ai-footprint card             # card PNG partageable (--since, --theme, --lang, --out)
ai-footprint statusline       # ligne compacte pour la session courante
ai-footprint resolve --list   # liste les modèles non couverts à résoudre
ai-footprint resolve --set "provider/modele=org/repo-hf"   # applique un mapping et recalcule
ai-footprint resolve --forget "provider/modele"            # retire un mapping et recalcule
ai-footprint nudge --json     # état des nudges (modèles non proposés, mise à jour dispo)
```

`ingest` résume la couverture obtenue, par exemple :

```
80 events ingérés · 33639/33709 mesurés · 70 non couverts (conservés, impact non estimé)
```

Les « non couverts » sont des modèles hors périmètre EcoLogits : l'event est
conservé mais exclu des totaux (afficher un faux chiffre serait pire qu'un
trou de couverture). Beaucoup sont des placeholders internes `<synthetic>` (0
token, sans impact réel) ; les vrais modèles tiers ou récents se résolvent
avec `ai-footprint resolve` (ou `/footprint-resolve`). Détails complets :
[METHODOLOGY.md](METHODOLOGY.md).

### Ingestion multi-outils

`ai-footprint ingest` lit les transcripts de session de chaque outil détecté
(Claude Code, Opencode, Pi) et les convertit en events dans la base
SQLite. L'ingestion est **idempotente** : rejouer un même transcript ne
duplique rien. Chaque outil déclenche l'ingestion à sa façon :

- **Claude Code** : un hook `Stop` ingère le transcript en fin de session, et
  un hook `SessionStart` propose en début de session une mise à jour ou la
  résolution des modèles non couverts, si pertinent.
- **Opencode** : un plugin déclenche l'ingestion sur les mêmes
  événements de cycle de vie de session.
- **Pi** : une extension fait de même sur ses propres événements de session.

### Statusline

La statusline affiche l'impact de la **session en cours**. L'outil transmet
l'identifiant de session à ai-footprint, qui ingère le transcript courant et
filtre les totaux dessus. Lancée manuellement hors session, elle retombe sur
le **total global** de l'historique :

```bash
~/.ai-footprint/src/scripts/statusline.sh
```

L'installeur ne remplace jamais une statusline déjà utilisée par un autre
outil — il affiche alors la commande pour basculer manuellement.

### Modèles non couverts et résolution

Voir [METHODOLOGY.md](METHODOLOGY.md) pour le détail de ce qui est mesuré et
pourquoi certains modèles restent hors périmètre. `ai-footprint resolve`
associe un modèle non couvert à un dépôt Hugging Face équivalent, vérifie ses
paramètres réels, et recalcule les impacts.
