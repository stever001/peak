#!/usr/bin/env python3
"""Phase 67 — create the **one** evidence reference for the approved R2 source-ingestion chain.

A narrow operator utility, not a general-purpose record creator. Every field is a constant; there
is no flag that can change the evidenced source, the engagement, the claim, or the posture. In
particular there is **no flag that can retarget R1, R8, the intake note, or the intake review** —
the evidenced source is a module constant, none of those record ids appears anywhere in this file,
and the argument parser exposes only the run mode.

**Why the existing Phase 21 evidence writer, and why no field is overloaded.**
``peak/db/evidence_writer.py`` is the only writer for ``evidence_references``, the table this phase
is authorized to write, and its Phase 18 draft has an honest slot for every part of this narrow
claim:

* ``evidence_type='document'`` and ``source_type='document'`` — the R2 artifact is a field-level
  export *description* document. ``system_export`` would have been the overload: it would assert an
  export of rows exists, and the artifact carries none. ``document`` is the schema-valid value that
  states exactly what was collected (schemas/evidence-reference.schema.json).
* ``source_reference_id`` — the registered packet reference, the field's exact declared meaning.
* ``source_location`` — a *pointer* to where this evidence originated, which is the field's declared
  meaning in ``EvidenceSourceReference``. Here it is a logical in-Peak locator for the R2 source
  ingestion record, in the same logical-URI style Phase 65 used for packet locations.
* ``observed_condition`` and ``normalized_summary`` — free descriptive text, carrying the claim, the
  supporting review record, and every limit in the record's own words.
* ``operational_area='back_office'`` and ``inventory_process_area='inventory_control'`` — both are
  values the repository's own deterministic vocabularies derive for a system/item-master artifact
  (``peak/workers/evidence_normalization.py``).
* ``confidence_level='low'`` — the cautious end of the schema's ``low|medium|high`` reliability
  vocabulary, matching a source whose upstream map is itself unreviewed.

Three contract limits are worth stating plainly rather than working around. The model has **no
typed related-object column** (the Phase 9 schema has ``related_object_ids``; the table does not),
so the supporting review record is named in the record's descriptive text rather than a join
column. The writer does not expose ``evidence_status``, so the row takes the model default
``collected`` — honest here, since the artifact *was* collected, and the review gate is carried on
the real ``review_status`` / ``output_status`` columns instead. And the writer does not persist
``draft.reasons``, so the limits live in ``normalized_summary`` and ``observed_condition``, which
*are* persisted. None of these required a field to be used against its meaning, and **no new writer
was added**.

**What this evidence reference means.** The R2 item-master artifact is available and registered, and
is suitable for a future item-master **data-readiness** review. That is the whole claim.

**What it deliberately does not do.** It does not support an inventory accuracy conclusion (R2
describes an item master, not measured on-hand quantity); it does not rely on R1 location claims,
whose location dimension stays provisional pending R9; it does not treat R8 as authoritative (R8
remains ``needs_review`` / ``draft`` / ``authoritative=false``); R3-R7 remain deferred; and it
authorizes no report drafting, no capsule candidacy, no client-facing output, and no AgentNet
resolver publication. ``evidence_references`` has no ``authoritative`` column to set false — the
prohibition is structural instead, and stronger: the writer *refuses* a draft that claims
``authoritative``, ``client_facing_approved``, or ``capsule_candidate_ready``, and server-stamps
``review_status='needs_review'`` and ``output_status='draft'`` itself. The limits are additionally
written into the stored summary so the row states them in its own text.

**Sanitized content only.** The stored text carries structural counts, posture flags, named gaps,
and record ids. It carries **no artifact body text, no field values, no item or SKU values, no
quantities, and no location identifiers**. The R2 artifact body stays outside the repository and is
**never read, printed, or stored by this tool**: this file opens no artifact and computes no hash.

**Dry-run by default.** With no flag (or ``--dry-run``) it runs the writer's own pre-DB governance
gate and stops **before any connection is opened**. Only ``--execute`` proceeds to the writer.

**Credential boundary.** The runtime session is resolved by the normal runtime path
(:func:`peak.db.session.create_session_factory`), which reads ``PEAK_RUNTIME_DATABASE_URL`` and
**only** that variable. This file reads no environment variable itself, imports no migration code,
issues no raw SQL, and has no ``UPDATE`` / ``DELETE`` / cleanup / stamp path. The only statements it
can cause are the writer's own stored-engagement load, its idempotency lookup, one ``INSERT``, and
the read-back.

Exit status:
  0  -> dry-run validated, or the evidence reference was created, or an exact idempotent replay
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

#: The Phase 59 engagement anchor — the authorization subject this evidence is written under.
ENGAGEMENT_ID = "internal_test_001"
CLIENT_ID = "99999"                       # reserved internal-test namespace (a visible marker)
OWNER_ID = "peak_internal_admin"
AUTHORIZATION_SCOPE = "internal_peak_only"

#: The Phase 65 R2 source ingestion record — the evidenced source. A constant, deliberately: no
#: flag can point this at R1, R8, or any other record, and no other record id is named in this file
#: except the Phase 66 review that authorized this narrow evidence reference.
SOURCE_INGESTION_RECORD_ID = "ing_884c94df03c34908"
#: The registered packet reference, carried on ``draft.source_reference_id``.
SOURCE_REFERENCE_ID = "pkt_internal_test_r2_sku_item_master_001"
#: A logical in-Peak locator for the evidenced source registration (never a filesystem path).
SOURCE_LOCATION = "peak-record://source_ingestion_records/" + SOURCE_INGESTION_RECORD_ID
#: The Phase 66 internal review decision that approved R2 for exactly this narrow evidence scope.
SUPPORTING_REVIEW_RECORD_ID = "rev_bf7f18a13d8f461c"

CAPTURED_BY = "peak_internal_admin"
REQUESTER_ROLE = "internal_admin"
IDEMPOTENCY_KEY = "phase67_internal_test_r2_evidence_reference_001"
SOURCE_PHASE = "phase67"

#: Schema-valid vocabulary (schemas/evidence-reference.schema.json). ``document`` states what was
#: actually collected: a field-level export *description*, not an export of rows.
EVIDENCE_TYPE = "document"
SOURCE_TYPE = "document"
#: The cautious end of the schema's low|medium|high reliability vocabulary.
CONFIDENCE_LEVEL = "low"
#: Both derived from the repository's own deterministic area vocabularies for a system/item-master
#: artifact (peak/workers/evidence_normalization.py).
OPERATIONAL_AREA = "back_office"
INVENTORY_PROCESS_AREA = "inventory_control"

NORMALIZED_TITLE = (
    "[internal_test] R2 item-master source availability and data readiness"
)

#: The condition observed. Sanitized: structural counts, posture flags, named gaps, and record ids
#: only — no artifact body text, no field values, no item/SKU values, no quantities, no locations.
OBSERVED_CONDITION = (
    "The R2 SKU / item master source artifact is available and registered in Peak as source "
    f"ingestion record {SOURCE_INGESTION_RECORD_ID}, under packet reference "
    f"{SOURCE_REFERENCE_ID}, and was internally approved for this narrow evidence scope by review "
    f"record {SUPPORTING_REVIEW_RECORD_ID} (approve_internal, authoritative=false). Its "
    "field-level structure is sufficient to proceed to an item-master data-readiness review: 10 "
    "described fields, 6 required and 4 optional, each carrying an explicit interpretation note "
    "and a named risk. It is an export description, not an export, and carries no rows."
)

#: The stored summary. Carries the claim and every limit, because evidence_references persists no
#: reasons list — the limits must live in a column that is actually written.
NORMALIZED_SUMMARY = (
    "EVIDENCE SCOPE - item-master source availability and data readiness only. "
    "The R2 SKU / item master source artifact is available and registered as source ingestion "
    f"record {SOURCE_INGESTION_RECORD_ID} (packet {SOURCE_REFERENCE_ID}), and is suitable for a "
    "future item-master data-readiness review. Internal approval for exactly this scope is "
    f"recorded on review record {SUPPORTING_REVIEW_RECORD_ID}. "
    "READINESS - the artifact describes 10 item-master fields, 6 required and 4 optional, each "
    "with an interpretation note and a named risk; the join key to the inventory export is the "
    "item identifier. "
    "OPEN QUESTIONS - the artifact is a field-level export description, not an export, and carries "
    "no rows; unit-of-measure posture is unconfirmed; item-status posture is unconfirmed; 6 "
    "duplicate and normalization risks remain review topics; whether the inventory export draws "
    "item identifiers from the same identifier domain is unconfirmed and must be checked at "
    "reconciliation time. "
    "LIMITS - this evidence reference does NOT support an inventory accuracy conclusion, because "
    "R2 describes an item master and not measured on-hand quantity. It does NOT rely on R1 "
    "location claims; R1's location dimension remains provisional pending R9, the location and "
    "bin naming model. It does NOT treat R8 as authoritative; R8 remains needs_review / draft / "
    "authoritative=false with an unconfirmed authority precedence rule, so no measure may yet be "
    "attributed to a system of record. R3-R7 remain deferred behind their unresolved R8 blockers. "
    "NOT AUTHORIZED - report drafting, capsule candidacy, client-facing output, and AgentNet "
    "resolver publication. The public resolver is live, which is why that gate stays shut rather "
    "than relaxed. "
    "POSTURE - internal_test engagement, no real client data, not client-facing, not capsule-ready, "
    "not authoritative, needs_review, internal_peak_only. "
    "CONTENT RULE - this record stores structural counts, posture flags, named gaps, and record "
    "ids only. No artifact body text, field values, item or SKU values, quantities, or location "
    "identifiers are stored here or anywhere in Peak."
)

RECEIPT_FIELDS = (
    "outcome", "permitted", "reason_code", "target_table", "target_action",
    "stored_record_id", "idempotency_key", "audit_trace_ref",
    "database_connection_made", "sql_execution_made", "database_write_made",
    "stored_record_created", "existing_record_returned", "transaction_committed",
    "outcome_uncertain", "review_status", "output_status",
    "created_at", "database_write_at",
)


def build_request():
    """Build the one controlled write request. Opens no connection and reads no environment."""
    from peak.db.writer_contracts import EVIDENCE_TARGET_ACTION, EVIDENCE_TARGET_TABLE
    from peak.evidence.persistence_contracts import EvidencePersistenceDraft
    from peak.persistence.contracts import ControlledWriteRequest, ControlledWriteSubject

    draft = EvidencePersistenceDraft(
        owner_id=OWNER_ID,
        client_id=CLIENT_ID,
        engagement_id=ENGAGEMENT_ID,
        source_reference_id=SOURCE_REFERENCE_ID,
        evidence_type=EVIDENCE_TYPE,
        normalized_title=NORMALIZED_TITLE,
        normalized_summary=NORMALIZED_SUMMARY,
        observed_condition=OBSERVED_CONDITION,
        operational_area=OPERATIONAL_AREA,
        inventory_process_area=INVENTORY_PROCESS_AREA,
        source_type=SOURCE_TYPE,
        source_location=SOURCE_LOCATION,
        confidence_level=CONFIDENCE_LEVEL,
        # Review-gated posture. The writer refuses any draft that claims otherwise.
        output_status="draft",
        review_status="needs_review",
        lifecycle_status="active",
        authoritative=False,
        client_facing_approved=False,
        capsule_candidate_ready=False,
    )
    return ControlledWriteRequest(
        owner_id=OWNER_ID,
        client_id=CLIENT_ID,
        engagement_id=ENGAGEMENT_ID,
        requested_by=CAPTURED_BY,
        requester_role=REQUESTER_ROLE,
        authorization_scope=AUTHORIZATION_SCOPE,
        target_table=EVIDENCE_TARGET_TABLE,
        requested_action=EVIDENCE_TARGET_ACTION,
        # The authorization anchor is the engagement, never the evidenced source record.
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
    print("Authorized packet (sanitized; the R2 artifact body is never read or printed)")
    for key, val in (("engagement_id (authorization anchor)", ENGAGEMENT_ID),
                     ("client_id", CLIENT_ID), ("owner_id", OWNER_ID),
                     ("authorization_scope", AUTHORIZATION_SCOPE),
                     ("evidenced source ingestion record", SOURCE_INGESTION_RECORD_ID),
                     ("source_reference_id (packet)", SOURCE_REFERENCE_ID),
                     ("source_location (logical locator)", SOURCE_LOCATION),
                     ("supporting review record", SUPPORTING_REVIEW_RECORD_ID),
                     ("evidence_type", EVIDENCE_TYPE), ("source_type", SOURCE_TYPE),
                     ("confidence_level -> reliability", CONFIDENCE_LEVEL),
                     ("operational_area", OPERATIONAL_AREA),
                     ("inventory_process_area", INVENTORY_PROCESS_AREA),
                     ("review_status", "needs_review"), ("output_status", "draft"),
                     ("lifecycle_status", "active"),
                     ("evidence_status", "collected (model default; writer sets none)"),
                     ("authoritative", "no such column - structurally impossible"),
                     ("client_facing_approved", False), ("capsule_candidate_ready", False),
                     ("captured_by / requested_by", CAPTURED_BY),
                     ("requester_role", REQUESTER_ROLE),
                     ("idempotency_key", IDEMPOTENCY_KEY), ("source_phase", SOURCE_PHASE)):
        print(f"  {key:<38}: {val}")
    print(f"  {'normalized_title':<38}: {NORMALIZED_TITLE}")
    print(f"  {'observed_condition':<38}: {len(OBSERVED_CONDITION)} chars, sanitized")
    print(f"  {'normalized_summary':<38}: {len(NORMALIZED_SUMMARY)} chars, sanitized")


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
    from peak.db.evidence_writer import _payload_fingerprint, _pre_db_validate

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
    from peak.db.evidence_writer import persist_evidence_reference

    receipt = persist_evidence_reference(request)
    emit_receipt(receipt)

    outcome = getattr(receipt, "outcome", None)
    if outcome == "created":
        print("\nRESULT: CREATED (exactly one evidence reference for the R2 source-ingestion "
              "chain, scoped to item-master source availability / data readiness)")
        return 0
    if outcome == "idempotent_replay":
        print("\nRESULT: IDEMPOTENT REPLAY (an identical evidence reference already existed; "
              "nothing was written or modified)")
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
        description=f"Create the one evidence reference for R2 source ingestion record "
                    f"{SOURCE_INGESTION_RECORD_ID} under engagement {ENGAGEMENT_ID}, via the "
                    "Phase 21 controlled evidence writer. Scoped to item-master source "
                    "availability / data readiness only - it supports no inventory accuracy "
                    "conclusion and authorizes no report, capsule, client-facing, or AgentNet "
                    "publication. Dry-run unless --execute is passed. Every field is hard-coded.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true",
                      help="Validate the packet and stop before opening a connection (default).")
    mode.add_argument("--execute", action="store_true",
                      help="Invoke the controlled writer. Creates at most one evidence reference.")
    args = parser.parse_args(argv)

    print("Peak Phase 67 — the first internal test evidence reference (R2 source availability)")
    print("=" * 70)
    emit_packet()

    request = build_request()
    if not args.execute:
        return dry_run(request)

    print("\n[execute] invoking the controlled evidence writer "
          "(runtime credential, SELECT + INSERT only)")
    return execute(request)


if __name__ == "__main__":
    raise SystemExit(main())
