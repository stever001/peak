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

#: Tables no controlled-writer path may reach — neither the generic allowlist nor the anchor
#: path. Until Phase 202 this set was ``NEVER_WRITABLE_TABLES`` ("never written by any path").
#: Phase 202 changed that explicitly rather than routing around it: `clients` is still unreachable
#: by every controlled writer, and its **only** approved write path is the consultant workspace
#: service (``peak.workspace``), restricted by ``WORKSPACE_WRITE_COLUMNS`` below.
WORKSPACE_ONLY_TABLES = frozenset({"clients"})

# --- Phase 202: the consultant workspace write path ------------------------------------------
#
# The consultant web app creates and edits client profiles and engagement workflow fields. That is
# a separate path from every controlled writer: it is not on ALLOWED_TABLES, not an anchor pair,
# and it is checked by its own predicate. Each (table, action) pair names the exact columns it may
# write; nothing else is writable through it. There is no delete action and no generic update.
#
# `engagements` stays in PROHIBITED_TABLES: the generic path still cannot touch it. A caller can
# never write a governance or classification column through this path. The one exception is the
# fixed creation stamp below, which the service itself applies to every engagement it creates.
# See docs/PHASE202_CLIENT_ENGAGEMENT_CRUD.md.
WORKSPACE_WRITE_PATH = "peak.workspace"

#: Client profile columns (``organization_label`` is the company name).
CLIENT_PROFILE_COLUMNS = frozenset(
    {
        "organization_label", "description",
        "address_line1", "address_line2", "city", "region", "postal_code", "country",
        "contact_name", "contact_title", "contact_email", "contact_phone",
        "key_personnel",
    }
)

#: Engagement workflow columns a consultant may set or edit.
ENGAGEMENT_WORKSPACE_COLUMNS = frozenset(
    {"engagement_label", "objective", "assigned_consultant_id", "status", "current_phase"}
)

#: The complete set of workspace (table, action) pairs and the columns each may write.
WORKSPACE_WRITE_COLUMNS = {
    ("clients", "create_client_profile"): frozenset({"id"}) | CLIENT_PROFILE_COLUMNS,
    ("clients", "update_client_profile"): CLIENT_PROFILE_COLUMNS,
    ("engagements", "create_workspace_engagement"):
        frozenset({"id", "client_id"}) | ENGAGEMENT_WORKSPACE_COLUMNS,
    ("engagements", "update_engagement_workspace_fields"): ENGAGEMENT_WORKSPACE_COLUMNS,
}

#: Columns the workspace path may never write: governance, classification, review/audit, and
#: publication state. Asserted disjoint from every workspace column set at import time.
WORKSPACE_FORBIDDEN_COLUMNS = frozenset(
    {
        "owner_id", "authorization_scope", "review_status", "lifecycle_status",
        "created_at", "created_by", "updated_at", "updated_by", "agent_run_id", "details_json",
        "engagement_category", "real_client_data", "client_accessible",
        "capsule_publication_authorized",
    }
)

#: Engagement status values the workspace may set (UI: Active / Paused / Closed). The stored
#: vocabulary is unchanged; "Paused" is the existing ``on_hold``.
WORKSPACE_ENGAGEMENT_STATUSES = frozenset({"active", "on_hold", "closed"})

#: Phase 202 authorization decision: every real-client engagement created through the workspace is
#: born with this organizational owner and canonical scope, so downstream controlled writers can
#: match it exactly. `peak_consultants` is organizational authority over the engagement (distinct
#: from `assigned_consultant_id`, which is workflow assignment only). `engagement_authorized` means
#: work records of an authorized real-client engagement, for internal consultant work; it does not
#: authorize client-facing disclosure, methodology publication, or AgentNet publication.
#: These are server-set constants: never read from a caller, never in an editable column set, and
#: both columns stay in WORKSPACE_FORBIDDEN_COLUMNS, so no workspace update can change them.
WORKSPACE_ENGAGEMENT_OWNER_ID = "peak_consultants"
WORKSPACE_ENGAGEMENT_AUTHORIZATION_SCOPE = "engagement_authorized"
WORKSPACE_ENGAGEMENT_CREATION_STAMP = {
    "owner_id": WORKSPACE_ENGAGEMENT_OWNER_ID,
    "authorization_scope": WORKSPACE_ENGAGEMENT_AUTHORIZATION_SCOPE,
}

assert not any(cols & WORKSPACE_FORBIDDEN_COLUMNS for cols in WORKSPACE_WRITE_COLUMNS.values())
assert set(WORKSPACE_ENGAGEMENT_CREATION_STAMP) <= WORKSPACE_FORBIDDEN_COLUMNS

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


def is_workspace_only_table(table_name) -> bool:
    """True if ``table_name`` is unreachable by every controlled writer (workspace path only)."""
    return _norm(table_name) in WORKSPACE_ONLY_TABLES


def is_allowed_workspace_write(table_name, action_name, columns) -> bool:
    """True only for a known workspace (table, action) pair writing a non-empty subset of its columns.

    Pair-wise like the anchor predicate: a known table with another action, or a known action on
    another table, is refused. The prohibited action-substring guard still applies, and a column
    outside the pair's set — above all a governance column — refuses the whole write.
    """
    table, action = _norm(table_name), _norm(action_name)
    if not table or not action or is_prohibited_action(action):
        return False
    allowed = WORKSPACE_WRITE_COLUMNS.get((table, action))
    cols = set(columns or ())
    return allowed is not None and bool(cols) and cols <= allowed \
        and not cols & WORKSPACE_FORBIDDEN_COLUMNS


def is_allowed_anchor_creation_pair(table_name, action_name) -> bool:
    """True only for the exact (table, action) pair permitted to create an authorization anchor.

    Deliberately pair-wise, not table-wise and not action-wise: an allowed table combined with a
    different action, or the allowed action aimed at a different table, is refused. The prohibited
    action-substring guard and the workspace-only table guard still apply on top, so this predicate
    can only ever narrow what is reachable, never widen it.
    """
    table = _norm(table_name)
    action = _norm(action_name)
    if not table or not action:
        return False
    if is_workspace_only_table(table) or is_prohibited_action(action):
        return False
    return (table, action) in ALLOWED_ANCHOR_CREATION_PAIRS
