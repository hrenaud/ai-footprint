#!/usr/bin/env bash
set -euo pipefail

# install.sh — Installeur one-line pour ai-footprint.
#
#   curl -fsSL https://raw.githubusercontent.com/hrenaud/ai-footprint/main/install.sh | bash
#
# Variables d'environnement (optionnelles) :
#   AI_FOOTPRINT_DIR        répertoire d'installation        (défaut: ~/.ai-footprint/src)
#   AI_FOOTPRINT_DB         chemin de la base SQLite          (défaut: ~/.ai-footprint/ai-footprint.db)
#   AI_FOOTPRINT_REF        branche/tag git à installer       (défaut: main)
#   AI_FOOTPRINT_NO_CLAUDE  =1 → ne touche pas à settings.json
#   AI_FOOTPRINT_NO_INGEST  =1 → pas d'ingestion initiale

REPO_URL="${AI_FOOTPRINT_REPO:-https://github.com/hrenaud/ai-footprint.git}"
INSTALL_DIR="${AI_FOOTPRINT_DIR:-$HOME/.ai-footprint/src}"
DB_PATH="${AI_FOOTPRINT_DB:-$HOME/.ai-footprint/ai-footprint.db}"
REF="${AI_FOOTPRINT_REF:-main}"
BIN_DIR="$HOME/.local/bin"
SETTINGS_FILE="$HOME/.claude/settings.json"

say()  { printf '  %s\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*" >&2; }
die()  { printf '  \033[31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

printf '\n  ai-footprint installer\n'
printf '  Compteur d'\''impact multi-critères (énergie, GWP, eau, ADPe, PE) via EcoLogits.\n\n'

# 1. Prérequis ---------------------------------------------------------------
command -v git >/dev/null 2>&1 || die "git est requis (brew install git / apt install git)."

# Trouve un Python >= 3.10 (EcoLogits 0.11 l'exige).
PYTHON=""
for cand in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$cand" >/dev/null 2>&1 && \
     "$cand" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3,10) else 1)' 2>/dev/null; then
    PYTHON="$cand"; break
  fi
done
[ -n "$PYTHON" ] || die "Python >= 3.10 introuvable (brew install python@3.13)."
ok "Python: $("$PYTHON" --version 2>&1) · git: présent"

# 1b. Migration depuis agent-carbon (ancien nom) -------------------------------
# La base et la config sont déplacées telles quelles (schéma inchangé) ; les
# restes de l'ancienne installation (clone, lien binaire, symlinks de skills)
# sont retirés — l'alias `agent-carbon` n'est pas conservé.
LEGACY_HOME="$HOME/.agent-carbon"
if [ "$DB_PATH" = "$HOME/.ai-footprint/ai-footprint.db" ] && \
   [ -f "$LEGACY_HOME/carbon.db" ] && [ ! -f "$DB_PATH" ]; then
  mkdir -p "$(dirname "$DB_PATH")"
  mv "$LEGACY_HOME/carbon.db" "$DB_PATH"
  for ext in -wal -shm; do
    [ -f "$LEGACY_HOME/carbon.db$ext" ] && mv "$LEGACY_HOME/carbon.db$ext" "$DB_PATH$ext"
  done
  ok "Base migrée: $LEGACY_HOME/carbon.db → $DB_PATH"
fi
if [ -f "$LEGACY_HOME/config.json" ] && [ ! -f "$HOME/.ai-footprint/config.json" ]; then
  mkdir -p "$HOME/.ai-footprint"
  mv "$LEGACY_HOME/config.json" "$HOME/.ai-footprint/config.json"
  ok "Config migrée: $LEGACY_HOME/config.json → ~/.ai-footprint/config.json"
fi
if [ -L "$BIN_DIR/agent-carbon" ]; then
  rm "$BIN_DIR/agent-carbon"
  ok "Ancien lien retiré: $BIN_DIR/agent-carbon"
fi
for legacy_skill in agent-carbon-config agent-carbon-crush agent-carbon-help \
                    agent-carbon-pi agent-carbon-report agent-carbon-resolve; do
  if [ -L "$HOME/.claude/skills/$legacy_skill" ]; then
    rm "$HOME/.claude/skills/$legacy_skill"
    ok "Ancien skill retiré: /$legacy_skill"
  fi
done
if [ -d "$LEGACY_HOME/src" ]; then
  rm -rf "$LEGACY_HOME/src"
  rmdir "$LEGACY_HOME" 2>/dev/null || true
  ok "Ancien clone retiré: $LEGACY_HOME/src"
fi
if [ -f "$HOME/.config/opencode/plugins/agent-carbon-crush.js" ]; then
  rm "$HOME/.config/opencode/plugins/agent-carbon-crush.js"
  ok "Ancien plugin Opencode retiré"
fi
if [ -f "$HOME/.pi/agent/extensions/agent-carbon-pi.ts" ]; then
  rm "$HOME/.pi/agent/extensions/agent-carbon-pi.ts"
  ok "Ancienne extension Pi retirée"
fi

# 2. Clone / mise à jour -----------------------------------------------------
if [ -d "$INSTALL_DIR/.git" ]; then
  say "Mise à jour de $INSTALL_DIR ..."
  git -C "$INSTALL_DIR" fetch --quiet origin "$REF"
  git -C "$INSTALL_DIR" checkout --quiet "$REF"
  git -C "$INSTALL_DIR" pull --ff-only --quiet origin "$REF"
else
  say "Clonage dans $INSTALL_DIR ..."
  mkdir -p "$(dirname "$INSTALL_DIR")"
  git clone --quiet --branch "$REF" "$REPO_URL" "$INSTALL_DIR"
fi
ok "Source: $INSTALL_DIR ($REF)"

# 3. Environnement virtuel + installation (EcoLogits depuis PyPI) ------------
say "Création du venv et installation (EcoLogits peut prendre 1-2 min) ..."
"$PYTHON" -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/python" -m pip install --quiet --upgrade pip
"$INSTALL_DIR/.venv/bin/python" -m pip install --quiet -e "$INSTALL_DIR"
AC_BIN="$INSTALL_DIR/.venv/bin/ai-footprint"
[ -x "$AC_BIN" ] || die "Installation échouée : $AC_BIN introuvable."
ok "ai-footprint installé dans le venv"

# 3b. Installation du CLI HuggingFace (pour resolve --set via hf models info) --
HF_BIN="$INSTALL_DIR/.venv/bin/hf"
if [ ! -x "$HF_BIN" ]; then
  say "Installation du CLI HuggingFace (hf) ..."
  "$INSTALL_DIR/.venv/bin/python" -m pip install --quiet huggingface_hub[cli]
  [ -x "$HF_BIN" ] || die "Installation du CLI hf échouée."
  ok "CLI hf installé dans le venv"
fi

# 4. Expose la commande sur le PATH -------------------------------------------
# Ne touche au lien global que pour l'install par défaut : un contributeur qui
# teste une branche via AI_FOOTPRINT_DIR/AI_FOOTPRINT_REF ne doit jamais
# écraser la commande `ai-footprint` de production.
if [ "$INSTALL_DIR" = "$HOME/.ai-footprint/src" ]; then
  mkdir -p "$BIN_DIR"
  ln -sf "$AC_BIN" "$BIN_DIR/ai-footprint"
  ok "Lien: $BIN_DIR/ai-footprint"
  case ":$PATH:" in
    *":$BIN_DIR:"*) : ;;
    *) warn "$BIN_DIR n'est pas dans votre PATH — ajoutez : export PATH=\"$BIN_DIR:\$PATH\"" ;;
  esac
else
  say "Répertoire de test (≠ install par défaut) — pas de lien global créé."
  say "Binaire de test : $AC_BIN"
fi

# 5. Câblage Claude Code (statusline + hook d'ingestion) ---------------------
if [ "${AI_FOOTPRINT_NO_CLAUDE:-0}" != "1" ]; then
  mkdir -p "$(dirname "$SETTINGS_FILE")"
  STATUSLINE_CMD="$INSTALL_DIR/scripts/statusline.sh $DB_PATH"
  INGEST_CMD="$AC_BIN ingest --db $DB_PATH"
  NUDGE_CMD="$AC_BIN nudge --db $DB_PATH --claude-hook"
  "$INSTALL_DIR/.venv/bin/python" - "$SETTINGS_FILE" "$STATUSLINE_CMD" "$INGEST_CMD" "$NUDGE_CMD" <<'PY'
import json, sys
path, statusline_cmd, ingest_cmd, nudge_cmd = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
try:
    with open(path, encoding="utf-8") as fh:
        cfg = json.load(fh)
except (FileNotFoundError, json.JSONDecodeError):
    cfg = {}

# statusLine — n'écrase jamais une statusLine d'un autre outil.
# « agent-carbon » (ancien nom) est reconnu et remplacé par la nouvelle commande.
sl = cfg.get("statusLine")
if not sl:
    cfg["statusLine"] = {"type": "command", "command": statusline_cmd}
    print("  statusLine: ajoutée")
elif "ai-footprint" in (sl.get("command") or "") or "agent-carbon" in (sl.get("command") or ""):
    cfg["statusLine"]["command"] = statusline_cmd
    print("  statusLine: déjà configurée (mise à jour)")
else:
    print("  statusLine: ignorée (déjà prise par un autre outil)")
    print("    Pour basculer, mettez dans ~/.claude/settings.json :")
    print("    " + statusline_cmd)

# Hook Stop → ingestion idempotente en fin de session.
# Les hooks de l'ancien nom (agent-carbon … ingest) sont retirés au passage.
hooks = cfg.setdefault("hooks", {})
stop = hooks.setdefault("Stop", [])
for group in stop:
    group["hooks"] = [
        h for h in group.get("hooks", [])
        if not ("agent-carbon" in (h.get("command") or "") and "ingest" in (h.get("command") or ""))
    ]
stop[:] = [g for g in stop if g.get("hooks")]
already = any(
    "ai-footprint" in (h.get("command") or "") and "ingest" in (h.get("command") or "")
    for group in stop for h in group.get("hooks", [])
)
if already:
    print("  hook Stop (ingest): déjà configuré")
else:
    stop.append({"matcher": "", "hooks": [{"type": "command", "command": ingest_cmd}]})
    print("  hook Stop (ingest): ajouté")

# Hook SessionStart → propose mise à jour ai-footprint / resolve des
# modèles non couverts en début de session (cf.
# .superpowers/specs/2026-07-12-nudges-resolve-maj.md).
session_start_hooks = hooks.setdefault("SessionStart", [])
already_nudge = any(
    "ai-footprint" in (h.get("command") or "") and "nudge" in (h.get("command") or "")
    for group in session_start_hooks
    for h in group.get("hooks", [])
)
if already_nudge:
    print("  hook SessionStart (nudge) : déjà configuré")
else:
    session_start_hooks.append({"matcher": "", "hooks": [{"type": "command", "command": nudge_cmd}]})
    print("  hook SessionStart (nudge) : ajouté")

with open(path, "w", encoding="utf-8") as fh:
    json.dump(cfg, fh, indent=2, ensure_ascii=False)
    fh.write("\n")
PY
  ok "Claude Code câblé ($SETTINGS_FILE)"

  # Skills (slash-skills) → ~/.claude/skills (symlinks, se mettent à jour avec le repo).
  SKILLS_SRC="$INSTALL_DIR/skills"
  SKILLS_DST="$HOME/.claude/skills"
  if [ -d "$SKILLS_SRC" ]; then
    mkdir -p "$SKILLS_DST"
    for d in "$SKILLS_SRC"/*/; do
      [ -d "$d" ] || continue
      name="$(basename "$d")"
      ln -sfn "$d" "$SKILLS_DST/$name"
      ok "skill: /$name"
    done
  fi
else
  say "Câblage Claude Code ignoré (AI_FOOTPRINT_NO_CLAUDE=1)."
fi

# 6. Ingestion initiale ------------------------------------------------------
if [ "${AI_FOOTPRINT_NO_INGEST:-0}" != "1" ]; then
  say "Ingestion initiale (peut être longue la première fois) ..."
  "$AC_BIN" ingest --db "$DB_PATH" || warn "Ingestion initiale non aboutie — relancez 'ai-footprint ingest'."
fi

# 7. Câblage Opencode/Crush (plugin + backfill) -------------------------------
if command -v opencode >/dev/null 2>&1 || command -v crush >/dev/null 2>&1; then
  OPENCODE_BIN="$(command -v opencode 2>/dev/null || command -v crush 2>/dev/null)"
  OPENCODE_PLUGIN_DIR="$HOME/.config/opencode/plugins"
  OPENCODE_CFG="$HOME/.config/opencode/opencode.json"
  OPENCODE_DB=""

  # Détecter la BDD Opencode/CRUSH locale.
  if [ -d "$HOME/.local/share/opencode" ]; then
    OPENCODE_DB="$HOME/.local/share/opencode/opencode.db"
  elif [ -d "$HOME/.local/share/crush" ]; then
    OPENCODE_DB="$HOME/.local/share/crush/crush.db"
  fi

  # 7a. Créer le plugin footprint-crush.js.
  mkdir -p "$OPENCODE_PLUGIN_DIR"
  PLUGIN_SRC="$INSTALL_DIR/skills/footprint-crush/footprint-crush.js"
  PLUGIN_DST="$OPENCODE_PLUGIN_DIR/footprint-crush.js"

  if [ -f "$PLUGIN_SRC" ]; then
    cp "$PLUGIN_SRC" "$PLUGIN_DST"
    ok "Plugin Opencode installé ($PLUGIN_DST)"
  else
    warn "Plugin Opencode introuvable dans $PLUGIN_SRC — omission."
  fi

  # 7b. Enregistrer le plugin dans opencode.json (si le fichier existe).
  if [ -f "$OPENCODE_CFG" ]; then
    "$INSTALL_DIR/.venv/bin/python" - "$OPENCODE_CFG" "$PLUGIN_DST" <<'PY'
import json, sys
cfg_path, plugin_path = sys.argv[1], sys.argv[2]
try:
    with open(cfg_path, encoding="utf-8") as fh:
        cfg = json.load(fh)
except (FileNotFoundError, json.JSONDecodeError):
    cfg = {}

plugins = cfg.setdefault("plugin", [])
# Purge de l'ancienne entrée agent-carbon-crush.js (fichier retiré à la migration).
plugins[:] = [p for p in plugins if "agent-carbon-crush.js" not in p]
if plugin_path not in plugins:
    plugins.append(plugin_path)
    print(f"  Plugin enregistré dans opencode.json: {plugin_path}")
else:
    print("  Plugin déjà enregistré dans opencode.json")

with open(cfg_path, "w", encoding="utf-8") as fh:
    json.dump(cfg, fh, indent=2, ensure_ascii=False)
    fh.write("\n")
PY
  else
    warn "opencode.json introuvable — le plugin ne sera pas chargé automatiquement."
    warn "  Pour charger manuellement : ajoutez « \"$PLUGIN_DST\" » à « plugin » dans $OPENCODE_CFG."
  fi

  # 7c. Backfill initial si la BDD locale existe.
  if [ -n "$OPENCODE_DB" ] && [ -f "$OPENCODE_DB" ]; then
    say "Backfill Opencode/CRUSH en cours (lecture directe de $OPENCODE_DB) ..."
    "$AC_BIN" ingest --db "$DB_PATH" --source-crush "$OPENCODE_DB" 2>/dev/null \
      && ok "Backfill initial effectué." \
      || warn "Backfill initial non abouti — relancez 'ai-footprint ingest --source-crush $OPENCODE_DB'."
  fi
else
  say "Opencode/CRUSH non détecté — câblage ignoré."
fi

# 8. Câblage Pi (extension + backfill) ----------------------------------------
if command -v pi >/dev/null 2>&1; then
  PI_EXT_DIR="$HOME/.pi/agent/extensions"
  PI_SESSIONS_DIR="$HOME/.pi/agent/sessions"

  EXT_SRC="$INSTALL_DIR/skills/footprint-pi/footprint-pi.ts"
  EXT_DST="$PI_EXT_DIR/footprint-pi.ts"

  if [ -f "$EXT_SRC" ]; then
    mkdir -p "$PI_EXT_DIR"
    cp "$EXT_SRC" "$EXT_DST"
    ok "Extension Pi installée ($EXT_DST)"
  else
    warn "Extension Pi introuvable dans $EXT_SRC — omission."
  fi

  if [ -d "$PI_SESSIONS_DIR" ]; then
    say "Backfill Pi en cours (lecture de $PI_SESSIONS_DIR) ..."
    "$AC_BIN" ingest --db "$DB_PATH" --source-pi "$PI_SESSIONS_DIR" 2>/dev/null \
      && ok "Backfill initial effectué." \
      || warn "Backfill initial non abouti — relancez 'ai-footprint ingest --source-pi $PI_SESSIONS_DIR'."
  fi
else
  say "Pi non détecté — câblage ignoré."
fi

printf '\n'
ok "Terminé."
say "Rapport   : ai-footprint report"
say "Statusline: redémarrez Claude Code pour voir l'impact en bas de l'écran."
printf '\n'
