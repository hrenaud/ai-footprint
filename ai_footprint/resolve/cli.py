import json
import sys

from ecologits.utils.range_value import RangeValue

from ai_footprint.config import Config
from ai_footprint.impact.engine import EcoLogitsEngine
from ai_footprint.impact.params import (
    fetch_hf_params, fetch_moe_params_from_hf, _param_to_json)
from ai_footprint.impact.resolver import ModelResolver
from ai_footprint.store.db import SQLiteStore


def fmt_params_md(v) -> str:
    """Formatte un compte de params (Md) — valeur ou fourchette."""
    if isinstance(v, RangeValue):
        return f"{v.min:.1f}–{v.max:.1f}"
    return f"{v:.1f}"


def parse_mapping(spec: str) -> tuple[str, str | None, float | None]:
    """ 'provider/model=hf_repo[:actif]' → (clé, repo, actif|None). Coupe au 1er '='.
    Un suffixe « :actif » côté repo déclare un MoE (params actifs en Md ; le total
    vient de HF). Le « : » est sans ambiguïté : un repo HF n'en contient pas (la
    révision se note « @ »), et le « : » d'une clé reste à gauche du « = »."""
    key, _, repo = spec.partition("=")
    repo, sep, active_str = repo.strip().partition(":")
    active = active_str if sep else None
    return key.strip(), repo, active


def set_mappings(config, specs: list[str]) -> list[dict]:
    """Pour chaque mapping, récupère les params sur HF et les persiste sous la clé
    provider/model avec provenance. Un suffixe « :actif » déclare un MoE (total HF,
    actif saisi). Échec géré par item, sans interrompre les autres."""
    results = []
    for spec in specs:
        key, repo, active_str = parse_mapping(spec)
        if not key or not repo:
            results.append({"key": key, "repo": repo, "ok": False, "error": "format"})
            continue
        active = None
        if active_str is not None:
            try:
                active = float(active_str)
            except ValueError:
                results.append({"key": key, "repo": repo, "ok": False,
                                "error": "active-format"})
                continue
        # Choisir la fonction de résolution selon qu'un actif est déclaré (MoE) ou non (dense).
        if active is not None:
            params = fetch_moe_params_from_hf(repo, active)
            if params is None:
                results.append({"key": key, "repo": repo, "ok": False,
                                "error": "hf-unresolved"})
                continue
            # Validation MoE : active doit être > 0 et ≤ total (prendre max si fourchette)
            total_max = params.total.max if isinstance(params.total, RangeValue) else params.total
            if active <= 0 or active > total_max:
                results.append({"key": key, "repo": repo, "ok": False,
                                "error": "active-gt-total"})
                continue
            entry_active, arch = active, "moe"
        else:
            params = fetch_hf_params(repo)
            if params is None:
                results.append({"key": key, "repo": repo, "ok": False,
                                "error": "hf-unresolved"})
                continue
            entry_active, arch = params.active, params.arch
        config.model_params[key] = {
            "active": _param_to_json(entry_active), "total": _param_to_json(params.total),
            "arch": arch, "source": "resolve", "hf_repo": repo}
        results.append({"key": key, "repo": repo, "ok": True,
                        "params": fmt_params_md(params.total),
                        "active": fmt_params_md(entry_active), "arch": arch})
    return results


def forget(config, keys: list[str]) -> list[dict]:
    """Retire chaque clé de model_params (revert d'un mapping)."""
    return [{"key": k, "removed": config.model_params.pop(k, None) is not None}
            for k in keys]


def _print_set(results: list[dict], as_json: bool) -> None:
    if as_json:
        print(json.dumps(results, ensure_ascii=False))
        return
    for r in results:
        if r["ok"]:
            if r.get("arch") == "moe":
                detail = f"MoE {r['active']} actifs / {r['params']} Md"
            else:
                detail = f"{r['params']} Md"
            print(f"✓ {r['key']} → {r['repo']} ({detail})")
        else:
            print(f"✗ {r['key']} → {r['repo'] or '?'} : {r['error']}")


def _print_forget(results: list[dict]) -> None:
    for r in results:
        print(f"{'retiré' if r['removed'] else 'absent'} : {r['key']}")


def _print_recompute(delta: dict) -> None:
    print(f"Recompute : {delta['before']} → {delta['after']} non couverts")


def _print_list(rows: list[dict], as_json: bool, *, numbered: bool = False) -> None:
    if as_json:
        print(json.dumps(rows, ensure_ascii=False))
        return
    if not rows:
        print("Aucun lot non résolu.")
        return
    for index, r in enumerate(rows, start=1):
        prefix = f"{index}. " if numbered else "· "
        print(
            f"{prefix}client={r['client'] or 'inconnu'} modèle={r['model_raw']} "
            f"session={r['session_id']} période={r['first_seen']}..{r['last_seen']} "
            f"tokens={r['tokens']} événements={r['events']}"
        )


def _field_error(field: str, reason: str) -> int:
    print(f"{field}: {reason}", file=sys.stderr)
    return 2


def _interactive_resolution(store: SQLiteStore) -> dict | None:
    batches = store.unresolved_batches()
    if not batches:
        print("Aucun lot non résolu.")
        return None
    _print_list(batches, False, numbered=True)
    while True:
        value = input("Lot à résoudre (numéro) : ").strip()
        try:
            batch = batches[int(value) - 1]
        except (ValueError, IndexError):
            print("lot: choisissez un numéro affiché.", file=sys.stderr)
            continue
        break
    routes = ("anthropic", "openai", "openrouter", "custom", "local")
    print("Routes : " + ", ".join(f"{i + 1}={route}" for i, route in enumerate(routes)))
    while True:
        value = input("Route (numéro ou nom) : ").strip().lower()
        route = routes[int(value) - 1] if value.isdigit() and 0 < int(value) <= len(routes) else value
        if route in routes:
            break
        print("route: choisissez une route affichée.", file=sys.stderr)
    while True:
        model = input("Modèle canonique : ").strip()
        if model:
            break
        print("model: obligatoire.", file=sys.stderr)
    result = {"session": batch["session_id"], "client": batch["client"],
              "raw_model": batch["model_raw"], "route": route, "model": model,
              "repo": None, "active_params": None, "total_params": None}
    if route == "local":
        result["repo"] = input("Dépôt Hugging Face (optionnel) : ").strip() or None
        while True:
            try:
                result["active_params"] = float(input("Paramètres actifs (Md) : "))
            except ValueError:
                print("active-params: saisissez un nombre en milliards.", file=sys.stderr)
                continue
            if result["active_params"] <= 0:
                print("active-params: doit être positif.", file=sys.stderr)
                continue
            break
        while True:
            try:
                result["total_params"] = float(input("Paramètres totaux (Md) : "))
            except ValueError:
                print("total-params: saisissez un nombre en milliards.", file=sys.stderr)
                continue
            if result["total_params"] <= 0:
                print("total-params: doit être positif.", file=sys.stderr)
                continue
            if result["total_params"] < result["active_params"]:
                print("total-params: must be at least active-params.", file=sys.stderr)
                continue
            break
    return result


def _resolve_selected(store: SQLiteStore, config: Config, args) -> int:
    route = getattr(args, "route", None)
    model = getattr(args, "model", None)
    session = getattr(args, "session", None)
    client = getattr(args, "client", None)
    raw_model = getattr(args, "raw_model", None)
    since = getattr(args, "since", None)
    repo = getattr(args, "repo", None)
    active = getattr(args, "active_params", None)
    total = getattr(args, "total_params", None)
    if not route and sys.stdin.isatty():
        selected = _interactive_resolution(store)
        if selected is None:
            return 0
        route, model, session = selected["route"], selected["model"], selected["session"]
        client, raw_model = selected["client"], selected["raw_model"]
        repo, active, total = selected["repo"], selected["active_params"], selected["total_params"]
    if not route:
        return 0
    if route not in {"anthropic", "openai", "openrouter", "custom", "local"}:
        return _field_error("route", "must be anthropic, openai, openrouter, custom, or local")
    if not session and not since:
        return _field_error("scope", "provide --session or --since")
    if not model:
        return _field_error("model", "required with --route")
    if client is None:
        return _field_error("client", "required with --route")
    if not raw_model:
        return _field_error("raw-model", "required with --route")
    if route == "local":
        if active is None or total is None:
            return _field_error("params", "--active-params and --total-params are required for local")
        if active <= 0:
            return _field_error("active-params", "must be positive")
        if total <= 0:
            return _field_error("total-params", "must be positive")
        if active > total:
            return _field_error("active-params", "must not exceed total-params")
        config.model_params[f"local/{model}"] = {
            "active": active, "total": total, "arch": "moe" if active != total else "dense",
            "source": "resolve", "hf_repo": repo,
        }
        config.save()
    changed = store.resolve_events(
        route=route, model_canonical=model, client=client, model_raw=raw_model,
        session_id=session, since=since,
    )
    engine = EcoLogitsEngine(ModelResolver(config.model_aliases))
    recomputed = store.recompute_selected_events(
        engine, config, route=route, model_canonical=model, client=client,
        model_raw=raw_model, session_id=session, since=since,
    )
    print(f"Résolution : {changed} événement(s), {recomputed} recalculé(s).")
    return 0


def cmd_resolve(args) -> int:
    store = SQLiteStore(args.db)
    config = Config.load()
    changed = False
    forgotten_models = []

    if args.set:
        results = set_mappings(config, args.set)
        changed = any(r["ok"] for r in results) or changed
        _print_set(results, args.json)
    if args.forget:
        results = forget(config, args.forget)
        changed = any(r["removed"] for r in results) or changed
        _print_forget(results)
        # Track which models were forgotten to mark their events as errors
        forgotten_models = [r["key"] for r in results if r["removed"]]
    if changed:
        config.save()
    # Mark events referencing forgotten models as errors, so they'll be recomputed
    for model_key in forgotten_models:
        provider, model = model_key.split("/", 1)
        store.mark_model_events_error(provider, model, "model-params-reset")

    retry_hf = getattr(args, "retry_hf", False)
    if retry_hf:
        # Purge du cache négatif pour les modèles encore non couverts, puis
        # recompute complet : la cascade retentera le tier Hugging Face.
        for provider, model in store.uncovered_keys():
            config.hf_unresolved.pop(f"{provider}/{model}", None)

    if args.recompute or retry_hf or changed:
        engine = EcoLogitsEngine(ModelResolver(config.model_aliases))
        _print_recompute(store.recompute_errors(engine, config, retry_all=retry_hf))
        if retry_hf:
            config.save()  # persiste les succès (cache positif) et les nouveaux échecs
    if args.list:
        _print_list(store.unresolved_batches(), args.json)
    return _resolve_selected(store, config, args)
