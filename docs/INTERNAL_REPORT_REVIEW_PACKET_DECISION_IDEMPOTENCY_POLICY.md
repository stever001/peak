# Internal Report Review Packet Decision Idempotency Policy (Phase 39)

DB-enforced idempotency for `internal_report_review_packet_decisions`, mirroring the policy every
prior controlled writer follows. The writer itself is documented in
[`INTERNAL_REPORT_REVIEW_PACKET_DECISION_CONTROLLED_WRITER.md`](INTERNAL_REPORT_REVIEW_PACKET_DECISION_CONTROLLED_WRITER.md).

---

## Uniqueness boundary

```
UNIQUE (owner_id, client_id, engagement_id, idempotency_key)
```

Index name: `uq_internal_report_review_packet_decisions_idem` (47 characters — within MySQL's
64-character identifier limit).

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
- audit chain: `internal_report_review_packet_id`, `source_packet_table`,
  `internal_assessment_report_draft_id`, `source_report_draft_table`, `report_plan_id`,
  `plan_fingerprint`, `packet_payload_fingerprint`, `report_draft_payload_fingerprint`
- decision content: `reviewer_ref`, `decision_intent`, `safe_decision_summary`,
  `requested_followup_actions`
- stored posture: `decision_status`, `decision_scope`, `audience`, `review_status`,
  `lifecycle_status`, and every posture boolean

The serialization is `sort_keys=True` with compact separators, so it is deterministic and
order-independent at the key level.

**Both upstream fingerprints are taken from the stored rows, not from the caller.** The digest is
therefore bound to the exact packet *and* report-draft payloads the decision was made against: if
either upstream artifact differs, the decision fingerprint differs, and a replay under the same key
becomes a conflict rather than a silent match.

**`decision_status` participates** even though it is server-derived — so a decision recorded under
`needs_more_evidence` can never silently replay as one recorded under `ready_for_internal_use`.

**No raw content participates.** The fingerprint is computed over references, labels, statuses, and
one bounded internal summary — the same material the row stores.

---

## Outcomes

| Situation | Outcome | Effect |
|---|---|---|
| No existing row on the boundary | `created` | exactly one row inserted, transaction committed |
| Same boundary + same key + **same** fingerprint | `idempotent_replay` | existing row id returned, **nothing modified** |
| Same boundary + same key + **different** fingerprint | `denied` / `idempotency_conflict` | **no mutation**, no row returned |
| Governance failure before the DB | `denied` | no connection opened, no SQL executed |
| Stored engagement / packet / report-draft check fails | `denied` | connection opened for the reads; **no write** |
| Infrastructure failure before insert | `failed_before_write` | no row created |
| Commit outcome unconfirmable | `write_outcome_uncertain` | never claims a row does or does not exist |

A replay is a **read**, not a write: the receipt reports
`database_connection_made=true`, `sql_execution_made=true`, `database_write_made=false`,
`stored_record_created=false`, `existing_record_returned=true`, `transaction_committed=false`.

In **every** outcome — including a successful create — `packet_row_updated` and
`report_draft_row_updated` remain false. Phase 39 is insert-only.

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
the exception **class name** is reported — never SQL, a connection URL, or decision content.

---

## Choosing a key

The caller owns the key. It must be a string of at most 128 characters and is stored verbatim as a
safe reference (it is not a secret). A stable, meaningful choice is the packet the decision covers —
for example `packet_decision::<internal_report_review_packet_id>` — so re-issuing the same decision
replays rather than duplicating.

Reusing a key with a materially different decision is a **conflict, not an overwrite** — this table
has no update path. A reviewer changing their mind writes a **new** row under a new key; the prior
decision stays intact. What a reviewer decided, and when, is a historical fact.

---

## Related

- [`INTERNAL_REPORT_REVIEW_PACKET_DECISION_CONTROLLED_WRITER.md`](INTERNAL_REPORT_REVIEW_PACKET_DECISION_CONTROLLED_WRITER.md)
- [`INTERNAL_REPORT_REVIEW_PACKET_CONTROLLED_WRITER.md`](INTERNAL_REPORT_REVIEW_PACKET_CONTROLLED_WRITER.md)
- [`INTERNAL_REVIEWER_DECISION_CONTROLLED_WRITER.md`](INTERNAL_REVIEWER_DECISION_CONTROLLED_WRITER.md) —
  the Phase 33 writer for **review-bundle** reviewer decisions, which is a different artifact
- [`CONTROLLED_WRITE_ALLOWLIST.md`](CONTROLLED_WRITE_ALLOWLIST.md)
- [`MANAGED_MYSQL_PERSISTENCE_RUBRIC.md`](MANAGED_MYSQL_PERSISTENCE_RUBRIC.md) — **SQLite is not the
  production-readiness proof path**; managed MySQL test/staging validation is required.
