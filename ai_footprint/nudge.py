"""Propositions proactives : mise à jour d'ai-footprint et modèles non
couverts jamais proposés. Cf.
.superpowers/specs/2026-07-12-nudges-resolve-maj.md."""

from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ai_footprint import __version__
from ai_footprint.cache import load_json_cache, save_json_cache, should_refresh
from ai_footprint.config import Config
from ai_footprint.store.db import SQLiteStore
from ai_footprint.tool_updates import parse_version

GITHUB_REPO_URL = "https://github.com/hrenaud/ai-footprint"
CACHE_TTL = timedelta(hours=24)


def _latest_github_tag(repo_url: str = GITHUB_REPO_URL) -> str | None:
    """Dernier tag `vX.Y.Z` du dépôt, ou None si le réseau est indisponible."""
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--tags", "--sort=-v:refname", repo_url],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    for line in result.stdout.splitlines():
        if "^{}" in line:  # dérérérrencement de tag annoté, ignorer
            continue
        ref = line.rsplit("refs/tags/", 1)[-1]
        if ref.startswith("v"):
            return ref[1:]
    return None


def check_self_update(config: Config, *, cache_path: Path,
                       current_version: str = __version__) -> dict | None:
    """Compare la version courante au dernier tag GitHub, throttlé 24h."""
    now = datetime.now(timezone.utc)
    cache = load_json_cache(cache_path)
    if should_refresh(cache, now=now, ttl=CACHE_TTL, key="self_update_checked_at"):
        latest = _latest_github_tag()
        if latest is None:
            return None
        save_json_cache(
            cache_path,
            self_update_checked_at=now.isoformat(),
            self_update_latest=latest,
        )
    else:
        latest = cache.get("self_update_latest")
        if latest is None:
            return None

    if parse_version(latest) > parse_version(current_version):
        return {"current": current_version, "latest": latest}
    return None


def check_uncovered_batch(store: SQLiteStore, config: Config) -> list[str]:
    """Clés `provider/model` non couvertes (hors `<synthetic>`) jamais
    proposées à l'utilisateur."""
    prompted = set(config.resolve_prompt_state.get("prompted_keys", []))
    keys = [f"{provider}/{model}" for provider, model in store.uncovered_keys()]
    return [k for k in keys if k not in prompted]


def mark_batch_prompted(config: Config, store: SQLiteStore) -> None:
    """Fusionne le lot non couvert actuel dans prompted_keys et sauvegarde."""
    prompted = set(config.resolve_prompt_state.get("prompted_keys", []))
    current = {f"{provider}/{model}" for provider, model in store.uncovered_keys()}
    config.resolve_prompt_state["prompted_keys"] = sorted(prompted | current)
    config.save()


def reset_prompted_keys(config: Config) -> None:
    """Réinitialise prompted_keys après une mise à jour d'ai-footprint réussie
    (le paysage de résolution a changé, cf. spec § Flux étape 2.2)."""
    config.resolve_prompt_state["prompted_keys"] = []
    config.save()


def build_claude_hook_output(update_available: dict | None,
                              uncovered_new: list[str]) -> dict | None:
    """Enveloppe hook SessionStart Claude Code (additionalContext), ou None
    si rien à signaler."""
    if not update_available and not uncovered_new:
        return None

    lines = []
    if update_available:
        lines.append(
            f"ai-footprint : mise à jour disponible ({update_available['current']} → "
            f"{update_available['latest']}). Propose à l'utilisateur de lancer "
            "l'installeur (curl -fsSL https://raw.githubusercontent.com/hrenaud/"
            "ai-footprint/main/install.sh | bash) via AskUserQuestion, avant toute "
            "autre action liée à ai-footprint. Si l'utilisateur accepte et que "
            "l'installation réussit, exécute ensuite silencieusement (sans "
            "confirmation) `ai-footprint resolve --retry-hf` puis `ai-footprint "
            "nudge --reset-prompted`, puis relance `ai-footprint nudge --json` "
            "avant de poursuivre avec les modèles non couverts éventuels."
        )
    if uncovered_new:
        lines.append(
            f"ai-footprint : {len(uncovered_new)} modèle(s) non couvert(s) jamais "
            f"proposés ({', '.join(uncovered_new)}). Propose à l'utilisateur (via "
            "AskUserQuestion) de lancer le skill /footprint-resolve, puis exécute "
            "`ai-footprint nudge --mark-prompted` que la réponse soit oui ou non."
        )
    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "\n".join(lines),
        }
    }
