---
name: footprint-help
description: Affiche l'aide d'ai-footprint — commandes (ingest, report, statusline, models, resolve) et leurs options — en interrogeant la CLI elle-même. À utiliser quand l'utilisateur demande comment utiliser ai-footprint, les options/flags disponibles, ou tape /footprint-help.
---

Présente l'aide d'ai-footprint en interrogeant la CLI (source de vérité), puis résume en français. Ne pas inventer d'options : n'affiche que ce que `--help` renvoie.

## Étapes

1. Localiser le binaire et récupérer l'aide réelle de chaque commande :

```bash
AC="$(command -v ai-footprint || echo "$HOME/.ai-footprint/src/.venv/bin/ai-footprint")"
[ -x "$AC" ] || { echo "ai-footprint non installé. Installer : curl -fsSL https://raw.githubusercontent.com/hrenaud/ai-footprint/main/install.sh | bash"; exit 1; }

"$AC" --help
for cmd in ingest report statusline models resolve; do
  echo "===== $cmd ====="
  "$AC" "$cmd" --help
done
```

2. Présenter une synthèse en français, **à partir de la sortie réelle** (ne pas réinventer), regroupée par commande :
   - **report** — rapport multi-critères. Options : `--since <date>` (date simple `2026-06-27`, `27/06/2026`, `27/06/26`, ou ISO 8601 complet), `--detail` / `--detailed` (fourchettes min–max au lieu de la centrale `~`), `--all-projects` (lister tous les projets), `--db`.
   - **ingest** — parse les transcripts et calcule l'impact (`--source`, `--db`).
   - **resolve** — résout les modèles non couverts (mapping → Hugging Face) : `--list [--json]`, `--set "provider/model=repo"`, `--recompute`, `--forget`, `--since`. Cf. skill `/footprint-resolve`.
   - **statusline** — ligne compacte (session courante) pour la statusline Claude Code.
   - **models** — lister/renseigner les modèles auto-hébergés non résolus.

3. Renvoyer vers les skills connexes : `/footprint-report` (rapport), `/footprint-resolve` (résolution), `/footprint-config` (zone du mix, PUE/WUE).

## Garde-fou

- La CLI est la **source de vérité** : si un flag du résumé ci-dessus n'apparaît plus dans `--help`, fie-toi à `--help` et signale l'écart.
