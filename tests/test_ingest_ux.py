import logging

from ai_footprint.config import Config
from ai_footprint.ingest.cli import ingest_summary
from ai_footprint.impact.engine import EcoLogitsEngine
from ai_footprint.impact.resolver import ModelResolver
from ai_footprint.models import InferenceEvent
from ai_footprint.store.db import SQLiteStore


def _events():
    return [
        # modèle connu d'EcoLogits → mesuré
        InferenceEvent("anthropic", "claude-opus-4-8", 100, 200, 0, 0,
                       "2026-06-27T10:00:00.000Z", "projA", "sess-A", "u1"),
        # modèle inconnu (local) → non couvert
        InferenceEvent("anthropic", "Qwen3.6-35B-A3B-4bit", 100, 50, 0, 0,
                       "2026-06-27T10:05:00.000Z", "projA", "sess-A", "u2"),
    ]


def test_ecologits_logger_is_silenced_on_import():
    # Importer l'engine doit museler le bruit brut d'EcoLogits (warning_once).
    assert logging.getLogger("ecologits").level >= logging.ERROR


def test_coverage_counts_measured_and_uncovered(tmp_path):
    store = SQLiteStore(str(tmp_path / "c.db"))
    store.ingest(_events(), EcoLogitsEngine(ModelResolver({})), Config())
    cov = store.coverage()
    assert cov["total"] == 2
    assert cov["measured"] == 1
    assert cov["uncovered"] == 1


def testingest_summary_wording_is_reassuring():
    # Avec des non-couverts : message calme, sans "erreur"/"warning".
    msg = ingest_summary(2, {"total": 100, "measured": 93, "uncovered": 7})
    assert "2 events ingérés" in msg
    assert "93/100 mesurés" in msg
    assert "non couverts" in msg
    assert "erreur" not in msg.lower()
    assert "warning" not in msg.lower()


def testingest_summary_no_uncovered_clause_when_full_coverage():
    msg = ingest_summary(2, {"total": 2, "measured": 2, "uncovered": 0})
    assert "2 events ingérés" in msg
    assert "non couverts" not in msg


def testingest_summary_suggests_resolve_skill_when_uncovered():
    msg = ingest_summary(2, {"total": 100, "measured": 93, "uncovered": 7})
    assert "/footprint-resolve" in msg


def testingest_summary_no_resolve_hint_when_full_coverage():
    msg = ingest_summary(2, {"total": 2, "measured": 2, "uncovered": 0})
    assert "/footprint-resolve" not in msg
