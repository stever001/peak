#!/usr/bin/env python3
"""Phase 68 — record the **one** internal review decision on the Phase 67 R2 evidence reference.

A narrow operator utility, not a general-purpose record creator. Every field is a constant; there
is no flag that can change the reviewed target, the engagement, the decision, or the posture. In
particular there is **no flag that can retarget R1, R8, the R2 source ingestion record, the intake
note, or any earlier review** — the reviewed target is a module constant, **no other stored record
id appears anywhere in this file**, and the argument parser exposes only the run mode.

**Why ``review_records`` is the right writer, and why it needs no field overloading.**
``peak/db/review_writer.py`` keeps apart the two things this review needs kept apart: the
**authorization anchor** (``request.subject``, which the writer requires to be the ``engagement``)
and the **reviewed target** (``draft.subject_record_id`` / ``draft.subject_record_type``, stored as
``target_id`` and documented in the model as the column that "disambiguates the reviewed target").
``draft.source_reference_id`` carries the reviewed packet reference, and ``draft.reasons`` is a free
findings list that the writer persists into ``details_json`` — so the limits are stored as findings
rather than squeezed into a field meant for something else. Phase 61 used this shape with
``subject_record_type='intake_note'`` and Phase 66 with ``'source_ingestion_record'``.

**Why ``subject_record_type='evidence_reference'``.** The reviewed target is a **stored
``evidence_references`` row**, so the value is derived from that table's name — the same convention
Phase 61 and Phase 66 used. Some older harness fixtures label an ``evid_`` target
``normalized_evidence_record``; that name belongs to the Phase 14 *in-memory* normalization output,
which is never stored, so using it here would point at the wrong artifact class. This is a
deliberate, documented choice, not an oversight.

**Why ``approve_internal``.** The writer's decision vocabulary is fixed (``approve_internal`` /
``reject`` / ``return_for_revision`` / ``supersede`` / ``keep_needs_review``);
``client_facing_approve``, ``verify_financial_impact``, and ``publish_capsule`` are rejected
outright. ``approve_internal`` means **internal reliance only and never client-facing approval**,
which is exactly the finding: the evidence reference may be relied on for a **future internal
assessment finding about item-master source availability and data readiness** — and for nothing
wider.

**What this decision deliberately does not authorize.** No inventory accuracy conclusion; no SKU or
location quantity reliability claim; no validation of **R1** location claims (that dimension stays
provisional pending **R9**); no confirmation of **R8** authority precedence (R8 stays
``needs_review`` / ``draft`` / ``authoritative=false``); **R3-R7** stay deferred; and no report
drafting, capsule publication, client-facing output, or AgentNet resolver publication.
``ReviewRecordDraft`` has no ``publication_allowed`` field to set false — the prohibition is
structural instead, and stronger: the writer refuses ``publish_capsule`` at the vocabulary level and
forces ``client_facing_approved=false`` and ``capsule_candidate_ready=false``. The limits are
additionally recorded in the ``reasons`` findings so the stored row states them in its own text.

**``authoritative`` is left false.** The writer would permit ``true`` for ``approve_internal``, but
the reviewed evidence rests on a source whose upstream map (R8) is itself unreviewed and carries
``reliability='low'``. Nothing downstream should yet treat it as settled.

**Findings, not prose.** The ``reasons`` list carries concise sanitized findings — structural
counts, posture flags, and named gaps. It carries **no artifact body text, no field values, no item
or SKU values, no quantities, and no location identifiers**. The R2 artifact body stays outside the
repository and is **never read, printed, or stored by this tool**: this file opens no artifact and
computes no hash.

**Dry-run by default.** With no flag (or ``--dry-run``) it runs the writer's own pre-DB governance
gate and stops **before any connection is opened**. Only ``--execute`` proceeds to the writer.

**Credential boundary.** The runtime session is resolved by the normal runtime path
(:func:`peak.db.session.create_session_factory`), which reads ``PEAK_RUNTIME_DATABASE_URL`` and
**only** that variable. This file reads no environment variable itself, imports no migration code,
issues no raw SQL, and has no ``UPDATE`` / ``DELETE`` / cleanup / stamp path. The only statements it
can cause are the writer's own stored-engagement load, its idempotency lookup, one ``INSERT``, and
the read-back.

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

#: The Phase 67 R2 evidence reference — the reviewed target, stored as ``target_id``. A constant,
#: deliberately: no flag can point this at R1, R8, the R2 source ingestion record, the intake note,
#: or any earlier review, and none of those ids appears anywhere in this file.
SUBJECT_RECORD_ID = "evid_56437d9b9c764560"
SUBJECT_RECORD_TYPE = "evidence_reference"
#: The reviewed packet reference, carried on ``draft.source_reference_id``.
SOURCE_REFERENCE_ID = "pkt_internal_test_r2_sku_item_master_001"

REVIEWER = "peak_internal_admin"
REVIEWER_ROLE = "internal_admin"
IDEMPOTENCY_KEY = "phase68_internal_test_r2_evidence_review_001"
SOURCE_PHASE = "phase68"

DECISION = "approve_internal"             # internal reliance only; never client-facing approval
NEXT_REVIEW_STATUS = "approved_internal"  # required by the writer for approve_internal
NEXT_OUTPUT_STATUS = "draft"              # the output stays non-final
NEXT_LIFECYCLE_STATUS = "active"
#: Left false deliberately: the reviewed evidence carries reliability='low' and rests on a source
#: whose upstream map (R8) is itself unreviewed. The writer permits either value here.
AUTHORITATIVE = False

#: Concise sanitized findings. Structural counts, posture flags, and named gaps only — no artifact
#: body text, no field values, no item/SKU values, no quantities, no location identifiers.
REASONS = (
    "evidence_review: R2 item-master source availability / data readiness evidence reference",
    "reviewed_target: evidence_reference created in phase67",
    "reviewed_packet: pkt_internal_test_r2_sku_item_master_001",
    "chain: phase66 approved the R2 source ingestion record internally for exactly this narrow "
    "downstream evidence use, and phase67 created the evidence reference inside that scope",
    "scope_check: the evidence reference claims item-master source availability and data "
    "readiness only - it does not exceed the scope phase66 approved",
    "structure: the evidence rests on an artifact describing 10 item-master fields - 6 required, "
    "4 optional - each carrying an interpretation note and a named risk",
    "structure: the artifact is a field-level export description, not an export; it carries no "
    "rows, so no measured quantity is in evidence",
    "confidence: reliability remains low, and evidence_references carries no authoritative column, "
    "so nothing downstream can treat the evidence as settled",
    "posture_check: the reviewed evidence reference is needs_review / draft, with "
    "client_facing_approved=false and capsule_candidate_ready=false",
    "gap: unit-of-measure posture remains unconfirmed - distinct UoM codes, multi-UoM items, and "
    "conversion factors must be measured before any quantity claim rests on it",
    "gap: item-status posture remains unconfirmed - master size is not meaningful until obsolete "
    "and blocked rows are separable",
    "gap: 6 duplicate/normalization risks remain future review topics - any duplicate rate must "
    "cite its normalization rule and status filter",
    "gap: whether R1 draws item identifiers from the same identifier domain is unconfirmed and "
    "must be checked at reconciliation time",
    "provenance_note: evidence_references has no typed related-object column, so the source "
    "ingestion and supporting review links live in the evidence record's own text; "
    "machine-joinable provenance remains a future consideration, not a blocker here",
    "decision_meaning: the evidence reference is internally approved for use in a future internal "
    "assessment finding about item-master source availability and data readiness",
    "not_authorized: inventory accuracy conclusions - the evidence describes an item master, not "
    "measured on-hand quantity",
    "not_authorized: SKU or location quantity reliability claims",
    "not_authorized: R1 location claims - the location dimension remains provisional pending R9",
    "not_authorized: R8 authority precedence - R8 remains needs_review / draft / "
    "authoritative=false, so no measure may yet be attributed to a system of record",
    "not_authorized: R3-R7 remain deferred behind their unresolved R8 blockers",
    "not_authorized: report drafting, capsule publication, client-facing output",
    "not_authorized: AgentNet resolver publication - the public resolver is live, which is why "
    "the gate stays shut rather than relaxed",
    "posture: internal_test engagement; no real client data; not client-facing; "
    "authoritative=false",
    "next_step: phase69 should likely collect R9, the location/bin naming model, which unblocks "
    "the R1 location dimension",
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
        # The reviewed target: the Phase 67 R2 evidence reference.
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
    print("Authorized packet (findings only; the R2 artifact body is never read or printed)")
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
        print("\nRESULT: CREATED (exactly one internal review decision on the R2 evidence "
              "reference)")
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
        description=f"Record the one internal review decision on R2 evidence reference "
                    f"{SUBJECT_RECORD_ID} under engagement {ENGAGEMENT_ID}, via the Phase 22 "
                    "controlled review writer. Approves internal reliance only, for a future "
                    "internal assessment finding about item-master source availability and data "
                    "readiness. Dry-run unless --execute is passed. Every field is hard-coded.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true",
                      help="Validate the packet and stop before opening a connection (default).")
    mode.add_argument("--execute", action="store_true",
                      help="Invoke the controlled writer. Creates at most one review record.")
    args = parser.parse_args(argv)

    print("Peak Phase 68 — internal review decision on the R2 evidence reference")
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
