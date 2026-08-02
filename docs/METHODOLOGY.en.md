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

For a confirmed provider route, the cascade is:

1. **Exact EcoLogits registry** — only for the confirmed provider; handles dense
   and **MoE** (active/total) models.
2. **Same-provider sibling version** — the newest strictly earlier model from the
   same family is used when the registry does not know the exact model.
3. **User-confirmed Hugging Face mapping** — parameters are read from the
   safetensors metadata (`total / 1e9`, in **billions**) of the confirmed
   repository. Without a confirmed repository, or on failure, the model remains
   unresolved.

Automatic cache entries and registry entries from another provider are excluded from
this cascade. For general resolution outside a confirmed route, the config cache
(`~/.ai-footprint/config.json`) can retain previously declared or resolved parameters,
with provenance (`source`, `hf_repo`).

Same-provider sibling and confirmed Hugging Face results are inferred sources, never exact
measurements of the requested model. They carry the provenance warnings
`model-source:sibling:<provider>:<model>` and
`model-source:huggingface:<repo>`, respectively.

**Active vs. total (MoE).** For a Mixture-of-Experts model, energy depends
on the **active** parameters per token (≪ total). Conflating active and
total strongly overestimates energy (observed ~10× on 120–225 B models).
The correct `(active, total)` pair gives an honest estimate. _(Current
limitation: automatic resolution via Hugging Face assumes "dense"; an MoE
pair must be declared manually — see backlog.)_

> **Unit (recurring pitfall)**: EcoLogits parameters are **in billions**
> everywhere. `safetensors.total` (raw count) is divided by `1e9`.

### Confirmed route, hint, and third-party service

The provenance read from a transcript is retained in `route_hint`. It is a
collector hint, not proof that a provider ran the inference. New events remain
on the `unknown` route until `ai-footprint resolve` explicitly confirms the
route and canonical model for a session or time-period batch. This operation
does not alter other batches or their impacts.

With `--route`, `resolve` also requires `--session` or `--since`: it confirms
the batch identity and recalculates that batch only. This is distinct from
`resolve --recompute`, which confirms no route and globally recalculates all
stored error events, for example after a parameter mapping; it does not reread
transcripts.

A confirmed `local` route can be estimated when active and total parameters are
declared in billions. Conversely, `openrouter` and `custom` identify a router
or third-party integration whose executing model cannot be attributed with
sufficient certainty: their events are retained with an unestimated impact and
excluded from totals. Confirming the router improves provenance without making
that absence of attribution calculable.

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

## Models too recent for the EcoLogits registry

A just-released closed model (for example `claude-sonnet-5`) may not yet be
in the registry or resolvable on Hugging Face. Rather than leaving it
**uncovered**, ai-footprint automatically finds the closest known earlier
sibling in the registry, from the same provider and family, and temporarily
reuses its parameters. The result is cached in `model_params` with
`source: "extrapolated"` and a `params-extrapolated-<provider>:<sibling>`
warning.

These models are flagged separately from HF estimates, in the report
(note "Params extrapolated from a sibling version") and in the statusline
(prefix `≈`): the displayed numbers are a **provisional reference**, not an
official EcoLogits measurement for this exact model. The exact registry is
checked first for every new event, so a future EcoLogits release automatically
replaces the sibling estimate without clearing the cache or running
`resolve --forget`. Previously stored provisional impacts require an explicit
recalculation.

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
