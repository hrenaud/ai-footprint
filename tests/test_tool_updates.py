from ai_footprint.tool_updates import (
    check_updates,
    current_ecologits_tag,
    current_hf_min_version,
    format_issue_body,
    parse_version,
)

PYPROJECT_SAMPLE = """
dependencies = [
  "ecologits==0.11.0",
  "huggingface_hub>=0.20",
]
"""


def test_current_ecologits_tag():
    assert current_ecologits_tag(PYPROJECT_SAMPLE) == "0.11.0"


def test_current_hf_min_version():
    assert current_hf_min_version(PYPROJECT_SAMPLE) == "0.20"


def test_parse_version_plain():
    assert parse_version("0.11.0") == (0, 11, 0)


def test_parse_version_with_v_prefix():
    assert parse_version("v0.11.2") == (0, 11, 2)


def test_parse_version_two_parts():
    assert parse_version("0.20") == (0, 20)


def test_check_updates_detects_newer_hf():
    updates = check_updates(PYPROJECT_SAMPLE, hf_latest="0.35.0", ecologits_latest="0.11.0")
    assert {"package": "huggingface_hub", "current": "0.20", "latest": "0.35.0"} in updates
    assert len(updates) == 1


def test_check_updates_detects_newer_ecologits():
    updates = check_updates(PYPROJECT_SAMPLE, hf_latest="0.20", ecologits_latest="0.12.0")
    assert {"package": "ecologits", "current": "0.11.0", "latest": "0.12.0"} in updates
    assert len(updates) == 1


def test_check_updates_no_diff_returns_empty():
    updates = check_updates(PYPROJECT_SAMPLE, hf_latest="0.20", ecologits_latest="0.11.0")
    assert updates == []


def test_format_issue_body_mentions_no_auto_update():
    body = format_issue_body({"package": "ecologits", "current": "0.11.0", "latest": "0.12.0"})
    assert "0.11.0" in body
    assert "0.12.0" in body
    assert "automatique" in body.lower()
