#!/usr/bin/env python3
"""Phase 65 — register the **two** internal test R2 and R1 source artifacts as source ingestion
records, **R2 first, then R1**.

A narrow operator utility, not a general-purpose record creator and not a packet importer. Both
packets are fixed constants: owner, client, engagement, scope, idempotency key, packet reference,
schema, source type, and logical location reference are all hard-coded. No flag can retarget
another engagement, change a posture, add a third packet, or reorder the two.

**Why a Phase 65 utility rather than a flag on the Phase 63 one.** The Phase 63 tool
(``tools/create_internal_test_source_ingestion_record.py``) states as its safety property that it
can express exactly one record and that no flag can retarget it. Parameterising it to accept two
different packets would delete that property from the tool that already wrote a production row.
This file leaves Phase 63 untouched and states the same property for its own fixed pair.

**Why R2 before R1.** Phase 64 (docs/PHASE64_INTERNAL_TEST_R1_R7_SOURCE_ARTIFACT_COLLECTION_PLAN.md)
recorded that R2 is the only request the Phase 63 R8 map shows as unblocked, and that R1 is not
interpretable without it: R1's item identifiers cannot be assessed for duplication or
unit-of-measure consistency without the item master. Registering R2 first also means a partial
Phase 65 still lands the unblocked artifact. The order is structural, not cosmetic — it is fixed in
``PACKETS`` and there is no flag to change it.

**R1's location dimension is provisional.** R8 flags the location/bin naming model as unconfirmed,
and per-location quantity is exactly what R1 supplies. That limitation is recorded in R1's
provenance notes at registration time rather than discovered later at evidence time.

**Metadata only — neither artifact body enters the database or this process's output.** Each file is
opened in binary solely to compute its length and SHA-256. Its bytes are never decoded, printed,
logged, or placed on a draft. The writer independently refuses any draft carrying a
``packet_payload`` / ``raw_packet_content`` / ``raw_content`` / ``payload`` or secret-named
attribute, so the metadata-only rule is enforced on both sides.

**Both artifacts must be real and must live outside the repository.** A row pointing at a
nonexistent packet would be dishonest, so this tool refuses to run when either artifact is missing
or empty. It refuses any path inside the repository working tree and any path other than the two
approved artifact paths, so an artifact body can never be committed by way of this tool.

**Dry-run by default.** With no flag (or ``--dry-run``) it hashes both artifacts, runs the writer's
own pre-DB governance gate on both packets, and stops **before any connection is opened**. Only
``--execute`` proceeds to the writer.

**Partial-failure rule.** The two writes are sequential and independent. If R2 does not succeed,
R1 is **not attempted** and the partial state is reported. If R2 succeeds and R1 fails, the tool
stops and reports the partial state; it never deletes, never retries with changed packet data, and
never touches the row it already created.

**Credential boundary.** The runtime session is resolved by the normal runtime path
(:func:`peak.db.session.create_session_factory`), which reads ``PEAK_RUNTIME_DATABASE_URL`` and
**only** that variable. This file reads no environment variable itself, imports no Alembic or
migration code, issues no raw SQL, and has no ``UPDATE`` / ``DELETE`` / cleanup / stamp path. The
only statements it can cause are, per packet, the writer's stored-engagement load, its idempotency
lookup, one ``INSERT``, and the read-back.

Exit status:
  0  -> dry-run validated both packets, or both records were created / exactly replayed
  1  -> any packet was denied, failed, or ended uncertain (including an idempotency conflict)
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

#: The Phase 59 engagement anchor — the stored authorization subject both writes are made under.
ENGAGEMENT_ID = "internal_test_001"
CLIENT_ID = "99999"                       # reserved internal-test namespace (a visible marker)
OWNER_ID = "peak_internal_admin"
AUTHORIZATION_SCOPE = "internal_peak_only"

REQUESTED_BY = "peak_internal_admin"
REQUESTER_ROLE = "internal_admin"
SOURCE_PHASE = "phase65"

PACKET_SCHEMA_NAME = "engagement_packet"
PACKET_SCHEMA_VERSION = "v0"
PACKET_SOURCE_TYPE = "internal_test_export"

#: The approved external artifact directory. Nothing outside it is accepted.
APPROVED_ARTIFACT_DIR = os.path.join(
    os.path.expanduser("~"), ".peak", "peak-internal-test-artifacts", "phase65")

#: Provenance notes shared by both packets. Descriptors only — never artifact content.
COMMON_REASONS = (
    "provenance: authored by Peak for internal pipeline testing; not a client-supplied export",
    "posture: internal_test engagement; no real client data; not client-facing",
    "content_rule: metadata only; artifact body stored outside the repository and outside the DB",
    "not_authorized: evidence characterization, report drafting, capsule candidacy, publication",
    "upstream: R8 system-of-record map (phase63) remains needs_review / draft / authoritative=false",
)

#: The two authorized packets, in the **only** order this tool will process them: R2, then R1.
#: This tuple is the whole expressible surface of the utility — there is no third entry and no
#: flag that appends one.
PACKETS = (
    {
        "key": "R2",
        "title": "R2 SKU / item master export",
        "artifact_name": "r2_sku_item_master_export_v1.json",
        "idempotency_key": "phase65_internal_test_source_ingestion_r2_001",
        "packet_reference_id": "pkt_internal_test_r2_sku_item_master_001",
        # Logical reference stored in the DB — never a filesystem path, so the stored row leaks
        # no operator home directory or machine layout.
        "packet_location_reference":
            "internal-test-artifact://phase65/r2-sku-item-master-export-v1",
        "reasons": (
            "source_ingestion: R2 SKU/item master export",
            "plan: PHASE64_INTERNAL_TEST_R1_R7_SOURCE_ARTIFACT_COLLECTION_PLAN R2",
            "rationale: R2 is the only request the R8 map shows as unblocked, so it is "
            "registered first",
            "rationale: R2 is the interpretive key for R1 - identifier, unit-of-measure and "
            "item-status posture come from the item master",
            "taxonomy: 03_item_sku_master, 09_data_exports_and_reporting, "
            "12_ai_agentnet_readiness",
            "scope_note: describes the export shape and field-level posture; carries no item "
            "values, descriptions or quantities",
            "open_question: unit-of-measure vocabulary, item-status vocabulary and duplicate "
            "normalization rule all remain unconfirmed and must be measured, not assumed",
        ),
    },
    {
        "key": "R1",
        "title": "R1 current inventory export by SKU and location",
        "artifact_name": "r1_current_inventory_sku_location_v1.json",
        "idempotency_key": "phase65_internal_test_source_ingestion_r1_001",
        "packet_reference_id": "pkt_internal_test_r1_inventory_sku_location_001",
        "packet_location_reference":
            "internal-test-artifact://phase65/r1-current-inventory-sku-location-v1",
        "reasons": (
            "source_ingestion: R1 current inventory export by SKU and location",
            "plan: PHASE64_INTERNAL_TEST_R1_R7_SOURCE_ARTIFACT_COLLECTION_PLAN R1",
            "rationale: registered after R2 because the inventory export is interpretable only "
            "once the item master is registered",
            "provisional: the location dimension is provisional - the R8 location/bin naming "
            "model is unconfirmed and per-location quantity is what R1 supplies",
            "provisional: any future evidence from R1 must carry degraded reliability for "
            "location-attributed claims until the location model is confirmed; SKU-level claims "
            "are not similarly limited",
            "unconfirmed: the R8 location/WMS posture and authority precedence rule remain "
            "unconfirmed, so no R1 measure may yet be attributed to a system of record",
            "dependency: R2 item master (pkt_internal_test_r2_sku_item_master_001) is required to "
            "interpret item identifiers, unit of measure and item status",
            "unblocker: R9 location/bin naming model remains uncollected and is the natural "
            "follow-on request",
            "taxonomy: 03_item_sku_master, 04_location_structure, 07_stockouts_and_overstocks, "
            "09_data_exports_and_reporting",
            "scope_note: describes the export shape and field-level posture; carries no item "
            "values, quantities or location identifiers",
        ),
    },
)

RECEIPT_FIELDS = (
    "outcome", "permitted", "reason_code", "target_table", "target_action",
    "stored_record_id", "idempotency_key", "audit_trace_ref",
    "database_connection_made", "sql_execution_made", "database_write_made",
    "stored_record_created", "existing_record_returned", "transaction_committed",
    "outcome_uncertain", "review_status", "output_status",
    "created_at", "database_write_at",
)

OK_OUTCOMES = ("created", "idempotent_replay")


# --------------------------------------------------------------------------- artifact handling


def approved_path(packet) -> str:
    return os.path.join(APPROVED_ARTIFACT_DIR, packet["artifact_name"])


def resolve_artifact_path(packet, candidate) -> str:
    """Return the approved artifact path for ``packet``, or raise ``SystemExit``.

    Refuses anything inside the repository working tree and anything other than this packet's own
    approved artifact. Only the *path* is ever reported, never file content.
    """
    path = os.path.realpath(os.path.expanduser(candidate or approved_path(packet)))
    repo = os.path.realpath(REPO_ROOT)
    expected = os.path.realpath(approved_path(packet))

    if path == repo or path.startswith(repo + os.sep):
        raise SystemExit("[refused] the artifact path is inside the repository working tree; "
                         "internal test artifact bodies must never live in the repo")
    if path != expected:
        shown = os.path.join("~", ".peak", "peak-internal-test-artifacts", "phase65",
                             packet["artifact_name"])
        raise SystemExit(f"[refused] the artifact path is not the approved Phase 65 "
                         f"{packet['key']} artifact ({shown})")
    if not os.path.isfile(path):
        raise SystemExit(f"[refused] the approved {packet['key']} artifact does not exist. A "
                         "source ingestion row must never point at a nonexistent packet; create "
                         "the artifact first, then re-run.")
    return path


def artifact_metadata(packet, path: str) -> "tuple[int, str]":
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
        raise SystemExit(f"[refused] the approved {packet['key']} artifact is empty; nothing to "
                         "register")
    return length, digest.hexdigest()


# --------------------------------------------------------------------------- the two requests


def build_request(packet, packet_hash: str):
    """Build one controlled write request. Opens no connection and reads no environment."""
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
        packet_reference_id=packet["packet_reference_id"],  # persisted as source_reference_id
        packet_schema_name=PACKET_SCHEMA_NAME,
        packet_schema_version=PACKET_SCHEMA_VERSION,
        packet_source_type=PACKET_SOURCE_TYPE,
        packet_location_reference=packet["packet_location_reference"],  # logical, never a path
        packet_hash=packet_hash,
        output_status="draft",
        review_status="needs_review",
        lifecycle_status="active",
        authoritative=False,
        client_facing_approved=False,
        capsule_candidate_ready=False,
        reasons=list(packet["reasons"]) + list(COMMON_REASONS),
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
        idempotency_key=packet["idempotency_key"],
    )


# --------------------------------------------------------------------------- output


def emit_packet(packet, position: int, path: str, length: int, packet_hash: str) -> None:
    print(f"\n[{position}/{len(PACKETS)}] {packet['key']} — {packet['title']}")
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
        ("packet_reference_id", packet["packet_reference_id"]),
        ("packet_schema_name", PACKET_SCHEMA_NAME),
        ("packet_schema_version", PACKET_SCHEMA_VERSION),
        ("packet_source_type", PACKET_SOURCE_TYPE),
        ("packet_location_reference (stored)", packet["packet_location_reference"]),
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
        ("idempotency_key", packet["idempotency_key"]),
        ("source_phase", SOURCE_PHASE),
    ):
        print(f"  {key:<38}: {val}")
    reasons = list(packet["reasons"]) + list(COMMON_REASONS)
    print(f"  {'provenance notes (reasons)':<38}: {len(reasons)} entries")
    for line in reasons:
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


def dry_run_one(packet, request) -> int:
    from peak.db.source_ingestion_writer import _payload_fingerprint, _pre_db_validate

    denial, draft = _pre_db_validate(request, None)
    if denial is not None:
        print(f"\n[denied] the {packet['key']} packet did not pass the writer's pre-DB "
              "governance gate")
        emit_receipt(denial)
        return 1

    print(f"\n[ok] the {packet['key']} packet passes the writer's own pre-DB governance gate")
    print(f"  payload fingerprint                   : {_payload_fingerprint(request, draft)}")
    print("  database_connection_made              : False")
    print("  sql_execution_made                    : False")
    print("  database_write_made                   : False")
    return 0


def execute_one(packet, request) -> "tuple[int, str]":
    """Run the writer for one packet. Returns ``(exit_code, outcome_label)``."""
    from peak.db.source_ingestion_writer import persist_source_ingestion_record

    receipt = persist_source_ingestion_record(request)
    emit_receipt(receipt)

    outcome = getattr(receipt, "outcome", None)
    if outcome == "created":
        print(f"\n  {packet['key']} RESULT: CREATED (one source ingestion record; metadata only)")
        return 0, "created"
    if outcome == "idempotent_replay":
        print(f"\n  {packet['key']} RESULT: IDEMPOTENT REPLAY (an identical record already "
              "existed; nothing was written or modified)")
        return 0, "idempotent_replay"
    if getattr(receipt, "reason_code", None) == "idempotency_conflict":
        print(f"\n  {packet['key']} RESULT: IDEMPOTENCY CONFLICT — this idempotency key already "
              "exists with a different payload. The existing record was NOT modified. Stop and "
              "review; do not delete or alter it.")
        return 1, "idempotency_conflict"
    print(f"\n  {packet['key']} RESULT: NOT CREATED ({outcome})")
    return 1, str(outcome)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Register the two approved Phase 65 artifacts (R2 SKU/item master, then R1 "
                    f"current inventory by SKU/location) as source ingestion records under "
                    f"engagement {ENGAGEMENT_ID}, via the Phase 24 controlled writer. Metadata "
                    "only. R2 is always processed first. Dry-run unless --execute is passed. "
                    "Identity, order, and packet fields are hard-coded.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true",
                      help="Validate both packets and stop before opening a connection (default).")
    mode.add_argument("--execute", action="store_true",
                      help="Invoke the controlled writer. Creates at most two records, R2 first.")
    parser.add_argument("--r2-artifact-path", default=None,
                        help="Path to the approved R2 artifact (defaults to the approved path). "
                             "Paths inside the repository, and any path other than the approved "
                             "R2 artifact, are refused.")
    parser.add_argument("--r1-artifact-path", default=None,
                        help="Path to the approved R1 artifact (defaults to the approved path). "
                             "Paths inside the repository, and any path other than the approved "
                             "R1 artifact, are refused.")
    args = parser.parse_args(argv)

    print("Peak Phase 65 — internal test R2 and R1 source ingestion records (R2 first, then R1)")
    print("=" * 70)

    overrides = {"R2": args.r2_artifact_path, "R1": args.r1_artifact_path}

    # Resolve and hash BOTH artifacts before any write, so a missing or unapproved second
    # artifact cannot be discovered only after the first row already exists.
    prepared = []
    for packet in PACKETS:
        path = resolve_artifact_path(packet, overrides[packet["key"]])
        length, packet_hash = artifact_metadata(packet, path)
        prepared.append((packet, path, length, packet_hash))

    for position, (packet, path, length, packet_hash) in enumerate(prepared, start=1):
        emit_packet(packet, position, path, length, packet_hash)

    requests = [(packet, build_request(packet, packet_hash))
                for packet, _path, _length, packet_hash in prepared]

    if not args.execute:
        failed = 0
        for packet, request in requests:
            failed |= dry_run_one(packet, request)
        print("\n  note: the stored-engagement authorization check runs at write time and needs a")
        print("        connection, so it is NOT exercised by this dry-run.")
        if failed:
            print("\nRESULT: DRY-RUN DENIED (no connection opened, nothing written)")
            return 1
        print("\nRESULT: DRY-RUN PASS (nothing was written; re-run with --execute to create them)")
        return 0

    print("\n[execute] invoking the controlled source ingestion writer for each packet in order "
          "(runtime credential, SELECT + INSERT only)")

    outcomes = []
    for position, (packet, request) in enumerate(requests, start=1):
        print(f"\n[{position}/{len(requests)}] writing {packet['key']}")
        print("-" * 70)
        code, label = execute_one(packet, request)
        outcomes.append((packet["key"], label))
        if code != 0:
            # Partial-failure rule: stop here. Never delete, never retry with changed packet data,
            # never touch a row already created.
            print("\n" + "=" * 70)
            print("RESULT: STOPPED — PARTIAL STATE")
            for key, lab in outcomes:
                print(f"  {key:<4}: {lab}")
            for key, _pkt in [(p["key"], p) for p in PACKETS][len(outcomes):]:
                print(f"  {key:<4}: not attempted")
            print("\n  Any record already created was NOT modified or removed. Do not delete, do "
                  "not clean up, and do not re-run with changed packet data. Report and review.")
            return 1

    print("\n" + "=" * 70)
    print("RESULT: BOTH PACKETS REGISTERED (metadata only; R2 processed before R1)")
    for key, label in outcomes:
        print(f"  {key:<4}: {label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
