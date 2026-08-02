# Routes d'inference et identite des modeles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separate client, observed model, route hint, confirmed route, and canonical model so impacts and reports reflect the route actually selected for each event.

**Architecture:** Events retain immutable transcript facts (`client`, `model_raw`, `route_hint`) and carry user-resolved fields (`route`, `model_canonical`). SQLite additive migrations preserve existing rows, backfill historical facts, then run the one-time declared route correction. The impact engine dispatches only from confirmed routes; the resolver updates only the selected session/date batch and reports aggregate canonical-model-plus-route data.

**Tech Stack:** Python 3.10+, sqlite3 additive migrations, argparse TTY prompts, EcoLogits 0.11.1, huggingface_hub 1.8.x, pytest.

## Global Constraints

- Work only in this linked worktree and on `feat/inference-routes`; do not push or open a PR.
- Keep all existing database rows and make every SQLite migration idempotent.
- Collectors extract source facts only: they must never infer a confirmed route from the client or model name.
- Valid confirmed routes are `anthropic`, `openai`, `openrouter`, `custom`, `local`, and `unknown`; new events default to `unknown`.
- `route_hint` is never used in impact calculations.
- `anthropic` and `openai` use only the EcoLogits registry; `local` uses resolved model parameters and local infrastructure configuration; `openrouter`, `custom`, and `unknown` remain stored but unestimated.
- Model parameters passed to EcoLogits are expressed in billions.
- Preserve the offline-first behavior: do not add ambient network calls; Hugging Face resolution occurs only from explicit resolution paths.
- Upgrade the dependency to `huggingface_hub>=1.8.0,<2` and verify `model_info(...).safetensors.total` compatibility with deterministic tests.
- Update French user and developer documentation and regenerate committed MkDocs output when Markdown documentation changes.
- Follow red-green-refactor: every production behavior begins with a failing pytest assertion observed locally.

---

## File Structure

- `ai_footprint/models.py`: normalized event fields and route constants.
- `ai_footprint/collectors/{claude_code,codex,pi,crush,stubs}.py`: source-only event collection, preserving provider metadata solely as `route_hint`.
- `ai_footprint/store/db.py`: idempotent schema migrations, historical correction, scoped resolution updates, route-aware recomputation and route/canonical aggregations.
- `ai_footprint/impact/engine.py`: confirmed-route calculation dispatch.
- `ai_footprint/impact/params.py`: canonical-model parameter lookup and current Hugging Face compatibility.
- `ai_footprint/resolve/cli.py` and `ai_footprint/__main__.py`: batch selection, explicit route/canonical resolution, local parameter capture, keyboard-only interactive flow and validation messages.
- `ai_footprint/report/cli.py`: primary `model_canonical + route` table and secondary canonical-model roll-up.
- `tests/test_{*_collector,store,engine,resolve,resolve_cli,report,params_huggingface}.py`: acceptance, migration, compatibility, and regression coverage.
- `README.md`, `docs/GUIDE.md`, `docs/GUIDE-AVANCE.md`, `docs/CONTRIBUTING.md`, `docs/METHODOLOGY.md`: user behavior, CLI examples, persisted schema, calculation semantics, and dependency rationale.

### Task 1: Define Event Route Data and Upgrade Hugging Face Hub

**Files:**
- Modify: `pyproject.toml:9-12`
- Modify: `ai_footprint/models.py:1-19`
- Modify: `ai_footprint/impact/params.py:186-208`
- Test: `tests/test_params_huggingface.py`
- Test: `tests/test_models.py` (new)

**Interfaces:**
- Produces: `InferenceEvent(model_raw: str, route_hint: str, route: str = "unknown", model_canonical: str = "")` and `ROUTES`.
- Produces: `fetch_hf_params(repo: str) -> ParamsResult | None` that remains compatible with `huggingface_hub` 1.8.x.

- [ ] **Step 1: Write failing route-data and current-HF API tests**

```python
def test_event_defaults_to_unknown_route():
    event = InferenceEvent(client="claude-code", model_raw="Qwen/Qwen3")
    assert event.route == "unknown"
    assert event.model_canonical == ""

def test_huggingface_model_info_uses_safetensors_total(monkeypatch):
    _fake_hf(7_000_000_000, monkeypatch)
    assert fetch_hf_params("Qwen/Qwen3-8B").total == 7.0
```

- [ ] **Step 2: Run focused tests and verify red**

Run: `.venv/bin/python -m pytest tests/test_models.py tests/test_params_huggingface.py -q`

Expected: FAIL because the new event fields and dependency compatibility contract do not exist.

- [ ] **Step 3: Implement the minimal data contract**

```python
ROUTES = frozenset({"anthropic", "openai", "openrouter", "custom", "local", "unknown"})

@dataclass(frozen=True)
class InferenceEvent:
    client: str
    model_raw: str
    route_hint: str = ""
    route: str = "unknown"
    model_canonical: str = ""
    # token, timestamp, project, session and message fields unchanged
```

Set `huggingface_hub>=1.8.0,<2`; continue using the documented optional `info.safetensors.total` and return `None` if unavailable.

- [ ] **Step 4: Run focused tests and verify green**

Run: `.venv/bin/python -m pytest tests/test_models.py tests/test_params_huggingface.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the task**

```bash
git add pyproject.toml ai_footprint/models.py ai_footprint/impact/params.py tests/test_models.py tests/test_params_huggingface.py
git commit -m "feat(models): add route identity fields"
```

### Task 2: Make Every Collector Fact-Only

**Files:**
- Modify: `ai_footprint/collectors/claude_code.py:30-79`
- Modify: `ai_footprint/collectors/codex.py:17-90`
- Modify: `ai_footprint/collectors/pi.py:17-82`
- Modify: `ai_footprint/collectors/crush.py:37-280`
- Modify: `ai_footprint/collectors/stubs.py:7-13`
- Test: `tests/test_claude_code_collector.py`
- Test: `tests/test_codex_collector.py`
- Test: `tests/test_pi_collector.py`
- Test: `tests/test_crush_collector.py`

**Interfaces:**
- Consumes: `InferenceEvent` from Task 1.
- Produces: collected events with transcript model in `model_raw`, source provider metadata in `route_hint`, and `route == "unknown"`.

- [ ] **Step 1: Write failing collector assertions for every supported source**

```python
def test_claude_qwen_stays_unknown_route(tmp_path):
    transcript = tmp_path / "session.jsonl"
    transcript.write_text('{"type":"assistant","message":{"model":"Qwen/Qwen3","usage":{"input_tokens":1,"output_tokens":1}}}\n')
    event = next(ClaudeCodeCollector(str(transcript)).collect())
    assert (event.client, event.model_raw, event.route) == ("claude-code", "Qwen/Qwen3", "unknown")
```

Add equivalent assertions for Codex, Pi, and Opencode/Crush: their observed provider becomes `route_hint`, never `route`.

- [ ] **Step 2: Run the collector tests and verify red**

Run: `.venv/bin/python -m pytest tests/test_claude_code_collector.py tests/test_codex_collector.py tests/test_pi_collector.py tests/test_crush_collector.py -q`

Expected: FAIL because collectors currently populate the legacy provider as a calculation input.

- [ ] **Step 3: Implement fact-only mapping**

```python
InferenceEvent(
    client=self.client,
    model_raw=model,
    route_hint=source_provider,
    # route and model_canonical use dataclass defaults
    input_tokens=input_tokens,
    output_tokens=output_tokens,
    ...,
)
```

Do not read environment variables or inspect a model name to choose a route.

- [ ] **Step 4: Run collector tests and verify green**

Run: `.venv/bin/python -m pytest tests/test_claude_code_collector.py tests/test_codex_collector.py tests/test_pi_collector.py tests/test_crush_collector.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the task**

```bash
git add ai_footprint/collectors tests/test_claude_code_collector.py tests/test_codex_collector.py tests/test_pi_collector.py tests/test_crush_collector.py
git commit -m "feat(collectors): preserve route hints without inference"
```

### Task 3: Migrate and Persist Route-Aware Events

**Files:**
- Modify: `ai_footprint/store/db.py:13-456`
- Test: `tests/test_store.py`
- Test: `tests/test_migrations.py` (new)

**Interfaces:**
- Consumes: route-aware `InferenceEvent`.
- Produces: `SQLiteStore.resolve_events(...)`, `unresolved_batches(...)`, `rows_for_report(...)`, `tokens_by_model_route(...)`, and `tokens_by_canonical_model(...)`.

- [ ] **Step 1: Write failing additive-migration and scope tests**

```python
def test_legacy_provider_moves_to_route_hint_without_confirming_route(tmp_path):
    store = legacy_store_with_event(tmp_path, provider="anthropic", model="Qwen/Qwen3")
    migrated = SQLiteStore(store.path).conn.execute("SELECT route_hint, route FROM events").fetchone()
    assert tuple(migrated) == ("anthropic", "unknown")

def test_resolution_changes_only_selected_session(tmp_path):
    store = store_with_two_qwen_sessions(tmp_path)
    store.resolve_events(session_id="local-session", route="local", model_canonical="Qwen/Qwen3-8B")
    assert store.event_route("local-session") == "local"
    assert store.event_route("router-session") == "unknown"
```

Add the historical correction acceptance test: Claude models become `anthropic`, ChatGPT models `openai`, `openrouter/free` becomes `openrouter`, and every remaining historical event becomes `local`; run it twice and assert the rows do not change.

- [ ] **Step 2: Run store migration tests and verify red**

Run: `.venv/bin/python -m pytest tests/test_store.py tests/test_migrations.py -q`

Expected: FAIL because the columns, migration, and scoped update methods are absent.

- [ ] **Step 3: Implement explicit additive migrations and scoped persistence**

```sql
ALTER TABLE events ADD COLUMN route_hint TEXT DEFAULT '';
ALTER TABLE events ADD COLUMN route TEXT DEFAULT 'unknown';
ALTER TABLE events ADD COLUMN model_raw TEXT DEFAULT '';
ALTER TABLE events ADD COLUMN model_canonical TEXT DEFAULT '';
```

Backfill `model_raw` from legacy `model` and `route_hint` from legacy `provider`, then run a version-marked, transactionally idempotent correction for the declared historical routes. Use named columns for all new inserts and reconstruct `InferenceEvent` from the new fields for recomputation. Keep the old columns only for compatibility with existing databases, not calculation decisions.

- [ ] **Step 4: Run store migration tests and verify green**

Run: `.venv/bin/python -m pytest tests/test_store.py tests/test_migrations.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the task**

```bash
git add ai_footprint/store/db.py tests/test_store.py tests/test_migrations.py
git commit -m "feat(store): persist scoped inference routes"
```

### Task 4: Calculate Only Confirmed Routes and Resolve Scoped Batches

**Files:**
- Modify: `ai_footprint/impact/engine.py:74-140`
- Modify: `ai_footprint/impact/params.py:311-418`
- Modify: `ai_footprint/resolve/cli.py:1-157`
- Modify: `ai_footprint/__main__.py:191-205`
- Test: `tests/test_engine.py`
- Test: `tests/test_engine_selfhosted.py`
- Test: `tests/test_resolve.py`
- Test: `tests/test_resolve_cli.py`

**Interfaces:**
- Consumes: persisted event route and canonical model from Task 3.
- Produces: `EcoLogitsEngine.compute(event, config)` with route dispatch and `resolve` flags `--route`, `--model`, `--session`, `--since`, `--repo`, `--active-params`, `--total-params`.

- [ ] **Step 1: Write failing engine and resolver acceptance tests**

```python
def test_openrouter_event_is_kept_but_not_estimated():
    record = engine.compute(event(route="openrouter", model_canonical="Qwen/Qwen3"), Config())
    assert record.error == "route-not-estimated"

def test_local_resolution_reuses_resolved_params_for_selected_session(tmp_path):
    store = store_with_qwen_session(tmp_path)
    resolve_local_session(store, "s1", "Qwen/Qwen3-8B", active=3.0, total=8.0)
    assert store.rows_for_report(session_id="s1")[0]["gwp_min"] > 0
```

Add tests proving routes `unknown` and `custom` are unestimated; a recognized canonical model on `anthropic`/`openai` uses the registry; and an invalid route or local active parameter greater than total returns a field-specific error without changing rows.

- [ ] **Step 2: Run engine and resolve tests and verify red**

Run: `.venv/bin/python -m pytest tests/test_engine.py tests/test_engine_selfhosted.py tests/test_resolve.py tests/test_resolve_cli.py -q`

Expected: FAIL because the engine currently uses the legacy provider and resolution is global by provider/model.

- [ ] **Step 3: Implement route dispatch and keyboard-accessible CLI resolution**

```python
if event.route in {"openrouter", "custom", "unknown"}:
    return ImpactRecord(..., error="route-not-estimated")
if event.route in {"anthropic", "openai"}:
    return self._compute_registry(event.model_canonical, event.route, config)
if event.route == "local":
    return self._compute_selfhosted(event, event.model_canonical, config)
```

`resolve --list` groups unresolved events by client, raw model, sessions, date range, and token count. Noninteractive flags select the target batch; an interactive TTY flow presents numbered choices, accepts typed values, repeats invalid fields with an explicit field name and reason, and never requires a mouse. Persist local parameters under the canonical model identity and recompute exactly the selected events.

- [ ] **Step 4: Run engine and resolve tests and verify green**

Run: `.venv/bin/python -m pytest tests/test_engine.py tests/test_engine_selfhosted.py tests/test_resolve.py tests/test_resolve_cli.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the task**

```bash
git add ai_footprint/impact ai_footprint/resolve/cli.py ai_footprint/__main__.py tests/test_engine.py tests/test_engine_selfhosted.py tests/test_resolve.py tests/test_resolve_cli.py
git commit -m "feat(resolve): confirm routes for selected event batches"
```

### Task 5: Render Route-Separated and Canonical Roll-Up Reports

**Files:**
- Modify: `ai_footprint/store/db.py:175-343`
- Modify: `ai_footprint/report/cli.py:137-301`
- Modify: `ai_footprint/__main__.py:256-285`
- Test: `tests/test_store.py`
- Test: `tests/test_report.py`

**Interfaces:**
- Consumes: `tokens_by_model_route(since)` and `tokens_by_canonical_model(since)`.
- Produces: `render_tokens_by_model_route(rows, detailed=False)` and `render_tokens_by_canonical_model(rows, detailed=False)`.

- [ ] **Step 1: Write failing report grouping tests**

```python
def test_report_separates_local_and_openrouter_for_same_canonical_model(tmp_path):
    store = resolved_local_and_openrouter_qwen_store(tmp_path)
    primary = store.tokens_by_model_route()
    secondary = store.tokens_by_canonical_model()
    assert {(row["model"], row["route"]) for row in primary} == {("Qwen/Qwen3-8B", "local")}
    assert secondary[0]["tokens"] == local_tokens + openrouter_tokens
```

Also assert that nonestimated OpenRouter tokens appear as explicitly unestimated in the primary view and that impact totals do not silently include them.

- [ ] **Step 2: Run report tests and verify red**

Run: `.venv/bin/python -m pytest tests/test_store.py tests/test_report.py -q`

Expected: FAIL because existing grouping only uses the raw model name.

- [ ] **Step 3: Implement route-aware report queries and renderers**

```python
GROUP BY e.model_canonical, e.route
```

Keep existing total/project views based only on estimated records. Add a second canonical-model view that sums all routes' tokens and labels each route's measured or unestimated contribution.

- [ ] **Step 4: Run report tests and verify green**

Run: `.venv/bin/python -m pytest tests/test_store.py tests/test_report.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the task**

```bash
git add ai_footprint/store/db.py ai_footprint/report/cli.py ai_footprint/__main__.py tests/test_store.py tests/test_report.py
git commit -m "feat(report): group impacts by canonical model and route"
```

### Task 6: Document the Route Model and Verify the Complete Release Surface

**Files:**
- Modify: `README.md`
- Modify: `docs/GUIDE.md`
- Modify: `docs/GUIDE-AVANCE.md`
- Modify: `docs/METHODOLOGY.md`
- Modify: `docs/CONTRIBUTING.md`
- Regenerate: `docs/guide/`
- Test: `tests/test_docs_site.py`

**Interfaces:**
- Documents: route confirmation, batch-limited resolution, nonestimated third-party routes, the legacy correction, SQLite fields, and `huggingface_hub` 1.8.x compatibility.

- [ ] **Step 1: Write failing documentation assertions**

```python
def test_docs_explain_that_route_hint_is_not_a_confirmed_route():
    text = Path("docs/GUIDE-AVANCE.md").read_text()
    assert "route_hint" in text
    assert "OpenRouter" in text
```

- [ ] **Step 2: Run documentation test and verify red**

Run: `.venv/bin/python -m pytest tests/test_docs_site.py -q`

Expected: FAIL because the documentation does not describe the new route model.

- [ ] **Step 3: Document usage and regenerate the static guide**

Explain that routes are confirmed only with `resolve`, all route hints stay advisory, and `openrouter`/`custom` remain unestimated. Update the developer schema and migration sections, state the pinned compatible Hugging Face range/API, then run `.venv/bin/python scripts/build_docs.py`.

- [ ] **Step 4: Run complete verification**

Run: `.venv/bin/python -m pytest`

Expected: PASS with no failures.

- [ ] **Step 5: Commit the task**

```bash
git add README.md docs tests/test_docs_site.py
git commit -m "docs: explain inference routes and model resolution"
```
