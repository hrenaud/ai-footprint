import json

from ai_footprint.config import Config
from ai_footprint.impact.engine import EcoLogitsEngine
from ai_footprint.impact.resolver import ModelResolver


def build_engine(config: Config) -> EcoLogitsEngine:
    """Construit le moteur EcoLogits avec les aliases configurés."""
    return EcoLogitsEngine(ModelResolver(config.model_aliases))


def config_snapshot(config: Config) -> str:
    """Empreinte des champs mutés par la résolution (pour ne sauver que si changé)."""
    return json.dumps(
        {"model_params": config.model_params, "hf_unresolved": config.hf_unresolved},
        sort_keys=True, default=str)


def ingest_and_save(store, events, engine, config) -> int:
    """Ingère les events puis persiste la config seulement si l'ingest a
    réussi et a modifié le cache de résolution HF (Q9 : pas de sauvegarde
    partielle si store.ingest() lève une exception)."""
    before = config_snapshot(config)
    n = store.ingest(events, engine, config)
    if config_snapshot(config) != before:
        config.save()
    return n


def ingest_summary(new_count: int, cov: dict, store=None) -> str:
    """Génère un résumé textuel de l'ingest."""
    line = f"{new_count} events ingérés · {cov['measured']}/{cov['total']} mesurés"
    if cov["uncovered"]:
        line += (
            f" · {cov['uncovered']} non couverts "
            "(inférence locale ou fournisseurs tiers non modélisés — conservés, impact non estimé)"
        )
        # Afficher les modèles non couverts (sauf <synthetic> à 0 token)
        if store and cov["uncovered"] > 0:
            rows = store.conn.execute(
                "SELECT e.provider, e.model, COUNT(*) as cnt "
                "FROM events e JOIN impacts i "
                "ON e.session_id=i.session_id AND e.msg_id=i.msg_id "
                "WHERE i.error IS NOT NULL "
                "GROUP BY e.provider, e.model "
                "ORDER BY cnt DESC"
            ).fetchall()
            # Filtrer les <synthetic> (0 token)
            real_models = [r for r in rows if r["model"] != "<synthetic>"]
            if real_models:
                line += "\n  modèles concernés :"
                for r in real_models:
                    line += f"\n    - {r['model']} ({r['cnt']} events)"
        line += (
            "\n  → lance le skill `/footprint-resolve` pour tenter de les "
            "résoudre via Hugging Face."
        )
    return line


def cmd_ingest(args) -> int:
    """Commande ingest : collecter les transcripts et ingérer les impacts."""
    from ai_footprint.collectors.claude_code import ClaudeCodeCollector
    from ai_footprint.collectors.crush import CrushCollector
    from ai_footprint.collectors.pi import PiCollector
    from ai_footprint.store.db import open_store

    store = open_store(args.db)
    if args.source_crush:
        # Détection du mode : si le chemin pointe vers une DB SQLite, backfill.
        if args.source_crush.endswith(".db"):
            events = CrushCollector(backfill_db_path=args.source_crush).collect()
        else:
            events = CrushCollector(root=args.source_crush).collect()
    elif args.source_pi:
        events = PiCollector(root=args.source_pi).collect()
    else:
        events = ClaudeCodeCollector(args.source).collect()
    config = Config.load()
    n = ingest_and_save(store, events, build_engine(config), config)
    print(ingest_summary(n, store.coverage(), store))
    return 0
