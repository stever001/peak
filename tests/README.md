# Tests

Validation for the source assets. Deliberately dependency-light: Python standard
library plus `jsonschema` (which brings `referencing`). No pytest, no database, no API
server, no network.

**No committed example data.** The repo stores source assets only. Where representative
objects are needed, the harnesses build **synthetic fixtures at runtime**
([`synthetic_fixtures.py`](synthetic_fixtures.py)) and write them to a temporary
directory that is auto-deleted. Nothing is stored. See
[`../docs/FIXTURE_STRATEGY.md`](../docs/FIXTURE_STRATEGY.md).

Fourteen harnesses, run together by `make validate`:

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
- `validate_phase11_db_scaffold.py` — MySQL DB-scaffold check (stdlib-only; `make db-check`).
- `validate_phase12_agentnet_mcp_boundary.py` — AgentNet MCP governance-boundary check (stdlib-only).
- `validate_phase13_agent_harness.py` — agent-execution-harness scaffold check (stdlib-only).
- `validate_phase14_evidence_worker.py` — evidence-normalization-worker check (stdlib-only).

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
implemented. Stdlib-only. (Note: `alembic.ini` is an allowed Phase 11 source asset and is
not treated as a forbidden DB config.)

## `validate_phase11_db_scaffold.py` (`make db-check`)

Structural check for the Phase 11 MySQL scaffold: the `peak/db/` package (base, enums,
models, session), `alembic.ini` + `alembic/env.py` + the initial migration, `.env.example`,
`requirements.txt`, and `docs/DATABASE_SCAFFOLD.md` all exist; `.env` is gitignored and
untracked while `.env.example` is allowed; there is **no stored data, no database file, no
seed/`INSERT` in migrations, and no obvious committed credential**; the `peak/db/enums.py`
values stay aligned to the Phase 9 schema enums; MySQL is documented; and AgentNet is not
claimed as implemented. If SQLAlchemy **and** Alembic are installed it additionally
imports them and `peak.db.models`, confirms `Base.metadata` defines **exactly** the 11
expected tables with unique names, and asserts every table carries the required
governance/audit columns (`owner_id`, `authorization_scope`, `review_status`,
`lifecycle_status`, `created_at`, `updated_at`); if the dependencies are absent that step
is skipped (structural check still runs). The structural portion is stdlib-only; the
dependency-backed portion runs when the `requirements.txt` packages are installed — e.g.
`make validate PYTHON=.venv/bin/python` (see
[`../docs/DATABASE_SCAFFOLD.md`](../docs/DATABASE_SCAFFOLD.md)).

## `validate_phase12_agentnet_mcp_boundary.py`

Boundary check for Peak's **governance wrapper** around the **existing AgentNet MCP
connector** (a separate repo; not reimplemented here). Confirms the `peak/agentnet/`
scaffold files exist and compile; imports the package and asserts `KNOWN_MCP_TOOLS` is
**exactly** `agentnet.resolve` / `agentnet.resolve_history` / `agentnet.validate_capsule`;
exercises the governance guards (a valid request is permitted; publication-style and
unknown tools, missing `owner_id`, and revoked/archived lifecycle are rejected); confirms
the **no-network mock boundary** always reports `live_call_made = False` and
`agentnet_integration_active = False`; scans the package for **network imports, credential
reads, or connector imports** (there are none); checks the boundary docs carry the
required language (no live calls, no capsule publication, AgentNet integration is not
complete); and re-asserts source-only discipline. Stdlib-only; **makes no network call**.
See [`../docs/AGENTNET_MCP_BOUNDARY.md`](../docs/AGENTNET_MCP_BOUNDARY.md).

## `validate_phase13_agent_harness.py`

Scaffold check for the Peak internal **agent execution harness** (`peak/agents/`; no live
execution). Confirms the package files exist and compile; imports the package and asserts
the registry lists **exactly** the 10 known agents/workers, each with a
workflow/purpose/output/review default and (where set) an existing prompt contract;
exercises the **no-op mock executor** (a permitted task returns `llm_call_made`,
`agentnet_call_made`, `database_write_made`, and `client_facing_output_created` all
`False`, with `output_status = draft` / `review_status = needs_review`); confirms
governance rejects an unknown agent, missing `owner_id`, revoked/archived lifecycle,
`client_facing_output_requested`, and `llm_execution_allowed`; scans the package for
**network and database imports** (there are none); checks the docs describe AgentNet as
not-yet-implemented; and re-asserts source-only discipline. Stdlib-only; **makes no live
call**. See [`../docs/AGENT_EXECUTION_HARNESS.md`](../docs/AGENT_EXECUTION_HARNESS.md).

## `validate_phase14_evidence_worker.py`

Check for the first production-shaped worker, the **Evidence Normalization Worker**
(`peak/workers/`). Confirms the package files exist and compile and the package imports;
normalizes a **valid in-memory synthetic request** and asserts the result is **review-gated**
(`permitted`, `output_status = draft`, `review_status = needs_review`, `authoritative`,
`client_facing_approved`, `capsule_candidate_ready`, `database_write_made`, `llm_call_made`,
`agentnet_call_made`, `network_call_made`, `capsule_publication_made` all as required);
confirms governance rejects missing `owner_id`/`client_id`/`engagement_id`, rejected
`review_status`, revoked/archived/deleted `lifecycle_status`, missing `raw_evidence` /
`source_reference`, and a request↔source scope mismatch; scans the package for
**network/database/LLM imports or credentials** (there are none); checks the docs carry the
review-gate phrases; and re-asserts source-only discipline. Stdlib-only; **no live call and
no stored data**. See
[`../docs/EVIDENCE_NORMALIZATION_WORKER.md`](../docs/EVIDENCE_NORMALIZATION_WORKER.md).

## Running

This machine uses `python3` (there is no bare `python`). From the repo root:

```bash
# one-time: install the dev dependency
make install-dev          # == python3 -m pip install -r requirements-dev.txt

# run all harnesses
make validate             # == phase1 … phase14

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
make validate-phase11   # == make db-check
make validate-phase12
make validate-phase13
make validate-phase14
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
python3 tests/validate_phase11_db_scaffold.py   # stdlib-only, no dependency needed
python3 tests/validate_phase12_agentnet_mcp_boundary.py  # stdlib-only, no dependency needed
python3 tests/validate_phase13_agent_harness.py          # stdlib-only, no dependency needed
python3 tests/validate_phase14_evidence_worker.py        # stdlib-only, no dependency needed
```

## Exit codes

All fourteen harnesses share the same convention:

| Code | Meaning |
| --- | --- |
| `0` | All blocking checks passed. |
| `1` | A schema, fixture/packet conformance, structure, or hygiene check failed. |
| `2` | A dependency is missing (install `requirements-dev.txt`). |

The nonzero-on-failure behavior makes these harnesses safe to wire into CI later
without additional tooling.
