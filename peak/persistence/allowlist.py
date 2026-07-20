"""Controlled write allowlists for the Controlled DB Writer Boundary (Phase 17).

The single source of truth for **which tables and actions a future controlled DB writer may
target**. These are constants and pure helper predicates — no database, no SQL, no network.
A **write plan is not a write**: appearing on the allowlist only means a *future* controlled
writer would be permitted to plan it, never that anything is written here.

Expanding the allowlist (e.g. to `financial_impact_estimates` or `resolver_capsule_records`)
must happen only through an explicit later governance gate — see
docs/CONTROLLED_WRITE_ALLOWLIST.md.
"""

from __future__ import annotations

# Tables a future controlled writer may target when planning a write.
ALLOWED_TABLES = frozenset(
    {
        "evidence_references",
        "engagement_records",
        "review_records",
        "agent_run_records",
        "source_ingestion_records",
        "agent_task_queue_records",
        "review_bundle_records",
        "capsule_publication_candidates",
    }
)

# Actions a future controlled writer may plan.
ALLOWED_ACTIONS = frozenset(
    {
        "create_draft",
        "create_review_record",
        "create_agent_run_record",
        "create_source_ingestion_record",
        "create_agent_task_queue_record",
        "create_review_bundle_record",
        "create_capsule_candidate_draft",
        "update_review_status",
        "update_lifecycle_status",
        "mark_superseded",
    }
)

# Tables explicitly excluded from this early writer boundary. `clients` and `engagements`
# are identity/root records not written through this generic path; the other two are gated
# behind future financial-verification / publication gates that do not exist yet.
PROHIBITED_TABLES = frozenset(
    {
        "clients",
        "engagements",
        "financial_impact_estimates",  # excluded until a financial verification gate exists
        "resolver_capsule_records",  # excluded until a publication gate exists
    }
)

# Any action whose name contains one of these substrings is prohibited outright, regardless
# of the allowlist — publication, client-facing approval, financial verification, deletes,
# credential/secret handling, seeds, migrations, and raw SQL are never planned here.
PROHIBITED_ACTION_SUBSTRINGS = (
    "publish",
    "client_facing_approve",
    "verify_financial",
    "delete",
    "hard_delete",
    "credential",
    "secret",
    "seed",
    "migrate",
    "raw_sql",
)


def _norm(name) -> str:
    return name.strip().lower() if isinstance(name, str) else ""


def is_allowed_table(table_name) -> bool:
    """True only if ``table_name`` is on the allowlist and not prohibited."""
    name = _norm(table_name)
    return bool(name) and name in ALLOWED_TABLES and name not in PROHIBITED_TABLES


def is_allowed_action(action_name) -> bool:
    """True only if ``action_name`` is on the allowlist and not a prohibited pattern."""
    name = _norm(action_name)
    return bool(name) and name in ALLOWED_ACTIONS and not is_prohibited_action(name)


def is_prohibited_table(table_name) -> bool:
    """True if ``table_name`` is explicitly prohibited."""
    return _norm(table_name) in PROHIBITED_TABLES


def is_prohibited_action(action_name) -> bool:
    """True if ``action_name`` contains any prohibited substring."""
    name = _norm(action_name)
    return any(bad in name for bad in PROHIBITED_ACTION_SUBSTRINGS)
