from collections.abc import Iterator

from ai_footprint.collectors.base import Collector
from ai_footprint.models import InferenceEvent


class LocalInferenceCollector(Collector):
    """Placeholder — inférence locale (Apple Silicon), hors MVP."""

    provider = "local"

    def collect(self) -> Iterator[InferenceEvent]:
        raise NotImplementedError("LocalInferenceCollector pas encore implémenté")
