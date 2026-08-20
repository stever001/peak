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
        "internal_reviewer_decision_records",
        "intake_note_records",
        "internal_assessment_report_drafts",
        "internal_report_review_packets",
        "internal_report_review_packet_decisions",
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
        "create_internal_reviewer_decision_record",
        "create_intake_note_record",
        "create_internal_assessment_report_draft",
        "create_internal_report_review_packet",
        "create_internal_report_review_packet_decision",
        "create_capsule_candidate_draft",
        "update_review_status",
        "update_lifecycle_status",
        "mark_superseded",
    }
)

# Tables explicitly excluded from this early writer boundary. `clients` and `engagements`
# are identity/root records not written through this generic path; the other two are gated
# behind future financial-verification / publication gates that do not exist yet.
#
# `engagements` stays here in Phase 54. The authorization-anchor writer added in that phase does
# **not** travel this generic path — it travels the separate, single-pair anchor-creation path
# below — so removing `engagements` from this set would silently open generic Engagement CRUD to
# every caller. The narrow exception is additive and lives beside this set, never inside it.
PROHIBITED_TABLES = frozenset(
    {
        "clients",
        "engagements",
        "financial_impact_estimates",  # excluded until a financial verification gate exists
        "resolver_capsule_records",  # excluded until a publication gate exists
    }
)

# --- Phase 54: the anchor-creation exception -------------------------------------------------
#
# An `engagements` row is the stored authorization anchor every controlled writer loads and
# checks its scope against. Nothing could ever be written until one existed, and nothing could
# create one — the generic allowlist prohibits the table, by design, because a root/identity
# record must not be reachable through a generic write path.
#
# The resolution is a second, deliberately tiny gate rather than a hole in the first: exactly one
# (table, action) pair, checked by its own predicate, consumed by exactly one writer. It grants
# creation of an engagement authorization anchor and nothing else — not update, not delete, not
# any other table, and above all not `clients`, which stays unreachable by any path.
#
# Expanding this set is a governance change of the same weight as expanding ALLOWED_TABLES, and
# it must not be used as a general-purpose escape hatch for root tables. See
# docs/PHASE54_CONTROLLED_ENGAGEMENT_AUTHORIZATION_ANCHOR_WRITER.md.
ANCHOR_CREATION_TABLE = "engagements"
ANCHOR_CREATION_ACTION = "create_engagement_authorization_anchor"

#: The complete set of (table, action) pairs permitted to create an authorization anchor.
ALLOWED_ANCHOR_CREATION_PAIRS = frozenset({(ANCHOR_CREATION_TABLE, ANCHOR_CREATION_ACTION)})

#: Tables that may never be reached by *any* path, generic or anchor-creation. `clients` is the
#: root identity record; nothing in Peak creates one through a controlled writer.
NEVER_WRITABLE_TABLES = frozenset({"clients"})

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


def is_never_writable_table(table_name) -> bool:
    """True if ``table_name`` may never be written through any controlled path."""
    return _norm(table_name) in NEVER_WRITABLE_TABLES


def is_allowed_anchor_creation_pair(table_name, action_name) -> bool:
    """True only for the exact (table, action) pair permitted to create an authorization anchor.

    Deliberately pair-wise, not table-wise and not action-wise: an allowed table combined with a
    different action, or the allowed action aimed at a different table, is refused. The prohibited
    action-substring guard and the never-writable table guard still apply on top, so this predicate
    can only ever narrow what is reachable, never widen it.
    """
    table = _norm(table_name)
    action = _norm(action_name)
    if not table or not action:
        return False
    if is_never_writable_table(table) or is_prohibited_action(action):
        return False
    return (table, action) in ALLOWED_ANCHOR_CREATION_PAIRS
