#!/usr/bin/env python3
"""Writer enablement decision gate (Phase 51) — OFFLINE, decision record only.

This tool records and enforces the *current* decision about production writes. It is a
decision-gate and reporting tool, **not** a database tool.

It has no database code path at all: it opens no connection, imports no engine or session helper,
imports no controlled writer, reads no environment variable, sources no operator file, and issues
no statement of any kind. Running it can therefore never touch production, by construction rather
than by policy.

**The decision it currently encodes:**

    no production smoke-write yet · no writer enablement yet
    no synthetic production write · no real engagement write until authorized engagement data exists

**Why a passing Phase 50 gate is not enough.** Phase 50 proved the runtime credential can connect
and holds exactly ``SELECT`` + ``INSERT``. That is *prerequisite evidence* — it says the plumbing
and privileges are correct. It says nothing about whether there is anything that ought to be
written, or who authorised writing it. Those are governance questions, and this gate is where they
are answered.

**Why synthetic writes need a cleanup decision first.** The runtime credential holds **no**
``DELETE``. A synthetic or administrative record written by runtime therefore **cannot be removed by
runtime**; removing it would require the migration credential, which is a separate approval and a
separate risk. So the cleanup posture must be decided *before* such a write, not discovered after
it. The honest default is to treat any synthetic record as **durable**.

Exit status:
  0  -> the current no-write decision is in force and was reported
  1  -> internal inconsistency in the decision record (should not happen)
  3  -> refused: a write-authorizing path was requested, which this phase does not grant

Enabling application writers remains a separate, approved phase.
"""

from __future__ import annotations

import argparse
import json
import sys

DECISION_GATE_VERSION = "1"

# --------------------------------------------------------------------------- decision paths

PATH_NO_WRITE = "no_production_smoke_write_yet"
PATH_SYNTHETIC = "synthetic_admin_smoke_write"
PATH_REAL_ENGAGEMENT = "real_engagement_write"

#: The only path this phase grants. Everything else is refused, loudly.
AUTHORIZED_PATHS = frozenset({PATH_NO_WRITE})

#: Selectable on the command line so a future phase can *ask*; asking is not being granted.
KNOWN_PATHS = (PATH_NO_WRITE, PATH_SYNTHETIC, PATH_REAL_ENGAGEMENT)

RECOMMENDED_NEXT_PATH = (
    "wait_for_authorized_engagement_or_separately_approve_no_cleanup_admin_smoke_record"
)

#: Ordered, so the emitted record is deterministic and diffable.
FIELDS = (
    "decision_gate_version",
    "selected_path",
    "production_write_authorized",
    "writer_enablement_authorized",
    "synthetic_write_authorized",
    "real_engagement_write_authorized",
    "requires_authorized_engagement_before_real_write",
    "requires_explicit_cleanup_plan_before_synthetic_write",
    "runtime_delete_available",
    "migration_credential_cleanup_requires_separate_approval",
    "runtime_connectivity_gate_required_before_future_write",
    "read_only_production_verifier_required_before_future_write",
    "production_migration_required",
    "schema_change_required",
    "safe_to_run_writers_now",
    "safe_to_write_production_now",
    "phase50_pass_is_prerequisite_evidence_not_write_permission",
    "database_contacted",
    "sql_issued",
    "writer_invoked",
    "environment_read",
    "secrets_printed",
    "recommended_next_path",
)

NOTES = (
    "phase50_runtime_connectivity_pass_is_prerequisite_evidence_not_write_permission",
    "runtime_credential_has_no_delete_so_a_synthetic_record_cannot_be_removed_by_runtime",
    "synthetic_record_must_be_treated_as_durable_unless_cleanup_is_separately_approved",
    "cleanup_posture_must_be_decided_before_any_synthetic_write_not_after",
    "future_write_phase_must_rerun_read_only_verifier_and_runtime_connectivity_gate",
    "future_write_phase_must_name_writer_table_action_scope_idempotency_key_and_cleanup_posture",
)


def build_decision(selected_path: str) -> dict:
    """Return the decision record for ``selected_path``.

    Every write-authorizing field is ``False`` for every path this phase knows about: selecting a
    write path is how a future phase *requests* one, and the request is refused by :func:`main`.
    Nothing here can be coaxed into returning an authorization.
    """
    return {
        "decision_gate_version": DECISION_GATE_VERSION,
        "selected_path": selected_path,
        "production_write_authorized": False,
        "writer_enablement_authorized": False,
        "synthetic_write_authorized": False,
        "real_engagement_write_authorized": False,
        "requires_authorized_engagement_before_real_write": True,
        "requires_explicit_cleanup_plan_before_synthetic_write": True,
        # The Phase 48 grant posture is read-plus-append only: no row-removal privilege.
        "runtime_delete_available": False,
        "migration_credential_cleanup_requires_separate_approval": True,
        "runtime_connectivity_gate_required_before_future_write": True,
        "read_only_production_verifier_required_before_future_write": True,
        "production_migration_required": False,
        "schema_change_required": False,
        "safe_to_run_writers_now": False,
        "safe_to_write_production_now": False,
        "phase50_pass_is_prerequisite_evidence_not_write_permission": True,
        # Structural invariants: this module has no code path that could make any of these True.
        "database_contacted": False,
        "sql_issued": False,
        "writer_invoked": False,
        "environment_read": False,
        "secrets_printed": False,
        "recommended_next_path": RECOMMENDED_NEXT_PATH,
    }


def _consistent(decision: dict) -> bool:
    """The record must never authorize anything while this phase is in force."""
    must_be_false = (
        "production_write_authorized", "writer_enablement_authorized",
        "synthetic_write_authorized", "real_engagement_write_authorized",
        "safe_to_run_writers_now", "safe_to_write_production_now",
        "runtime_delete_available", "database_contacted", "sql_issued",
        "writer_invoked", "environment_read", "secrets_printed",
    )
    must_be_true = (
        "requires_authorized_engagement_before_real_write",
        "requires_explicit_cleanup_plan_before_synthetic_write",
        "migration_credential_cleanup_requires_separate_approval",
        "runtime_connectivity_gate_required_before_future_write",
        "read_only_production_verifier_required_before_future_write",
        "phase50_pass_is_prerequisite_evidence_not_write_permission",
    )
    return (all(decision[f] is False for f in must_be_false)
            and all(decision[f] is True for f in must_be_true)
            and set(decision) == set(FIELDS))


def _emit(decision: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps({**decision, "notes": list(NOTES)}, indent=2, sort_keys=False))
        return
    for field in FIELDS:
        value = decision[field]
        # Lower-cased booleans so key=value output and --json agree token-for-token.
        rendered = "true" if value is True else ("false" if value is False else value)
        print(f"{field}={rendered}")
    for note in NOTES:
        print(f"note={note}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Writer enablement decision gate (offline; records the current decision).")
    parser.add_argument(
        "--decision", default=PATH_NO_WRITE, choices=list(KNOWN_PATHS),
        help="Path to record. Only the no-write path is granted in this phase; requesting a "
             "write-authorizing path is refused with exit 3.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of key=value lines.")
    args = parser.parse_args(argv)

    # In --json mode stdout carries the JSON document and nothing else, so it parses directly.
    # Human framing goes to stderr there.
    banner = (lambda *a: print(*a, file=sys.stderr)) if args.json else print

    banner("Peak writer enablement decision gate — OFFLINE, decision record only")
    banner("=" * 68)

    decision = build_decision(args.decision)
    _emit(decision, args.json)

    banner("=" * 68)
    if not _consistent(decision):
        banner("RESULT: INCONSISTENT")
        return 1
    if args.decision not in AUTHORIZED_PATHS:
        banner(f"RESULT: REFUSED ({args.decision} is not authorized in this phase)")
        banner("A passing runtime connectivity gate is prerequisite evidence, not write "
               "permission. Authorizing a write is a separate, explicitly approved phase.")
        return 3
    banner("RESULT: PASS (no production write and no writer enablement are authorized)")
    banner("This tool contacts no database, issues no statement, reads no environment variable, "
           "and invokes no writer. It records a decision; it does not perform one.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
