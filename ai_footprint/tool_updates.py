"""Détecte les nouvelles versions d'ecologits / huggingface_hub disponibles.

Aucune mise à jour automatique n'est effectuée : le risque de breaking change
(ecologits est épinglé sur une version PyPI exacte, huggingface_hub sans
plafond de version) est trop élevé pour un bump silencieux. Ce module se contente
d'alerter (ouverture d'une issue GitHub via `gh`) — c'est à l'utilisateur de
tester puis d'épingler la nouvelle version dans pyproject.toml.

Utilisé par .github/workflows/check-tool-updates.yml (cron hebdomadaire).
"""

from __future__ import annotations

import json
import re
import subprocess
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ai_footprint.cache import load_json_cache, save_json_cache
from ai_footprint.cache import should_refresh as _cache_should_refresh

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"
CACHE_TTL = timedelta(hours=24)

_ECOLOGITS_PIN_RE = re.compile(r"ecologits==([\w\.\-]+)")
_HF_MIN_VERSION_RE = re.compile(r"huggingface_hub>=([\d.]+)")


def current_ecologits_tag(pyproject_text: str) -> str:
    m = _ECOLOGITS_PIN_RE.search(pyproject_text)
    if m is None:
        raise ValueError("Version ecologits introuvable dans pyproject.toml")
    return m.group(1)


def current_hf_min_version(pyproject_text: str) -> str:
    m = _HF_MIN_VERSION_RE.search(pyproject_text)
    if m is None:
        raise ValueError("Version minimale huggingface_hub introuvable dans pyproject.toml")
    return m.group(1)


def parse_version(v: str) -> tuple[int, ...]:
    """Convertit "0.11.0" / "v0.11.0" en tuple d'entiers comparable."""
    return tuple(int(p) for p in re.findall(r"\d+", v))


def latest_pypi_version(package: str) -> str:
    with urllib.request.urlopen(f"https://pypi.org/pypi/{package}/json", timeout=10) as resp:
        data = json.load(resp)
    return data["info"]["version"]


def check_updates(pyproject_text: str, *, hf_latest: str, ecologits_latest: str) -> list[dict]:
    """Compare les versions courantes (pyproject.toml) aux dernières connues."""
    updates = []

    current_hf = current_hf_min_version(pyproject_text)
    if parse_version(hf_latest) > parse_version(current_hf):
        updates.append({"package": "huggingface_hub", "current": current_hf, "latest": hf_latest})

    current_eco = current_ecologits_tag(pyproject_text)
    if parse_version(ecologits_latest) > parse_version(current_eco):
        updates.append({"package": "ecologits", "current": current_eco, "latest": ecologits_latest})

    return updates


def format_issue_body(update: dict) -> str:
    return (
        f"Nouvelle version de `{update['package']}` disponible : "
        f"`{update['current']}` → `{update['latest']}`.\n\n"
        "Aucune mise à jour automatique n'est effectuée (risque de breaking "
        "change) — à tester manuellement puis à épingler dans `pyproject.toml`."
    )


def session_start_notice(pyproject_text: str, *, hf_latest: str, ecologits_latest: str) -> str | None:
    """Message court pour le hook SessionStart, ou None si rien à signaler."""
    updates = check_updates(pyproject_text, hf_latest=hf_latest, ecologits_latest=ecologits_latest)
    if not updates:
        return None
    lines = [
        f"  - {u['package']} : {u['current']} → {u['latest']}"
        for u in updates
    ]
    return (
        "🔄 Mise à jour disponible (à tester puis épingler manuellement dans pyproject.toml) :\n"
        + "\n".join(lines)
    )


def load_cache(cache_path: Path) -> dict:
    return load_json_cache(cache_path)


def save_cache(cache_path: Path, *, checked_at: datetime, hf_latest: str, ecologits_latest: str) -> None:
    save_json_cache(
        cache_path,
        checked_at=checked_at.isoformat(),
        hf_latest=hf_latest,
        ecologits_latest=ecologits_latest,
    )


def should_refresh(cache: dict, *, now: datetime) -> bool:
    return _cache_should_refresh(cache, now=now, ttl=CACHE_TTL)


def session_start_check(cache_path: Path) -> str | None:
    """Point d'entrée du hook SessionStart : réseau throttlé (24h) via cache."""
    now = datetime.now(timezone.utc)
    cache = load_cache(cache_path)
    if should_refresh(cache, now=now):
        try:
            hf_latest = latest_pypi_version("huggingface_hub")
            eco_latest = latest_pypi_version("ecologits")
        except OSError:
            return None
        save_cache(cache_path, checked_at=now, hf_latest=hf_latest, ecologits_latest=eco_latest)
    else:
        hf_latest = cache["hf_latest"]
        eco_latest = cache["ecologits_latest"]

    pyproject_text = PYPROJECT.read_text(encoding="utf-8")
    return session_start_notice(pyproject_text, hf_latest=hf_latest, ecologits_latest=eco_latest)


def main() -> None:
    pyproject_text = PYPROJECT.read_text(encoding="utf-8")
    hf_latest = latest_pypi_version("huggingface_hub")
    eco_latest = latest_pypi_version("ecologits")

    updates = check_updates(pyproject_text, hf_latest=hf_latest, ecologits_latest=eco_latest)
    if not updates:
        print("Aucune mise à jour disponible.")
        return

    for update in updates:
        title = f"[tool-update] {update['package']} {update['latest']} disponible"
        existing = subprocess.run(
            ["gh", "issue", "list", "--state", "open", "--search", f'"{title}" in:title', "--json", "title"],
            capture_output=True,
            text=True,
            check=True,
        )
        titles = [i["title"] for i in json.loads(existing.stdout or "[]")]
        if title in titles:
            print(f"Issue déjà ouverte pour {update['package']} {update['latest']} — ignoré.")
            continue
        subprocess.run(
            ["gh", "issue", "create", "--title", title, "--body", format_issue_body(update)],
            check=True,
        )
        print(f"Issue créée : {title}")


if __name__ == "__main__":
    main()
