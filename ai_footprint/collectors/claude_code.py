import glob
import json
import logging
import os
from collections.abc import Iterator
from datetime import datetime

from ai_footprint.collectors.base import Collector
from ai_footprint.dates import parse_iso_ts as _parse_ts
from ai_footprint.models import InferenceEvent

logger = logging.getLogger(__name__)

# Plafond du temps actif par message : au-delà, le delta reflète un temps mort
# (session reprise, pause de lecture) et non du travail → ignoré (0).
_ACTIVE_CAP_SECONDS = 300.0


def _project_from_cwd(cwd: str) -> str:
    return os.path.basename(cwd.rstrip("/")) or "unknown"


def _active_seconds(prev: datetime | None, cur: datetime | None) -> float:
    if prev is None or cur is None:
        return 0.0
    d = (cur - prev).total_seconds()
    return d if 0 < d <= _ACTIVE_CAP_SECONDS else 0.0


class ClaudeCodeCollector(Collector):
    provider = "anthropic"
    client = "claude-code"

    def __init__(self, root: str):
        self.root = os.path.expanduser(root)

    def collect(self) -> Iterator[InferenceEvent]:
        # `root` peut être un répertoire (tous les transcripts) ou un fichier
        # unique (transcript de la session courante, pour la statusline).
        if os.path.isfile(self.root):
            yield from self._parse_file(self.root)
            return
        pattern = os.path.join(self.root, "**", "*.jsonl")
        for path in glob.glob(pattern, recursive=True):
            yield from self._parse_file(path)

    def _parse_file(self, path: str) -> Iterator[InferenceEvent]:
        prev_ts: datetime | None = None
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as exc:
                    logger.debug("Skipping malformed JSON line in %s: %s", path, exc)
                    continue
                cur_ts = _parse_ts(obj.get("timestamp", ""))
                if obj.get("type") == "assistant":
                    msg = obj.get("message") or {}
                    usage = msg.get("usage")
                    if usage:
                        yield InferenceEvent(
                            provider=self.provider,
                            model=msg.get("model", ""),
                            input_tokens=usage.get("input_tokens", 0),
                            output_tokens=usage.get("output_tokens", 0),
                            cache_creation_tokens=usage.get("cache_creation_input_tokens", 0),
                            cache_read_tokens=usage.get("cache_read_input_tokens", 0),
                            timestamp=obj.get("timestamp", ""),
                            project=_project_from_cwd(obj.get("cwd", "")),
                            session_id=obj.get("sessionId", ""),
                            msg_id=obj.get("uuid", ""),
                            active_seconds=_active_seconds(prev_ts, cur_ts),
                            client=self.client,
                        )
                if cur_ts is not None:
                    prev_ts = cur_ts
