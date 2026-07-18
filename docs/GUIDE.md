# Guide utilisateur

Mode d'emploi d'`ai-footprint` : installation, désinstallation et usage des
skills au quotidien. Pour une présentation rapide du produit, voir le
[README](https://github.com/hrenaud/ai-footprint#readme) ; pour comprendre
comment les impacts sont calculés, voir [METHODOLOGY.md](METHODOLOGY.md).

`ai-footprint` fonctionne avec **Claude Code**, **Opencode**, **Pi** et **Codex CLI** :
l'installeur détecte automatiquement les outils présents sur ta machine et
active les skills/le suivi pour chacun d'eux, sans réglage à faire toi-même.

## Installation

### Prérequis

- Python ≥ 3.10.
- Chrome ou Chromium installés localement, uniquement si tu comptes utiliser
  `/footprint-card` (export de ton empreinte en image).

### Installer

```bash
curl -fsSL https://raw.githubusercontent.com/hrenaud/ai-footprint/main/install.sh | bash
```

Cette commande installe `ai-footprint`, l'active pour tous les outils
compatibles détectés sur ta machine (Claude Code, Opencode, Pi, Codex CLI), et
reprend l'historique de tes sessions passées. **Redémarre ton outil** (Claude
Code, Opencode, Pi ou Codex CLI) une fois l'installation terminée pour activer
les skills.

### Mettre à jour

Relance simplement la commande d'installation ci-dessus : elle met à jour
`ai-footprint` sans perdre ton historique. Une mise à jour disponible t'est
aussi proposée automatiquement en début de session.

## Désinstallation

```bash
curl -fsSL https://raw.githubusercontent.com/hrenaud/ai-footprint/main/uninstall.sh | bash
```

Cette commande retire `ai-footprint` de tous les outils où il était actif.
**Ton historique d'impact est conservé par défaut** — pour le supprimer
aussi, voir le [guide avancé](GUIDE-AVANCE.md#desinstallation-complete).

## Utilisation via les skills

C'est la façon recommandée d'utiliser ai-footprint : tape la commande slash,
ou demande simplement en langage naturel (les skills se déclenchent aussi sur
des formulations comme « mon impact » ou « mon empreinte CO₂ »).

### `/footprint-report` — le rapport complet

Affiche l'impact multi-critères de tes sessions :

- **Impact total** — les cinq critères (GWP, eau, ADPe, énergie, énergie
  primaire), en fourchette min–max.
- **Projets les plus impactants** — répartition par répertoire de travail.
- **Tokens & impact par modèle** — quel modèle consomme le plus.
- **Modèles non couverts** — modèles dont l'impact n'a pas pu être estimé.
  Voir `/footprint-resolve` ci-dessous pour les résoudre.
- **Intensité par modèle** — impact par heure de travail (révèle qu'à débit
  de travail égal, un modèle plus gros comme Opus émet bien plus qu'un
  modèle léger comme Haiku).
- **Intensité par outil** (dès que tes données couvrent plusieurs outils) —
  quel outil consomme le plus, à débit égal.

Tu peux filtrer sur une période (« depuis le 27 juin », par exemple), ou
demander le détail par modèle/projet.

### `/footprint-card` — export en image

Génère une image partageable résumant ton empreinte : le carbone en héro, les
autres critères (eau, énergie, métaux, énergie primaire) en tuiles, et le
top 3 des projets les plus impactants. Nécessite Chrome ou Chromium.

### `/footprint-resolve` — résoudre les modèles non couverts

Certains modèles (tiers, locaux, ou trop récents) sont hors périmètre du
moteur de calcul : ai-footprint conserve l'event mais exclut son impact des
totaux plutôt que d'afficher un chiffre inventé. Ce skill propose, pour
chaque modèle non couvert, une correspondance avec un modèle équivalent connu,
et recalcule les impacts après ta confirmation.

Se déclenche automatiquement en proposition en début de session si pertinent,
ou manuellement à tout moment.

### `/footprint-config` — réglages

Ajuste les hypothèses utilisées pour le calcul (zone du mix électrique,
rendement du datacenter…). Détectées automatiquement au premier rapport si
non réglées.

### `/footprint-help` — aide

Affiche l'aide réelle d'ai-footprint : toutes les commandes disponibles.

## Suivi en temps réel

Une fois l'installation terminée, ton outil affiche en continu l'impact de la
**session en cours**, par exemple :

```
⚡ 18.9–33.5 kWh · 🌍 7.93–13.5 kgCO2e · 💧 61.3–134 L
```

Un préfixe `≈` signale que la session utilise un modèle trop récent pour être
précisément mesuré : l'impact affiché est alors un repère provisoire — voir
[METHODOLOGY.md](METHODOLOGY.md#modeles-anthropic-trop-recents-pour-le-registre-ecologits).

## Pour aller plus loin

- **[Guide avancé](GUIDE-AVANCE.md)** — installation manuelle (Homebrew,
  PyPI, depuis les sources), variables d'environnement, et comment
  ai-footprint fonctionne sous le capot.
- **[METHODOLOGY.md](METHODOLOGY.md)** — comment l'impact est évalué : les
  échanges avec EcoLogits, les choix de méthodologie et leurs limites.
- **[CONTRIBUTING.md](CONTRIBUTING.md)** — côté technique : architecture,
  schéma de données, mise en place dev et comment étendre le projet.
