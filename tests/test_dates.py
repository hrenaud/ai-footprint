import pytest

from ai_footprint.dates import parse_since, parse_iso_ts, ts_from_epoch_ms


def test_iso_date_kept():
    assert parse_since("2026-06-27") == "2026-06-27"


def test_french_full_year():
    assert parse_since("27/06/2026") == "2026-06-27"


def test_french_short_year():
    assert parse_since("27/06/26") == "2026-06-27"


def test_full_iso_timestamp_passthrough():
    # un timestamp ISO complet (avec heure/TZ) reste inchangé (rétro-compat)
    assert parse_since("2026-06-27T00:00:00Z") == "2026-06-27T00:00:00Z"


def test_whitespace_trimmed():
    assert parse_since("  2026-06-27  ") == "2026-06-27"


def test_unrecognized_raises():
    with pytest.raises(ValueError):
        parse_since("pas-une-date")


def test_parse_iso_ts_with_z_suffix():
    dt = parse_iso_ts("2026-07-13T10:00:00Z")
    assert dt is not None
    assert dt.isoformat() == "2026-07-13T10:00:00+00:00"


def test_parse_iso_ts_invalid_returns_none():
    assert parse_iso_ts("not-a-date") is None


def test_parse_iso_ts_non_string_returns_none():
    assert parse_iso_ts(None) is None


def test_ts_from_epoch_ms_none_returns_none():
    assert ts_from_epoch_ms(None) is None


def test_ts_from_epoch_ms_converts_to_iso_utc():
    result = ts_from_epoch_ms(1783936800000)
    assert result == "2026-07-13T10:00:00+00:00"
