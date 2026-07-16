# Controlled Write Allowlist (Phase 17)

The explicit list of tables and actions a *future* controlled DB writer may target, and the
tables/actions that are prohibited. This is a governance **contract** enforced by the
Phase 17 boundary ([`CONTROLLED_DB_WRITER_BOUNDARY.md`](CONTROLLED_DB_WRITER_BOUNDARY.md)).
It is **DB-aware but not DB-writing**: **write plans are not writes**, and appearing on this
allowlist only means a future writer *would be permitted to plan* the write — nothing is
persisted here.

## Allowed tables

| Table | Written by (future) |
| --- | --- |
| `evidence_references` | normalized evidence records (Phase 14 → **Phase 18 mapping** → **Phase 21 live writer**) |
| `engagement_records` | engagement-scoped records |
| `review_records` | QA / review decisions (Phase 15 → Phase 16 → **Phase 22 live writer**) |
| `agent_run_records` | agent/worker run provenance (Phase 13 → **Phase 19 mapping** → **Phase 20 live writer**) |
| `source_ingestion_records` | controlled source-ingestion provenance (Phase 23 → **Phase 24 live writer**) |
| `capsule_publication_candidates` | *draft* capsule candidates only (not publication) |

## Allowed actions

- `create_draft`
- `create_review_record`
- `create_agent_run_record`
- `create_source_ingestion_record`
- `create_capsule_candidate_draft`
- `update_review_status`
- `update_lifecycle_status`
- `mark_superseded`

## Prohibited tables/actions

**Prohibited tables:** `clients`, `engagements`, `financial_impact_estimates`,
`resolver_capsule_records`.

**Prohibited action patterns:** any action whose name contains `publish`,
`client_facing_approve`, `verify_financial`, `delete`, `hard_delete`, `credential`,
`secret`, `seed`, `migrate`, or `raw_sql` — rejected regardless of the allowlist.

## Why `financial_impact_estimates` and `resolver_capsule_records` are excluded for now

- **`financial_impact_estimates`** is excluded until a later **financial verification gate**
  exists. Verifying or approving financial impact is a separate, human-governed decision; no
  generic writer may create or advance a financial estimate. There is **no financial
  verification** at this boundary.
- **`resolver_capsule_records`** is excluded until a later **capsule publication gate**
  exists. Publishing a resolver capsule is a separate governed decision; the writer boundary
  may only ever plan a *draft* `capsule_publication_candidates` row — never a published
  capsule. There is **no capsule publication** at this boundary.

## Why `clients` and `engagements` are excluded from this early writer boundary

`clients` and `engagements` are **identity / root records** that anchor an entire
engagement's governance. They are not created or mutated through this generic content-writer
path; they are established through a separate, more tightly controlled process. Excluding
them keeps the early writer boundary focused on engagement *content* (evidence, reviews,
runs, ingestion, capsule drafts) rather than the identity spine.

## How later phases may expand the allowlist

The allowlist is expanded **only through an explicit governance gate** in a later phase —
never by ad-hoc edits at a call site. Adding `financial_impact_estimates` requires a
financial-verification gate; adding `resolver_capsule_records` requires a capsule-publication
gate. Each expansion documents the new table/action, the human review it requires, and the
audit expectations for the write.

## Raw SQL, migrations, seeds, deletes

- **Raw SQL is prohibited** — a `raw_sql` action is never planned; a future writer maps
  allowlisted actions to parameterized operations, never free-form SQL.
- **Migration / seed / delete actions are prohibited** — schema changes and destructive or
  seeding operations never pass this boundary.

## Write plans are not writes

Enforcing the allowlist produces a **no-op** `ControlledWritePlan` and an in-memory
`ControlledWriteAuditDraft` — never a database write. **Write plans are not writes**: no
connection is opened, no SQL runs, and no record is stored until a future controlled DB
writer executes the plan under access control. The **Phase 18 Evidence Persistence Mapping**
([`EVIDENCE_PERSISTENCE_MAPPING.md`](EVIDENCE_PERSISTENCE_MAPPING.md)) is the first consumer
(`evidence_references` / `create_draft`); the **Phase 19 Agent Run Persistence Mapping**
([`AGENT_RUN_PERSISTENCE_MAPPING.md`](AGENT_RUN_PERSISTENCE_MAPPING.md)) is the second
(`agent_run_records` / `create_agent_run_record`) — both through this allowlist.
