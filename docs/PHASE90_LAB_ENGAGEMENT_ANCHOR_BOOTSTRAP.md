# Phase 90 — The Lab Engagement Anchor Bootstrap

Phase 90 made **one durable internal-test engagement authorization anchor** in `peak_lab`, through
the existing Phase 54/56 controlled writer, after adding a **bootstrap-only** path to the lab writer
enablement gate. Repo baseline at entry: `ebc3d13`, Alembic head `014_engagement_classification`,
14 migrations, 18 controlled tables, 12 writers.

**This is the first Peak writer invocation ever made against `peak_lab`.**

**Production writer enablement remains false and the production gate is unchanged.** **Exactly one
writer was invoked** — the engagement anchor writer — and **exactly one record was created**. **No
source-ingestion, evidence, review, intake, or client record was created.** **No write occurred to
`peak_lab_scenario`.** **No production access occurred.** **No live Alembic migration ran** and **no
migration `015` was created.** No schema, model, enum, allowlist, governance module, or writer source
was modified.

**This document carries no row body.** Only governed identifiers, closed-vocabulary labels, counts,
and booleans appear here.

---

## 1. Why the anchor had to come first

Every other controlled writer loads the stored `Engagement` row at write time and requires its
request scope to match. A lab rehearsal of the source-ingestion, evidence, or review writers
therefore has **nothing to hang records from** until an anchor exists in the lab.

Phase 89 refused the anchor writer outright and flagged exactly this as the likely blocker. Phase 90
is the explicit reviewed change that admits it — **for bootstrap only**, never as general lab writer
authority.

---

## 2. The gate change

One new variable, required **in addition to** everything Phase 89 already required:

```
PEAK_LAB_ENGAGEMENT_ANCHOR_BOOTSTRAP_CONFIRM=1
```

**The anchor did not become generally enableable.** It is still **absent** from
`LAB_ENABLEABLE_WRITER_TARGETS`, so no ordinary lab request can ever be granted it. It travels a
**separate branch** that requires, all at once:

1. every ordinary lab check from Phase 89 — `lab` target, exact lab confirmation, MySQL/MariaDB
   dialect, schema exactly `peak_lab` (not the scenario schema, not the provider default, not
   production-marked), and the approved `peak_lab_runtime` role;
2. the new bootstrap confirmation, exactly `1`;
3. the anchor as the **only** requested target.

**Bootstrapping an identity/root record and writing data records stay different authorities.** A
request mixing the anchor with any data-record target denies **whole**, with reason
`anchor_bootstrap_must_be_the_only_requested_target`.

**Unchanged:** the three Phase 89 data-record pairs behave exactly as before and need no bootstrap
confirmation; `clients/create_draft` remains never enableable on any path; no `update_*` or `mark_*`
action is enableable; `PEAK_LAB_CONFIRM`, the Phase 84 migration variables, the Phase 85 scenario
variables, and the production-named URL variables all remain refused as authorizers; and production
is denied on every path.

**A superseded Phase 89 assertion.** That harness asserted the anchor pair was in
`NEVER_LAB_ENABLEABLE`. Phase 90 moves it to its own bootstrap branch, so the check was updated to
the invariant that still matters and that Phase 89 was really asserting: **the anchor is not
generally lab-enableable**. `clients/create_draft` remains the never-enableable set's sole member.

---

## 3. The gate is a precondition, not a report

The operator tool evaluates the gate **before any connection is opened** and exits `3` without
writing if the decision is anything other than `lab_anchor_bootstrap_authorized` granting exactly
the anchor target. The decision is not advisory here; it is the thing that lets the write proceed.

---

## 4. Two contract corrections found by the writer, not by the plan

**`authorization_scope` is a closed vocabulary.** The phase plan specified
`internal_peak_lab_only`. That is **not a member** of `peak.db.enums.AuthorizationScope`, and the
writer refused the request at its own boundary with `reason_code=invalid_authorization_scope` —
**with `database_connection_made=false`, so nothing was written and nothing was reached.** The
canonical member `internal_peak_only` was used instead, which is what the Phase 59 production anchor
uses.

Lab-ness is carried by **the database, the engagement id, and the classification columns** — not by
inventing a scope value, which would be an enum and schema change and a governance change of its
own.

**Worth noting for future phases:** the dry-run governance pre-check reported `permitted=True` for
the invalid scope, while the writer's own boundary denied it. **The pre-check is weaker than the
write boundary.** Defence in depth worked exactly as designed — the writer is the authority — but a
green dry-run must not be read as proof that a write will be accepted.

**`capsule_publication_authorized` is `false` here.** Phase 59's production anchor set it `true`;
the lab anchor does not need publication authority and does not claim it. Strictly more
conservative, and permitted by the classification rule.

---

## 5. Credential posture

Sixteen **value-free** structural checks passed against the lab runtime environment file —
existence, mode `600`, exactly one variable, the expected variable name, scheme, role, target
database, and the *presence* (never the content) of password, host, port and CA path; not the
provider default, not the scenario schema, no production marker, and not the migration or scenario
role. **No value was printed, echoed, or logged.**

Read back as the credential itself: `SELECT, INSERT` plus `USAGE`, **no `GRANT OPTION`**, and **no
visibility into `peak_lab_scenario` at all** — 0 schemas and 0 tables — so writing to the scenario
schema was structurally impossible on this path.

---

## 6. Before and after

| measure | before | after |
| --- | ---: | ---: |
| base tables in `peak_lab` | 19 | 19 |
| controlled tables | 18 | 18 |
| `alembic_version` rows / head | 1 / `014_engagement_classification` | 1 / `014_engagement_classification` |
| **application rows, all 18 controlled tables** | **0** | **1** |
| tables holding any row | 0 | 1 (`engagements`) |
| the target anchor | absent | present |

**The one record**, governed fields only:

| field | value |
| --- | --- |
| id | `lab_internal_test_001` |
| client_id | `99999` (reserved internal-test namespace) |
| owner_id | `peak_internal_admin` |
| authorization_scope | `internal_peak_only` |
| status / review_status / lifecycle_status | `active` / `needs_review` / `active` |
| engagement_category | `internal_test` |
| real_client_data | false |
| client_accessible | false |
| capsule_publication_authorized | false |

The `engagement_label` is stored but is **never echoed** — by the writer, the tool, or this
document — because a label can carry a client organisation name.

---

## 7. The receipt

`outcome=created`, `permitted=true`, `stored_record_created=true`, `transaction_committed=true`,
`existing_record_returned=false`, `outcome_uncertain=false`, idempotency key
`phase90_lab_internal_test_engagement_anchor_001`.

Every negative flag held: `other_table_write_made=false`, `client_record_write_made=false`,
`update_made=false`, `delete_made=false`, `review_approval_made=false`,
`client_facing_output_created=false`, `financial_verification_made=false`,
`capsule_publication_made=false`, `agentnet_publication_made=false`, `agent_execution_made=false`,
`llm_call_made=false`, `agentnet_call_made=false`, `resolver_call_made=false`,
`network_call_made=false`.

**Idempotency was exercised, not merely asserted.** A second run of the same tool returned
`outcome=idempotent_replay` with `database_write_made=false`, `stored_record_created=false`,
`existing_record_returned=true` — and the table still holds **exactly one row**. Same anchor, same
definition, no second write. A different definition under the same id would have been an
`idempotency_conflict` denial, never a silent overwrite.

---

## 8. Durability, and the absence of cleanup

**This record is durable and is meant to be.** `peak_lab_runtime` holds `SELECT` + `INSERT` and
**no `DELETE`**, so it cannot be removed by runtime — and no cleanup was attempted, planned, or
built. The operator tool contains no `UPDATE`, `DELETE`, cleanup, or stamp path, and the harness
asserts that.

**A correction means a new engagement id, never a rewrite of this one.** Removing it would require
the migration credential, which is a separate approval and a separate risk, and is not authorized
here.

---

## 9. Testing

**96 checks** in `validate_phase90_lab_engagement_anchor_bootstrap.py`, wired into `make validate`
as `validate-phase90`, plus **29 self-test assertions** in the gate module. All offline, synthetic
and unroutable URLs only, contacting nothing.

Coverage: baseline unchanged, including that the anchor writer, allowlist, governance module and
enum vocabulary were **not** modified; the production gate byte-identical and byte-identical in
output with the bootstrap variables set; the bootstrap as a separate branch; fifteen deny branches;
the authorize branch and its exact grant; Phase 89 data-record behaviour unchanged across all three
pairs; bootstrap-never-implies-production across four environments; the operator tool's gating,
single-writer import, absence of mutation paths, hard-coded packet, canonical scope, and label
withholding; and value-free output.

---

## 10. What remains unauthorized

- **Lab source-ingestion, evidence, and review writes.** The three Phase 89 pairs are *enableable*
  by the gate; that is not approval to run them. Each remains a separately approved phase.
- **Any second anchor.** This tool creates this record or none.
- **Production writes and production writer enablement.** Unchanged and false.
- **The `clients` table.** Never writable by any path.
- **Cleanup or correction of this record.** Not available through runtime, not attempted.

A future phase proposing lab data-record writes must still name, in advance: the writer, the
records and expected count, the source measurements they derive from, the authorization scope, the
idempotency keys, the expected receipts, the post-write verification, and the durability posture.

---

## 11. Warnings and decisions needing review

1. **The dry-run governance pre-check is weaker than the writer boundary.** It passed a scope value
   the writer then refused. Nothing was written, and defence in depth worked — but a green dry-run
   is not evidence that a write will be accepted, and future phases should not treat it as one.
   Worth considering whether the pre-check should validate the scope enum too.

2. **The lab anchor's `authorization_scope` is identical to the production anchor's**
   (`internal_peak_only`), because the vocabulary is closed and has no lab-specific member. The two
   are separated by *database*, not by scope value. Anything that ever compares anchors across
   environments must not rely on scope to tell them apart.

3. **`peak_lab` is no longer empty.** Every prior phase could assert "0 application rows across all
   18 controlled tables" as a safety check. That assertion is now false by design; future harnesses
   and verifiers must expect exactly one `engagements` row and must not read its presence as drift.

4. **The bootstrap confirmation is a standing capability once documented.** Anyone holding the lab
   runtime credential and knowing the four variable names can create an anchor. The narrowing
   controls are the hard-coded packet, the single-target requirement, and the idempotency key — not
   secrecy.

5. **A second lab anchor would need a new engagement id**, and nothing in the gate prevents a future
   tool from choosing one. The single-record discipline lives in the operator tool's hard-coded
   packet, not in the gate.
