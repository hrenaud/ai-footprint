"""Cache JSON générique throttlé par TTL — réutilisé par tool_updates.py
(veille ecologits/huggingface_hub) et nudge.py (auto-update ai-footprint)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path


def load_json_cache(cache_path: Path) -> dict:
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_json_cache(cache_path: Path, **fields) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(fields), encoding="utf-8")


def should_refresh(cache: dict, *, now: datetime, ttl: timedelta, key: str = "checked_at") -> bool:
    checked_at = cache.get(key)
    if not checked_at:
        return True
    try:
        last = datetime.fromisoformat(checked_at)
    except ValueError:
        return True
    return now - last > ttl
