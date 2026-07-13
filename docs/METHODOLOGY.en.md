# Methodology — how impact is evaluated

ai-footprint **does not rewrite any impact model**. It collects usage
metadata (tokens, model, timestamp) and delegates all environmental
calculations to **[EcoLogits](https://github.com/mlco2/ecologits)** (an
offline, multi-criteria, multi-phase engine). This document describes what
we send to EcoLogits, what we get back, and the methodological choices
(with their limits).

## Why EcoLogits

The audit of `claude-carbon` (single CO₂ criterion, factors derived from
**price**) showed the limits of an in-house model. ai-footprint relies on
EcoLogits instead:

- **multi-criteria** (5 criteria, not just CO₂);
- **multi-phase** (usage + manufacturing);
- **offline** (no data sent over the network for the calculation);
- **maintained and reviewed** by a specialized community.

## Exchanges with EcoLogits

For **each inference message** (one model call in a transcript),
ai-footprint runs a calculation. There are two paths depending on whether
the model is known to EcoLogits or not.

### What we send

| Data                   | Source                                                                          | Note                                         |
| ---------------------- | ------------------------------------------------------------------------------- | -------------------------------------------- |
| `provider`             | transcript (default `anthropic`)                                                | identifies the provider                      |
| `model_name`           | transcript, after applying aliases                                              | e.g. `claude-opus-4-8`                       |
| `output_token_count`   | message usage                                                                   | **only output tokens** feed the calculation  |
| `request_latency`      | **estimated**: `output_tokens / throughput_tok_s` (default 50 tok/s, min 0.5 s) | affects the datacenter's "idle energy" share |
| `electricity_mix_zone` | config (default USA, configurable)                                              | the datacenter's electricity mix             |

For a **self-hosted / unrecognized model**, we additionally provide the
**model parameters** (active/total, in billions), the **PUE** (default
range 1.1–1.5), and the datacenter's **WUE**.

### What we receive

For each message, EcoLogits returns the **5 criteria**, each as a
**`(min, max)` range**, split into two **phases**:

| Criterion | Unit     | What                                |
| --------- | -------- | ----------------------------------- |
| `energy`  | kWh      | energy consumed                     |
| `gwp`     | kg CO₂eq | global warming potential            |
| `adpe`    | kg Sbeq  | abiotic resource depletion (metals) |
| `pe`      | MJ       | primary energy                      |
| `wcf`     | L        | water footprint                     |

- **usage**: the inference itself.
- **embodied**: hardware manufacturing/amortization (gwp, adpe, pe).

ai-footprint stores these ranges as-is (`impacts` table), along with the
methodology version used. The report then aggregates by total / project /
model, and displays a **central value `~`** (average of the bounds)
alongside the **min–max range**.

### The two calculation paths

1. **EcoLogits-recognized model** → `llm_impacts()` (the EcoLogits registry
   already has the model's architecture and parameters).
2. **Unknown model** → we resolve the parameters (see below) and then call
   `compute_llm_impacts()` directly, using the zone's electricity mix and
   the PUE range. The PUE range (min/max) drives the min/max range of the
   results.

## Methodological choices (and why)

- **Output tokens only.** The dominant inference cost is generation. Input
  and cache tokens are **not** counted in the impact (they are, however,
  displayed in "tokens used", for transparency). This is a deliberate
  approximation, aligned with EcoLogits.
- **Estimated latency.** The transcript doesn't give the real call
  duration; we estimate it via a throughput (`throughput_tok_s`). An
  approximation, configurable.
- **Min–max ranges, never a single point.** The uncertainty is
  **irreducible**:
  - Anthropic's **datacenter region** (and thus its real electricity mix)
    is unknown;
  - a datacenter's **PUE** varies (range 1.1–1.5).
    We document this uncertainty rather than hiding it behind a falsely
    precise number. The central value `~` is only a reference point.
- **Configurable electricity zone.** Default USA; adjustable (e.g. FRA)
  via `/footprint-config`. It strongly affects GWP (the mix varies by a
  factor of ~10 between countries).

## Self-hosted and third-party models

Many models are not in the EcoLogits registry (local inference, open-weight
models, third-party routers). Estimating their impact requires their
**parameters**. ai-footprint resolves them through a cascade:

1. **EcoLogits registry** (if ultimately recognized) — handles dense and
   **MoE** (active/total) models.
2. **Config cache** (`~/.ai-footprint/config.json`) — parameters previously
   declared or resolved, with provenance (`source`, `hf_repo`).
3. **Hugging Face** — parameter count read from safetensors metadata
   (`total ÷ 1e9`, in **billions**). Offline-safe: any failure ⇒
   unresolved.
4. **Otherwise** — the model stays **uncovered** (impact not estimated),
   queued.

**Active vs. total (MoE).** For a Mixture-of-Experts model, energy depends
on the **active** parameters per token (≪ total). Conflating active and
total strongly overestimates energy (observed ~10× on 120–225 B models).
The correct `(active, total)` pair gives an honest estimate. _(Current
limitation: automatic resolution via Hugging Face assumes "dense"; an MoE
pair must be declared manually — see backlog.)_

> **Unit (recurring pitfall)**: EcoLogits parameters are **in billions**
> everywhere. `safetensors.total` (raw count) is divided by `1e9`.

## Reading the numbers: coverage

The output of `ingest` (and the report) distinguishes:

- **measured** — impact estimated by EcoLogits.
- **uncovered** — model out of scope: the event is **kept** but its impact
  is **not** estimated (showing a fake number would be worse) and it is
  **excluded from totals**. Two families:
  - Claude Code's internal `<synthetic>` placeholders (0 tokens, no real
    inference) — uncoverable by nature, excluded from the report;
  - real third-party/self-hosted models that aren't resolved yet —
    **resolvable** to a Hugging Face repo via `ai-footprint resolve`
    (skill `/footprint-resolve`).

Resolving a model triggers a **recalculation** of the impacts already in
the database (`resolve --recompute`), without re-parsing transcripts.

## Reproducibility

Each impact record stores its `methodology_version`
(`engine=…;ecologits=…`). This allows recalculating after an EcoLogits
update and comparing old/new results.

This recalculation (`ai-footprint resolve --retry-hf`) is no longer purely
manual: at the start of each session, `ai-footprint nudge` proactively
offers an ai-footprint update if one exists, then a `footprint-resolve`
prompt for uncovered models that have never been proposed before (batch
silence — a declined model is only re-proposed after an ai-footprint
update, the only event likely to change its coverage). See
`ai_footprint/nudge.py` and `CONTRIBUTING.md` § Modules.

## Estimating self-hosted model parameters

When a model is neither in the EcoLogits registry nor has safetensors
metadata, its parameters are **estimated from the file sizes** of the
Hugging Face repo. The dtype (bytes/param) is inferred from the repo name
(`-4bit` → 0.5, `-int8` → 1, `-fp16`/`-bf16` → 2, `-fp32` → 4); if it can't
be detected, we produce a **range** (0.5–2 bytes/param, i.e. a 1:4 ratio on
parameters) rather than a single value. These estimates carry a provenance
warning in the database, and the affected models are flagged in the report
("Params estimated from file size").

## Anthropic models too recent for the EcoLogits registry

The EcoLogits registry carries its own estimates (extrapolated,
`model-arch-not-released`) for closed Anthropic models — but a model that
just came out (e.g. `claude-sonnet-5`, `claude-fable-5`) may not be listed
yet. Rather than leaving it **uncovered**, ai-footprint temporarily reuses
the parameters EcoLogits declares for the known version of the same
lineage (e.g. the Sonnet-4.x family: MoE, 440 B total, 44–132 B active —
stable across the whole lineage, only the `tps` throughput changes between
versions). This stand-in is declared manually in `model_params`
(`source: "extrapolated"`) and carries a dedicated warning
(`params-extrapolated-anthropic:…`).

These models are flagged separately from HF estimates, in the report
(note "Params extrapolated from a sibling version") and in the statusline
(prefix `≈`): the displayed numbers are a **provisional reference**, not an
official EcoLogits measurement for this exact model. As soon as an
EcoLogits release covers the model, the manual entry should be removed
(`resolve --forget`) to switch back to the registry.

## Assumed limitations

- Impact is driven by **output tokens** (input/cache not counted).
- **Unknown datacenter region** → ranges; default USA mix (configurable).
- **Estimated latency**, not measured.
- **Local inference / workstation energy**: out of scope (only the
  inference is modeled, not the user's machine consumption).
- **MoE auto-resolved as dense** by the Hugging Face tier (the
  active/total pair must currently be declared manually).

## References

- EcoLogits — https://github.com/mlco2/ecologits
- CodeCarbon — https://github.com/mlco2/codecarbon
- claude-carbon — original audit and reporting UX
