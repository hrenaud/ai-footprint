#!/usr/bin/env bash
# statusline.sh — ligne compacte ai-footprint pour la statusLine de Claude Code.
#
# Claude Code exécute ce script à chaque rafraîchissement et affiche sa sortie ;
# il envoie du JSON sur stdin, qu'on ignore (on lit la base ai-footprint).
# Résilient : ne renvoie jamais d'erreur dans la barre — au pire, une ligne vide.
#
# Usage (référencé depuis ~/.claude/settings.json) :
#   scripts/statusline.sh [DB_PATH]
set -uo pipefail

DB="${1:-${AI_FOOTPRINT_DB:-$HOME/.ai-footprint/ai-footprint.db}}"
AC="$(command -v ai-footprint 2>/dev/null || echo "$HOME/.ai-footprint/src/.venv/bin/ai-footprint")"

[ -x "$AC" ] || exit 0
"$AC" statusline --db "$DB" 2>/dev/null || true
