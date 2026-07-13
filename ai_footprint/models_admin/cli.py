import sys

from ai_footprint.config import Config
from ai_footprint.impact.params import (
    ModelParamsResolver,
    fetch_moe_params_from_hf,
    _param_from_json,
    _param_to_json,
)
from ai_footprint.store.db import open_store


def cmd_models(args) -> int:
    """Lister et renseigner les modèles auto-hébergés non résolus."""
    store = open_store(args.db)
    pending = store.list_pending()
    if not pending:
        print("Aucun modèle auto-hébergé en attente.")
        return 0
    for row in pending:
        print(f"· {row['provider']}/{row['model']} "
              f"({row['occurrences']} occurrences)")
    if not sys.stdin.isatty():
        return 0
    config = Config.load()
    accepted = []  # Collect (provider, model) to clear AFTER save
    for row in pending:
        # Étape 1 : type (dense/MoE)
        ans = input(
            f"Type pour {row['model']} (dense/MoE, vide = dense) : "
        ).strip().lower()
        if not ans or ans == "dense":
            # Dense : seul total demandé
            total_str = input(
                f"Params totaux pour {row['model']} "
                "en milliards (ex. 7 pour un modèle 7B, vide = ignorer) : "
            ).strip()
            if not total_str:
                continue
            try:
                total = float(total_str)
            except ValueError:
                print("Format invalide, ignoré.")
                continue
            config.model_params[f"{row['provider']}/{row['model']}"] = {
                "active": total, "total": total, "arch": "dense", "source": "user"}
            accepted.append((row["provider"], row["model"]))
        elif ans == "moe":
            # MoE : actif demandé, total cherché dans cache, registry, HF
            active_str = input(
                f"Params actifs pour {row['model']} "
                "en milliards (ex. 3,5 pour 3,5 Md) : "
            ).strip()
            if not active_str:
                continue
            try:
                active = float(active_str)
            except ValueError:
                print("Format invalide, ignoré.")
                continue
            # 1) Chercher dans cache (peut-être dense)
            key = f"{row['provider']}/{row['model']}"
            cache_entry = config.model_params.get(key)
            cache_total = None
            if cache_entry is not None:
                cached = _param_from_json(cache_entry.get("total", active))
                cache_total = cached.max if hasattr(cached, "max") else float(cached)
            # 2) Chercher dans registry via ModelParamsResolver
            resolver = ModelParamsResolver(config)
            res = resolver.resolve(row["provider"], row["model"])
            # 3) Tenter fetch MoE depuis HF
            hf_res = fetch_moe_params_from_hf(row["model"], active)
            if hf_res is not None:
                # HF trouvé → stocker comme MoE avec hf_repo
                config.model_params[key] = {
                    "active": _param_to_json(active), "total": _param_to_json(hf_res.total),
                    "arch": "moe", "source": "user",
                    "hf_repo": row["model"]}
            elif cache_total is not None:
                # Cache trouvé → utiliser son total, garder l'archi MoE du user
                # Ne pas écraser l'archi du cache si c'est dense
                # Laisser l'entry existante inchangée, juste stocker active si manquant
                if key not in config.model_params:
                    config.model_params[key] = {
                        "active": _param_to_json(active), "total": _param_to_json(cache_total),
                        "arch": "moe", "source": "user"}
            else:
                # 4) Fallback : ni cache ni HF → total = active, stocker pour résolution future
                config.model_params[key] = {
                    "active": _param_to_json(active), "total": _param_to_json(active),
                    "arch": "moe", "source": "user"}
            accepted.append((row["provider"], row["model"]))
    # Save config durably BEFORE clearing any pending models
    config.save()
    # Now clear the accepted models from pending
    for provider, model in accepted:
        store.clear_pending(provider, model)
    print("Paramètres enregistrés. Relancez `ai-footprint ingest`.")
    return 0
