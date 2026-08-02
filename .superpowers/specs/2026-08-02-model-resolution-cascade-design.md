# Model Resolution Cascade Design

## Goal

Estimate impacts for attributable models absent from the EcoLogits registry while
preserving the original model name and making every inference visible.

## Scope

The cascade applies only after an execution route is confirmed as `openai`,
`anthropic`, or `local`.

`openrouter`, `custom`, and `unknown` remain unestimated because their executor
cannot be established automatically. `resolve` must ask the user to confirm the
route and canonical model for an `unknown` batch before it can enter the cascade.

That confirmation persists an identity-resolution rule keyed by client and raw
model. Every later ingestion applies the confirmed route and canonical model
before calculating its impact. The rule never stores a sibling model: it stores
the requested canonical model so that a later EcoLogits release automatically
uses the exact model without a data migration.

Rules are stored in `~/.ai-footprint/config.json` under `model_resolutions`, for
example `opencode/gpt-5.6-terra` to `{route: "openai", model:
"gpt-5.6-terra"}`. Re-running `resolve` for the same client and raw model
replaces the rule.

## Resolution Order

1. Use the exact provider/model entry from EcoLogits.
2. If absent, use the newest strictly earlier model from the same provider and
   model family in the EcoLogits registry.
3. If no sibling exists, look up parameters on Hugging Face and calculate with
   EcoLogits parameter-based impacts.

Explicit user mappings remain authoritative over automatic Hugging Face lookup.
Hugging Face repositories are proposed to, and confirmed by, the user before
being persisted. A missing or unverifiable repository leaves the event
unestimated.

## Provenance

`events.model_raw` always keeps the transcript value. `events.model_canonical`
stores the confirmed identity. Exact registry results retain EcoLogits' native
provenance without a fallback warning. Inferred results keep that canonical
identity and record one of these warnings:

- `model-source:sibling:<provider>:<model>`
- `model-source:huggingface:<repo>`

Existing EcoLogits, parameter-range, and MoE warnings are retained. The sibling
or Hugging Face source is an estimate, never represented as an exact model
measurement.

## Data Backfill

The existing `gpt-5.6-terra` OpenCode events are confirmed as `openai` with
canonical model `gpt-5.6-terra`. They retain their raw name and are recalculated
through the cascade. Later OpenCode events with the same raw model automatically
receive that confirmed identity and use the current cascade. A timestamped SQLite
backup is created first.

## Acceptance Criteria

- An exact supported model uses EcoLogits without a fallback warning.
- A missing attributable model uses the nearest earlier same-provider sibling
  and records the sibling provenance.
- A model without an eligible sibling can use a user-confirmed Hugging Face
  mapping and records its provenance.
- Unconfirmed routes are never estimated automatically.
- A user-confirmed identity resolution is applied to future matching events.
- When EcoLogits later supports a previously inferred canonical model, new
  events use it exactly without changing the persisted identity resolution.
- `model_raw` is unchanged by all resolutions and backfills.
- The GPT backfill has no remaining `gpt-5.6-terra` impact errors.
