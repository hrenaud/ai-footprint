from dataclasses import dataclass


ROUTES = frozenset({"anthropic", "openai", "openrouter", "custom", "local", "unknown"})


@dataclass(frozen=True, init=False)
class InferenceEvent:
    """Un message d'inférence normalisé, neutre vis-à-vis de l'outil source."""

    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_creation_tokens: int
    cache_read_tokens: int
    timestamp: str  # ISO 8601 UTC
    project: str
    session_id: str
    msg_id: str  # unique par message → clé d'idempotence
    active_seconds: float
    client: str
    model_raw: str
    route_hint: str
    route: str
    model_canonical: str

    def __init__(
        self,
        provider: str = "",
        model: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_creation_tokens: int = 0,
        cache_read_tokens: int = 0,
        timestamp: str = "",
        project: str = "",
        session_id: str = "",
        msg_id: str = "",
        active_seconds: float = 0.0,
        client: str = "",
        *,
        model_raw: str | None = None,
        route_hint: str = "",
        route: str = "unknown",
        model_canonical: str = "",
    ) -> None:
        """Accept legacy positional data while exposing route-aware fields."""
        if route not in ROUTES:
            raise ValueError(f"Unsupported route: {route}")

        model_raw = model if model_raw is None else model_raw
        route_hint = provider if not route_hint else route_hint
        provider = provider if provider else route_hint
        model = model if model else model_raw
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "model", model)
        object.__setattr__(self, "input_tokens", input_tokens)
        object.__setattr__(self, "output_tokens", output_tokens)
        object.__setattr__(self, "cache_creation_tokens", cache_creation_tokens)
        object.__setattr__(self, "cache_read_tokens", cache_read_tokens)
        object.__setattr__(self, "timestamp", timestamp)
        object.__setattr__(self, "project", project)
        object.__setattr__(self, "session_id", session_id)
        object.__setattr__(self, "msg_id", msg_id)
        object.__setattr__(self, "active_seconds", active_seconds)
        object.__setattr__(self, "client", client)
        object.__setattr__(self, "model_raw", model_raw)
        object.__setattr__(self, "route_hint", route_hint)
        object.__setattr__(self, "route", route)
        object.__setattr__(self, "model_canonical", model_canonical)
