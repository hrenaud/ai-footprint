from dataclasses import dataclass, field

from ecologits.model_repository import ParametersMoE, models
from ecologits.utils.range_value import RangeValue


@dataclass
class ParamsResult:
    active: float
    total: float
    arch: str            # "dense" | "moe"
    source: str          # "registry" | "user" | "huggingface"
    warnings: list[str] = field(default_factory=list)


class ModelParamsResolver:
    """Résout (params actifs, totaux) pour un modèle, en cascade :
    registre EcoLogits → cache config → Hugging Face → None."""

    def __init__(self, config):
        self.config = config

    def resolve(self, provider: str, model: str) -> ParamsResult | None:
        return (
            self._from_registry(provider, model)
            or self._from_cache(provider, model)
            or self._from_huggingface(provider, model)
        )

    def _from_registry(self, provider: str, model: str) -> ParamsResult | None:
        for prov in (provider, "huggingface_hub"):
            m = models.find_model(provider=prov, model_name=model)
            if m is not None:
                p = m.architecture.parameters
                if isinstance(p, ParametersMoE):
                    return ParamsResult(active=float(p.active), total=float(p.total),
                                        arch="moe", source="registry")
                # Gérer RangeValue (min/max) en prenant la moyenne
                if isinstance(p, RangeValue):
                    val = (p.min + p.max) / 2.0
                else:
                    val = float(p)
                return ParamsResult(active=val, total=val,
                                    arch="dense", source="registry")
        return None

    def _from_cache(self, provider: str, model: str) -> ParamsResult | None:
        entry = self.config.model_params.get(f"{provider}/{model}")
        if entry is None:
            return None
        return ParamsResult(
            active=float(entry["active"]), total=float(entry["total"]),
            arch=entry.get("arch", "dense"), source=entry.get("source", "user"))

    def _from_huggingface(self, provider: str, model: str) -> ParamsResult | None:
        return None  # implémenté en Task 4
