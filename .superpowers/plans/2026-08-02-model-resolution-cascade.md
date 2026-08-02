# Model Resolution Cascade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Estimate attributable models missing from EcoLogits through a documented exact-registry, sibling, then user-confirmed Hugging Face cascade.

**Architecture:** Keep EcoLogits as the only calculation engine. Confirmed `openai` and `anthropic` events first use their normal `llm_impacts` calculation; a registry miss falls back to the nearest earlier sibling of the same provider through that same provider path. Confirmed `local` events, and models without a sibling, use the existing parameter-based EcoLogits calculation only when explicit parameters or a user-confirmed Hugging Face repository are available.

**Tech Stack:** Python 3.13, EcoLogits, huggingface_hub, SQLite, pytest.

## Global Constraints

- Preserve `events.model_raw` exactly; only `route` and `model_canonical` are confirmed by `resolve`.
- Never estimate `unknown`, `openrouter`, or `custom` routes without an explicit `resolve` confirmation.
- Do not invent a Hugging Face repository or MoE active parameter count.
- Explicit user mappings in `Config.model_params` override automatic Hugging Face lookup.
- Use the project test command: `/Users/renaudheluin/DEV/ia/agent-carbon/.venv/bin/python -m pytest`.

---

### Task 1: Expose Provider-Specific Sibling Resolution

**Files:**
- Modify: `ai_footprint/impact/params.py:267-425`
- Test: `tests/test_params_resolver.py`

**Interfaces:**
- Produces: `ModelParamsResolver.find_sibling(provider: str, model: str) -> str | None`.
- Produces: `ModelParamsResolver.resolve(provider: str, model: str) -> ParamsResult | None` with order exact registry, explicit cached mapping, sibling, then Hugging Face.

- [ ] **Step 1: Write the failing tests**

```python
def test_find_sibling_returns_newest_prior_model_for_same_provider(monkeypatch):
    resolver = ModelParamsResolver(Config())
    monkeypatch.setattr(params_mod.models, "list_models", lambda: [
        _model("openai", "gpt-5.4"),
        _model("openai", "gpt-5.5"),
        _model("anthropic", "gpt-5.9"),
    ])
    assert resolver.find_sibling("openai", "gpt-5.6-terra") == "gpt-5.5"


def test_resolve_uses_sibling_before_huggingface(monkeypatch):
    resolver = ModelParamsResolver(Config())
    monkeypatch.setattr(resolver, "_from_registry", lambda *_: None)
    monkeypatch.setattr(resolver, "_from_cache", lambda *_: None)
    monkeypatch.setattr(resolver, "find_sibling", lambda *_: "gpt-5.5")
    monkeypatch.setattr(resolver, "_from_huggingface", lambda *_: pytest.fail("HF must not run"))
    assert resolver.resolve("openai", "gpt-5.6-terra").warnings == [
        "params-extrapolated-openai:gpt-5.5"
    ]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `/Users/renaudheluin/DEV/ia/agent-carbon/.venv/bin/python -m pytest tests/test_params_resolver.py -q`

Expected: FAIL because `find_sibling` is not public and Hugging Face is currently tried before siblings.

- [ ] **Step 3: Implement the minimal resolution order**

```python
def find_sibling(self, provider: str, model: str) -> str | None:
    return _find_sibling(provider, model)

def resolve(self, provider: str, model: str) -> ParamsResult | None:
    return (
        self._from_registry(provider, model)
        or self._from_cache(provider, model)
        or self._from_sibling_extrapolation(provider, model)
        or self._from_huggingface(provider, model)
    )
```

- [ ] **Step 4: Run the focused tests**

Run: `/Users/renaudheluin/DEV/ia/agent-carbon/.venv/bin/python -m pytest tests/test_params_resolver.py -q`

Expected: PASS.

### Task 2: Apply the Cascade to Confirmed Provider Routes

**Files:**
- Modify: `ai_footprint/impact/engine.py:74-153`
- Test: `tests/test_engine.py`

**Interfaces:**
- Consumes: `ModelParamsResolver.find_sibling()` and `ParamsResult`.
- Produces: provider impact records that retain the requested canonical model and add `model-source:sibling:<provider>:<model>` only when a sibling is used.

- [ ] **Step 1: Write failing engine tests**

```python
def test_openai_registry_miss_uses_prior_sibling(monkeypatch):
    event = InferenceEvent(
        "openai", "gpt-5.6-terra", 10, 20, 0, 0, "2026-08-02T00:00:00Z",
        route="openai", model_canonical="gpt-5.6-terra",
    )
    monkeypatch.setattr(engine_mod, "llm_impacts", _unknown_model_then_gpt_55)
    record = EcoLogitsEngine(ModelResolver({})).compute(event, Config())
    assert record.error is None
    assert record.model_resolved == "gpt-5.6-terra"
    assert "model-source:sibling:openai:gpt-5.5" in record.warnings


def test_unknown_route_never_uses_sibling(monkeypatch):
    event = InferenceEvent("openai", "gpt-5.6-terra", 10, 20, 0, 0,
                           "2026-08-02T00:00:00Z", route="unknown")
    assert EcoLogitsEngine(ModelResolver({})).compute(event, Config()).error == "route-not-estimated"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `/Users/renaudheluin/DEV/ia/agent-carbon/.venv/bin/python -m pytest tests/test_engine.py -q`

Expected: FAIL because `_compute_registry()` returns EcoLogits' unknown-model error without retrying a sibling.

- [ ] **Step 3: Implement the provider fallback**

Retry `llm_impacts()` only after an exact-model error and only with the sibling
returned by `ModelParamsResolver.find_sibling(route, canonical)`. Build the
result with `model_resolved=event.model_canonical`, retain EcoLogits warnings,
and append `model-source:sibling:<route>:<sibling>`. Do not retry when no sibling
exists.

- [ ] **Step 4: Run focused engine tests**

Run: `/Users/renaudheluin/DEV/ia/agent-carbon/.venv/bin/python -m pytest tests/test_engine.py tests/test_engine_selfhosted.py -q`

Expected: PASS.

### Task 3: Use Confirmed Parameter Mappings After a Provider Registry Miss

**Files:**
- Modify: `ai_footprint/impact/engine.py:118-153`
- Modify: `ai_footprint/impact/params.py:386-425`
- Test: `tests/test_engine.py`
- Test: `tests/test_engine_selfhosted.py`
- Test: `tests/test_params_huggingface.py`

**Interfaces:**
- Consumes: a persisted explicit mapping `Config.model_params["<provider>/<canonical>"]`.
- Produces: parameter-based impacts for confirmed `openai`, `anthropic`, and `local` routes when neither the exact registry nor a sibling is available.
- Produces: `model-source:huggingface:<repo>` in the inferred impact warnings.

- [ ] **Step 1: Write failing provenance tests**

```python
def test_openai_huggingface_mapping_calculates_after_registry_miss(monkeypatch):
    config = Config(model_params={"openai/Org/Model": {
        "active": 7.0, "total": 7.0, "arch": "dense", "source": "resolve",
        "hf_repo": "Org/Model",
    }})
    record = EcoLogitsEngine(ModelResolver({})).compute(_openai_event("Org/Model"), config)
    assert record.error is None
    assert record.model_resolved == "Org/Model"
    assert "model-source:huggingface:Org/Model" in record.warnings
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `/Users/renaudheluin/DEV/ia/agent-carbon/.venv/bin/python -m pytest tests/test_engine.py tests/test_engine_selfhosted.py tests/test_params_huggingface.py -q`

Expected: FAIL because `_compute_registry()` returns the registry error instead of using the confirmed parameter mapping.

- [ ] **Step 3: Implement the minimal provenance warning**

Extract the existing direct `compute_llm_impacts()` call into one private engine
method that accepts the requested canonical model, `ParamsResult`, and the event.
Use it for local models and after an attributable provider's exact-registry and
sibling paths have both failed. Resolve parameters with
`ModelParamsResolver.resolve(event.route, canonical)` so explicit
`<provider>/<canonical>` mappings work for provider routes. When the resolved
mapping has `hf_repo`, append `model-source:huggingface:<repo>` once. Preserve
current range, MoE, and extrapolation warnings.

- [ ] **Step 4: Run focused fallback tests**

Run: `/Users/renaudheluin/DEV/ia/agent-carbon/.venv/bin/python -m pytest tests/test_engine.py tests/test_engine_selfhosted.py tests/test_params_huggingface.py -q`

Expected: PASS.

### Task 4: Document Interactive Resolution and Provenance

**Files:**
- Modify: `docs/GUIDE-AVANCE.md:109-136`
- Modify: `docs/METHODOLOGY.md:84-104`
- Test: `tests/test_docs_site.py`

**Interfaces:**
- Documents: confirmed route requirement, exact/sibling/HF order, warnings, and the non-estimation of opaque routes.

- [ ] **Step 1: Update the advanced guide**

Document that interactive `resolve` prompts for each `unknown` batch, that a
non-interactive resolution requires the scoped flags, and that the cascade only
runs after route confirmation.

- [ ] **Step 2: Update the methodology**

Document that sibling estimates use the latest earlier same-provider model,
Hugging Face parameter estimates require a confirmed repository, and both are
reported as inferred sources.

- [ ] **Step 3: Run documentation tests**

Run: `/Users/renaudheluin/DEV/ia/agent-carbon/.venv/bin/python -m pytest tests/test_docs_site.py -q`

Expected: PASS.

### Task 5: Backfill Confirmed GPT Events

**Files:**
- Modify: `~/.ai-footprint/ai-footprint.db` (user data only; no repository file)

**Interfaces:**
- Consumes: the engine from this worktree and the user-approved route `openai` / canonical model `gpt-5.6-terra`.
- Produces: recalculated GPT impacts retaining `model_raw="gpt-5.6-terra"` and sibling provenance.

- [ ] **Step 1: Back up the database**

Run:

```bash
sqlite3 "$HOME/.ai-footprint/ai-footprint.db" \
  ".backup '$HOME/.ai-footprint/ai-footprint.db.before-gpt-resolution-20260802.sqlite'"
```

- [ ] **Step 2: Confirm and recalculate the bounded OpenCode batch**

Run:

```bash
/Users/renaudheluin/DEV/ia/agent-carbon/.venv/bin/python -m ai_footprint resolve \
  --db "$HOME/.ai-footprint/ai-footprint.db" \
  --since "2026-01-01T00:00:00Z" \
  --client opencode \
  --raw-model "gpt-5.6-terra" \
  --route openai \
  --model "gpt-5.6-terra"
```

- [ ] **Step 3: Verify the backfill**

Run:

```bash
sqlite3 "$HOME/.ai-footprint/ai-footprint.db" \
  "SELECT COUNT(*) FROM events e JOIN impacts i ON e.session_id=i.session_id AND e.msg_id=i.msg_id WHERE e.model_raw='gpt-5.6-terra' AND i.error IS NOT NULL;"
```

Expected: `0`.

### Task 6: Run the Full Verification Suite

**Files:**
- No additional files.

- [ ] **Step 1: Run all tests**

Run: `/Users/renaudheluin/DEV/ia/agent-carbon/.venv/bin/python -m pytest`

Expected: PASS with no failures.

- [ ] **Step 2: Inspect the intended changes**

Run: `git diff --check && git diff -- . ':!CHANGELOG.md'`

Expected: only the cascade, its tests, documentation, and the approved spec/plan.

### Task 7: Persist Confirmed Identity Resolutions

**Files:**
- Modify: `ai_footprint/config.py`
- Modify: `ai_footprint/store/db.py:138-187`
- Modify: `ai_footprint/resolve/cli.py:189-242`
- Modify: `docs/GUIDE-AVANCE.md`
- Test: `tests/test_config_persist.py`
- Test: `tests/test_resolve_cli.py`
- Test: `tests/test_ingest_and_save.py`
- Test: `tests/test_docs_site.py`

**Interfaces:**
- Produces: `Config.model_resolutions: dict[str, dict[str, str]]`, keyed by
  `"<client>/<model_raw>"`, whose values contain `route` and `model`.
- Consumes: an `unknown` `InferenceEvent` during `SQLiteStore.ingest()`.
- Produces: events that retain `model_raw` and receive the persisted confirmed
  route and canonical model before impact calculation.

- [ ] **Step 1: Write failing persistence and ingestion tests**

```python
def test_config_persists_model_resolution(tmp_path):
    path = tmp_path / "config.json"
    Config(model_resolutions={"opencode/gpt-5.6-terra": {
        "route": "openai", "model": "gpt-5.6-terra",
    }}).save(str(path))
    assert Config.load(str(path)).model_resolutions["opencode/gpt-5.6-terra"] == {
        "route": "openai", "model": "gpt-5.6-terra",
    }


def test_ingest_applies_persisted_resolution_before_calculation(tmp_path):
    config = Config(model_resolutions={"opencode/gpt-5.6-terra": {
        "route": "openai", "model": "gpt-5.6-terra",
    }})
    store = SQLiteStore(str(tmp_path / "footprint.db"))
    store.ingest([_unknown_opencode_gpt_event()], _engine(), config)
    row = store.conn.execute("SELECT route, model_raw, model_canonical FROM events").fetchone()
    assert tuple(row) == ("openai", "gpt-5.6-terra", "gpt-5.6-terra")
```

Add a CLI test asserting an explicit scoped `resolve` stores the same rule and
that a later matching event is estimated without another `resolve` invocation.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `/Users/renaudheluin/DEV/ia/agent-carbon/.venv/bin/python -m pytest tests/test_config_persist.py tests/test_ingest_and_save.py tests/test_resolve_cli.py -q`

Expected: FAIL because `Config` has no `model_resolutions` and ingestion leaves
the event route as `unknown`.

- [ ] **Step 3: Implement the minimal persisted rule**

Add this field to `Config`:

```python
model_resolutions: dict[str, dict[str, str]] = field(default_factory=dict)
```

In `_resolve_selected()`, after validating the explicit route, write:

```python
config.model_resolutions[f"{client}/{raw_model}"] = {
    "route": route,
    "model": model,
}
config.save()
```

Before inserting an event in `SQLiteStore.ingest()`, apply a rule only when the
event route is `unknown`:

```python
rule = config.model_resolutions.get(f"{e.client}/{e.model_raw}")
if e.route == "unknown" and rule:
    e = dataclasses.replace(e, route=rule["route"], model_canonical=rule["model"])
```

Do not change a collector-supplied confirmed route. Do not persist aliases or a
sibling fallback in this rule.

- [ ] **Step 4: Run the focused tests**

Run: `/Users/renaudheluin/DEV/ia/agent-carbon/.venv/bin/python -m pytest tests/test_config_persist.py tests/test_ingest_and_save.py tests/test_resolve_cli.py -q`

Expected: PASS.

- [ ] **Step 5: Document persistent identity resolution**

Explain that a confirmed `resolve` stores a client/raw-model rule in
`~/.ai-footprint/config.json`, applies it to future unknown events, and does
not persist a fallback sibling. State that EcoLogits is checked again for every
new event, so a future exact registry entry supersedes the prior sibling
estimate automatically.

- [ ] **Step 6: Run the documentation test**

Run: `/Users/renaudheluin/DEV/ia/agent-carbon/.venv/bin/python -m pytest tests/test_docs_site.py -q`

Expected: PASS.

### Task 8: Refresh the GPT Backfill With the Persisted Rule

**Files:**
- Modify: `~/.ai-footprint/ai-footprint.db` (user data only; no repository file)
- Modify: `~/.ai-footprint/config.json` (user configuration only)

- [ ] **Step 1: Run the approved bounded resolve again**

Run the Task 5 command after Task 7. It confirms all current OpenCode
`gpt-5.6-terra` events and persists the rule for later matching events.

- [ ] **Step 2: Verify the persisted rule**

Run:

```bash
sqlite3 "$HOME/.ai-footprint/ai-footprint.db" \
  "SELECT COUNT(*) FROM events e JOIN impacts i ON e.session_id=i.session_id AND e.msg_id=i.msg_id WHERE e.model_raw='gpt-5.6-terra' AND i.error IS NOT NULL;"
```

Expected: `0` at the verification instant. New matching events are estimated
through the persisted identity rule rather than creating another unknown batch.
