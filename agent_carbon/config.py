from dataclasses import dataclass, field


@dataclass
class Config:
    """Constantes maison — source de vérité unique."""

    electricity_mix_zone: str = "USA"          # zone ISO pour EcoLogits
    throughput_tok_s: float = 50.0             # débit pour estimer request_latency
    model_aliases: dict[str, str] = field(default_factory=dict)
    local_wh_per_token: float | None = None    # placeholder inférence locale (hors MVP)
