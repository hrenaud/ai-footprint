import argparse
import json
import os
import sys

from ai_footprint.card.cli import cmd_card
from ai_footprint.collectors.claude_code import ClaudeCodeCollector
from ai_footprint.ingest.cli import build_engine, cmd_ingest, ingest_and_save
from ai_footprint.models_admin.cli import cmd_models
from ai_footprint.store.db import open_store
from ai_footprint.collectors.crush import CrushCollector
from ai_footprint.collectors.pi import PiCollector
from ai_footprint.config import Config, DEFAULT_CONFIG_PATH
from ai_footprint.config_detect import detect_zone, system_locale
from ai_footprint.dates import parse_since
from ai_footprint.impact.engine import EcoLogitsEngine
from ai_footprint.impact.params import (
    ModelParamsResolver,
    fetch_moe_params_from_hf,
    _param_from_json,
    _param_to_json,
)
from ai_footprint.impact.resolver import ModelResolver
from ai_footprint.report.cli import (
    render_estimated_note,
    render_extrapolated_note,
    render_intensity,
    render_intensity_by_client,
    render_projects,
    render_report,
    render_tokens_by_model,
    render_uncovered,
)
from ai_footprint.release import ReleaseError, run as run_release
from ai_footprint.resolve.cli import cmd_resolve
from ai_footprint.statusline.line import render_statusline
from ai_footprint.store.db import SQLiteStore
from ai_footprint.tool_updates import session_start_check

_DEFAULT_SOURCE = os.path.expanduser("~/.claude/projects")
_DEFAULT_DB = os.path.expanduser("~/.ai-footprint/ai-footprint.db")
_LEGACY_DB = os.path.expanduser("~/.agent-carbon/carbon.db")


def _legacy_db_hint(db_path: str = _DEFAULT_DB,
                    legacy_path: str = _LEGACY_DB) -> str | None:
    """Base agent-carbon présente mais base ai-footprint absente → la migration
    (un simple déplacement du fichier) est faite par install.sh, jamais ici."""
    if os.path.exists(db_path) or not os.path.exists(legacy_path):
        return None
    return (
        f"Base agent-carbon détectée ({legacy_path}) mais pas encore migrée.\n"
        "Relancez l'installeur pour la déplacer vers ~/.ai-footprint/ :\n"
        "  curl -fsSL https://raw.githubusercontent.com/hrenaud/ai-footprint/main/install.sh | bash"
    )

# Rappel affiché en pied de chaque rapport : options et aide.
_REPORT_FOOTER = (
    "ℹ️  Options : `ai-footprint report --help` "
    "(--since <date> · --detail · --all-projects) · aide complète : skill `/footprint-help`"
)


def _store(db_path: str) -> SQLiteStore:
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    return SQLiteStore(db_path)


def _engine(config: Config) -> EcoLogitsEngine:
    return EcoLogitsEngine(ModelResolver(config.model_aliases))


def _maybe_detect_mix(config: Config) -> None:
    if config.electricity_mix_zone is not None or not sys.stdin.isatty():
        return
    guess = detect_zone(system_locale())
    prompt = f"Zone du mix électrique [{guess or 'ex. FRA'}] : "
    answer = input(prompt).strip().upper() or (guess or "")
    if answer:
        config.electricity_mix_zone = answer
        config.save()
        print(f"Zone enregistrée : {answer}")


def _cmd_nudge(args) -> int:
    from pathlib import Path

    from ai_footprint.nudge import (
        build_claude_hook_output,
        check_self_update,
        check_uncovered_batch,
        mark_batch_prompted,
        reset_prompted_keys,
    )

    store = _store(args.db)
    config = Config.load()

    if args.mark_prompted:
        mark_batch_prompted(config, store)
        if not args.json:
            print("Lot de modèles non couverts marqué comme proposé.")
        return 0

    if args.reset_prompted:
        reset_prompted_keys(config)
        if not args.json:
            print("prompted_keys réinitialisé.")
        return 0

    update_available = check_self_update(config, cache_path=Path(args.cache))
    uncovered_new = check_uncovered_batch(store, config, cache_path=Path(args.cache))

    if args.claude_hook:
        output = build_claude_hook_output(update_available, uncovered_new)
        if output:
            print(json.dumps(output, ensure_ascii=False))
        return 0

    result = {"update_available": update_available, "uncovered_new": uncovered_new}
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
        return 0

    if update_available:
        print(f"Mise à jour disponible : {update_available['current']} → {update_available['latest']}")
    if uncovered_new:
        print(f"{len(uncovered_new)} modèle(s) non couvert(s) jamais proposés : {', '.join(uncovered_new)}")
    if not update_available and not uncovered_new:
        print("Rien à signaler.")
    return 0


def _read_stdin_json() -> dict | None:
    """Claude Code passe un JSON de session sur stdin (session_id,
    transcript_path…). Renvoie None en lancement manuel (terminal)."""
    if sys.stdin.isatty():
        return None
    try:
        raw = sys.stdin.read()
    except (OSError, ValueError):
        return None
    if not raw.strip():
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ai-footprint")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ing = sub.add_parser("ingest", help="parser les transcripts et calculer l'impact")
    p_ing.add_argument("--source", default=_DEFAULT_SOURCE)
    p_ing.add_argument("--source-crush", default=None,
                       help="directory d'exports JSON Opencode/Crush, ou chemin vers opencode.db (backfill SQLite)")
    p_ing.add_argument("--source-pi", default=None,
                       help="directory des sessions Pi (~/.pi/agent/sessions), ou fichier JSONL unique")
    p_ing.add_argument("--source-codex", default=None,
                       help="directory des sessions Codex CLI (rollout JSONL), ou fichier unique "
                            "(défaut : $CODEX_HOME/sessions ou ~/.codex/sessions)")
    p_ing.add_argument("--db", default=_DEFAULT_DB)

    p_rep = sub.add_parser("report", help="afficher le rapport multi-critères")
    p_rep.add_argument("--db", default=_DEFAULT_DB)
    p_rep.add_argument("--since", default=None, type=parse_since,
                       help="date de début (ex. 2026-06-27, 27/06/2026, 27/06/26)")
    p_rep.add_argument("--all-projects", action="store_true",
                       help="lister tous les projets (sinon top 5 + « autres »)")
    p_rep.add_argument("--detail", "--detailed", dest="detail", action="store_true",
                       help="afficher les fourchettes min–max au lieu de la valeur centrale (~)")

    p_card = sub.add_parser("card", help="générer une card PNG partageable")
    p_card.add_argument("--db", default=_DEFAULT_DB)
    p_card.add_argument("--since", default=None, type=parse_since,
                        help="date de début (ex. 2026-06-27, 27/06/2026, 27/06/26)")
    p_card.add_argument("--out", default=os.path.expanduser("~/.ai-footprint/exports/"))
    p_card.add_argument("--lang", choices=("fr", "en", "both"), default="both")
    p_card.add_argument("--theme", choices=("light", "dark", "both"), default="light")

    p_st = sub.add_parser("statusline", help="ligne compacte pour la statusline")
    p_st.add_argument("--db", default=_DEFAULT_DB)

    p_mod = sub.add_parser("models", help="lister/renseigner les modèles auto-hébergés non résolus")
    p_mod.add_argument("--db", default=_DEFAULT_DB)

    p_res = sub.add_parser("resolve",
                           help="résoudre les modèles non couverts (params HF) et recalculer")
    p_res.add_argument("--db", default=_DEFAULT_DB)
    p_res.add_argument("--since", default=None, type=parse_since,
                       help="date de début (ex. 2026-06-27, 27/06/2026, 27/06/26)")
    p_res.add_argument("--list", action="store_true")
    p_res.add_argument("--json", action="store_true")
    p_res.add_argument("--set", action="append", default=[], metavar="P/M=REPO")
    p_res.add_argument("--forget", action="append", default=[], metavar="P/M")
    p_res.add_argument("--recompute", action="store_true",
                       help="recalcule les events en erreur des modèles déjà mappés "
                            "(ne tente PAS de nouvelle résolution — voir --retry-hf)")
    p_res.add_argument("--retry-hf", dest="retry_hf", action="store_true",
                       help="purge le cache négatif des non couverts et retente la "
                            "cascade Hugging Face sur tous les events en erreur")

    p_rel = sub.add_parser(
        "release",
        help="bump sémantique, génère le CHANGELOG et créer le tag",
    )
    p_rel_sub = p_rel.add_subparsers(dest="rel_cmd", required=True)
    p_bump = p_rel_sub.add_parser("bump", help="bump la version")
    p_bump.add_argument(
        "part", choices=("patch", "minor", "major"),
        help="partie à bump (patch, minor ou major)",
    )
    p_bump.add_argument("--no-push", action="store_true",
                        help="ne pas pusher main + tags après le release (push par défaut)")

    p_tu = sub.add_parser(
        "tool-updates-check",
        help="signale (hook SessionStart) une mise à jour ecologits/huggingface_hub disponible",
    )
    p_tu.add_argument(
        "--cache",
        default=os.path.join(os.path.dirname(__file__), "..", ".claude", "tool-updates-cache.json"),
    )

    p_nudge = sub.add_parser(
        "nudge",
        help="propose une mise à jour ai-footprint et/ou un resolve des modèles non couverts",
    )
    p_nudge.add_argument("--db", default=_DEFAULT_DB)
    p_nudge.add_argument(
        "--cache",
        default=os.path.expanduser("~/.ai-footprint/nudge-cache.json"),
    )
    p_nudge.add_argument("--json", action="store_true")
    p_nudge.add_argument("--mark-prompted", dest="mark_prompted", action="store_true")
    p_nudge.add_argument("--reset-prompted", dest="reset_prompted", action="store_true")
    p_nudge.add_argument("--claude-hook", dest="claude_hook", action="store_true")

    args = parser.parse_args(argv)

    if getattr(args, "db", None) == _DEFAULT_DB:
        hint = _legacy_db_hint()
        if hint:
            print(hint, file=sys.stderr)
            return 1

    config = Config.load()

    if args.cmd == "ingest":
        return cmd_ingest(args)

    if args.cmd == "report":
        store = _store(args.db)
        _maybe_detect_mix(config)
        rows = store.rows_for_report(args.since)
        out = render_report(rows)
        projects = render_projects(rows, show_all=args.all_projects, detailed=args.detail)
        if projects:
            out += "\n\n" + projects
        tokens = render_tokens_by_model(store.tokens_by_model(args.since), detailed=args.detail)
        if tokens:
            out += "\n\n" + tokens
        estimated = render_estimated_note(store.estimated_param_models(args.since))
        if estimated:
            out += "\n\n" + estimated
        extrapolated = render_extrapolated_note(store.extrapolated_param_models(args.since))
        if extrapolated:
            out += "\n\n" + extrapolated
        uncovered = render_uncovered(store.uncovered_by_model(args.since))
        if uncovered:
            out += "\n\n" + uncovered
        intensity = render_intensity(store.intensity_by_model(args.since), detailed=args.detail)
        if intensity:
            out += "\n\n" + intensity
        by_client = store.intensity_by_client(args.since)
        if len(by_client) > 1:  # n'a de sens que si plusieurs outils sont présents
            intensity_client = render_intensity_by_client(by_client, detailed=args.detail)
            if intensity_client:
                out += "\n\n" + intensity_client
        out += "\n\n" + _REPORT_FOOTER
        print(out)
        return 0

    if args.cmd == "card":
        return cmd_card(args)

    if args.cmd == "statusline":
        store = _store(args.db)
        # Claude Code fournit la session courante sur stdin.
        data = _read_stdin_json()
        session_id = data.get("session_id") if data else None
        transcript = data.get("transcript_path") if data else None
        # Ingestion à la volée du transcript courant (idempotent) → impact à
        # jour même en cours de session, sans attendre le hook Stop.
        if transcript and os.path.exists(transcript):
            ingest_and_save(store, ClaudeCodeCollector(transcript).collect(), build_engine(config), config)
        print(render_statusline(store.rows_for_report(session_id=session_id)))
        return 0

    if args.cmd == "models":
        return cmd_models(args)

    if args.cmd == "resolve":
        return cmd_resolve(args)

    if args.cmd == "release":
        try:
            new = run_release(args.part, push=not args.no_push)
            if args.no_push:
                print(f"Release {new} créé (tag `v{new}`) — push avec `git push origin main --tags`.")
            else:
                print(f"Release {new} créé et pushé (tag `v{new}`).")
            return 0
        except ReleaseError as e:
            print(f"Release bloqué : {e}", file=sys.stderr)
            return 1

    if args.cmd == "tool-updates-check":
        from pathlib import Path
        notice = session_start_check(Path(args.cache))
        if notice:
            print(notice)
        return 0

    if args.cmd == "nudge":
        return _cmd_nudge(args)

    return 1


if __name__ == "__main__":
    sys.exit(main())
