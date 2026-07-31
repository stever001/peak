# Internal Assessment Report Draft Idempotency Policy (Phase 37)

DB-enforced idempotency for `internal_assessment_report_drafts`, mirroring the policy every prior
controlled writer follows. The writer itself is documented in
[`INTERNAL_ASSESSMENT_REPORT_DRAFT_CONTROLLED_WRITER.md`](INTERNAL_ASSESSMENT_REPORT_DRAFT_CONTROLLED_WRITER.md).

---

## Uniqueness boundary

```
UNIQUE (owner_id, client_id, engagement_id, idempotency_key)
```

Index name: `uq_internal_assessment_report_drafts_idem`.

The boundary includes identity context, so an idempotency key **cannot collide across
owner / client / engagement**. Two different engagements may safely reuse the same caller key. The
constraint is a real DB index — portable across managed MySQL and the local SQLite structural-smoke
database — so uniqueness is enforced by the database, not by application logic alone.

---

## Payload fingerprint

`payload_fingerprint` is a SHA-256 over a canonical, sorted JSON serialization of the identity plus
the exact payload that will be stored:

- identity and authorization: `owner_id`, `client_id`, `engagement_id`, `authorization_scope`
- requester: `requested_by`, `requester_role`
- controlled-write target: `target_table`, `requested_action`, `idempotency_key`
- Phase 36 provenance: `report_plan_id`, `plan_fingerprint`, `report_purpose`, `workflow_id`,
  `managed_record_workflow_ref`
- structure: `sections`, `evidence_trace_map`, `finding_candidates`, `recommendation_candidates`,
  `open_gaps`, `blocked_items`
- future-gate placeholders: `future_financial_verification_items`,
  `future_capsule_candidate_items`
- stored posture: `audience`, `output_status`, `review_status`, `lifecycle_status`, and every
  posture boolean

The serialization is `sort_keys=True` with compact separators, so it is deterministic and
order-independent at the key level. Note that the Phase 36 `plan_fingerprint` participates **as a
value**: two plans that differ in any way already differ in their own fingerprint, and this digest
additionally covers the write-request identity and the stored posture.

**No raw content participates.** The fingerprint is computed over references, labels, counts, and
readiness states — the same material the row stores.

---

## Outcomes

| Situation | Outcome | Effect |
|---|---|---|
| No existing row on the boundary | `created` | exactly one row inserted, transaction committed |
| Same boundary + same key + **same** fingerprint | `idempotent_replay` | existing row id returned, **nothing modified** |
| Same boundary + same key + **different** fingerprint | `denied` / `idempotency_conflict` | **no mutation**, no row returned |
| Governance failure before the DB | `denied` | no connection opened, no SQL executed |
| Infrastructure failure before insert | `failed_before_write` | no row created |
| Commit outcome unconfirmable | `write_outcome_uncertain` | never claims a row does or does not exist |

A replay is a **read**, not a write: the receipt reports
`database_connection_made=true`, `sql_execution_made=true`, `database_write_made=false`,
`stored_record_created=false`, `existing_record_returned=true`, `transaction_committed=false`.

---

## Race handling

The pre-check lookup on the uniqueness boundary handles the common replay path. A concurrent writer
can still win the race between the pre-check and the commit, so the insert is wrapped:

1. `IntegrityError` on commit → `session.rollback()`.
2. Re-query **inline** on the boundary (deliberately not via the pre-check helper, so a race is
   still classifiable even if that helper missed it).
3. Row found with a matching fingerprint → `idempotent_replay`.
4. Row found with a different fingerprint → `denied` / `idempotency_conflict`.
5. No row found → `write_outcome_uncertain` with `reason_code="integrity_no_row"` — the writer
   never claims the row does not exist when it cannot confirm that.

An unexpected `SQLAlchemyError` is converted into a safe structured result: `commit_uncertain`
(`write_outcome_uncertain`) if a commit had been attempted, otherwise `failed_before_write`. Only
the exception **class name** is reported — never SQL, a connection URL, or plan content.

---

## Choosing a key

The caller owns the key. It must be a string of at most 128 characters and is stored verbatim as a
safe reference (it is not a secret). A stable, meaningful choice is the Phase 36 `report_plan_id`,
or a workflow-scoped key such as `wf35::report_draft::<workflow_id>` when the draft is persisted as
part of a managed record workflow run.

Reusing a key with a materially different plan is a **conflict, not an overwrite** — this table has
no update path. Correcting a stored plan means writing a new row under a new key, leaving the prior
row intact for audit.

---

## Related

- [`INTERNAL_ASSESSMENT_REPORT_DRAFT_CONTROLLED_WRITER.md`](INTERNAL_ASSESSMENT_REPORT_DRAFT_CONTROLLED_WRITER.md)
- [`INTERNAL_ASSESSMENT_REPORT_PLANNING_BOUNDARY.md`](INTERNAL_ASSESSMENT_REPORT_PLANNING_BOUNDARY.md)
- [`CONTROLLED_WRITE_ALLOWLIST.md`](CONTROLLED_WRITE_ALLOWLIST.md)
- [`MANAGED_MYSQL_PERSISTENCE_RUBRIC.md`](MANAGED_MYSQL_PERSISTENCE_RUBRIC.md) — **SQLite is not the
  production-readiness proof path**; managed MySQL test/staging validation is required.
