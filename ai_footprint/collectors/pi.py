"""Collecteur pour les transcripts JSONL de Pi (https://pi.dev/)."""

import glob
import json
import os
from collections.abc import Iterator

from ai_footprint.collectors.base import Collector
from ai_footprint.collectors.claude_code import (
    _active_seconds,
    _parse_ts,
    _project_from_cwd,
)
from ai_footprint.models import InferenceEvent


class PiCollector(Collector):
    provider: str = ""  # chaque event porte son propre provider
    client: str = "pi"

    def __init__(self, root: str):
        self.root = os.path.expanduser(root)

    def collect(self) -> Iterator[InferenceEvent]:
        # `root` peut être un répertoire (~/.pi/agent/sessions) ou un fichier
        # unique (une session Pi).
        if os.path.isfile(self.root):
            yield from self._parse_file(self.root)
            return
        pattern = os.path.join(self.root, "**", "*.jsonl")
        for path in glob.glob(pattern, recursive=True):
            yield from self._parse_file(path)

    def _parse_file(self, path: str) -> Iterator[InferenceEvent]:
        # Chaque fichier de session commence par une entrée d'en-tête
        # (type "session") qui porte le `cwd` et l'id de session, valables
        # pour toutes les entrées "message" qui suivent dans le fichier.
        session_id = ""
        project = "unknown"
        prev_ts = None
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if not isinstance(obj, dict):
                    continue

                cur_ts = _parse_ts(obj.get("timestamp", ""))
                entry_type = obj.get("type")

                if entry_type == "session":
                    session_id = obj.get("id", "")
                    cwd = obj.get("cwd")
                    if cwd:
                        project = _project_from_cwd(cwd)
                elif entry_type == "message":
                    msg = obj.get("message") or {}
                    usage = msg.get("usage")
                    if msg.get("role") == "assistant" and usage:
                        yield InferenceEvent(
                            provider=msg.get("provider", ""),
                            model=msg.get("model", ""),
                            input_tokens=usage.get("input", 0),
                            output_tokens=usage.get("output", 0),
                            cache_creation_tokens=usage.get("cacheWrite", 0),
                            cache_read_tokens=usage.get("cacheRead", 0),
                            timestamp=obj.get("timestamp", ""),
                            project=project,
                            session_id=session_id,
                            msg_id=obj.get("id", ""),
                            active_seconds=_active_seconds(prev_ts, cur_ts),
                            client=self.client,
                        )

                if cur_ts is not None:
                    prev_ts = cur_ts
