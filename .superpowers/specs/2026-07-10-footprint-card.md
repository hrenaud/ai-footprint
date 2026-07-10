# /footprint-card — card d'empreinte partageable (PNG)

**Date** : 2026-07-10 · **Statut** : design validé (variantes claire + sombre), à implémenter
**Maquette** : https://claude.ai/code/artifact/72ba5ff1-b354-4224-b98a-67dfb193d3f5
(source : `.superpowers/specs/assets/2026-07-10-footprint-card-mockup.html` —
base du futur `template.html`)

## Objectif

Un skill **`/footprint-card`** qui génère une **card PNG 1080×1080 partageable**
(réseaux sociaux) à partir d'une partie des données du report — à l'instar du
skill `carbon-card` du projet claude-carbon, mais avec nos différenciateurs :
**multi-critères** et **fourchettes d'incertitude min–max**.

Nommage `footprint-card` : anticipe le renommage AI Footprint
(cf. `.superpowers/specs/2026-07-09-renommage-ai-footprint.md`) ; le skill naît
directement sous son nom définitif.

## Référence : carbon-card (claude-carbon)

Pipeline observé : script bash → requêtes SQLite → injection dans des templates
HTML (1080×1080) → screenshot PNG via Playwright/chromium → exports datés
(`exports/<nom>-<lang>-<date>.png`), variantes FR + EN et summary + detailed.
On reprend le pipeline (éprouvé), pas le design (mono-critère CO₂, crème/serif).

## Données affichées (extrait du report)

Toutes issues des mêmes agrégats que `agent_carbon/report/cli.py` :

| Zone        | Données                                                                     | Source                                                   |
| ----------- | --------------------------------------------------------------------------- | -------------------------------------------------------- |
| Header      | wordmark « ai footprint », période (« depuis <mois AAAA> »), date du jour   | libellé auto depuis la 1re session (comme claude-carbon) |
| Héro        | **GWP central** (~, gros chiffre) + unité auto-échelle + jauge min–max      | totaux `render_report`                                   |
| Sous-héro   | nb sessions · tokens totaux · outils couverts (claude-code, opencode, pi…)  | DB                                                       |
| Tuiles ×4   | Eau, Énergie, ADPe, Énergie primaire : valeur centrale + mini-jauge min–max | totaux `render_report`                                   |
| Top projets | top 3 par GWP : barre proportionnelle + valeur centrale + part %            | `render_projects`                                        |
| Footer      | « estimations EcoLogits · fourchettes min–max » + URL du repo               | statique                                                 |

Exclus (volontairement — la card est un résumé, pas le report) : intensité par
modèle/outil, tokens par modèle, modèles non couverts, équivalents (km voiture,
coût $) — les équivalents pourront venir plus tard, hors périmètre v1.

## Design (validé par maquette, données réelles du 2026-07-10)

Méthode : skills `dataviz` (stat tiles / hero figure / mark specs / validation
palette) + `frontend-design`.

- **Signature : la jauge de fourchette.** Chaque valeur est posée sur son
  intervalle min–max (piste, segment rempli, marqueur central avec anneau
  surface 2px) au lieu d'un chiffre faussement précis. L'honnêteté de
  l'estimation EcoLogits devient l'identité visuelle de la card.
- **Deux traitements, la claire par défaut** (la card est un PNG single-theme ;
  arbitrage 2026-07-10 : le sombre fait « codes couleurs développeurs », la
  cible est grand public). Même structure, seuls les tokens changent :
  - **Claire (défaut)** : papier teinté vert `#f6f9f7`, panel `#e3ebe6`, encre
    `#16211b`, secondaire `#52645a`, muted `#7d8d84`, accent `#0f8f63`, accent
    foncé `#0b7a54`, hairline `#dbe4de`.
  - **Sombre (option, ex. `--theme dark`)** : surface vert-noir `#171c1a`,
    panel `#1d2420`, encre `#f2f5f2`, secondaire `#9fada5`, muted `#75837b`,
    accent `#1fb47f`, accent clair `#43d99e`, hairline `#2a332e`.

  Contrastes accent/surface ≥ 3:1 validés dans les deux modes
  (`dataviz/scripts/validate_palette.js`). Papier vert ≠ crème claude-carbon :
  les deux cards ne doivent pas se confondre.

- **Une seule teinte** : les 5 critères sont identifiés par libellé, jamais par
  couleur (pas de palette catégorielle → pas de contrainte CVD).
- **Typo** : sans system-ui en graisses fortes pour les chiffres (héro 152px,
  ~1,84) ; **mono (ui-monospace) pour libellés, unités, bornes et footer** —
  vernaculaire d'instrument de mesure. Pas d'emoji (contrairement au report
  CLI) : libellés mono uppercase.
- **Marques** : barres projets 14px, bout arrondi 4px côté donnée / carré à la
  base, valeur au bout de barre ; hairlines 1px pour séparer les zones.

### Robustesse aux valeurs fluctuantes (règles obligatoires)

Les valeurs varient en nombre de digits d'un usage à l'autre ; la disposition
ne doit jamais casser (validé en maquette avec les données réelles du
2026-07-10, dont la fourchette ADPe quasi ponctuelle 58,5–61) :

- **Largeur bornée à la source** : réutiliser l'échelle d'unités du report
  (`_UNIT_LADDERS` + `.3g`, 3 chiffres significatifs) → une valeur fait au plus
  ~5 caractères, l'unité absorbe les ordres de grandeur.
- **`white-space: nowrap`** sur toutes les valeurs, bornes et colonnes
  chiffrées (tuiles, bornes de jauges, valeurs projets, footer).
- **Tuiles** : libellé avec hauteur réservée de 2 lignes (min-height) et jauge
  calée en bas (`margin-top: auto`) → valeurs et jauges restent alignées entre
  tuiles même quand un libellé wrappe (« Énergie primaire »).
- **Bornes de jauge** ancrées aux extrémités de la piste
  (flex `space-between`), en mono `tabular-nums`.
- **Jauge** : échelle 0 → max×1,1 par critère (le max ne colle pas au bord) ;
  la fourchette étroite reste lisible grâce au marqueur central (tick) qui ne
  dépend pas de la largeur du segment.
- **Noms de projets** tronqués avec ellipse (colonne fixe 300px) ; colonne
  valeur en `auto` + nowrap (jamais de retour à la ligne).

## Implémentation

### Skill

- `skills/footprint-card/SKILL.md` : lance `ai-footprint card` (binaire venv du
  clone installé, comme les autres skills) et affiche le(s) chemin(s) PNG
  exporté(s). Symlinké par `install.sh` comme les autres.
- **Le skill pose les options avant de lancer la commande** — mêmes mécanique
  et règles que le skill report (`AskUserQuestion` sous Claude Code, `question`
  sous OpenCode, repli texte numéroté sinon ; JSON pur, jamais d'exécution
  avant réponse — reprendre la section « Comment poser les questions » du
  SKILL.md du report). Deux questions :
  - **Période** — header « Période ». Options : `Tout l'historique`
    (recommandé, pas de `--since`), `30 derniers jours`, `7 derniers jours` ;
    l'« Other » automatique accepte une date précise, comme pour le report.
  - **Thème** — header « Thème ». Options : `Clair` (recommandé, défaut),
    `Sombre` (`--theme dark`), `Les deux` (`--theme both`, un PNG par thème).

### CLI `ai-footprint card`

Plutôt qu'un script bash séparé (choix claude-carbon), la génération vit dans
le package Python — testable, et les agrégats existent déjà :

- `agent_carbon/card/` : `template.html` (le design ci-dessus, placeholders
  `{{...}}`), `cli.py` (requêtes → injection → rendu PNG).
- Options : `--since <date>` (défaut : tout l'historique, libellé « depuis
  <mois de la 1re session> »), `--db`, `--out <dir>` (défaut
  `~/.ai-footprint/exports/`), `--lang fr|en` (défaut : les deux, comme
  claude-carbon), `--theme light|dark|both` (défaut : `light`).
- Sortie : `ai-footprint-<theme>-<lang>-<AAAA-MM-JJ>.png` (1080×1080, device
  scale 2 → 2160×2160 comme claude-carbon) ; `<theme>` omis quand `light`.

### Rendu HTML → PNG

Réutiliser l'approche claude-carbon : chromium headless (via
`playwright`-python en dépendance optionnelle `[card]`, ou détection d'un
Chrome local en `--headless --screenshot`). Décision à trancher à
l'implémentation ; contrainte : ne pas alourdir l'install par défaut (le hook
Stop n'a pas besoin de chromium). Message clair si le moteur de rendu manque,
avec la commande d'installation.

Le template est **auto-contenu** (fonts système, pas de CDN) : rendu offline
garanti et aucune dépendance réseau — contrairement aux templates claude-carbon
(fonts Fontshare).

### Ordre TDD

1. Tests des agrégats card (réutilisation report) et du formatage
   (échelles d'unités, libellé période, positions min/central/max en %) →
   implémentation `card/cli.py`.
2. Test d'injection template (placeholders tous remplis, HTML valide).
3. Rendu PNG : test d'intégration (skippé si chromium absent) — fichier créé,
   1080×1080 (×2).
4. SKILL.md + câblage install.sh + doc (README « Card partageable », CONTRIBUTING).

## Articulation avec le renommage AI Footprint

Ce skill s'implémente **après** (ou avec) le renommage : il utilise le binaire
`ai-footprint`, le dossier `~/.ai-footprint/` et porte le wordmark « ai
footprint » + l'URL `github.com/hrenaud/ai-footprint`. Si implémenté avant, les
seuls points à variabiliser sont le wordmark, l'URL et le chemin d'export.
