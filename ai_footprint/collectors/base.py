from abc import ABC, abstractmethod
from collections.abc import Iterator

from ai_footprint.models import InferenceEvent


class Collector(ABC):
    """Transforme une source spécifique à un outil en InferenceEvent normalisés."""

    provider: str = ""
    client: str = ""

    @abstractmethod
    def collect(self) -> Iterator[InferenceEvent]:
        ...
