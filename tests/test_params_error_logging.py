import json
import logging
import sys
import types

import pytest

import ai_footprint.impact.params as params_mod


def test_hf_total_params_model_info_failure_is_logged(monkeypatch, caplog):
    mod = types.ModuleType("huggingface_hub")

    def fake_model_info(repo, timeout=10):
        raise OSError("boom")

    mod.model_info = fake_model_info
    monkeypatch.setattr(params_mod, "huggingface_hub", mod)
    monkeypatch.setattr(
        params_mod, "_fetch_safetensors_index_bytes", lambda repo: None)

    with caplog.at_level(logging.DEBUG, logger="ai_footprint.impact.params"):
        result = params_mod._fetch_hf_total_params("org/model")

    assert result is None
    assert "org/model" in caplog.text


def test_index_bytes_request_failure_is_logged(monkeypatch, caplog):
    import urllib.request

    def fake_urlopen(req, timeout=15):
        raise __import__("urllib.error", fromlist=["URLError"]).URLError("dns fail")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    with caplog.at_level(logging.DEBUG, logger="ai_footprint.impact.params"):
        result = params_mod._fetch_safetensors_index_bytes("org/model")

    assert result is None
    assert "org/model" in caplog.text


def test_index_bytes_head_failure_is_logged(monkeypatch, caplog):
    import urllib.request

    index = {
        "weight_map": {"a": "model-00001-of-00002.safetensors",
                        "b": "model-00002-of-00002.safetensors"}
    }

    class _Resp:
        def __init__(self, for_head=False):
            self.for_head = for_head
            self.headers = {"Content-Length": "1024"}

        def read(self):
            return json.dumps(index).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=15):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        is_head = hasattr(req, "method") and req.method == "HEAD"
        if is_head and "resolve" in url and "model-00001" in url:
            raise OSError("head failed")
        return _Resp(for_head=is_head)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    with caplog.at_level(logging.DEBUG, logger="ai_footprint.impact.params"):
        params_mod._fetch_safetensors_index_bytes("org/model")

    assert "org/model" in caplog.text
