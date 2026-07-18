"""Collecteur pour les transcripts JSONL de Codex CLI (rollout sessions)."""

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


class CodexCollector(Collector):
    provider: str = "openai"
    client: str = "codex"

    def __init__(self, root: str):
        self.root = os.path.expanduser(root)

    def collect(self) -> Iterator[InferenceEvent]:
        if os.path.isfile(self.root):
            yield from self._parse_file(self.root)
            return
        pattern = os.path.join(self.root, "**", "*.jsonl")
        for path in glob.glob(pattern, recursive=True):
            yield from self._parse_file(path)

    def _parse_file(self, path: str) -> Iterator[InferenceEvent]:
        # Une session Codex commence par une ligne "session_meta" (id, cwd,
        # model_provider). Le modèle courant est ensuite mis à jour par
        # chaque ligne "turn_context" (un modèle peut changer d'un tour à
        # l'autre). Les usages de tokens arrivent en "event_msg"/"token_count".
        session_id = ""
        project = "unknown"
        provider = self.provider
        model = ""
        prev_ts = None
        idx = 0
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

                idx += 1
                cur_ts = _parse_ts(obj.get("timestamp", ""))
                entry_type = obj.get("type")
                payload = obj.get("payload") or {}

                if entry_type == "session_meta":
                    session_id = payload.get("id", "")
                    provider = payload.get("model_provider", self.provider)
                    cwd = payload.get("cwd")
                    if cwd:
                        project = _project_from_cwd(cwd)
                elif entry_type == "turn_context":
                    model = payload.get("model", model)
                elif entry_type == "event_msg" and payload.get("type") == "token_count":
                    usage = (payload.get("info") or {}).get("last_token_usage")
                    if usage:
                        input_total = usage.get("input_tokens", 0)
                        cached = usage.get("cached_input_tokens", 0)
                        yield InferenceEvent(
                            provider=provider,
                            model=model,
                            input_tokens=input_total - cached,
                            output_tokens=usage.get("output_tokens", 0),
                            cache_creation_tokens=0,
                            cache_read_tokens=cached,
                            timestamp=obj.get("timestamp", ""),
                            project=project,
                            session_id=session_id,
                            msg_id=f"{session_id}:{idx}",
                            active_seconds=_active_seconds(prev_ts, cur_ts),
                            client=self.client,
                        )

                if cur_ts is not None:
                    prev_ts = cur_ts
