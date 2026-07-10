import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from ecologits.model_repository import ParametersMoE, models
from ecologits.utils.range_value import RangeValue

# TTL du cache négatif persisté : au-delà, on retente la résolution HF
# (le modèle a pu être publié/renommé entre-temps).
HF_NEGATIVE_TTL_DAYS = 7

# Noms de modèles MoE : motif « a<N>b » isolé (ex. -A3B, …120b-a12b).
_MOE_NAME_RE = re.compile(r"(?:^|[^a-z0-9])a\d+b(?:[^a-z0-9]|$)", re.IGNORECASE)

# N4 : plafonds de la méthode 3 (index.json + HEAD séquentiels).
_MAX_INDEX_FILES = 30
_INDEX_BUDGET_SECONDS = 60.0

# Identifiant de repo HF valide : « org/name » (lettres, chiffres, . _ -).
_REPO_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9._-]+$")


def _looks_moe(repo: str) -> bool:
    """Vrai si le nom du repo suggère une architecture MoE (motif « aNb »)."""
    return bool(_MOE_NAME_RE.search(repo))


# Détection du dtype depuis le nom du repo → octets par paramètre.
# Ordre : du plus spécifique au plus général ; premier motif gagnant.
_BYTES_PER_PARAM_PATTERNS: tuple[tuple[re.Pattern, float], ...] = (
    (re.compile(r"4[-_]?bit|q4|int4|awq|gptq|mxfp4|nf4", re.IGNORECASE), 0.5),
    (re.compile(r"8[-_]?bit|q8|int8|fp8", re.IGNORECASE), 1.0),
    (re.compile(r"fp16|bf16|f16|half", re.IGNORECASE), 2.0),
    (re.compile(r"fp32|f32", re.IGNORECASE), 4.0),
)


def _detect_bytes_per_param(repo: str) -> float | None:
    """Octets/param déduits du nom du repo (`-4bit` → 0.5, `-fp16` → 2.0…).
    None si le nom ne dit rien (dtype inconnu → fourchette, cf. Task M2b)."""
    for pattern, bpp in _BYTES_PER_PARAM_PATTERNS:
        if pattern.search(repo):
            return bpp
    return None


@dataclass
class ParamsResult:
    active: float | RangeValue
    total: float | RangeValue
    arch: str            # "dense" | "moe"
    source: str          # "registry" | "user" | "huggingface"
    warnings: list[str] = field(default_factory=list)


def _param_to_json(v: float | RangeValue) -> float | dict:
    """Sérialise un compte de params pour le cache config (JSON pur)."""
    if isinstance(v, RangeValue):
        return {"min": float(v.min), "max": float(v.max)}
    return float(v)


def _param_from_json(v) -> float | RangeValue:
    """Désérialise un compte de params du cache config."""
    if isinstance(v, dict):
        return RangeValue(min=v["min"], max=v["max"])
    return float(v)


def _fetch_safetensors_index_bytes(repo: str) -> int | None:
    """Récupère la taille totale des fichiers safetensors d'un repo HF via le
    model.safetensors.index.json. Retourne None en cas d'échec."""
    try:
        import urllib.request
        index_url = f"https://huggingface.co/{repo}/resolve/main/model.safetensors.index.json"
        req = urllib.request.Request(index_url, headers={"Accept": "application/json"})
        resp = urllib.request.urlopen(req, timeout=15)
        index_data = json.loads(resp.read())

        # Extraire les noms de fichiers uniques du weight_map
        weight_map = index_data.get("weight_map", {})
        files = sorted(set(weight_map.values()))

        if len(files) > _MAX_INDEX_FILES:
            return None  # trop de shards : budget réseau déraisonnable, on abandonne

        # Calculer la taille totale via HEAD requests
        base_url = f"https://huggingface.co/{repo}/resolve/main/"
        total_bytes = 0
        start = time.monotonic()
        for f in files:
            if time.monotonic() - start > _INDEX_BUDGET_SECONDS:
                return None  # budget temps global dépassé
            try:
                file_url = base_url + f
                req = urllib.request.Request(file_url, method="HEAD")
                resp = urllib.request.urlopen(req, timeout=10)
                size = int(resp.headers.get("Content-Length", 0))
                total_bytes += size
            except Exception:
                continue

        return total_bytes if total_bytes > 0 else None
    except Exception:
        return None


def _bytes_to_params_estimated(total_bytes: int, bytes_per_param: float) -> float:
    """Estime le nombre de paramètres (en milliards) depuis la taille totale
    des fichiers et le dtype détecté."""
    return (total_bytes / bytes_per_param) / 1e9


def _fetch_hf_cli_info(repo: str) -> dict | None:
    """Récupère les infos d'un repo HF via le CLI `hf models info`.
    Retourne le dict d'info ou None en cas d'échec.

    Heuristique de localisation du binaire (fail-safe : introuvable → None,
    la cascade continue) : 1) PATH, 2) venv actif (déduit de sys.executable),
    3) `.venv/bin/hf` du cwd puis de ~/.ai-footprint/src (clone installé)."""
    try:
        import subprocess
        import shutil
        import os
        import sys
        
        hf_path = None
        
        # 1. Chercher dans le PATH
        hf_path = shutil.which("hf")
        
        # 2. Chercher dans le venv actif (sys.executable → ./venv/bin/hf)
        if hf_path is None and sys.executable:
            # sys.executable = ".../.venv/bin/pythonX.Y" → "./venv/bin/hf"
            candidate = os.path.join(
                os.path.dirname(os.path.dirname(sys.executable)),
                "bin", "hf"
            )
            if os.path.exists(candidate) and os.access(candidate, os.X_OK):
                hf_path = candidate
        
        # 3. Fallback : répertoires courants connus
        if hf_path is None:
            for base in [os.getcwd(), os.path.expanduser("~/.ai-footprint/src")]:
                candidate = os.path.join(base, ".venv", "bin", "hf")
                if os.path.exists(candidate) and os.access(candidate, os.X_OK):
                    hf_path = candidate
                    break
        
        if hf_path is None:
            return None
            
        result = subprocess.run(
            [hf_path, "models", "info", repo],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout.strip())
    except (FileNotFoundError, subprocess.SubprocessError, json.JSONDecodeError, ValueError):
        pass
    return None


def _fetch_hf_total_params(repo: str) -> tuple[float | RangeValue, list[str]] | None:
    """Cascade offline-safe repo HF → (total params en Md, warnings de provenance).
    Trois méthodes en fallback : metadata safetensors → CLI `hf models info`
    (used_storage, 4bit) → fichiers safetensors via index.json (4bit). Gère les
    modèles dont le metadata ne popule pas safetensors mais dont les fichiers
    existent (GGUF avec index, modèles récents). Quand le dtype est inconnu (bpp
    None), retourne une fourchette (min=bytes/2, max=bytes/0.5). None si tout
    échoue (lib absente, réseau, 404, identifiant invalide) — jamais d'exception."""
    if not _REPO_RE.match(repo):
        # Identifiant impossible sur le Hub (placeholder, nom local, path
        # traversal) : aucune requête réseau.
        return None

    try:
        import huggingface_hub
    except ImportError:
        huggingface_hub = None

    # Méthode 1 : metadata HF standard (safetensors.total)
    if huggingface_hub is not None:
        try:
            info = huggingface_hub.model_info(repo, timeout=10)
            if info.safetensors is not None:
                total = float(info.safetensors.total) / 1e9
                if total > 0:
                    return total, []
        except Exception:
            pass

    bpp = _detect_bytes_per_param(repo)

    def _estimated(total_bytes: int) -> tuple[float | RangeValue, list[str]]:
        """Params estimés depuis des octets : valeur si dtype connu, fourchette sinon."""
        if bpp is not None:
            return (_bytes_to_params_estimated(total_bytes, bpp),
                    [f"params-bytes-per-param:{bpp}"])
        return (RangeValue(min=_bytes_to_params_estimated(total_bytes, 2.0),
                           max=_bytes_to_params_estimated(total_bytes, 0.5)),
                ["params-range-unknown-dtype"])

    # Méthode 2 : CLI `hf models info` (used_storage → params estimés)
    cli_info = _fetch_hf_cli_info(repo)
    if cli_info is not None:
        used_storage = cli_info.get("used_storage", 0)
        if used_storage and used_storage > 0:
            total, extra = _estimated(used_storage)
            return total, ["params-from-cli-used_storage", *extra]

    # Méthode 3 : fichiers safetensors via index.json (fallback final)
    total_bytes = _fetch_safetensors_index_bytes(repo)
    if total_bytes is not None and total_bytes > 0:
        total, extra = _estimated(total_bytes)
        return total, ["params-estimated-from-files", *extra]

    return None


def fetch_hf_params(repo: str) -> ParamsResult | None:
    """repo HF → paramètres (total ÷ 1e9, supposé dense). Offline-safe : None si
    la résolution échoue (cf. _fetch_hf_total_params)."""
    resolved = _fetch_hf_total_params(repo)
    if resolved is None:
        return None
    total, warnings = resolved
    if _looks_moe(repo):
        # Nom type MoE traité en dense : l'énergie serait surestimée (calculée
        # sur le total au lieu des params actifs) — signalé en provenance.
        warnings = ["moe-assumed-dense", *warnings]
    return ParamsResult(active=total, total=total, arch="dense",
                        source="huggingface", warnings=warnings)


def fetch_moe_params_from_hf(repo: str, active: float) -> ParamsResult | None:
    """Comme fetch_hf_params mais pour un MoE : le total vient de HF, l'actif est
    fourni par l'utilisateur. None si HF échoue."""
    resolved = _fetch_hf_total_params(repo)
    if resolved is None:
        return None
    total, warnings = resolved
    return ParamsResult(active=active, total=total, arch="moe",
                        source="huggingface", warnings=warnings)


class ModelParamsResolver:
    """Résout (params actifs, totaux) pour un modèle, en cascade :
    registre EcoLogits → cache config → Hugging Face → None."""

    def __init__(self, config):
        self.config = config
        # M1a : clés « provider/model » dont la résolution HF a échoué dans ce
        # run — évite de relancer la cascade réseau à chaque event du même modèle.
        self._hf_failed: set[str] = set()

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
                # Gérer RangeValue (min/max) en prenant la moyenne.
                # EcoLogits expose parfois une plage de paramètres quand l'architecture
                # n'est pas précisément spécifiée. On prend la valeur centrale comme
                # estimation typique ; l'incertitude dominante vient du PUE et du mix,
                # pas de la fourchette des paramètres.
                if isinstance(p, RangeValue):
                    val = (p.min + p.max) / 2.0
                else:
                    val = float(p)
                return ParamsResult(active=val, total=val,
                                    arch="dense", source="registry")
        return None

    def _from_cache(self, provider: str, model: str) -> ParamsResult | None:
        """Tier 2 : params déclarés par l'utilisateur ou résolus précédemment via HF,
        mémorisés dans la config (clé « provider/model »)."""
        entry = self.config.model_params.get(f"{provider}/{model}")
        if entry is None:
            return None
        return ParamsResult(
            active=_param_from_json(entry["active"]),
            total=_param_from_json(entry["total"]),
            arch=entry.get("arch", "dense"), source=entry.get("source", "user"))

    def _negative_fresh(self, key: str) -> bool:
        """Vrai si un échec HF récent (< TTL) est mémorisé en config pour key."""
        ts = self.config.hf_unresolved.get(key)
        if ts is None:
            return False
        try:
            failed_at = datetime.fromisoformat(ts)
        except (ValueError, TypeError):
            return False
        if failed_at.tzinfo is None:
            failed_at = failed_at.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - failed_at < timedelta(days=HF_NEGATIVE_TTL_DAYS)

    def _from_huggingface(self, provider: str, model: str) -> ParamsResult | None:
        """Tier 3 : params depuis le Hub via fetch_hf_params, puis mise en cache.
        arch toujours « dense » ici (fetch_hf_params suppose dense) ; l'affinage
        MoE passe par `resolve --set "P/M=repo:<actifs>"` (cf. resolve/cli.py)."""
        key = f"{provider}/{model}"
        if key in self._hf_failed or self._negative_fresh(key):
            return None
        res = fetch_hf_params(model)
        if res is None:
            self._hf_failed.add(key)
            self.config.hf_unresolved[key] = datetime.now(timezone.utc).isoformat()
            return None
        self.config.hf_unresolved.pop(key, None)
        self.config.model_params[key] = {
            "active": _param_to_json(res.active), "total": _param_to_json(res.total),
            "arch": res.arch, "source": res.source}
        return res
