#!/usr/bin/env python3
"""Phase 70 — record the **one** internal review decision on the Phase 69 R9 source ingestion
record (the location/bin naming model).

A narrow operator utility, not a general-purpose record creator. Every field is a constant; there
is no flag that can change the reviewed target, the engagement, the decision, or the posture. In
particular there is **no flag that can retarget R1, R2, R8, the intake note, an evidence reference,
a report, or a capsule** — the reviewed target is a module constant, no other stored record id
appears anywhere in this file, and the argument parser exposes only the run mode.

**Why ``review_records`` is the right writer, and why it needs no field overloading.**
``peak/db/review_writer.py`` keeps two things apart that this review needs kept apart: the
**authorization anchor** (``request.subject``, which the writer requires to be the ``engagement``)
and the **reviewed target** (``draft.subject_record_id`` / ``draft.subject_record_type``, which the
writer stores as ``target_id`` and documents as "distinct from the Engagement authorization
anchor"). ``subject_record_type='source_ingestion_record'`` is the same honest value **Phase 66**
used for the R2 source-ingestion review, and the reviewed target here is the same class of record.
``draft.source_reference_id`` carries the reviewed packet reference, and ``draft.reasons`` is a free
findings list the writer persists into ``details_json`` — so the limits are stored **as findings**,
not squeezed into a field meant for something else. No new writer, model, migration, or allowlist
pair is required.

**Why ``approve_internal``.** The writer's decision vocabulary is fixed (``approve_internal`` /
``reject`` / ``return_for_revision`` / ``supersede`` / ``keep_needs_review``);
``client_facing_approve``, ``verify_financial_impact``, and ``publish_capsule`` are rejected
outright by the writer. ``approve_internal`` means **internal reliance only and never client-facing
approval**, which is exactly the finding: R9 is sufficient to proceed to **future evidence work
about R1 location-dimension readiness** — and to nothing wider.

**The central honest limit of this review.** R9 as collected is a **question set, not an answered
model**. Every hierarchy level and every location type/status field is marked presence-unknown, and
the artifact poses many structural questions without answering any of them. That is appropriate for
a collected source and is not a defect — but it means R9 **defines what must be measured** rather
than reporting what is true. It therefore **cannot by itself lift R1's provisional location
marking**; only measured answers could. This limit is recorded in the findings so the stored row
states it in its own text.

**What this decision deliberately does not authorize.** It does not create an
``evidence_reference``; it does not validate any inventory quantity (R9 contains no instance data at
all, so it can support no count, rate, or total); it does not lift **R1's provisional** location
dimension; it does not confirm **R8's** authority precedence (R8 stays ``needs_review`` / ``draft``
/ ``authoritative=false``); it does not resolve **R5's WMS scope uncertainty**; it leaves **R3-R7
deferred**; and it authorizes **no report drafting, no capsule candidacy, no client-facing output,
and no AgentNet resolver publication**. ``ReviewRecordDraft`` has no ``publication_allowed`` field
to set false — the prohibition is structural instead, and stronger: the writer refuses
``publish_capsule`` at the vocabulary level and forces ``client_facing_approved=false`` and
``capsule_candidate_ready=false``.

**``authoritative`` is left false.** The writer would permit ``true`` for ``approve_internal``, but
this decision reviews a location model that answers none of its own questions, whose ownership is
undetermined, and whose upstream map (R8) is itself unreviewed. Nothing downstream should yet treat
it as settled.

**Findings, not prose, and no artifact body.** The ``reasons`` list carries concise sanitized
findings — structural counts, posture flags, and named gaps. It carries **no artifact body text, no
field values, no item or SKU values, no quantities, and no location, bin, aisle, rack, warehouse, or
site identifiers**. The R9 artifact body stays outside the repository and is **never read, printed,
or stored by this tool**: this file opens no artifact and computes no hash.

**Dry-run by default.** With no flag (or ``--dry-run``) it runs the writer's own pre-DB governance
gate and stops **before any connection is opened**. Only ``--execute`` proceeds to the writer.

**Credential boundary.** The runtime session is resolved by the normal runtime path
(:func:`peak.db.session.create_session_factory`), which reads ``PEAK_RUNTIME_DATABASE_URL`` and
**only** that variable. This file reads no environment variable itself, imports no Alembic or
migration code, issues no raw SQL, and has no ``UPDATE`` / ``DELETE`` / cleanup / stamp path. The
only statements it can cause are the writer's own stored-engagement load, its idempotency lookup,
one ``INSERT``, and the read-back.

Exit status:
  0  -> dry-run validated, or the decision was created, or an exact idempotent replay
  1  -> denied, failed, or the outcome is uncertain (including an idempotency conflict)
"""

from __future__ import annotations

import argparse
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# --------------------------------------------------------------------------- fixed identity

#: The Phase 59 engagement anchor — the authorization subject this decision is written under.
ENGAGEMENT_ID = "internal_test_001"
CLIENT_ID = "99999"                       # reserved internal-test namespace (a visible marker)
OWNER_ID = "peak_internal_admin"
AUTHORIZATION_SCOPE = "internal_peak_only"

#: The Phase 69 R9 source ingestion record — the reviewed target, stored as ``target_id``.
#: A constant, deliberately: no flag can point this at R1, R2, R8, or any other record.
SUBJECT_RECORD_ID = "ing_64b2e2648ac1402b"
SUBJECT_RECORD_TYPE = "source_ingestion_record"
#: The reviewed packet reference, carried on ``draft.source_reference_id``.
SOURCE_REFERENCE_ID = "pkt_internal_test_r9_location_bin_model_001"

REVIEWER = "peak_internal_admin"
REVIEWER_ROLE = "internal_admin"
IDEMPOTENCY_KEY = "phase70_internal_test_r9_source_ingestion_review_001"
SOURCE_PHASE = "phase70"

DECISION = "approve_internal"             # internal reliance only; never client-facing approval
NEXT_REVIEW_STATUS = "approved_internal"  # required by the writer for approve_internal
NEXT_OUTPUT_STATUS = "draft"              # the output stays non-final
NEXT_LIFECYCLE_STATUS = "active"
#: Left false deliberately: R9 answers none of its own questions, its ownership is undetermined,
#: and its upstream map (R8) is unreviewed. The writer permits either value here.
AUTHORITATIVE = False

#: Concise sanitized findings. Structural counts, posture flags, and named gaps only — no artifact
#: body text, no field values, no item/SKU values, no quantities, and no location, bin, aisle,
#: rack, warehouse, or site identifiers.
REASONS = (
    "source_review: R9 location/bin naming model source ingestion record",
    "reviewed_target: source_ingestion_record registered in phase69",
    "reviewed_packet: pkt_internal_test_r9_location_bin_model_001",
    "registration_integrity: reviewed artifact hash matches the registered packet_hash; the "
    "artifact registered in phase69 is unchanged",
    "structure: artifact is a concept/field-level location model in 17 top-level sections; it is "
    "a description of a model, not an export, and carries no rows",
    "structure: 6 location hierarchy levels are described, from site down to bin",
    "structure: 5 bin/location naming fields plus 3 normalization questions are described",
    "structure: 3 location type/status fields are described",
    "structure: 4 inventory availability treatment concepts are described, including the "
    "status-bucket versus physical-position distinction",
    "structure: 6 virtual/non-physical concepts are described - virtual/logical, staging, hold, "
    "damaged, quarantine/inspection, and unavailable inventory",
    "structure: 4 candidate ownership postures are recorded - ERP, WMS, manual, and unknown - "
    "each stated as an open question rather than an ownership claim",
    "structure: 8 explicit non-validation statements are carried on the artifact itself",
    "content_rule_verified: every contains-instance-data flag on the artifact is false; no "
    "location identifiers, bin codes, aisle, rack, warehouse or site names, item values, "
    "quantities, or row-like export data are present",
    "limit: R9 is a question set, not an answered model - all 6 hierarchy levels and all 3 "
    "type/status fields are marked presence-unknown, and roughly 53 structural questions are "
    "posed without any being answered",
    "limit: because R9 defines what must be measured rather than reporting what is true, it "
    "cannot by itself lift R1's provisional location marking; only measured answers could",
    "limit: R9 supplies no basis for choosing among the 4 candidate ownership postures, so "
    "location attribution to a system of record remains unavailable",
    "readiness: R9 is sufficient to define the R1 location-dimension readiness question set and "
    "to scope future evidence work against it",
    "decision_meaning: R9 is internally approved only for future evidence work about R1 "
    "location-dimension readiness, and for nothing wider",
    "not_authorized: no evidence_reference is created by this decision; a narrow R9 evidence "
    "reference remains a separately approved phase",
    "not_authorized: inventory accuracy or quantity conclusions - R9 contains no instance data "
    "and can support no count, rate, or total",
    "not_authorized: R1 location claims - the location dimension remains provisional and this "
    "decision does not lift that marking",
    "not_authorized: R8 remains provisional - needs_review / draft / authoritative=false, with "
    "an unconfirmed authority precedence rule, so no measure may yet be attributed to a system "
    "of record",
    "not_authorized: R5 WMS scope remains unresolved - R9 records the shared dependency but is "
    "not evidence about WMS scope",
    "not_authorized: R3-R7 remain deferred behind their unresolved R8 blockers",
    "not_authorized: report drafting, capsule candidacy, client-facing output",
    "not_authorized: AgentNet resolver publication - the public resolver is live, which is why "
    "the gate stays shut rather than relaxed",
    "posture: internal_test engagement; no real client data; not client-facing; "
    "authoritative=false",
    "next_step: either a single narrow R9 evidence_reference scoped to location-model "
    "availability and readiness, or a combined R1/R9 evidence-readiness planning step - either "
    "way a separately approved phase",
)

RECEIPT_FIELDS = (
    "outcome", "permitted", "reason_code", "target_table", "target_action",
    "stored_record_id", "idempotency_key", "audit_trace_ref",
    "database_connection_made", "sql_execution_made", "database_write_made",
    "stored_record_created", "existing_record_returned", "transaction_committed",
    "outcome_uncertain",
    "decision", "authoritative", "review_status", "lifecycle_status", "output_status",
    "subject_record_type", "target_id",
    "client_facing_approved", "capsule_candidate_ready",
    "other_table_write_made", "client_record_write_made", "engagement_record_write_made",
    "intake_note_record_created", "source_ingestion_record_created",
    "evidence_reference_created", "report_draft_created", "review_packet_created",
    "update_made", "delete_made", "client_facing_output_created",
    "financial_verification_made", "capsule_publication_made", "agentnet_publication_made",
    "agent_execution_made", "agent_run_record_created", "llm_call_made", "agentnet_call_made",
    "resolver_call_made", "network_call_made", "created_at", "database_write_at",
)


def build_request():
    """Build the one controlled write request. Opens no connection and reads no environment."""
    from peak.db.writer_contracts import REVIEW_TARGET_ACTION, REVIEW_TARGET_TABLE
    from peak.persistence.contracts import ControlledWriteRequest, ControlledWriteSubject
    from peak.review.persistence_contracts import ReviewRecordDraft

    draft = ReviewRecordDraft(
        # The reviewed target: the Phase 69 R9 source ingestion record.
        subject_record_id=SUBJECT_RECORD_ID,
        subject_record_type=SUBJECT_RECORD_TYPE,
        owner_id=OWNER_ID,
        client_id=CLIENT_ID,
        engagement_id=ENGAGEMENT_ID,
        reviewer_role=REVIEWER_ROLE,
        requested_by=REVIEWER,
        decision=DECISION,
        next_output_status=NEXT_OUTPUT_STATUS,
        next_review_status=NEXT_REVIEW_STATUS,
        next_lifecycle_status=NEXT_LIFECYCLE_STATUS,
        authoritative=AUTHORITATIVE,
        client_facing_approved=False,
        capsule_candidate_ready=False,
        reasons=list(REASONS),
        source_reference_id=SOURCE_REFERENCE_ID,
    )
    return ControlledWriteRequest(
        owner_id=OWNER_ID,
        client_id=CLIENT_ID,
        engagement_id=ENGAGEMENT_ID,
        requested_by=REVIEWER,
        requester_role=REVIEWER_ROLE,
        authorization_scope=AUTHORIZATION_SCOPE,
        target_table=REVIEW_TARGET_TABLE,
        requested_action=REVIEW_TARGET_ACTION,
        # The authorization anchor is the engagement, never the reviewed target.
        subject=ControlledWriteSubject(
            subject_record_id=ENGAGEMENT_ID,
            subject_record_type="engagement",
            owner_id=OWNER_ID,
            client_id=CLIENT_ID,
            engagement_id=ENGAGEMENT_ID,
            stored_authorization_scope=AUTHORIZATION_SCOPE,
            stored_lifecycle_status="active",
        ),
        record_draft=draft,
        source_phase=SOURCE_PHASE,
        lifecycle_status="active",
        idempotency_key=IDEMPOTENCY_KEY,
    )


def emit_packet() -> None:
    print("Authorized packet (findings only; the R9 artifact body is never read or printed)")
    for key, val in (("engagement_id (authorization anchor)", ENGAGEMENT_ID),
                     ("client_id", CLIENT_ID), ("owner_id", OWNER_ID),
                     ("authorization_scope", AUTHORIZATION_SCOPE),
                     ("subject_record_id (reviewed)", SUBJECT_RECORD_ID),
                     ("subject_record_type", SUBJECT_RECORD_TYPE),
                     ("source_reference_id (reviewed packet)", SOURCE_REFERENCE_ID),
                     ("decision", DECISION), ("authoritative", AUTHORITATIVE),
                     ("next_review_status", NEXT_REVIEW_STATUS),
                     ("next_output_status", NEXT_OUTPUT_STATUS),
                     ("next_lifecycle_status", NEXT_LIFECYCLE_STATUS),
                     ("client_facing_approved", False), ("capsule_candidate_ready", False),
                     ("reviewer", REVIEWER), ("reviewer_role", REVIEWER_ROLE),
                     ("idempotency_key", IDEMPOTENCY_KEY), ("source_phase", SOURCE_PHASE)):
        print(f"  {key:<38}: {val}")
    print(f"  {'findings (reasons)':<38}: {len(REASONS)} entries")
    for line in REASONS:
        print(f"      - {line}")


def emit_receipt(receipt) -> None:
    print("\nReceipt (typed fields only; no artifact body, DSN, environment value, or SQL)")
    for field in RECEIPT_FIELDS:
        if hasattr(receipt, field):
            print(f"  {field:<38}: {getattr(receipt, field)}")
    for line in getattr(receipt, "reasons", []) or []:
        print(f"  reason  : {line}")
    for line in getattr(receipt, "warnings", []) or []:
        print(f"  warning : {line}")


def dry_run(request) -> int:
    from peak.db.review_writer import _payload_fingerprint, _pre_db_validate

    denial, draft = _pre_db_validate(request, None)
    if denial is not None:
        print("\n[denied] the packet did not pass the writer's pre-DB governance gate")
        emit_receipt(denial)
        print("\nRESULT: DRY-RUN DENIED (no connection opened, nothing written)")
        return 1

    print("\n[ok] packet passes the writer's own pre-DB governance gate")
    print(f"  payload fingerprint                   : {_payload_fingerprint(request, draft)}")
    print("  database_connection_made              : False")
    print("  sql_execution_made                    : False")
    print("  database_write_made                   : False")
    print("\n  note: the stored-engagement authorization check runs at write time and needs a")
    print("        connection, so it is NOT exercised by this dry-run.")
    print("\nRESULT: DRY-RUN PASS (nothing was written; re-run with --execute to create it)")
    return 0


def execute(request) -> int:
    from peak.db.review_writer import persist_review_record

    receipt = persist_review_record(request)
    emit_receipt(receipt)

    outcome = getattr(receipt, "outcome", None)
    if outcome == "created":
        print("\nRESULT: CREATED (exactly one internal review decision on the R9 source "
              "ingestion record)")
        return 0
    if outcome == "idempotent_replay":
        print("\nRESULT: IDEMPOTENT REPLAY (an identical decision already existed; nothing was "
              "written or modified)")
        return 0
    if getattr(receipt, "reason_code", None) == "idempotency_conflict":
        print("\nRESULT: IDEMPOTENCY CONFLICT — this idempotency key already exists with a "
              "different payload. The existing record was NOT modified. Stop and review; do not "
              "delete or alter it.")
        return 1
    print(f"\nRESULT: NOT CREATED ({outcome})")
    return 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=f"Record the one internal review decision on R9 source ingestion record "
                    f"{SUBJECT_RECORD_ID} (the location/bin naming model) under engagement "
                    f"{ENGAGEMENT_ID}, via the Phase 22 controlled review writer. Approves "
                    "internal reliance only, for future evidence work about R1 location-dimension "
                    "readiness. Dry-run unless --execute is passed. Every field is hard-coded.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true",
                      help="Validate the packet and stop before opening a connection (default).")
    mode.add_argument("--execute", action="store_true",
                      help="Invoke the controlled writer. Creates at most one review record.")
    args = parser.parse_args(argv)

    print("Peak Phase 70 — internal review decision on the R9 source ingestion record")
    print("=" * 70)
    emit_packet()

    request = build_request()
    if not args.execute:
        return dry_run(request)

    print("\n[execute] invoking the controlled review writer "
          "(runtime credential, SELECT + INSERT only)")
    return execute(request)


if __name__ == "__main__":
    raise SystemExit(main())
