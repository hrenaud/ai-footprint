# Changelog

Toutes les évolutions notables du projet. Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/).

## [Non publié]

### Ajouté

- **MVP** : compteur d'impact multi-critères (énergie, GWP, eau, ADPe, PE) avec fourchettes min–max, pour les sessions Claude Code.
  - Collecte des transcripts JSONL (`ClaudeCodeCollector`), confidentialité par conception (aucun contenu stocké).
  - Calcul d'impact **offline** délégué à EcoLogits (`mlco2/ecologits@0.11.0`), piloté par les tokens de sortie.
  - Stockage SQLite (`events` / `impacts` / `sessions`), ingestion idempotente, `methodology_version` par record.
  - Rapport CLI multi-critères (`--by model|project|total`, `--since`) et statusline compacte.
- **Installeur one-line** (`install.sh`, `curl … | bash`) : détection Python ≥ 3.10, venv, install EcoLogits, commande dans `~/.local/bin`, câblage Claude Code idempotent (statusline + hook `Stop` d'ingestion), première ingestion.
- **Skill `/agent-carbon-report`** (`skills/`) déployé par l'installeur dans `~/.claude/skills/`.
- **Script `scripts/statusline.sh`** : statusLine via script versionné (résilient) plutôt qu'une commande inline.
- **Sortie d'ingestion** : résumé de couverture clair (`mesurés` / `non couverts`) ; les warnings bruts d'EcoLogits sont silencés (information conservée par record) pour ne pas faire craindre un plantage.

### Modifié

- **Statusline** : ajout de l'**eau** (💧 L) à côté de l'énergie et du GWP.
- **Rapport CLI** : colonnes du tableau **alignées** (padding) ; ajout d'une section **« Impact total (tous modèles) »** avec les 5 critères et leurs icônes.

### Notes

- L'incertitude (région datacenter d'Anthropic inconnue) est affichée en fourchette, jamais masquée.
- Hors MVP, posés en coutures : inférence locale, énergie du poste, backfill `carbon.db`, mode live, export fichier, multi-provider.
