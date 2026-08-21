#!/usr/bin/env python3
"""Phase 60 — create the **one** durable internal test intake note.

A narrow operator utility, not a general-purpose record creator. Every identity and control field
is hard-coded to the Phase 59 internal test anchor; the only caller-supplied value is the note body,
and that is read from an **untracked file outside the repository** (or stdin) on purpose.

**Why the note body is never in this file.** ``peak/db/intake_note_writer.py`` states the rule
plainly: intake notes persist authorized operational prose, and that prose is acceptable **only in
the managed DB — never in Git, fixtures, examples, sample packets, logs, receipts, or test data**.
Hard-coding a realistic note body here would commit exactly the kind of record text the writer
exists to keep out of source control, so the body is loaded at runtime and this file holds none of
it. What *is* hard-coded is the identity and posture: the anchor it attaches to, the reserved
client namespace, the scope, and the idempotency key.

**It can target one engagement and no other.** ``engagement_id`` is the constant
``internal_test_001`` and ``client_id`` the reserved ``99999``. There is no flag to point it
elsewhere, and no flag to supply a different owner, scope, or classification.

**Dry-run by default.** With no flag (or ``--dry-run``) it runs the writer's own pre-DB governance
gate and stops **before any connection is opened**. Only ``--execute`` proceeds to the writer.

**Replay is fingerprint-bound.** The writer's payload fingerprint includes a SHA-256 of the note
body, so replaying with the *same* body is an idempotent success that writes nothing, and replaying
with a *changed* body is an ``idempotency_conflict`` denial that stops and modifies nothing. Keep
the note file if a later replay is ever intended.

**Credential boundary.** The runtime session is resolved by the normal runtime path
(:func:`peak.db.session.create_session_factory`), which reads ``PEAK_RUNTIME_DATABASE_URL`` and
**only** that variable. This file reads no environment variable itself, imports no Alembic or
migration code, issues no raw SQL, and has no ``UPDATE`` / ``DELETE`` / cleanup / stamp path. The
only statements it can cause are the writer's own stored-engagement load, its idempotency lookup,
one ``INSERT``, and the read-back.

**Output hygiene.** It prints the writer's typed receipt fields only — governed identifiers, closed
vocabulary labels, and booleans. **Never the note body**, never a body excerpt, never a DSN,
environment value, credential, grant, SQL string, or stack trace. Only the body's length and
SHA-256 are reported, so a run is auditable without reproducing its content.

Exit status:
  0  -> dry-run validated, or the note was created, or an exact idempotent replay
  1  -> denied, failed, or the outcome is uncertain (including an idempotency conflict)
  2  -> no note body was supplied
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

#: Identity and posture. Constants: this tool attaches a note to that anchor, or to nothing.
ENGAGEMENT_ID = "internal_test_001"
CLIENT_ID = "99999"                       # reserved internal-test namespace (a visible marker)
OWNER_ID = "peak_internal_admin"
AUTHORIZATION_SCOPE = "internal_peak_only"
REQUESTED_BY = "peak_internal_admin"
REQUESTER_ROLE = "internal_admin"
IDEMPOTENCY_KEY = "phase60_internal_test_intake_note_001"
SOURCE_PHASE = "phase60"

NOTE_TYPE = "walkaround"
NOTE_SOURCE = "internal_test"
CAPTURED_BY = "peak_internal_admin"
CAPTURED_ROLE = "internal_admin"
#: A posture statement, not note content — it carries no operational detail about any operation.
NOTE_SUMMARY = "Internal test intake note. Internal test data only; no real client data."

#: Default location for the runtime note body: outside the repository, never tracked.
DEFAULT_NOTE_FILE = os.path.join(os.path.expanduser("~"), ".peak",
                                 "phase60_internal_test_intake_note.txt")

RECEIPT_FIELDS = (
    "outcome", "permitted", "reason_code", "target_table", "target_action",
    "stored_record_id", "idempotency_key", "audit_trace_ref",
    "database_connection_made", "sql_execution_made", "database_write_made",
    "stored_record_created", "existing_record_returned", "transaction_committed",
    "outcome_uncertain",
    "note_type", "note_source", "review_status", "lifecycle_status",
    "client_facing_approved", "financial_verified", "capsule_candidate_ready",
    "publication_allowed", "execution_allowed", "requires_human_review",
    "other_table_write_made", "client_record_write_made", "engagement_record_write_made",
    "update_made", "delete_made", "review_approval_made", "review_record_created",
    "client_facing_output_created", "financial_verification_made",
    "capsule_publication_made", "agentnet_publication_made", "agent_execution_made",
    "agent_run_record_created", "llm_call_made", "agentnet_call_made", "resolver_call_made",
    "network_call_made", "created_at", "database_write_at",
)


def load_note_body(path, use_stdin: bool):
    """Read the note body from an untracked file or stdin. Never returns repo content."""
    if use_stdin:
        return sys.stdin.read()
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def build_request(note_text: str):
    """Build the one controlled write request. Opens no connection and reads no environment."""
    from peak.db.intake_note_writer import build_intake_note_controlled_write_request
    from peak.db.writer_contracts import IntakeNoteDraft

    draft = IntakeNoteDraft(
        owner_id=OWNER_ID,
        client_id=CLIENT_ID,
        engagement_id=ENGAGEMENT_ID,
        authorization_scope=AUTHORIZATION_SCOPE,
        note_type=NOTE_TYPE,
        note_source=NOTE_SOURCE,
        note_text=note_text,
        note_summary=NOTE_SUMMARY,
        captured_by=CAPTURED_BY,
        captured_role=CAPTURED_ROLE,
    )
    return build_intake_note_controlled_write_request(
        draft,
        requested_by=REQUESTED_BY,
        requester_role=REQUESTER_ROLE,
        idempotency_key=IDEMPOTENCY_KEY,
        source_phase=SOURCE_PHASE,
    )


def emit_packet(note_text: str) -> None:
    """Print the packet's identity and posture — never the note body."""
    digest = hashlib.sha256(note_text.encode("utf-8")).hexdigest()
    print("Authorized packet (note body withheld: intake prose belongs only in the managed DB)")
    for key, val in (("engagement_id", ENGAGEMENT_ID), ("client_id", CLIENT_ID),
                     ("owner_id", OWNER_ID), ("authorization_scope", AUTHORIZATION_SCOPE),
                     ("note_type", NOTE_TYPE), ("note_source", NOTE_SOURCE),
                     ("captured_by", CAPTURED_BY), ("captured_role", CAPTURED_ROLE),
                     ("requested_by", REQUESTED_BY), ("requester_role", REQUESTER_ROLE),
                     ("idempotency_key", IDEMPOTENCY_KEY), ("source_phase", SOURCE_PHASE),
                     ("review_status", "needs_review"), ("lifecycle_status", "draft")):
        print(f"  {key:<32}: {val}")
    print(f"  {'note_text':<32}: <withheld> ({len(note_text)} chars)")
    print(f"  {'note_text_sha256':<32}: {digest}")


def emit_receipt(receipt) -> None:
    print("\nReceipt (typed fields only; no note body, DSN, environment value, or SQL)")
    for field in RECEIPT_FIELDS:
        if hasattr(receipt, field):
            print(f"  {field:<32}: {getattr(receipt, field)}")
    for line in getattr(receipt, "reasons", []) or []:
        print(f"  reason  : {line}")
    for line in getattr(receipt, "warnings", []) or []:
        print(f"  warning : {line}")


def dry_run(request) -> int:
    """Run the writer's own pre-DB gate. Stops before any connection is opened."""
    from peak.db.intake_note_writer import _pre_db_validate

    denial, draft = _pre_db_validate(request)
    if denial is not None:
        print("\n[denied] the packet did not pass the writer's pre-DB governance gate")
        emit_receipt(denial)
        print("\nRESULT: DRY-RUN DENIED (no connection opened, nothing written)")
        return 1

    print("\n[ok] packet passes the writer's own pre-DB governance gate")
    print("  database_connection_made        : False")
    print("  sql_execution_made              : False")
    print("  database_write_made             : False")
    print("\n  note: the stored-engagement authorization check runs at write time and needs a")
    print("        connection, so it is NOT exercised by this dry-run.")
    print("\nRESULT: DRY-RUN PASS (nothing was written; re-run with --execute to create it)")
    return 0


def execute(request) -> int:
    """Hand the request to the controlled intake-note writer. One note, or none."""
    from peak.db.intake_note_writer import persist_intake_note_record

    receipt = persist_intake_note_record(request)
    emit_receipt(receipt)

    outcome = getattr(receipt, "outcome", None)
    if outcome == "created":
        print("\nRESULT: CREATED (exactly one internal_test intake note)")
        return 0
    if outcome == "idempotent_replay":
        print("\nRESULT: IDEMPOTENT REPLAY (an identical note already existed; nothing was "
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
        description="Create the one durable internal_test intake note against engagement "
                    f"{ENGAGEMENT_ID} via the Phase 34 controlled writer. Dry-run unless "
                    "--execute is passed. Identity and posture are hard-coded; only the note "
                    "body is supplied, and only from an untracked file or stdin.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true",
                      help="Validate the packet and stop before opening a connection (default).")
    mode.add_argument("--execute", action="store_true",
                      help="Invoke the controlled writer. Creates at most one intake note.")
    parser.add_argument("--note-file", default=DEFAULT_NOTE_FILE,
                        help="Path to the untracked note body (default: %(default)s). Must live "
                             "outside the repository; intake prose is never committed.")
    parser.add_argument("--stdin", action="store_true",
                        help="Read the note body from stdin instead of a file.")
    args = parser.parse_args(argv)

    print("Peak Phase 60 — durable internal test intake note")
    print("=" * 70)

    note_text = load_note_body(args.note_file, args.stdin)
    if note_text is None or not note_text.strip():
        print("\n[stop] no note body supplied.")
        print("       Provide one with --note-file <path outside the repo> or --stdin.")
        print("       Intake prose is never stored in this repository.")
        print("\nRESULT: NO NOTE BODY (nothing validated, nothing written)")
        return 2
    if os.path.abspath(args.note_file).startswith(REPO_ROOT + os.sep) and not args.stdin:
        print("\n[stop] the note file is inside the repository. Intake prose must not live in "
              "source control; move it outside the repo and re-run.")
        print("\nRESULT: REFUSED (note file inside the repository)")
        return 2

    emit_packet(note_text)
    request = build_request(note_text)
    if not args.execute:
        return dry_run(request)

    print("\n[execute] invoking the controlled intake-note writer "
          "(runtime credential, SELECT + INSERT only)")
    return execute(request)


if __name__ == "__main__":
    raise SystemExit(main())
