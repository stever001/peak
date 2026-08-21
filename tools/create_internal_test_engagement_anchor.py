#!/usr/bin/env python3
"""Phase 59 — create the **one** durable internal test engagement anchor.

A narrow operator utility, not a general-purpose record creator. It holds a single hard-coded
packet describing Peak's first durable ``internal_test`` engagement anchor and hands it to the
existing Phase 54/56 controlled writer,
:func:`peak.db.engagement_authorization_anchor_writer.persist_engagement_authorization_anchor`.
It builds no other packet, accepts no record fields from the caller, and can express no other
record.

**Why the packet is hard-coded.** An operator tool that accepted ``--client-id`` /
``--category`` / ``--label`` would be a generic ``engagements`` writer wearing a phase name, and
``engagements`` is a root/identity table that stays on ``PROHIBITED_TABLES`` precisely so no such
thing exists. The one anchor this phase authorises is therefore a constant, reviewable in the
diff, and the only record this file can ever produce.

**Dry-run by default.** With no flag (or ``--dry-run``) it runs the writer's own pre-DB governance
gate and stops **before any connection is opened**. Only ``--execute`` proceeds to the writer.

**Durable, not disposable.** This is an internal/admin record retained on purpose — for
development, live testing, training, and demonstration. It is not a smoke record: the runtime
credential holds ``SELECT`` + ``INSERT`` and no ``DELETE``, so it cannot be cleaned up afterwards
and is not meant to be. Disposable production smoke records remain disallowed.

**Classification is the control, not the id.** ``engagement_category=internal_test``,
``real_client_data=false``, and ``client_accessible=false`` are real columns and are what read
isolation filters on. The reserved ``client_id`` is a *visible marker* on top of that, never the
control by itself.

**Credential boundary.** The runtime session is resolved by the normal runtime path
(:func:`peak.db.session.create_session_factory`), which reads ``PEAK_RUNTIME_DATABASE_URL`` and
**only** that variable. This file reads no environment variable itself, imports no Alembic or
migration code, issues no raw SQL, and has no ``UPDATE`` / ``DELETE`` / cleanup / stamp path. The
only statements it can cause are the writer's own single-primary-key ``SELECT``, one ``INSERT``,
and the read-back of the row it created.

**Output hygiene.** It prints the writer's typed receipt fields only: governed identifiers, closed
vocabulary status labels, and booleans. Never a DSN, environment value, credential, grant, SQL
string, stack trace, or the ``engagement_label`` — a label can carry a client organisation name,
so the writer never echoes it and neither does this tool.

Exit status:
  0  -> dry-run validated, or the anchor was created, or an exact idempotent replay
  1  -> denied, failed, or the outcome is uncertain (including an idempotency conflict)
"""

from __future__ import annotations

import argparse
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# --------------------------------------------------------------------------- the one packet

#: The single authorized anchor. Every field is a constant: this tool creates this record or none.
#: ``status`` / ``lifecycle_status`` are the minimal valid values for a durable, active internal
#: test anchor; ``review_status`` is server-stamped and must be declared as ``needs_review``.
ANCHOR = {
    "owner_id": "peak_internal_admin",
    "client_id": "99999",                       # reserved internal-test namespace (a marker)
    "engagement_id": "internal_test_001",
    "authorization_scope": "internal_peak_only",
    "engagement_label": "Internal Test Engagement 001",
    "status": "active",
    "review_status": "needs_review",
    "lifecycle_status": "active",
    "engagement_category": "internal_test",     # the actual control
    "real_client_data": False,                  # the actual control
    "client_accessible": False,                 # the actual control
    "capsule_publication_authorized": True,     # permitted only by the compound rule below
}

REQUESTED_BY = "peak_internal_admin"
REQUESTER_ROLE = "peak_internal_admin"
#: Deterministic and specific to this anchor — never random per run, so a re-run replays the same
#: key rather than minting a second identity.
IDEMPOTENCY_KEY = "phase59_internal_test_anchor_001"
SOURCE_PHASE = "phase59"

#: Receipt fields worth printing. All are governed identifiers, closed-vocabulary labels, or
#: booleans. ``engagement_label`` is deliberately absent.
RECEIPT_FIELDS = (
    "outcome", "permitted", "reason_code", "target_table", "target_action",
    "stored_record_id", "idempotency_key", "audit_trace_ref",
    "database_connection_made", "sql_execution_made", "database_write_made",
    "stored_record_created", "existing_record_returned", "transaction_committed",
    "outcome_uncertain",
    "authorization_scope", "engagement_status", "review_status", "lifecycle_status",
    "engagement_category", "real_client_data", "client_accessible",
    "capsule_publication_authorized",
    "other_table_write_made", "client_record_write_made", "update_made", "delete_made",
    "review_approval_made", "client_facing_output_created", "financial_verification_made",
    "capsule_publication_made", "agentnet_publication_made", "agent_execution_made",
    "llm_call_made", "agentnet_call_made", "resolver_call_made", "network_call_made",
    "created_at", "database_write_at",
)

SUCCESS_OUTCOMES = ("created", "idempotent_replay")


def build_request():
    """Build the one controlled write request. Opens no connection and reads no environment."""
    from peak.db.engagement_authorization_anchor_writer import (
        build_engagement_anchor_controlled_write_request,
    )
    from peak.db.writer_contracts import EngagementAuthorizationAnchorDraft

    draft = EngagementAuthorizationAnchorDraft(**ANCHOR)
    return build_engagement_anchor_controlled_write_request(
        draft,
        requested_by=REQUESTED_BY,
        requester_role=REQUESTER_ROLE,
        idempotency_key=IDEMPOTENCY_KEY,
        source_phase=SOURCE_PHASE,
    )


def emit_packet() -> None:
    """Print the packet's governed fields — never the label."""
    print("Authorized packet (label withheld: a label can carry a client organisation name)")
    for key in ("owner_id", "client_id", "engagement_id", "authorization_scope", "status",
                "review_status", "lifecycle_status", "engagement_category", "real_client_data",
                "client_accessible", "capsule_publication_authorized"):
        print(f"  {key:<32}: {ANCHOR[key]}")
    print(f"  {'requested_by':<32}: {REQUESTED_BY}")
    print(f"  {'requester_role':<32}: {REQUESTER_ROLE}")
    print(f"  {'idempotency_key':<32}: {IDEMPOTENCY_KEY}")
    print(f"  {'source_phase':<32}: {SOURCE_PHASE}")
    print(f"  {'engagement_label':<32}: <withheld>")


def emit_receipt(receipt) -> None:
    print("\nReceipt (typed fields only; no DSN, environment value, SQL, or label)")
    for field in RECEIPT_FIELDS:
        if hasattr(receipt, field):
            print(f"  {field:<32}: {getattr(receipt, field)}")
    for line in getattr(receipt, "reasons", []) or []:
        print(f"  reason  : {line}")
    for line in getattr(receipt, "warnings", []) or []:
        print(f"  warning : {line}")


def dry_run(request) -> int:
    """Run the writer's own pre-DB gate. Stops before any connection is opened."""
    from peak.db.engagement_authorization_anchor_writer import (
        _fingerprint_from_request, _pre_db_validate,
    )

    denial, draft = _pre_db_validate(request)
    if denial is not None:
        print("\n[denied] the packet did not pass the writer's pre-DB governance gate")
        emit_receipt(denial)
        print("\nRESULT: DRY-RUN DENIED (no connection opened, nothing written)")
        return 1

    print("\n[ok] packet passes the writer's own pre-DB governance gate")
    print(f"  anchor fingerprint              : {_fingerprint_from_request(request, draft)}")
    print("  database_connection_made        : False")
    print("  sql_execution_made              : False")
    print("  database_write_made             : False")
    print("\nRESULT: DRY-RUN PASS (nothing was written; re-run with --execute to create it)")
    return 0


def execute(request) -> int:
    """Hand the request to the controlled writer. One anchor, or none."""
    from peak.db.engagement_authorization_anchor_writer import (
        persist_engagement_authorization_anchor,
    )

    receipt = persist_engagement_authorization_anchor(request)
    emit_receipt(receipt)

    outcome = getattr(receipt, "outcome", None)
    if outcome == "created":
        print("\nRESULT: CREATED (exactly one internal_test engagement anchor)")
        return 0
    if outcome == "idempotent_replay":
        print("\nRESULT: IDEMPOTENT REPLAY (the anchor already existed with an identical "
              "definition; nothing was written or modified)")
        return 0
    if getattr(receipt, "reason_code", None) == "idempotency_conflict":
        print("\nRESULT: IDEMPOTENCY CONFLICT — an anchor with this engagement_id already exists "
              "with a different governed definition. It was NOT modified. Stop and review; do "
              "not delete or alter it.")
        return 1
    print(f"\nRESULT: NOT CREATED ({outcome})")
    return 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Create the one durable internal_test engagement anchor via the Phase 54/56 "
                    "controlled writer. Dry-run unless --execute is passed. The packet is "
                    "hard-coded; no record field can be supplied on the command line.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true",
                       help="Validate the packet and stop before opening a connection (default).")
    group.add_argument("--execute", action="store_true",
                       help="Invoke the controlled writer. Creates at most one anchor row.")
    args = parser.parse_args(argv)

    print("Peak Phase 59 — durable internal test engagement anchor")
    print("=" * 70)
    emit_packet()

    request = build_request()
    if not args.execute:
        return dry_run(request)

    print("\n[execute] invoking the controlled anchor writer "
          "(runtime credential, SELECT + INSERT only)")
    return execute(request)


if __name__ == "__main__":
    raise SystemExit(main())
