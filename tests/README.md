# Tests

Validation for the source assets. Deliberately dependency-light: Python standard
library plus `jsonschema` (which brings `referencing`). No pytest, no database, no API
server, no network.

**No committed example data.** The repo stores source assets only. Where representative
objects are needed, the harnesses build **synthetic fixtures at runtime**
([`synthetic_fixtures.py`](synthetic_fixtures.py)) and write them to a temporary
directory that is auto-deleted. Nothing is stored. See
[`../docs/FIXTURE_STRATEGY.md`](../docs/FIXTURE_STRATEGY.md).

Ten harnesses, run together by `make validate`:

- `validate_phase1.py` — schemas + synthetic object fixtures.
- `validate_phase2.py` — schemas + a synthetic `EngagementPacket`.
- `validate_phase3_prompts.py` — prompt-contract inventory (stdlib-only).
- `validate_phase4_outputs.py` — output-structure spec, synthetic (stdlib-only).
- `validate_phase5_runner.py` — packet-runner smoke check on a temp fixture (stdlib-only).
- `validate_phase6_docs.py` — consultant-guide doc check (stdlib-only).
- `validate_phase7_policy.py` — repo-hygiene / data-artifact guard (stdlib-only).
- `validate_phase8_architecture.py` — controlled-data architecture doc check (stdlib-only).
- `validate_phase9_governance.py` — governance-state contract check (jsonschema + stdlib).
- `validate_phase10_database_plan.py` — database-plan doc check (stdlib-only).

## `synthetic_fixtures.py`

Not a test — a **module** that builds clearly-synthetic, schema-conforming objects in
memory (ids/labels carry a `synthetic` marker). It is code, not stored data, and is
imported by the phase 1/2 harnesses.

## `validate_phase1.py`

1. **Schema self-check** — every `schemas/*.schema.json` is valid draft 2020-12.
2. **Synthetic fixture conformance** — a synthetic instance of each object is written to
   a temp dir and validated against its schema.
3. **Prefix lint** — synthetic ids/references use their expected prefixes
   (`intake_`, `evid_`, `intv_`, `vobs_`, `wobs_`, `isp_`).

## `validate_phase2.py`

Validates a **synthetic** `EngagementPacket`, which composes the object schemas via
local relative `$ref`. Refs are resolved **offline** via a `referencing` registry built
from every schema's `$id`.

1. **Schema self-check** — all schemas, including `engagement-packet.schema.json`.
2. **Packet conformance** — a synthetic packet (temp file, auto-deleted) validates with
   `$ref`s resolved.
3. **Packet referential lint (blocking)** — every nested `evidence_references` id
   resolves within the packet; every nested `related_intake_id` equals
   `client_intake.intake_id`; ids use expected prefixes.

## `validate_phase3_prompts.py`

Inventory check for the prompt contracts in [`../prompts/`](../prompts/): every required
contract exists and contains all ten required section headings plus a fenced reusable
body. Structure only.

## `validate_phase4_outputs.py`

Validates the **output-structure contract**. Peak commits no sample outputs, so for each
artifact type the harness holds the required section spec, **generates a synthetic
document** into a temp dir, and confirms it contains every required section plus a
synthetic evidence citation. Structure only.

## `validate_phase5_runner.py`

Smoke check for the packet runner ([`../tools/packet_runner.py`](../tools/packet_runner.py)).
The runner has no demo/sample mode, so this test generates a **temporary synthetic
packet** with `tempfile`, passes it via `--packet`, then deletes it. It confirms the
runner exists, exits 0, the output contains the fixture `packet_id`, the prompt-contract
list, and the no-LLM / no-AgentNet / not-stored disclaimers, and that the run **writes
no files**.

## `validate_phase6_docs.py`

Doc check for the consultant guide
([`../docs/CONSULTANT_WORKFLOW.md`](../docs/CONSULTANT_WORKFLOW.md)): required sections
plus honesty/scope phrases. Structure only.

## `validate_phase7_policy.py` (repo-hygiene / data-artifact guard)

Enforces that the repo stores **source assets only**:

1. **Policy docs present** — [`../docs/DATA_HANDLING_POLICY.md`](../docs/DATA_HANDLING_POLICY.md)
   and [`../docs/FIXTURE_STRATEGY.md`](../docs/FIXTURE_STRATEGY.md) exist with their
   required markers.
2. **No stored data artifacts** — forbidden paths must not exist: `examples/`, the old
   redaction guide (removed), any `*.example.json` / `*.example.md`, or `redacted`
   files. The guard fails if they reappear.
3. **Redaction framing stays removed** — tracked docs/code must not reintroduce it (a
   historical note in the two policy docs is allowed).

This is the guard that keeps the repo clean of data artifacts. It does not attempt to
detect real client data inside a supposedly-synthetic file — that remains a human
discipline plus the "client data never in the repo" policy.

## `validate_phase8_architecture.py`

Doc check for the Phase 8 controlled-data architecture:
[`../docs/CONTROLLED_DATA_ARCHITECTURE.md`](../docs/CONTROLLED_DATA_ARCHITECTURE.md),
[`../docs/RESOLVER_CAPSULE_ARCHITECTURE.md`](../docs/RESOLVER_CAPSULE_ARCHITECTURE.md),
[`../docs/ENGAGEMENT_DATA_MODEL.md`](../docs/ENGAGEMENT_DATA_MODEL.md), and
[`../docs/SOURCE_SYSTEM_CAPSULIZATION.md`](../docs/SOURCE_SYSTEM_CAPSULIZATION.md). It
confirms each doc exists with its required markers, re-asserts source-only discipline (no
`examples/`, no removed redaction guide, no `*.example.*` artifacts), checks the
source-only phrase in the README, and fails if any file claims AgentNet is *implemented*
(explicit completion claims; negated policy statements and future-phase descriptions are
fine). The Phase 8 architecture-contract schemas are covered by the schema self-check in
phases 1–2; they carry no fixtures.

## `validate_phase9_governance.py`

Checks the Phase 9 governance-state contracts:
[`../docs/GOVERNANCE_STATES.md`](../docs/GOVERNANCE_STATES.md) and
[`../docs/STATE_TRANSITIONS.md`](../docs/STATE_TRANSITIONS.md) exist; the governance
schemas (`governance-state`, `authorization-scope`, `review-status`, `lifecycle-status`)
pass `check_schema`; all **eight** state families contain their required enum values; the
key transition arrows and agent guardrail phrases appear in `STATE_TRANSITIONS.md`; the
repo stays source-only; and AgentNet is not claimed as implemented. Uses `jsonschema`
(already a dev dep) plus stdlib.

## `validate_phase10_database_plan.py`

Doc check for the Phase 10 database-planning docs (`DATABASE_IMPLEMENTATION_PLAN.md`,
`DATABASE_RECORD_MODEL.md`, `DATABASE_ACCESS_AND_AUDIT.md`,
`DATABASE_TO_RESOLVER_MAPPING.md`): each exists with its required markers; the strategic
phrases are present (source-only, controlled database, private resolver capsules,
public-but-segregated, private resolver option, no client data in Git, human review
gates, agent permission limits); the repo stays source-only **with no DB implementation**
(no `*.sql`/`*.db`, no `migrations/`, no DB config files); and AgentNet is not claimed as
implemented. Stdlib-only.

## Running

This machine uses `python3` (there is no bare `python`). From the repo root:

```bash
# one-time: install the dev dependency
make install-dev          # == python3 -m pip install -r requirements-dev.txt

# run all harnesses
make validate             # == phase1 … phase10

# or run one at a time
make validate-phase1
make validate-phase2
make validate-phase3
make validate-phase4
make validate-phase5
make validate-phase6
make validate-phase7
make validate-phase8
make validate-phase9
make validate-phase10
```

Or invoke them directly, without the Makefile:

```bash
python3 tests/validate_phase1.py
python3 tests/validate_phase2.py
python3 tests/validate_phase3_prompts.py       # stdlib-only, no dependency needed
python3 tests/validate_phase4_outputs.py       # stdlib-only, no dependency needed
python3 tests/validate_phase5_runner.py        # stdlib-only, no dependency needed
python3 tests/validate_phase6_docs.py          # stdlib-only, no dependency needed
python3 tests/validate_phase7_policy.py        # stdlib-only, no dependency needed
python3 tests/validate_phase8_architecture.py  # stdlib-only, no dependency needed
python3 tests/validate_phase9_governance.py    # jsonschema + stdlib
python3 tests/validate_phase10_database_plan.py # stdlib-only, no dependency needed
```

## Exit codes

All ten harnesses share the same convention:

| Code | Meaning |
| --- | --- |
| `0` | All blocking checks passed. |
| `1` | A schema, fixture/packet conformance, structure, or hygiene check failed. |
| `2` | A dependency is missing (install `requirements-dev.txt`). |

The nonzero-on-failure behavior makes these harnesses safe to wire into CI later
without additional tooling.
