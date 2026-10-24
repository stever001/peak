"""Runtime persistence classification of every application table (the canonical policy).

One entry per table says how the **deployed application** (the runtime credential) may persist it.
The production runtime grant gate (``tools/production_runtime_connectivity_gate.py``, Phase 50)
derives its table-level UPDATE allowance from this module and keeps no table list of its own. So a
phase that adds a table declares its mutability once, here.

Vocabulary (the smallest set that describes the current tables):

- ``mutable``: the application inserts and updates rows. The runtime needs table-level UPDATE.
- ``append_only``: the application inserts rows and never updates or deletes them. A correction is
  a new row. The runtime must hold no UPDATE.
- ``read_only``: no runtime write path exists; rows come from migrations or operator tools. The
  runtime must hold no UPDATE.

**What the database enforces today.** The runtime holds ``SELECT, INSERT`` on the whole schema, so
``append_only`` and ``read_only`` differ in application policy only. The database enforces just the
UPDATE boundary: table-level UPDATE exists on ``mutable`` tables alone, and the gate fails on
UPDATE anywhere else. Nothing here claims a per-table INSERT restriction the grants do not make.

Stdlib only, like the rest of ``peak.persistence``. It imports the write-path allowlist, not
``peak.db``, so the gate can load it without the application stack.
"""

from __future__ import annotations

from .allowlist import (
    ALLOWED_ANCHOR_CREATION_PAIRS,
    ALLOWED_TABLES,
    WORKSPACE_WRITE_COLUMNS,
)

MUTABLE = "mutable"
APPEND_ONLY = "append_only"
READ_ONLY = "read_only"
CLASSIFICATIONS = frozenset({MUTABLE, APPEND_ONLY, READ_ONLY})

#: The canonical classification. Every table in ``peak.db.models`` appears exactly once (the Phase
#: 50 harness checks coverage against the models).
RUNTIME_TABLE_PERSISTENCE = {
    # Workspace path with update actions (Phases 202, 204, 216, 217).
    "clients": MUTABLE,
    "engagements": MUTABLE,
    "discovery_questions": MUTABLE,
    "discovery_sessions": MUTABLE,
    "discovery_answers": MUTABLE,
    "discovery_observations": MUTABLE,
    "roadmap_items": MUTABLE,
    "engagement_phases": MUTABLE,
    "phase_tasks": MUTABLE,
    # Workspace path, create-only: artifacts and versions are immutable, approval and release
    # records are append-only (Phases 212-213), task records are corrected by supersession (217).
    "artifacts": APPEND_ONLY,
    "artifact_versions": APPEND_ONLY,
    "artifact_release_packages": APPEND_ONLY,
    "artifact_renditions": APPEND_ONLY,
    "artifact_approvals": APPEND_ONLY,
    "artifact_final_approver_designations": APPEND_ONLY,
    "artifact_releases": APPEND_ONLY,
    "phase_task_records": APPEND_ONLY,
    # Consultant accounts are created by ``peak.accounts``. The only update (an Admin password
    # reset) runs as the migration credential, never the runtime.
    "consultants": APPEND_ONLY,
    # Controlled writers (Phase 17 onward): create-only.
    "agent_run_records": APPEND_ONLY,
    "agent_task_queue_records": APPEND_ONLY,
    "capsule_publication_candidates": APPEND_ONLY,
    "engagement_records": APPEND_ONLY,
    "evidence_references": APPEND_ONLY,
    "intake_note_records": APPEND_ONLY,
    "internal_assessment_report_drafts": APPEND_ONLY,
    "internal_report_review_packet_decisions": APPEND_ONLY,
    "internal_report_review_packets": APPEND_ONLY,
    "internal_reviewer_decision_records": APPEND_ONLY,
    "review_bundle_records": APPEND_ONLY,
    "review_records": APPEND_ONLY,
    "source_ingestion_records": APPEND_ONLY,
    # No runtime write path.
    "financial_impact_estimates": READ_ONLY,
    "resolver_capsule_records": READ_ONLY,
    "source_system_references": READ_ONLY,
}


def update_eligible_tables(policy=None) -> frozenset:
    """The tables on which the runtime may hold table-level UPDATE: exactly the ``mutable`` ones.

    An unclassified table, or any value other than ``mutable``, is never eligible.
    """
    policy = RUNTIME_TABLE_PERSISTENCE if policy is None else policy
    return frozenset(table for table, kind in policy.items() if kind == MUTABLE)


def policy_problems(policy=None) -> list:
    """Disagreements between a classification and the write-path allowlist; empty when consistent.

    Action names cannot say whether a write is an insert (``start_discovery_session`` is one), so
    the classification is declared, not derived. These rules keep it honest:

    - every value is in the vocabulary;
    - every table a runtime path writes is classified;
    - a table is ``mutable`` exactly when it has a workspace action other than ``create_*``, so
      an append-only table cannot be made UPDATE-eligible without adding an update action;
    - a ``read_only`` table has no write path at all.
    """
    policy = RUNTIME_TABLE_PERSISTENCE if policy is None else policy
    non_create = {table for table, action in WORKSPACE_WRITE_COLUMNS
                  if not action.startswith("create_")}
    written = ({table for table, _ in WORKSPACE_WRITE_COLUMNS} | set(ALLOWED_TABLES)
               | {table for table, _ in ALLOWED_ANCHOR_CREATION_PAIRS})
    problems = [f"{t}: unknown classification {k!r}" for t, k in sorted(policy.items(), key=str)
                if k not in CLASSIFICATIONS]
    problems += [f"{t}: written at runtime but unclassified" for t in sorted(written - set(policy))]
    mutable = update_eligible_tables(policy)
    problems += [f"{t}: has an update action but is not mutable"
                 for t in sorted(non_create - mutable)]
    problems += [f"{t}: mutable but has no update action" for t in sorted(mutable - non_create)]
    problems += [f"{t}: read_only but has a write path" for t in sorted(written)
                 if policy.get(t) == READ_ONLY]
    return problems


assert not policy_problems(), policy_problems()
