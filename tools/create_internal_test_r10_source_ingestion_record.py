#!/usr/bin/env python3
"""Phase 72 — register the internal test **R10 measured location model answer set** artifact as
**exactly one** source ingestion record.

A narrow operator utility, not a general-purpose record creator and not a packet importer. The
single packet is a fixed constant: owner, client, engagement, scope, idempotency key, packet
reference, schema, source type, and logical location reference are all hard-coded. No flag can
retarget another engagement, change a posture, add a second packet, or re-express R1, R2, or R8.

**Why a Phase 72 utility rather than a flag on an earlier one.** The Phase 63, 65, and 69 tools
each state as their safety property that they can express exactly the records they were written for
and that no flag can retarget them. Parameterising any of them to accept a substitute packet would
delete that property from a tool that has already written production rows. This file leaves all
three untouched and states the same property for its own single packet.

**What R10 is for.** R9 defines the location question set; **R10 supplies the measured answer set**.
Phase 71 fixed a fifteen-item checklist of measured answers required before R1 can support a
location-dimension ``evidence_reference``, and R10 is the artifact that records those answers —
including the negative, unknown, and blocked ones.

**What R10 is not.** R10 is an answer-state record, not an export. It carries no quantity, no item
value, and no location identifier, so it cannot support any count, rate, or total. It does not
validate any inventory quantity, does not create an inventory accuracy conclusion, does not lift
R1's provisional location marking, does not confirm R8's authority precedence, and does not resolve
R5's WMS scope. Registration is collection, not review: **R10 must be reviewed before it may be
cited in an ``evidence_reference``**, and it does not make R1 evidence-ready by itself.

**Metadata only — the artifact body never enters the database or this process's output.** The file
is opened in binary solely to compute its length and SHA-256. Its bytes are never decoded, printed,
logged, or placed on a draft. The writer independently refuses any draft carrying a
``packet_payload`` / ``raw_packet_content`` / ``raw_content`` / ``payload`` or secret-named
attribute, so the metadata-only rule is enforced on both sides.

**The artifact must be real and must live outside the repository.** A row pointing at a nonexistent
packet would be dishonest, so this tool refuses to run when the artifact is missing or empty. It
refuses any path inside the repository working tree and any path other than the one approved
artifact path, so an artifact body can never be committed by way of this tool.

**The answer set must keep its unfavourable answers.** An answer set that quietly dropped the
questions that came back negative would be worse than no answer set, because it would look like
readiness. That property lives in the artifact and is asserted by the Phase 72 harness; this tool
registers the artifact by hash, so any later softening of it would change the hash and be refused as
an idempotency conflict rather than silently replacing the registered answers.

**Dry-run by default.** With no flag (or ``--dry-run``) it hashes the artifact, runs the writer's
own pre-DB governance gate on the packet, and stops **before any connection is opened**. Only
``--execute`` proceeds to the writer.

**Credential boundary.** The runtime session is resolved by the normal runtime path
(:func:`peak.db.session.create_session_factory`), which reads ``PEAK_RUNTIME_DATABASE_URL`` and
**only** that variable. This file reads no environment variable itself, imports no Alembic or
migration code, issues no raw SQL, and has no ``UPDATE`` / ``DELETE`` / cleanup / stamp path. The
only statements it can cause are the writer's stored-engagement load, its idempotency lookup, one
``INSERT``, and the read-back.

Exit status:
  0  -> dry-run validated the packet, or the record was created / exactly replayed
  1  -> the packet was denied, failed, or ended uncertain (including an idempotency conflict)
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
SOURCE_PHASE = "phase72"

PACKET_SCHEMA_NAME = "engagement_packet"
PACKET_SCHEMA_VERSION = "v0"
# `packet_source_type` is a free-form metadata descriptor on the draft — the repository enforces no
# closed vocabulary for it. `internal_test_export` is the value Phase 63 and Phase 65 already used
# for internal-test artifacts, so it is reused here rather than inventing a parallel term.
PACKET_SOURCE_TYPE = "internal_test_export"

#: The approved external artifact directory. Nothing outside it is accepted.
APPROVED_ARTIFACT_DIR = os.path.join(
    os.path.expanduser("~"), ".peak", "peak-internal-test-artifacts", "phase72")

ARTIFACT_NAME = "r10_location_model_answer_set_v1.json"

IDEMPOTENCY_KEY = "phase72_internal_test_source_ingestion_r10_001"
PACKET_REFERENCE_ID = "pkt_internal_test_r10_location_model_answer_set_001"

#: Logical reference stored in the DB — never a filesystem path, so the stored row leaks no
#: operator home directory or machine layout.
PACKET_LOCATION_REFERENCE = "internal-test-artifact://phase72/r10-location-model-answer-set-v1"

PACKET_KEY = "R10"
PACKET_TITLE = "R10 measured location model answer set"

#: Provenance and posture notes. Descriptors only — never artifact content.
REASONS = (
    "source_ingestion: R10 measured location model answer set",
    "plan: PHASE71_R1_R9_EVIDENCE_READINESS_PLAN recommends R10 as the next collection step",
    "responds_to: the R9 location/bin naming model question set (ing_64b2e2648ac1402b), reviewed "
    "in phase70",
    "rationale: R9 defines the questions and R10 supplies the measured answers; R10 is collected "
    "to support future R1 location-dimension evidence-readiness work",
    "structure: all 15 Phase 71 checklist items are answered with an explicit answer state; none "
    "was dropped, merged or softened",
    "structure: answer states used are answered_yes, answered_no, partial, unknown, not_measured, "
    "blocked_by_r8 and blocked_by_r5",
    "negative_answers_retained: 11 of 15 items resolve to a negative, unknown or blocked state, "
    "and those answers are recorded rather than omitted",
    "measurement_basis: measured against the registered R1, R2 and R9 artifact descriptions only; "
    "no live ERP, WMS, production or client system exists to measure against in this "
    "internal_test engagement",
    "headline_finding: on the thresholds fixed in advance in phase71, R1's location dimension is "
    "not currently readable and is not reliable enough for location-attributed evidence",
    "headline_finding: R10 does not make R1 readable - it records that R1 is not yet readable and "
    "names the follow-up each unresolved item requires",
    "scope_note: answer-state and concept level only; carries no location identifiers, bin codes, "
    "aisle names, rack names, warehouse names, site names, item values, quantities or row-like "
    "export data",
    "does_not_validate: R10 does not validate any inventory quantity or location-level total",
    "does_not_validate: R10 does not create an inventory accuracy conclusion and must not be "
    "presented as one",
    "provisional: R10 does not lift R1's provisional location marking and does not make R1 "
    "evidence-ready by itself; that requires R10 review and then a separately created and "
    "reviewed evidence reference",
    "unconfirmed: R10 does not confirm R8 authority precedence; the items depending on it are "
    "recorded as blocked_by_r8 and R8 remains needs_review / draft / authoritative=false",
    "unconfirmed: R10 does not resolve R5 WMS scope; the items depending on it are recorded as "
    "blocked_by_r5",
    "review_required: R10 must be reviewed before it may be cited in an evidence_reference",
    "taxonomy: 04_location_structure, 11_evidence_availability, 09_data_exports_and_reporting",
    "provenance: authored by Peak for internal pipeline testing; not a client-supplied export",
    "posture: internal_test engagement; no real client data; not client-facing",
    "content_rule: metadata only; artifact body stored outside the repository and outside the DB",
    "not_authorized: evidence characterization, report drafting, capsule candidacy, publication",
    "next_step: an R10 source-ingestion review decision, as a separately approved phase",
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


def approved_path() -> str:
    return os.path.join(APPROVED_ARTIFACT_DIR, ARTIFACT_NAME)


def resolve_artifact_path(candidate) -> str:
    """Return the approved artifact path, or raise ``SystemExit``.

    Refuses anything inside the repository working tree and anything other than the one approved
    artifact. Only the *path* is ever reported, never file content.
    """
    path = os.path.realpath(os.path.expanduser(candidate or approved_path()))
    repo = os.path.realpath(REPO_ROOT)
    expected = os.path.realpath(approved_path())

    if path == repo or path.startswith(repo + os.sep):
        raise SystemExit("[refused] the artifact path is inside the repository working tree; "
                         "internal test artifact bodies must never live in the repo")
    if path != expected:
        shown = os.path.join("~", ".peak", "peak-internal-test-artifacts", "phase72",
                             ARTIFACT_NAME)
        raise SystemExit(f"[refused] the artifact path is not the approved Phase 72 "
                         f"{PACKET_KEY} artifact ({shown})")
    if not os.path.isfile(path):
        raise SystemExit(f"[refused] the approved {PACKET_KEY} artifact does not exist. A source "
                         "ingestion row must never point at a nonexistent packet; create the "
                         "artifact first, then re-run.")
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
        raise SystemExit(f"[refused] the approved {PACKET_KEY} artifact is empty; nothing to "
                         "register")
    return length, digest.hexdigest()


# --------------------------------------------------------------------------- the single request


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
        packet_reference_id=PACKET_REFERENCE_ID,  # persisted as source_reference_id
        packet_schema_name=PACKET_SCHEMA_NAME,
        packet_schema_version=PACKET_SCHEMA_VERSION,
        packet_source_type=PACKET_SOURCE_TYPE,
        packet_location_reference=PACKET_LOCATION_REFERENCE,  # logical, never a path
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
    print(f"\n{PACKET_KEY} — {PACKET_TITLE}")
    print("-" * 70)
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
        print(f"\n[denied] the {PACKET_KEY} packet did not pass the writer's pre-DB governance "
              "gate")
        emit_receipt(denial)
        return 1

    print(f"\n[ok] the {PACKET_KEY} packet passes the writer's own pre-DB governance gate")
    print(f"  payload fingerprint                   : {_payload_fingerprint(request, draft)}")
    print("  database_connection_made              : False")
    print("  sql_execution_made                    : False")
    print("  database_write_made                   : False")
    return 0


def execute(request) -> int:
    from peak.db.source_ingestion_writer import persist_source_ingestion_record

    receipt = persist_source_ingestion_record(request)
    emit_receipt(receipt)

    outcome = getattr(receipt, "outcome", None)
    if outcome == "created":
        print(f"\nRESULT: CREATED (one {PACKET_KEY} source ingestion record; metadata only)")
        return 0
    if outcome == "idempotent_replay":
        print(f"\nRESULT: IDEMPOTENT REPLAY (an identical {PACKET_KEY} record already existed; "
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
        description=f"Register the one approved Phase 72 artifact ({PACKET_TITLE}) as a single "
                    f"source ingestion record under engagement {ENGAGEMENT_ID}, via the Phase 24 "
                    "controlled writer. Metadata only. Dry-run unless --execute is passed. "
                    "Identity and packet fields are hard-coded; no flag can retarget them.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true",
                      help="Validate the packet and stop before opening a connection (default).")
    mode.add_argument("--execute", action="store_true",
                      help="Invoke the controlled writer. Creates at most one record.")
    parser.add_argument("--artifact-path", default=None,
                        help="Path to the approved R10 artifact (defaults to the approved path). "
                             "Paths inside the repository, and any path other than the approved "
                             "R10 artifact, are refused.")
    args = parser.parse_args(argv)

    print(f"Peak Phase 72 — internal test {PACKET_KEY} source ingestion record "
          "(measured location model answer set)")
    print("=" * 70)

    path = resolve_artifact_path(args.artifact_path)
    length, packet_hash = artifact_metadata(path)
    emit_packet(path, length, packet_hash)

    request = build_request(packet_hash)

    if not args.execute:
        code = dry_run(request)
        print("\n  note: the stored-engagement authorization check runs at write time and needs a")
        print("        connection, so it is NOT exercised by this dry-run.")
        if code:
            print("\nRESULT: DRY-RUN DENIED (no connection opened, nothing written)")
            return 1
        print("\nRESULT: DRY-RUN PASS (nothing was written; re-run with --execute to create it)")
        return 0

    print("\n[execute] invoking the controlled source ingestion writer for the single packet "
          "(runtime credential, SELECT + INSERT only)")
    print("-" * 70)
    return execute(request)


if __name__ == "__main__":
    raise SystemExit(main())
