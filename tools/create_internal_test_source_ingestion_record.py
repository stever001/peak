#!/usr/bin/env python3
"""Phase 63 — register the **one** internal test R8 source artifact as a source ingestion record.

A narrow operator utility, not a general-purpose record creator and not a packet importer. The
engagement, client, owner, scope, idempotency key, and packet reference are all constants; no flag
can retarget another engagement, change the posture, or create a second record.

**Why ``source_ingestion_records`` is the right writer.** Phase 62
(docs/PHASE62_INTERNAL_TEST_SOURCE_EVIDENCE_REQUEST_PLAN.md) concluded that
``peak/db/source_ingestion_writer.py`` is the only writer-backed, allowlisted path that *registers
an inbound artifact against an engagement*, and that it is metadata-only by contract. That is
exactly the claim R8 needs: **this artifact exists and is registered under this engagement** — with
no claim about its contents, no reliability rating, and no evidence characterization.
``evidence_references`` deliberately comes later: its columns assert ``evidence_status``,
``reliability``, and characterization that presuppose a registered source.

**Why R8 first.** Phase 62 ranked the system-of-record and data-export map ahead of R1–R7 because
it determines whether the other requests are fulfillable at all.

**Metadata only — the artifact body never enters the database or this process's output.** The file
is read in binary solely to compute its length and SHA-256. Its bytes are never decoded, printed,
logged, or placed on the draft. The writer independently refuses any draft carrying a
``packet_payload`` / ``raw_packet_content`` / ``raw_content`` / ``payload`` or secret-named
attribute, so the metadata-only rule is enforced on both sides.

**The artifact must be real and must live outside the repository.** Phase 62 recorded that writing
a row pointing at a nonexistent packet would be dishonest, so this tool refuses to run when the
artifact is missing. It also refuses any path inside the repository working tree and any path
outside the approved internal-test artifact directory, so an artifact body can never be committed
by way of this tool.

**Dry-run by default.** With no flag (or ``--dry-run``) it hashes the artifact, runs the writer's
own pre-DB governance gate, and stops **before any connection is opened**. Only ``--execute``
proceeds to the writer.

**Credential boundary.** The runtime session is resolved by the normal runtime path
(:func:`peak.db.session.create_session_factory`), which reads ``PEAK_RUNTIME_DATABASE_URL`` and
**only** that variable. This file reads no environment variable itself, imports no Alembic or
migration code, issues no raw SQL, and has no ``UPDATE`` / ``DELETE`` / cleanup / stamp path. The
only statements it can cause are the writer's own stored-engagement load, its idempotency lookup,
one ``INSERT``, and the read-back.

Exit status:
  0  -> dry-run validated, or the record was created, or an exact idempotent replay
  1  -> denied, failed, or the outcome is uncertain (including an idempotency conflict)
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# --------------------------------------------------------------------------- fixed identity

#: The Phase 59 engagement anchor — the stored authorization subject this write is made under.
ENGAGEMENT_ID = "internal_test_001"
CLIENT_ID = "99999"                       # reserved internal-test namespace (a visible marker)
OWNER_ID = "peak_internal_admin"
AUTHORIZATION_SCOPE = "internal_peak_only"

REQUESTED_BY = "peak_internal_admin"
REQUESTER_ROLE = "internal_admin"
IDEMPOTENCY_KEY = "phase63_internal_test_source_ingestion_r8_001"
SOURCE_PHASE = "phase63"

#: Packet metadata. ``PACKET_LOCATION_REFERENCE`` is a **logical** reference stored in the DB —
#: never a filesystem path, so the stored row leaks no operator home directory or machine layout.
PACKET_REFERENCE_ID = "pkt_internal_test_r8_system_record_map_001"
PACKET_SCHEMA_NAME = "engagement_packet"
PACKET_SCHEMA_VERSION = "v0"
PACKET_SOURCE_TYPE = "internal_test_export"
PACKET_LOCATION_REFERENCE = (
    "internal-test-artifact://phase63/r8-system-of-record-data-export-map-v1"
)

#: The approved external artifact directory. Nothing outside it is accepted.
APPROVED_ARTIFACT_DIR = os.path.join(
    os.path.expanduser("~"), ".peak", "peak-internal-test-artifacts", "phase63")
APPROVED_ARTIFACT_NAME = "r8_system_of_record_data_export_map_v1.json"
DEFAULT_ARTIFACT_PATH = os.path.join(APPROVED_ARTIFACT_DIR, APPROVED_ARTIFACT_NAME)

#: Sanitized provenance notes carried on the draft. Descriptors only — never artifact content.
REASONS = (
    "source_ingestion: R8 system-of-record and data-export map",
    "plan: PHASE62_INTERNAL_TEST_SOURCE_EVIDENCE_REQUEST_PLAN R8",
    "rationale: R8 precedes R1-R7 because it determines whether they are fulfillable",
    "taxonomy: 08_systems_of_record, 09_data_exports_and_reporting, "
    "11_evidence_availability, 12_ai_agentnet_readiness",
    "provenance: authored by Peak for internal pipeline testing; not a client-supplied export",
    "posture: internal_test engagement; no real client data; not client-facing",
    "content_rule: metadata only; artifact body stored outside the repository and outside the DB",
    "not_authorized: evidence characterization, report drafting, capsule candidacy, publication",
)

RECEIPT_FIELDS = (
    "outcome", "permitted", "reason_code", "target_table", "target_action",
    "stored_record_id", "idempotency_key", "audit_trace_ref",
    "database_connection_made", "sql_execution_made", "database_write_made",
    "stored_record_created", "existing_record_returned", "transaction_committed",
    "outcome_uncertain", "review_status", "output_status",
    "created_at", "database_write_at",
)


# --------------------------------------------------------------------------- artifact handling


def resolve_artifact_path(candidate) -> str:
    """Return the approved artifact path, or raise ``SystemExit`` with a sanitized reason.

    Refuses anything inside the repository working tree and anything outside the approved
    internal-test artifact directory. Only the *path* is ever reported, never file content.
    """
    path = os.path.realpath(os.path.expanduser(candidate or DEFAULT_ARTIFACT_PATH))
    repo = os.path.realpath(REPO_ROOT)
    approved_dir = os.path.realpath(APPROVED_ARTIFACT_DIR)

    if path == repo or path.startswith(repo + os.sep):
        raise SystemExit("[refused] the artifact path is inside the repository working tree; "
                         "internal test artifact bodies must never live in the repo")
    if path != os.path.join(approved_dir, APPROVED_ARTIFACT_NAME):
        raise SystemExit("[refused] the artifact path is not the approved Phase 63 R8 artifact "
                         f"({os.path.join('~', '.peak', 'peak-internal-test-artifacts', 'phase63', APPROVED_ARTIFACT_NAME)})")
    if not os.path.isfile(path):
        raise SystemExit("[refused] the approved R8 artifact does not exist. Phase 62 recorded "
                         "that a source ingestion row must never point at a nonexistent packet; "
                         "create the artifact first, then re-run.")
    return path


def artifact_metadata(path: str) -> "tuple[int, str]":
    """Return ``(byte_length, sha256_hex)``. The bytes are hashed, never decoded or printed."""
    digest = hashlib.sha256()
    length = 0
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(65536)
            if not chunk:
                break
            length += len(chunk)
            digest.update(chunk)
    if length == 0:
        raise SystemExit("[refused] the approved R8 artifact is empty; nothing to register")
    return length, digest.hexdigest()


# --------------------------------------------------------------------------- the one request


def build_request(packet_hash: str):
    """Build the one controlled write request. Opens no connection and reads no environment."""
    from peak.db.writer_contracts import (
        SOURCE_INGESTION_TARGET_ACTION, SOURCE_INGESTION_TARGET_TABLE,
    )
    from peak.ingestion.contracts import SourceIngestionDraft
    from peak.persistence.contracts import ControlledWriteRequest, ControlledWriteSubject

    draft = SourceIngestionDraft(
        # source_ingestion_record_id and created_at stay None — the writer assigns both.
        owner_id=OWNER_ID,
        client_id=CLIENT_ID,
        engagement_id=ENGAGEMENT_ID,
        packet_reference_id=PACKET_REFERENCE_ID,   # persisted as source_reference_id
        packet_schema_name=PACKET_SCHEMA_NAME,
        packet_schema_version=PACKET_SCHEMA_VERSION,
        packet_source_type=PACKET_SOURCE_TYPE,
        packet_location_reference=PACKET_LOCATION_REFERENCE,  # logical, never a filesystem path
        packet_hash=packet_hash,
        output_status="draft",
        review_status="needs_review",
        lifecycle_status="active",
        authoritative=False,
        client_facing_approved=False,
        capsule_candidate_ready=False,
        reasons=list(REASONS),
    )
    return ControlledWriteRequest(
        owner_id=OWNER_ID,
        client_id=CLIENT_ID,
        engagement_id=ENGAGEMENT_ID,
        requested_by=REQUESTED_BY,
        requester_role=REQUESTER_ROLE,
        authorization_scope=AUTHORIZATION_SCOPE,
        target_table=SOURCE_INGESTION_TARGET_TABLE,
        requested_action=SOURCE_INGESTION_TARGET_ACTION,
        # The authorization anchor is the engagement, and only ever the engagement.
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


# --------------------------------------------------------------------------- output


def emit_packet(path: str, length: int, packet_hash: str) -> None:
    print("Authorized packet (metadata only; the artifact body is never read into memory as text,")
    print("printed, logged, or stored in the database)")
    for key, val in (
        ("engagement_id (authorization anchor)", ENGAGEMENT_ID),
        ("client_id", CLIENT_ID),
        ("owner_id", OWNER_ID),
        ("authorization_scope", AUTHORIZATION_SCOPE),
        ("target_table", "source_ingestion_records"),
        ("target_action", "create_source_ingestion_record"),
        ("packet_reference_id", PACKET_REFERENCE_ID),
        ("packet_schema_name", PACKET_SCHEMA_NAME),
        ("packet_schema_version", PACKET_SCHEMA_VERSION),
        ("packet_source_type", PACKET_SOURCE_TYPE),
        ("packet_location_reference (stored)", PACKET_LOCATION_REFERENCE),
        ("packet_hash (sha256)", packet_hash),
        ("artifact bytes", length),
        ("artifact path (NOT stored in DB)", path.replace(os.path.expanduser("~"), "~")),
        ("output_status", "draft"),
        ("review_status", "needs_review"),
        ("lifecycle_status", "active"),
        ("authoritative", False),
        ("client_facing_approved", False),
        ("capsule_candidate_ready", False),
        ("requested_by", REQUESTED_BY),
        ("requester_role", REQUESTER_ROLE),
        ("idempotency_key", IDEMPOTENCY_KEY),
        ("source_phase", SOURCE_PHASE),
    ):
        print(f"  {key:<38}: {val}")
    print(f"  {'provenance notes (reasons)':<38}: {len(REASONS)} entries")
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


# --------------------------------------------------------------------------- modes


def dry_run(request) -> int:
    from peak.db.source_ingestion_writer import _payload_fingerprint, _pre_db_validate

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
    from peak.db.source_ingestion_writer import persist_source_ingestion_record

    receipt = persist_source_ingestion_record(request)
    emit_receipt(receipt)

    outcome = getattr(receipt, "outcome", None)
    if outcome == "created":
        print("\nRESULT: CREATED (exactly one source ingestion record; metadata only)")
        return 0
    if outcome == "idempotent_replay":
        print("\nRESULT: IDEMPOTENT REPLAY (an identical record already existed; nothing was "
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
        description=f"Register the approved Phase 63 R8 artifact as one source ingestion record "
                    f"under engagement {ENGAGEMENT_ID}, via the Phase 24 controlled writer. "
                    "Metadata only. Dry-run unless --execute is passed. Identity is hard-coded.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true",
                      help="Validate the packet and stop before opening a connection (default).")
    mode.add_argument("--execute", action="store_true",
                      help="Invoke the controlled writer. Creates at most one record.")
    parser.add_argument("--artifact-path", default=None,
                        help="Path to the approved R8 artifact (defaults to the approved path). "
                             "Paths inside the repository, and any path other than the approved "
                             "artifact, are refused.")
    args = parser.parse_args(argv)

    print("Peak Phase 63 — first internal test source ingestion record (R8)")
    print("=" * 70)

    path = resolve_artifact_path(args.artifact_path)
    length, packet_hash = artifact_metadata(path)
    emit_packet(path, length, packet_hash)

    request = build_request(packet_hash)
    if not args.execute:
        return dry_run(request)

    print("\n[execute] invoking the controlled source ingestion writer "
          "(runtime credential, SELECT + INSERT only)")
    return execute(request)


if __name__ == "__main__":
    raise SystemExit(main())
