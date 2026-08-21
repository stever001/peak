#!/usr/bin/env python3
"""Phase 61 — record the **one** internal review decision on the Phase 60 intake note.

A narrow operator utility, not a general-purpose record creator. Every field is a constant; there
is no flag that can change the reviewed target, the engagement, the decision, or the posture.

**Why ``review_records`` is the right writer.** ``peak/db/review_writer.py`` separates two things
this review needs kept apart: the **authorization anchor** (``request.subject``, which must be the
``engagement``) and the **reviewed target** (``draft.subject_record_id`` /
``draft.subject_record_type``, which the writer stores as ``target_id`` and is explicitly "distinct
from the Engagement authorization anchor"). That lets the Phase 60 intake note be reviewed under
the Phase 59 anchor's authority without overloading either field. The alternative,
``internal_reviewer_decision_records``, is shaped around a **review bundle** — bundle refs, review
plan items, evidence and source-ingestion ids — and has no reviewed-target field, so representing
an intake note there would mean misusing a bundle reference. ``review_records`` is the narrower
honest fit.

**Why ``approve_internal``.** The writer's decision vocabulary is fixed
(``approve_internal`` / ``reject`` / ``return_for_revision`` / ``supersede`` /
``keep_needs_review``); ``client_facing_approve``, ``verify_financial_impact``, and
``publish_capsule`` are rejected outright. ``approve_internal`` means **internal reliance only and
never client-facing approval**, which is exactly the finding: the intake note is sufficient to
*begin* source and evidence collection as an internal/admin workflow. It authorises no report, no
capsule candidacy, and no publication.

**Findings, not prose.** The ``reasons`` list carries concise sanitized findings — which V0
taxonomy categories are covered, which remain incomplete, and what evidence to request next. It
carries **no note body text**. The note body stays outside the repository and is never read,
printed, or stored by this tool.

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

#: The Phase 60 intake note — the reviewed target, stored as ``target_id``.
SUBJECT_RECORD_ID = "intn_b8b86b8c196c4595"
SUBJECT_RECORD_TYPE = "intake_note"

REVIEWER = "peak_internal_admin"
REVIEWER_ROLE = "internal_admin"
IDEMPOTENCY_KEY = "phase61_internal_test_intake_review_decision_001"
SOURCE_PHASE = "phase61"

DECISION = "approve_internal"             # internal reliance only; never client-facing approval
NEXT_REVIEW_STATUS = "approved_internal"  # required by the writer for approve_internal
NEXT_OUTPUT_STATUS = "draft"              # the output stays non-final
NEXT_LIFECYCLE_STATUS = "active"
#: Left false deliberately: this records an internal determination, and nothing downstream should
#: yet treat it as authoritative. The writer permits either value for ``approve_internal``.
AUTHORITATIVE = False

#: Concise sanitized findings. Category labels and gap descriptors only — no note body text.
REASONS = (
    "intake_review: taxonomy=PEAK_INTAKE_QUESTION_TAXONOMY_V0",
    "covered_qualitatively: all 14 V0 categories have narrative coverage",
    "incomplete_quantitatively: note carries no counts, rates, cadences, or dates",
    "incomplete: 03_item_sku_master - duplicate rate and master size unquantified",
    "incomplete: 04_location_structure - no location/bin naming model supplied",
    "incomplete: 06_counts_adjustments - count cadence, coverage, adjustment volume unquantified",
    "incomplete: 07_stockouts_overstocks - frequency and carrying cost unquantified",
    "incomplete: 08_systems_of_record - systems unnamed; precedence rule informal",
    "incomplete: 09_exports_reporting - export inventory, formats, cadence not enumerated",
    "incomplete: 11_evidence_availability - nothing collected or normalized yet",
    "incomplete: 14_metrics_urgency - no target metric, baseline, or deadline",
    "evidence_next: current inventory export by SKU and location",
    "evidence_next: item/SKU master export",
    "evidence_next: adjustment history with reason codes, if available",
    "evidence_next: recent receiving and putaway records",
    "evidence_next: recent cycle count or physical count results",
    "evidence_next: stockout/backorder or fulfillment exception data",
    "evidence_next: available SOP and process documentation",
    "evidence_next: system-of-record and data-export map",
    "posture: internal_test engagement; no real client data; not client-facing",
    "next_step: source/evidence request and source ingestion planning",
    "not_authorized: report drafting, capsule candidacy, publication",
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
        subject_record_id=SUBJECT_RECORD_ID,      # the reviewed target: the Phase 60 intake note
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
    print("Authorized packet (findings only; the intake note body is never read or printed)")
    for key, val in (("engagement_id (authorization anchor)", ENGAGEMENT_ID),
                     ("client_id", CLIENT_ID), ("owner_id", OWNER_ID),
                     ("authorization_scope", AUTHORIZATION_SCOPE),
                     ("subject_record_id (reviewed)", SUBJECT_RECORD_ID),
                     ("subject_record_type", SUBJECT_RECORD_TYPE),
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
    print("\nReceipt (typed fields only; no note body, DSN, environment value, or SQL)")
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
        print("\nRESULT: CREATED (exactly one internal review decision)")
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
        description=f"Record the one internal review decision on intake note {SUBJECT_RECORD_ID} "
                    f"under engagement {ENGAGEMENT_ID}, via the Phase 22 controlled review writer. "
                    "Dry-run unless --execute is passed. Every field is hard-coded.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true",
                      help="Validate the packet and stop before opening a connection (default).")
    mode.add_argument("--execute", action="store_true",
                      help="Invoke the controlled writer. Creates at most one review record.")
    args = parser.parse_args(argv)

    print("Peak Phase 61 — internal test intake review decision")
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
