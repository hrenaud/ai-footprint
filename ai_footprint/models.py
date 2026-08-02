from dataclasses import dataclass


ROUTES = frozenset({"anthropic", "openai", "openrouter", "custom", "local", "unknown"})


@dataclass(frozen=True)
class InferenceEvent:
    """Un message d'inférence normalisé, neutre vis-à-vis de l'outil source."""

    client: str
    model_raw: str
    route_hint: str = ""
    route: str = "unknown"
    model_canonical: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    timestamp: str = ""          # ISO 8601 UTC
    project: str = ""
    session_id: str = ""
    msg_id: str = ""             # unique par message → clé d'idempotence
    active_seconds: float = 0.0  # temps actif estimé (delta depuis le message précédent)
