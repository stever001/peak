#!/usr/bin/env python3
"""Phase 90 — create the one durable **lab** internal-test engagement authorization anchor.

The lab counterpart to the Phase 59 production tool, and the first Peak writer invocation ever
made against ``peak_lab``. It creates **exactly one** ``engagements`` row through the existing
Phase 54/56 controlled anchor writer, or none.

**Why a lab anchor is needed at all.** Every other controlled writer loads the stored
``Engagement`` row at write time and requires its request scope to match. A lab rehearsal of the
source-ingestion, evidence, or review writers therefore has nothing to hang records from until an
anchor exists in the lab. Phase 89 deliberately refused the anchor writer; Phase 90 is the explicit
reviewed change that admits it, for bootstrap only.

**The gate is a precondition here, not a report.** Before any write this tool evaluates the lab
writer enablement gate and refuses unless it returns ``anchor_bootstrap_authorized``. That requires
``PEAK_WRITER_TARGET=lab``, ``PEAK_LAB_WRITER_ENABLEMENT_CONFIRM=1``,
``PEAK_LAB_ENGAGEMENT_ANCHOR_BOOTSTRAP_CONFIRM=1``, a ``PEAK_LAB_WRITER_TARGET_URL`` whose schema
is exactly ``peak_lab`` under the approved lab runtime role, and the anchor as the **only**
requested target. A production target is refused on every path.

**Durable, not disposable.** This record is retained on purpose. ``peak_lab_runtime`` holds
``SELECT`` + ``INSERT`` and no ``DELETE``, so it cannot be cleaned up afterwards and is not meant
to be. There is no cleanup path in this file and none is planned: a correction means a new
engagement id, never a rewrite of this one.

**Classification is the control, not the id.** ``engagement_category=internal_test``,
``real_client_data=false`` and ``client_accessible=false`` are real columns and are what read
isolation filters on. The reserved ``client_id`` is a visible marker on top of that, never the
control by itself.

**Credential boundary.** The session is resolved by the normal runtime path
(:func:`peak.db.session.create_session_factory`), which reads ``PEAK_RUNTIME_DATABASE_URL`` and
only that variable. This file opens no credential file, issues no raw SQL, imports no Alembic or
migration code, and has no ``UPDATE`` / ``DELETE`` / cleanup / stamp path. The only statements it
can cause are the writer's own single-primary-key ``SELECT``, one ``INSERT``, and the read-back of
the row it created.

**Output hygiene.** Typed receipt fields only — governed identifiers, closed-vocabulary status
labels, and booleans. Never a DSN, environment value, credential, grant, SQL string, stack trace,
or the ``engagement_label``, since a label can carry a client organisation name.

Exit status:
  0  -> dry-run validated, or the anchor was created, or an exact idempotent replay
  1  -> denied, failed, or the outcome is uncertain (including an idempotency conflict)
  3  -> refused before any write: the lab anchor-bootstrap gate did not authorize
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# --------------------------------------------------------------------------- the one packet

#: The single authorized lab anchor. Every field is a constant: this tool creates this record or
#: none. No record field can be supplied on the command line.
ANCHOR = {
    "owner_id": "peak_internal_admin",
    "client_id": "99999",                        # reserved internal-test namespace (a marker)
    "engagement_id": "lab_internal_test_001",
    # `authorization_scope` is a CLOSED vocabulary (peak.db.enums.AuthorizationScope) that the
    # writer re-checks at its own boundary. "internal_peak_lab_only" is not a member and was
    # refused with reason_code=invalid_authorization_scope before any connection was opened, so
    # the canonical member is used instead. Lab-ness is carried by the database, the engagement
    # id, and the classification columns — not by inventing a scope value, which would be an
    # enum/schema change and a governance change of its own.
    "authorization_scope": "internal_peak_only",
    "engagement_label": "Lab Internal Test Engagement 001",
    "status": "active",
    "review_status": "needs_review",
    "lifecycle_status": "active",
    "engagement_category": "internal_test",      # the actual control
    "real_client_data": False,                   # the actual control
    "client_accessible": False,                  # the actual control
    # Phase 59's production anchor set this true; the lab anchor does not need publication
    # authority and does not claim it. Strictly more conservative, and permitted by the rule.
    "capsule_publication_authorized": False,
}

REQUESTED_BY = "peak_internal_admin"
REQUESTER_ROLE = "peak_internal_admin"

#: Deterministic and specific to this anchor — never random per run, so a re-run replays the same
#: key rather than minting a second identity.
IDEMPOTENCY_KEY = "phase90_lab_internal_test_engagement_anchor_001"
SOURCE_PHASE = "phase90"

#: The one target this tool may ever request.
ANCHOR_TARGET = "engagements/create_engagement_authorization_anchor"

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


def _load_lab_gate():
    """Load the lab writer enablement gate by path — the same module `make` exercises."""
    path = os.path.join(REPO_ROOT, "tools", "lab_writer_enablement_decision_gate.py")
    spec = importlib.util.spec_from_file_location("_peak_lab_writer_gate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def gate_allows_anchor_bootstrap() -> tuple:
    """Return ``(allowed, reason, outcome)`` from the lab gate. Prints no connection value."""
    gate = _load_lab_gate()
    decision = gate.evaluate(os.environ)
    allowed = (decision["anchor_bootstrap_authorized"] is True
               and decision["lab_write_authorized"] is True
               and decision["outcome"] == gate.OUTCOME_ANCHOR_BOOTSTRAP
               and decision["authorized_writer_targets"] == [ANCHOR_TARGET]
               and decision["safe_to_write_production_now"] is False
               and gate.is_consistent(decision))
    return allowed, decision["reason"], decision["outcome"]


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
    print("Authorized lab packet (label withheld: a label can carry a client organisation name)")
    for key in ("owner_id", "client_id", "engagement_id", "authorization_scope", "status",
                "review_status", "lifecycle_status", "engagement_category", "real_client_data",
                "client_accessible", "capsule_publication_authorized"):
        print(f"  {key:<32}: {ANCHOR[key]}")
    print(f"  {'idempotency_key':<32}: {IDEMPOTENCY_KEY}")
    print(f"  {'source_phase':<32}: {SOURCE_PHASE}")
    print(f"  {'target':<32}: {ANCHOR_TARGET}")


def emit_receipt(receipt) -> None:
    print("\nReceipt (typed fields only; no DSN, environment value, SQL, or label)")
    for field in RECEIPT_FIELDS:
        if hasattr(receipt, field):
            print(f"  {field:<36}: {getattr(receipt, field)}")


def dry_run(request) -> int:
    """Validate the packet without opening a connection."""
    from peak.persistence.governance import (
        evaluate_engagement_anchor_creation_request,
    )
    emit_packet()
    decision = evaluate_engagement_anchor_creation_request(request)
    permitted = getattr(decision, "permitted", None)
    print("\nGovernance pre-check (no connection opened)")
    print(f"  permitted                           : {permitted}")
    reasons = list(getattr(decision, "reasons", []) or [])
    print(f"  reasons                             : {len(reasons)}")
    for r in reasons:
        print(f"      - {r}")
    if permitted:
        print("\nRESULT: DRY-RUN OK (nothing was written; pass --execute to create the anchor)")
        return 0
    print("\nRESULT: DRY-RUN DENIED")
    return 1


def execute(request) -> int:
    """Hand the request to the controlled writer. One anchor, or none."""
    from peak.db.engagement_authorization_anchor_writer import (
        persist_engagement_authorization_anchor,
    )

    receipt = persist_engagement_authorization_anchor(request)
    emit_receipt(receipt)

    outcome = getattr(receipt, "outcome", None)
    if outcome == "created":
        print("\nRESULT: CREATED (exactly one internal_test engagement anchor in the lab)")
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
        description="Create the one durable lab internal_test engagement anchor via the Phase "
                    "54/56 controlled writer, gated on the Phase 90 lab anchor-bootstrap "
                    "decision. Dry-run unless --execute is passed. The packet is hard-coded; no "
                    "record field can be supplied on the command line.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true",
                       help="Validate the packet and the gate; open no connection (default).")
    group.add_argument("--execute", action="store_true",
                       help="Create the anchor. Requires the lab anchor-bootstrap gate to pass.")
    args = parser.parse_args(argv)

    print("Peak lab internal-test engagement anchor — one record, or none")
    print("=" * 72)

    allowed, reason, outcome = gate_allows_anchor_bootstrap()
    print(f"Lab anchor-bootstrap gate: outcome={outcome} reason={reason}")
    if not allowed:
        print("\nRESULT: REFUSED (the lab anchor-bootstrap gate did not authorize this write)")
        print("No connection was opened and nothing was written.")
        return 3
    print("Gate authorized the anchor bootstrap. Production write enablement remains false.")

    request = build_request()
    if args.execute:
        emit_packet()
        return execute(request)
    return dry_run(request)


if __name__ == "__main__":
    raise SystemExit(main())
