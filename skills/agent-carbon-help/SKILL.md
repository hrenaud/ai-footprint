---
name: agent-carbon-help
description: Affiche l'aide d'agent-carbon — commandes (ingest, report, statusline, models, resolve) et leurs options — en interrogeant la CLI elle-même. À utiliser quand l'utilisateur demande comment utiliser agent-carbon, les options/flags disponibles, ou tape /agent-carbon-help.
---

Présente l'aide d'agent-carbon en interrogeant la CLI (source de vérité), puis résume en français. Ne pas inventer d'options : n'affiche que ce que `--help` renvoie.

## Étapes

1. Localiser le binaire et récupérer l'aide réelle de chaque commande :

```bash
AC="$(command -v agent-carbon || echo "$HOME/.agent-carbon/src/.venv/bin/agent-carbon")"
[ -x "$AC" ] || { echo "agent-carbon non installé. Installer : curl -fsSL https://raw.githubusercontent.com/hrenaud/agent-carbon/main/install.sh | bash"; exit 1; }

"$AC" --help
for cmd in ingest report statusline models resolve; do
  echo "===== $cmd ====="
  "$AC" "$cmd" --help
done
```

2. Présenter une synthèse en français, **à partir de la sortie réelle** (ne pas réinventer), regroupée par commande :
   - **report** — rapport multi-critères. Options : `--since <date>` (date simple `2026-06-27`, `27/06/2026`, `27/06/26`, ou ISO 8601 complet), `--detail` / `--detailed` (fourchettes min–max au lieu de la centrale `~`), `--all-projects` (lister tous les projets), `--db`.
   - **ingest** — parse les transcripts et calcule l'impact (`--source`, `--db`).
   - **resolve** — résout les modèles non couverts (mapping → Hugging Face) : `--list [--json]`, `--set "provider/model=repo"`, `--recompute`, `--forget`, `--since`. Cf. skill `/agent-carbon-resolve`.
   - **statusline** — ligne compacte (session courante) pour la statusline Claude Code.
   - **models** — lister/renseigner les modèles auto-hébergés non résolus.

3. Renvoyer vers les skills connexes : `/agent-carbon-report` (rapport), `/agent-carbon-resolve` (résolution), `/agent-carbon-config` (zone du mix, PUE/WUE).

## Garde-fou

- La CLI est la **source de vérité** : si un flag du résumé ci-dessus n'apparaît plus dans `--help`, fie-toi à `--help` et signale l'écart.
