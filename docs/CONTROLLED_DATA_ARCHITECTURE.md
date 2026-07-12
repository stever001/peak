# Controlled Data Architecture

How Peak stores and grounds real engagement data **outside** this repository. This is
**architecture documentation only** — no database, API, resolver, or ingestion pipeline
is implemented here. AgentNet grounding/resolution is **intended future architecture,
not implemented**.

## Principles

- **The repo is source-only.** It contains source assets only: docs, schemas, prompt
  contracts, tools, validation logic, and policy. It stores **no client data** and **no
  data artifacts**.
- **Controlled storage is the system of record.** Live engagement data lives in Peak's
  **controlled engagement database/storage**, under access control and authorization —
  never in Git.
- **Private resolver capsules are the governed grounding layer.** Grounding/resolution
  operates over **private resolver capsules** (see
  [`RESOLVER_CAPSULE_ARCHITECTURE.md`](RESOLVER_CAPSULE_ARCHITECTURE.md)), not over repo
  files.
- **Source systems remain the origin of operational facts** where applicable (ERP/WMS,
  reports, telemetry, logs). See
  [`SOURCE_SYSTEM_CAPSULIZATION.md`](SOURCE_SYSTEM_CAPSULIZATION.md).
- **Agent/AI workflows consume authorized data through controlled access paths** — they
  read from controlled storage / resolver capsules under authorization, never from
  committed repo data (there is none).
- **No client data in Git.** Not for examples, fixtures, demos, training, tests, or any
  non-engagement use.
- **Synthetic runtime fixtures only for validation** — generated in temp locations,
  never committed (see [`FIXTURE_STRATEGY.md`](FIXTURE_STRATEGY.md)).

## Architecture diagram

```
Peak repo
  -> source definitions only (docs, schemas, prompt contracts, tools, validation, policy)

Client source systems / notes / exports / telemetry
  -> controlled engagement database        (system of record for live engagement data)
  -> capsulization pipeline                (intended future architecture)
  -> private resolver capsules             (governed grounding/resolution layer)
  -> internal Peak AI workflows            (consume authorized data via controlled access)
```

The two lanes never cross: the repo defines the *shapes and process*; the controlled
data layer holds the *data*. Agent/AI workflows are driven by the repo's definitions but
operate on data only through controlled, authorized access paths.

## Data classification

Every item is exactly one of these classes:

| Class | Meaning | Where it lives |
| --- | --- | --- |
| `source_asset` | Repo-owned, non-data material (docs, schemas, prompts, tools, tests, policy) | This repository |
| `live_client_data` | Authorized engagement data | Controlled engagement storage (authorized use only) |
| `private_capsule` | Resolver-grounded client/project knowledge | Resolver layer (governed) |
| `peak_methodology` | Reusable internal Peak knowledge | Repo (as source assets) and/or methodology capsules |
| `synthetic_runtime_fixture` | Temporary generated test fixture | Temp dir at test time only — never committed |
| `prohibited_repo_data` | Any data-like thing stored in Git | **Not allowed** — the data-artifact guard fails on it |

Rules:

- `live_client_data` is used **only for authorized live client engagement work**, never
  for examples/fixtures/demos/training/tests.
- Nothing that is `live_client_data` or `private_capsule` is ever committed to the repo.
- The only data-shaped thing allowed near the repo is a `synthetic_runtime_fixture`, and
  only transiently at test time.

## What this repo defines (architecture contracts)

The controlled data layer is described by architecture-contract schemas (shapes only —
**no instances are committed**):

- [`../schemas/engagement-record.schema.json`](../schemas/engagement-record.schema.json)
- [`../schemas/financial-impact-estimate.schema.json`](../schemas/financial-impact-estimate.schema.json)
- [`../schemas/source-system-reference.schema.json`](../schemas/source-system-reference.schema.json)
- [`../schemas/resolver-capsule-record.schema.json`](../schemas/resolver-capsule-record.schema.json)

See [`ENGAGEMENT_DATA_MODEL.md`](ENGAGEMENT_DATA_MODEL.md) for the full model. These are
**architecture models, not a database migration** — no DB vendor is chosen and no SQL is
written.

## Governance states

Every record in controlled storage carries governance state (authorization, review,
lifecycle, plus domain-specific status) that gates how it may be used and who may advance
it. The allowed states and transitions are defined in
[`GOVERNANCE_STATES.md`](GOVERNANCE_STATES.md) and
[`STATE_TRANSITIONS.md`](STATE_TRANSITIONS.md), with enum contracts in
[`../schemas/governance-state.schema.json`](../schemas/governance-state.schema.json).
Agent/AI workflows must default their output to `draft`/`needs_review` and may never set
`client_facing_approved` — human review gates are preserved by contract.
