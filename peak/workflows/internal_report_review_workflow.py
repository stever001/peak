"""End-to-End Internal Report Review Workflow Integration (Phase 40).

A **read-only workflow integration and consolidation layer**, not a new persistence primitive.
Phase 40 adds **no DB table, model, or Alembic migration** (the head stays
``012_internal_report_review_packet_decisions``; ``make db-check`` stays at 18 tables), **no new
Phase 17 allowlist pair**, no writer, no update/delete/upsert path, no generic CRUD, no raw-SQL
executor, and no broad repository.

It answers one operational question over records that already exist::

    internal_assessment_report_drafts   (Phase 37)
      -> internal_report_review_packets (Phase 38)
      -> internal_report_review_packet_decisions (Phase 39)

*Where is this internal report review right now?*

**The Phase 39 gap this closes.** The Phase 39 decision writer is insert-only: it records *which*
packet was decided but never updates the Phase 38 packet row's ``reviewer_decision_status`` /
``reviewer_decision_record_id``. Phase 40 closes that gap by **deriving** the packet's decision
state from the Phase 39 decision rows — it does **not** mutate the packet row, the report-draft
row, or anything else.

**Read-only means read-only.** This module calls no writer function and never uses ``session.add``,
``session.delete``, ``session.merge``, ``session.flush``, ``session.commit``, ``update()``, or raw
SQL. Records are loaded with ``session.get`` / ORM ``session.query`` only, and no loaded ORM object
is modified.

**No ambient DSN.** A summary requires an injected ``session_factory``; this layer never falls back
to an environment database URL, so standard validation needs no live credentials and no network.

**Nothing escalates.** Phase 40 approves nothing for client use (``ready_for_internal_use`` is
internal readiness, **not** client-facing approval), verifies no financial claim, creates no
client-facing output, publishes no capsule, and makes no AgentNet / MCP / resolver / LLM / agent /
network call. Every result carries ``requires_human_review=True`` and ``read_only=True``.

**Leak safety.** Results carry only refs, ids, closed-vocabulary statuses, counts, and safe reason
codes — never note text, packet payloads, raw evidence/interview text, source bytes, generated agent
output, report prose, recommendations, LLM prompts, credentials, DSNs, raw SQL, stack traces,
client-facing approvals, ROI/savings figures, capsule payloads, or AgentNet publish payloads. Stored
values are never echoed: a blocker names the field and the *expected* value, not what was found.

The SQLAlchemy models are imported **lazily** inside the load step, so this module — and the whole
``peak.workflows`` package — still imports without a database driver installed.

See docs/INTERNAL_REPORT_REVIEW_WORKFLOW_INTEGRATION.md and
docs/WORKFLOW_INTEGRATION_GOVERNANCE_POLICY.md.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# Public, DB-free Phase 32 decision vocabulary + value classifier (neither imports peak.db).
from peak.reviewer_decisions.contracts import ALLOWED_DECISION_INTENTS
from peak.reviewer_decisions.governance import classify_prohibited_value_marker

# --------------------------------------------------------------------------- stored expectations

SOURCE_PHASE = "phase40"

AUDIENCE_INTERNAL = "internal"
BLOCKED_AUTHORIZATION_SCOPES = frozenset({"revoked"})
BLOCKED_LIFECYCLE_STATUSES = frozenset({"revoked", "archived", "deleted_reference_only"})

#: The stored Phase 37 report-draft posture a live internal review runs against.
REQUIRED_DRAFT_OUTPUT_STATUS = "plan_persisted"
REQUIRED_DRAFT_REVIEW_STATUS = "needs_review"
REQUIRED_DRAFT_LIFECYCLE_STATUS = "draft"
#: The stored Phase 38 packet posture a live internal review runs against.
REQUIRED_PACKET_STATUS = "ready_for_internal_review"
REQUIRED_PACKET_REVIEW_STATUS = "needs_review"
REQUIRED_PACKET_LIFECYCLE_STATUS = "draft"
#: Phase 38 creates a packet pre-decision and Phase 39 never updates it, so this is the only
#: stored value Phase 40 can explain without decision rows.
PACKET_NOT_DECIDED = "not_decided"

#: Posture flags that must be false on the stored report draft.
DRAFT_REQUIRED_FALSE_FLAGS = ("client_facing_approved", "financial_verified",
                              "capsule_candidate_ready", "publication_allowed",
                              "execution_allowed")
#: Posture flags that must be false on the stored review packet.
PACKET_REQUIRED_FALSE_FLAGS = ("client_facing_approved", "review_approval_made",
                               "financial_verified", "capsule_candidate_ready",
                               "publication_allowed", "execution_allowed")

#: Source tables this layer reads. It reads nothing else and writes nothing at all.
SOURCE_TABLES = (
    "engagements",
    "internal_assessment_report_drafts",
    "internal_report_review_packets",
    "internal_report_review_packet_decisions",
)

# --------------------------------------------------------------------------- decision vocabulary

#: The server-derived Phase 39 ``decision_status`` axis, mirrored here as plain strings so this
#: module needs no ``peak.db`` import. Kept in lockstep with
#: ``peak.db.writer_contracts.PACKET_DECISION_STATUS_*`` by
#: tests/validate_phase40_internal_report_review_workflow.py.
DECISION_STATUS_RECORDED = "decision_recorded"
DECISION_STATUS_NEEDS_FOLLOWUP = "needs_followup"

#: Mirrors Phase 39's ``NEEDS_FOLLOWUP_INTENTS`` -> ``decision_status`` derivation. A stored row
#: whose ``decision_status`` disagrees with its ``decision_intent`` is treated as inconsistent and
#: excluded from the effective decision set (with a warning) rather than silently trusted.
EXPECTED_DECISION_STATUS_BY_INTENT = {
    "needs_more_evidence": DECISION_STATUS_NEEDS_FOLLOWUP,
    "return_for_revision": DECISION_STATUS_NEEDS_FOLLOWUP,
    "blocked_by_scope": DECISION_STATUS_NEEDS_FOLLOWUP,
    "blocked_by_quality": DECISION_STATUS_NEEDS_FOLLOWUP,
    "blocked_by_missing_source": DECISION_STATUS_NEEDS_FOLLOWUP,
    "defer_review": DECISION_STATUS_NEEDS_FOLLOWUP,
    "ready_for_internal_use": DECISION_STATUS_RECORDED,
    "rejected_for_policy": DECISION_STATUS_RECORDED,
}

#: The fixed Phase 39 decision scope. A row outside it is not a packet decision.
PACKET_DECISION_SCOPE = "internal_report_review_packet"

# --------------------------------------------------------------------------- computed vocabulary


class InternalReportReviewWorkflowState:
    """The closed computed workflow-state vocabulary (str constants; no Enum dependency).

    Deliberately **internal-only**: there is no approved / approved_for_client / published /
    verified state here. ``decision_recorded_ready_for_internal_use`` means a Peak reviewer found
    the internal report draft usable *inside Peak* — it is not client-facing approval.
    """

    BLOCKED_MISSING_ENGAGEMENT = "blocked_missing_engagement"
    BLOCKED_MISSING_REPORT_DRAFT = "blocked_missing_report_draft"
    BLOCKED_MISSING_REVIEW_PACKET = "blocked_missing_review_packet"
    BLOCKED_SCOPE_MISMATCH = "blocked_scope_mismatch"
    BLOCKED_INVALID_REPORT_DRAFT = "blocked_invalid_report_draft"
    BLOCKED_INVALID_REVIEW_PACKET = "blocked_invalid_review_packet"
    AWAITING_REVIEWER_DECISION = "awaiting_reviewer_decision"
    DECISION_RECORDED_NEEDS_FOLLOWUP = "decision_recorded_needs_followup"
    DECISION_RECORDED_READY_FOR_INTERNAL_USE = "decision_recorded_ready_for_internal_use"
    DECISION_RECORDED_REJECTED_FOR_POLICY = "decision_recorded_rejected_for_policy"
    DECISION_RECORDED_BLOCKED = "decision_recorded_blocked"
    DECISION_RECORDED_RETURN_FOR_REVISION = "decision_recorded_return_for_revision"
    CONFLICTING_DECISIONS = "conflicting_decisions"


#: Every state this layer can ever report (used by the validation harness).
WORKFLOW_STATES = frozenset({
    InternalReportReviewWorkflowState.BLOCKED_MISSING_ENGAGEMENT,
    InternalReportReviewWorkflowState.BLOCKED_MISSING_REPORT_DRAFT,
    InternalReportReviewWorkflowState.BLOCKED_MISSING_REVIEW_PACKET,
    InternalReportReviewWorkflowState.BLOCKED_SCOPE_MISMATCH,
    InternalReportReviewWorkflowState.BLOCKED_INVALID_REPORT_DRAFT,
    InternalReportReviewWorkflowState.BLOCKED_INVALID_REVIEW_PACKET,
    InternalReportReviewWorkflowState.AWAITING_REVIEWER_DECISION,
    InternalReportReviewWorkflowState.DECISION_RECORDED_NEEDS_FOLLOWUP,
    InternalReportReviewWorkflowState.DECISION_RECORDED_READY_FOR_INTERNAL_USE,
    InternalReportReviewWorkflowState.DECISION_RECORDED_REJECTED_FOR_POLICY,
    InternalReportReviewWorkflowState.DECISION_RECORDED_BLOCKED,
    InternalReportReviewWorkflowState.DECISION_RECORDED_RETURN_FOR_REVISION,
    InternalReportReviewWorkflowState.CONFLICTING_DECISIONS,
})

#: ``decision_intent`` -> computed workflow state. Covers the whole closed Phase 32 vocabulary.
INTENT_WORKFLOW_STATES = {
    "ready_for_internal_use":
        InternalReportReviewWorkflowState.DECISION_RECORDED_READY_FOR_INTERNAL_USE,
    "needs_more_evidence": InternalReportReviewWorkflowState.DECISION_RECORDED_NEEDS_FOLLOWUP,
    "defer_review": InternalReportReviewWorkflowState.DECISION_RECORDED_NEEDS_FOLLOWUP,
    "return_for_revision":
        InternalReportReviewWorkflowState.DECISION_RECORDED_RETURN_FOR_REVISION,
    "rejected_for_policy":
        InternalReportReviewWorkflowState.DECISION_RECORDED_REJECTED_FOR_POLICY,
    "blocked_by_scope": InternalReportReviewWorkflowState.DECISION_RECORDED_BLOCKED,
    "blocked_by_quality": InternalReportReviewWorkflowState.DECISION_RECORDED_BLOCKED,
    "blocked_by_missing_source": InternalReportReviewWorkflowState.DECISION_RECORDED_BLOCKED,
}


class ComputedPacketDecisionState:
    """The closed computed packet-decision-state vocabulary.

    This is **derived** from the Phase 39 decision rows. It is never read from, and never written
    to, the Phase 38 packet row's ``reviewer_decision_status`` column.
    """

    NOT_COMPUTED = "not_computed"          # blocked before decisions could be located
    AWAITING_DECISION = "awaiting_decision"
    DECISION_RECORDED = DECISION_STATUS_RECORDED
    NEEDS_FOLLOWUP = DECISION_STATUS_NEEDS_FOLLOWUP
    CONFLICTED = "conflicted"


PACKET_DECISION_STATES = frozenset({
    ComputedPacketDecisionState.NOT_COMPUTED,
    ComputedPacketDecisionState.AWAITING_DECISION,
    ComputedPacketDecisionState.DECISION_RECORDED,
    ComputedPacketDecisionState.NEEDS_FOLLOWUP,
    ComputedPacketDecisionState.CONFLICTED,
})


class InternalReportReviewWorkflowOutcome:
    """Aggregate outcome codes for one summary call."""

    DENIED = "denied"          # request pre-flight denial; no connection opened
    BLOCKED = "blocked"        # records loaded but the chain is not a usable internal review
    SUMMARIZED = "summarized"  # a workflow state was computed from the stored chain
    FAILED = "failed"          # a read failed; nothing was written and nothing is claimed


# --------------------------------------------------------------------------- contracts


@dataclass
class InternalReportReviewWorkflowRequest:
    """One read-only internal report review workflow summary request.

    Carries identity + the two stored refs to consolidate. It accepts **no** payload, no prose, no
    file, no DB URL, no credential, no raw SQL, and no workflow JSON blob: everything it needs is
    already durable in the managed database.
    """

    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    authorization_scope: Optional[str] = None
    requested_by: Optional[str] = None
    requester_role: Optional[str] = None
    # The stored chain to summarize.
    internal_assessment_report_draft_id: Optional[str] = None
    internal_report_review_packet_id: Optional[str] = None
    # Optional caller expectations. When supplied they are compared against the stored rows; a
    # mismatch is a blocker, never a silent pass.
    expected_report_plan_id: Optional[str] = None
    expected_plan_fingerprint: Optional[str] = None
    # Strict mode: any warning makes the summary non-permitted (the state is still reported).
    strict_mode: bool = False


@dataclass
class InternalReportReviewWorkflowTrace:
    """Sanitized traceability across report draft -> review packet -> packet decision.

    Refs, fingerprints, counts, and table names only — never stored content.
    """

    engagement_ref: Optional[str] = None
    report_draft_ref: Optional[str] = None
    review_packet_ref: Optional[str] = None
    report_plan_id: Optional[str] = None
    plan_fingerprint: Optional[str] = None
    report_draft_payload_fingerprint: Optional[str] = None
    packet_payload_fingerprint: Optional[str] = None
    decision_record_refs: List[str] = field(default_factory=list)
    decision_records_found: int = 0
    decision_records_considered: int = 0
    decision_records_skipped: int = 0
    distinct_decision_positions: int = 0
    # What the Phase 38 packet row itself still says. Phase 39 is insert-only, so this normally
    # stays 'not_decided'/None while the computed state moves on — that difference is the point.
    stored_packet_reviewer_decision_status: Optional[str] = None
    stored_packet_reviewer_decision_record_id: Optional[str] = None
    source_tables: List[str] = field(default_factory=lambda: list(SOURCE_TABLES))


@dataclass
class InternalReportReviewWorkflowResult:
    """The auditable, sanitized receipt for one read-only workflow summary.

    Every side-effect flag below is a statement about what this layer did. Only
    ``database_connection_made`` / ``sql_execution_made`` can ever be true.
    """

    outcome: str = InternalReportReviewWorkflowOutcome.DENIED
    permitted: bool = False
    reason_code: Optional[str] = None
    workflow_state: Optional[str] = None
    computed_packet_decision_state: str = ComputedPacketDecisionState.NOT_COMPUTED
    # Identity echo (safe identifiers the caller supplied; never credentials).
    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    engagement_id: Optional[str] = None
    authorization_scope: Optional[str] = None
    # The stored chain.
    internal_assessment_report_draft_id: Optional[str] = None
    internal_report_review_packet_id: Optional[str] = None
    report_plan_id: Optional[str] = None
    plan_fingerprint: Optional[str] = None
    # Located decision records (refs + closed-vocabulary labels only).
    decision_record_ids: List[str] = field(default_factory=list)
    decision_intents: List[str] = field(default_factory=list)
    decision_statuses: List[str] = field(default_factory=list)
    decision_record_count: int = 0
    trace: Optional[InternalReportReviewWorkflowTrace] = None
    strict_mode: bool = False
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    # Posture — constant for this layer.
    requires_human_review: bool = True
    read_only: bool = True
    # Actual-behavior flags.
    database_connection_made: bool = False
    sql_execution_made: bool = False
    # Non-effect flags — always False (Phase 40 writes, approves, publishes, executes nothing).
    database_write_made: bool = False
    stored_record_created: bool = False
    packet_row_updated: bool = False
    report_draft_row_updated: bool = False
    review_records_write_made: bool = False
    agent_run_records_write_made: bool = False
    review_approval_made: bool = False
    client_facing_output_created: bool = False
    financial_verification_made: bool = False
    capsule_publication_made: bool = False
    agent_execution_made: bool = False
    mock_agent_execution_made: bool = False
    llm_call_made: bool = False
    agentnet_call_made: bool = False
    resolver_call_made: bool = False
    network_call_made: bool = False


# --------------------------------------------------------------------------- safety helpers

MAX_ID_LEN = 128
#: A safe short ref/id: no whitespace, no newlines, no quotes, bounded length.
SAFE_REF_RE = re.compile(r"^[A-Za-z0-9_.:/\-]{1,128}$")
_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")
_STACKTRACE_RE = re.compile(
    r"traceback \(most recent call last\)|File \"[^\"]+\", line \d+", re.IGNORECASE)
_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")

#: Prohibited attribute-name markers, scanned only on *unexpected* request attributes. Declared
#: request fields are the known-safe identity/ref set and are value-scanned instead.
PROHIBITED_KEY_MARKERS = (
    "database_url", "db_url", "dsn", "connection_string",
    "raw_sql", "sql_statement", "sql_text",
    "source_bytes", "file_bytes", "raw_source",
    "generated_output", "agent_output", "llm_output", "llm_prompt", "prompt_text",
    "raw_evidence_text", "raw_evidence", "evidence_text",
    "raw_interview_text", "raw_interview", "interview_text",
    "note_text", "raw_note_text", "raw_content", "raw_text", "raw_packet", "packet_payload",
    "payload", "report_prose", "recommendation_text", "findings_text",
    "final_client_report", "client_facing_output", "client_report",
    "approve_internal", "approve_client_facing", "approval_decision", "signoff", "sign_off",
    "send_to_client", "publish_report", "export_client_deliverable",
    "publish_capsule", "agentnet_publish", "publish",
    "verify_financial", "financial_verif", "roi_verified", "savings_verified",
    "resolver_credentials", "credential", "credentials",
    "password", "passwd", "secret", "api_key", "apikey", "access_key", "private_key", "token",
    "stack_trace", "traceback",
)

#: The declared request fields that must be short safe refs/ids when supplied.
REQUEST_REF_FIELDS = ("owner_id", "client_id", "engagement_id", "authorization_scope",
                      "requested_by", "requester_role", "internal_assessment_report_draft_id",
                      "internal_report_review_packet_id", "expected_report_plan_id")
REQUIRED_IDENTITY_FIELDS = ("owner_id", "client_id", "engagement_id", "authorization_scope",
                            "requested_by", "requester_role")
REQUIRED_CHAIN_FIELDS = ("internal_assessment_report_draft_id",
                         "internal_report_review_packet_id")


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def value_marker(value) -> Optional[str]:
    """Return a marker *category* for an unsafe value, or ``None``. Never returns the value.

    Delegates to the public Phase 32 :func:`classify_prohibited_value_marker` and adds a
    stack-trace shape on top of it.
    """
    if not isinstance(value, str):
        return None
    if _STACKTRACE_RE.search(value):
        return "stack-trace"
    return classify_prohibited_value_marker(value)


def sanitize_text(value) -> str:
    """Return a string safe to place in a reason/warning list, or a category-only placeholder."""
    if not isinstance(value, str):
        return ""
    category = value_marker(value)
    if category is None:
        return value
    return f"[redacted: {category} marker in message]"


def sanitize_messages(values) -> List[str]:
    """Sanitize a list of reason/warning strings (see :func:`sanitize_text`)."""
    return [sanitize_text(v) for v in (values or []) if isinstance(v, str)]


def _safe_name(name) -> str:
    if isinstance(name, str) and _SAFE_NAME_RE.match(name):
        return name
    return "<unsafe-field-name>"


def _safe_label(value, allowed) -> Optional[str]:
    """Echo a stored label only when it is inside a closed, known-safe vocabulary.

    ``None`` passes through as ``None`` (a nullable column is not an unsafe value); anything else
    outside the vocabulary becomes ``'<unrecognized>'`` so no stored string is ever echoed.
    """
    if value is None:
        return None
    return value if isinstance(value, str) and value in allowed else "<unrecognized>"


def _unexpected_attr_names(request) -> List[str]:
    declared = set(getattr(type(request), "__dataclass_fields__", {}))
    own = getattr(request, "__dict__", None) or {}
    return [k for k in own if isinstance(k, str) and k not in declared]


# --------------------------------------------------------------------------- request pre-flight


def evaluate_internal_report_review_workflow_request(request) -> Optional[Tuple[str, str]]:
    """Validate the request itself. Returns ``(reason_code, message)`` on denial, else ``None``.

    Runs entirely DB-free: a denial here means **no database connection was ever opened**. No
    caller value is ever echoed — only a field name and a marker *category*.
    """
    if not isinstance(request, InternalReportReviewWorkflowRequest):
        return ("invalid_request_type", "request is not an InternalReportReviewWorkflowRequest")

    # 1. Unexpected attributes carrying prohibited names (payloads, prose, credentials, SQL, ...).
    for name in sorted(_unexpected_attr_names(request)):
        low = name.lower()
        if any(marker in low for marker in PROHIBITED_KEY_MARKERS):
            return ("prohibited_request_key",
                    f"request carries a prohibited attribute '{_safe_name(name)}' "
                    "(value not echoed)")

    # 2. Value safety on every declared string field, before any structural check.
    for name in sorted(getattr(type(request), "__dataclass_fields__", {})):
        category = value_marker(getattr(request, name, None))
        if category is not None:
            return ("prohibited_request_value",
                    f"request field '{_safe_name(name)}' carries a {category} marker "
                    "(value not echoed)")

    # 3. Required identity / traceability fields.
    for attr in REQUIRED_IDENTITY_FIELDS:
        if _is_blank(getattr(request, attr, None)):
            return ("missing_identity_field", f"request.{attr} is required")

    # 4. Required stored-chain refs.
    for attr in REQUIRED_CHAIN_FIELDS:
        if _is_blank(getattr(request, attr, None)):
            return ("missing_chain_ref", f"request.{attr} is required")

    # 5. Every supplied ref must be a short safe id/label.
    for attr in REQUEST_REF_FIELDS:
        value = getattr(request, attr, None)
        if value is None:
            continue
        if not isinstance(value, str) or len(value) > MAX_ID_LEN or not SAFE_REF_RE.match(value):
            return ("unsafe_request_ref",
                    f"request.{attr} must be a short safe ref/id of at most {MAX_ID_LEN} "
                    "characters (value not echoed)")

    # 6. A revoked scope is never workable, whatever the stored Engagement says.
    if request.authorization_scope in BLOCKED_AUTHORIZATION_SCOPES:
        return ("blocked_authorization_scope",
                "authorization_scope 'revoked' is not permitted")

    # 7. An expected plan fingerprint, when supplied, must be a sha256 hex digest.
    fingerprint = request.expected_plan_fingerprint
    if fingerprint is not None and not _SHA256_HEX_RE.match(str(fingerprint)):
        return ("invalid_expected_plan_fingerprint",
                "request.expected_plan_fingerprint must be a 64-character sha256 hex digest")

    # 8. strict_mode must be an explicit bool.
    if not isinstance(request.strict_mode, bool):
        return ("invalid_strict_mode", "strict_mode must be a bool")

    return None


# --------------------------------------------------------------------------- stored validation


def _stored_engagement_blocker(engagement, request) -> Optional[Tuple[str, str, str]]:
    """Validate the stored ``Engagement`` — the authorization subject.

    Returns ``(workflow_state, reason_code, message)`` on a blocker. Identity matching is
    necessary but **not** sufficient: the stored ``authorization_scope`` must match too.
    """
    S = InternalReportReviewWorkflowState
    if engagement is None:
        return (S.BLOCKED_MISSING_ENGAGEMENT, "missing_engagement",
                "stored engagement not found")
    stored_scope = getattr(engagement, "authorization_scope", None)
    if _is_blank(stored_scope):
        return (S.BLOCKED_SCOPE_MISMATCH, "missing_stored_authorization_scope",
                "stored engagement carries no authorization_scope")
    if stored_scope != request.authorization_scope:
        return (S.BLOCKED_SCOPE_MISMATCH, "authorization_scope_mismatch",
                "request.authorization_scope does not match the stored engagement's "
                "authorization_scope (identity matching is necessary but not sufficient)")
    if getattr(engagement, "owner_id", None) != request.owner_id:
        return (S.BLOCKED_SCOPE_MISMATCH, "engagement_identity_mismatch",
                "stored engagement owner_id does not match request.owner_id")
    if getattr(engagement, "client_id", None) != request.client_id:
        return (S.BLOCKED_SCOPE_MISMATCH, "engagement_identity_mismatch",
                "stored engagement client_id does not match request.client_id")
    if getattr(engagement, "id", None) != request.engagement_id:
        return (S.BLOCKED_SCOPE_MISMATCH, "engagement_identity_mismatch",
                "stored engagement id does not match request.engagement_id")
    if getattr(engagement, "lifecycle_status", None) in BLOCKED_LIFECYCLE_STATUSES:
        return (S.BLOCKED_SCOPE_MISMATCH, "blocked_engagement_lifecycle",
                "stored engagement lifecycle_status is revoked / archived / "
                "deleted_reference_only")
    return None


def _stored_report_draft_blocker(draft, request) -> Optional[Tuple[str, str, str]]:
    """Validate the stored Phase 37 report draft. Never modifies it."""
    S = InternalReportReviewWorkflowState
    if draft is None:
        return (S.BLOCKED_MISSING_REPORT_DRAFT, "missing_report_draft",
                "stored internal assessment report draft not found")
    invalid = S.BLOCKED_INVALID_REPORT_DRAFT
    for attr in ("owner_id", "client_id", "engagement_id", "authorization_scope"):
        if getattr(draft, attr, None) != getattr(request, attr, None):
            return (S.BLOCKED_SCOPE_MISMATCH, "report_draft_identity_mismatch",
                    f"stored report draft {attr} does not match request.{attr}")
    if request.expected_report_plan_id is not None \
            and getattr(draft, "report_plan_id", None) != request.expected_report_plan_id:
        return (invalid, "report_draft_plan_mismatch",
                "stored report draft report_plan_id does not match "
                "request.expected_report_plan_id")
    if request.expected_plan_fingerprint is not None \
            and getattr(draft, "plan_fingerprint", None) != request.expected_plan_fingerprint:
        return (invalid, "report_draft_plan_mismatch",
                "stored report draft plan_fingerprint does not match "
                "request.expected_plan_fingerprint")
    if getattr(draft, "audience", None) != AUDIENCE_INTERNAL:
        return (invalid, "report_draft_not_internal",
                f"stored report draft audience is not '{AUDIENCE_INTERNAL}'")
    if getattr(draft, "output_status", None) != REQUIRED_DRAFT_OUTPUT_STATUS:
        return (invalid, "report_draft_invalid_output_status",
                f"stored report draft output_status is not '{REQUIRED_DRAFT_OUTPUT_STATUS}'")
    if getattr(draft, "review_status", None) != REQUIRED_DRAFT_REVIEW_STATUS:
        return (invalid, "report_draft_invalid_review_status",
                f"stored report draft review_status is not '{REQUIRED_DRAFT_REVIEW_STATUS}'")
    if getattr(draft, "lifecycle_status", None) != REQUIRED_DRAFT_LIFECYCLE_STATUS:
        return (invalid, "report_draft_invalid_lifecycle_status",
                f"stored report draft lifecycle_status is not "
                f"'{REQUIRED_DRAFT_LIFECYCLE_STATUS}'")
    for flag in DRAFT_REQUIRED_FALSE_FLAGS:
        if getattr(draft, flag, False) is not False:
            return (invalid, "report_draft_posture_elevated",
                    f"stored report draft {flag} must be false")
    if getattr(draft, "requires_human_review", True) is not True:
        return (invalid, "report_draft_posture_elevated",
                "stored report draft requires_human_review must be true")
    return None


def _stored_review_packet_blocker(packet, request, draft) -> Optional[Tuple[str, str, str]]:
    """Validate the stored Phase 38 review packet against the request and the stored draft.

    The ``reviewer_decision_status`` / ``reviewer_decision_record_id`` columns are **not** checked
    here: Phase 39 is insert-only, so they are only explicable once the decision rows are loaded.
    See :func:`_packet_decision_linkage_blocker`.
    """
    S = InternalReportReviewWorkflowState
    if packet is None:
        return (S.BLOCKED_MISSING_REVIEW_PACKET, "missing_review_packet",
                "stored internal report review packet not found")
    invalid = S.BLOCKED_INVALID_REVIEW_PACKET
    for attr in ("owner_id", "client_id", "engagement_id", "authorization_scope"):
        if getattr(packet, attr, None) != getattr(request, attr, None):
            return (S.BLOCKED_SCOPE_MISMATCH, "review_packet_identity_mismatch",
                    f"stored review packet {attr} does not match request.{attr}")
    if getattr(packet, "internal_assessment_report_draft_id", None) \
            != request.internal_assessment_report_draft_id:
        return (invalid, "review_packet_draft_mismatch",
                "stored review packet internal_assessment_report_draft_id does not match "
                "request.internal_assessment_report_draft_id")
    for attr in ("report_plan_id", "plan_fingerprint"):
        if getattr(packet, attr, None) != getattr(draft, attr, None):
            return (invalid, "review_packet_linkage_mismatch",
                    f"stored review packet {attr} does not match the stored report draft's "
                    f"{attr}")
    if getattr(packet, "audience", None) != AUDIENCE_INTERNAL:
        return (invalid, "review_packet_not_internal",
                f"stored review packet audience is not '{AUDIENCE_INTERNAL}'")
    if getattr(packet, "packet_status", None) != REQUIRED_PACKET_STATUS:
        return (invalid, "review_packet_invalid_status",
                f"stored review packet packet_status is not '{REQUIRED_PACKET_STATUS}'")
    if getattr(packet, "review_status", None) != REQUIRED_PACKET_REVIEW_STATUS:
        return (invalid, "review_packet_invalid_review_status",
                f"stored review packet review_status is not '{REQUIRED_PACKET_REVIEW_STATUS}'")
    if getattr(packet, "lifecycle_status", None) != REQUIRED_PACKET_LIFECYCLE_STATUS:
        return (invalid, "review_packet_invalid_lifecycle_status",
                f"stored review packet lifecycle_status is not "
                f"'{REQUIRED_PACKET_LIFECYCLE_STATUS}'")
    for flag in PACKET_REQUIRED_FALSE_FLAGS:
        if getattr(packet, flag, False) is not False:
            return (invalid, "review_packet_posture_elevated",
                    f"stored review packet {flag} must be false")
    if getattr(packet, "requires_human_review", True) is not True:
        return (invalid, "review_packet_posture_elevated",
                "stored review packet requires_human_review must be true")
    return None


def _packet_decision_linkage_blocker(packet, decision_ids,
                                     effective_status) -> Optional[Tuple[str, str, str]]:
    """Reconcile the packet row's own decision columns against the computed decision rows.

    Phase 38 creates a packet with ``reviewer_decision_status='not_decided'`` and a null
    ``reviewer_decision_record_id``, and Phase 39 never updates them — so any other stored value
    was not produced by the controlled path. It is accepted **only** when the located decision
    records explain it, and is a blocker otherwise. Phase 40 never repairs it by writing.
    """
    S = InternalReportReviewWorkflowState
    stored_status = getattr(packet, "reviewer_decision_status", None)
    stored_ref = getattr(packet, "reviewer_decision_record_id", None)
    if stored_status != PACKET_NOT_DECIDED:
        if not decision_ids or stored_status != effective_status:
            return (S.BLOCKED_INVALID_REVIEW_PACKET, "review_packet_decision_status_unexplained",
                    f"stored review packet reviewer_decision_status is not "
                    f"'{PACKET_NOT_DECIDED}' and is not explained by the located packet decision "
                    "records")
    if stored_ref is not None and stored_ref not in decision_ids:
        return (S.BLOCKED_INVALID_REVIEW_PACKET, "review_packet_decision_ref_unexplained",
                "stored review packet reviewer_decision_record_id does not name any located "
                "packet decision record")
    return None


# --------------------------------------------------------------------------- decision loading


def _load_decision_rows(session, request, draft):
    """Locate the Phase 39 decision rows for this exact chain, deterministically ordered.

    ORM query only — no raw SQL, no ``session.execute``. The filter pins every identity and
    linkage axis, so a row from another tenant, engagement, packet, draft, or plan revision can
    never be counted.
    """
    from peak.db.models import InternalReportReviewPacketDecisionRecord as Decision

    return (session.query(Decision)
            .filter(Decision.owner_id == request.owner_id,
                    Decision.client_id == request.client_id,
                    Decision.engagement_id == request.engagement_id,
                    Decision.authorization_scope == request.authorization_scope,
                    Decision.internal_report_review_packet_id
                    == request.internal_report_review_packet_id,
                    Decision.internal_assessment_report_draft_id
                    == request.internal_assessment_report_draft_id,
                    Decision.report_plan_id == getattr(draft, "report_plan_id", None),
                    Decision.plan_fingerprint == getattr(draft, "plan_fingerprint", None))
            .order_by(Decision.id)
            .all())


def _classify_decision_rows(rows) -> Tuple[List[object], List[str]]:
    """Split located rows into the effective set and a warning list. Never echoes a stored value."""
    effective: List[object] = []
    warnings: List[str] = []
    for index, row in enumerate(rows):
        intent = getattr(row, "decision_intent", None)
        status = getattr(row, "decision_status", None)
        if getattr(row, "decision_scope", None) != PACKET_DECISION_SCOPE:
            warnings.append(f"packet decision record [{index}] has a decision_scope other than "
                            f"'{PACKET_DECISION_SCOPE}' and was excluded")
            continue
        if getattr(row, "audience", None) != AUDIENCE_INTERNAL:
            warnings.append(f"packet decision record [{index}] audience is not "
                            f"'{AUDIENCE_INTERNAL}' and was excluded")
            continue
        if intent not in ALLOWED_DECISION_INTENTS or intent not in INTENT_WORKFLOW_STATES:
            warnings.append(f"packet decision record [{index}] carries a decision_intent outside "
                            "the closed internal vocabulary and was excluded")
            continue
        if status != EXPECTED_DECISION_STATUS_BY_INTENT[intent]:
            warnings.append(f"packet decision record [{index}] decision_status is inconsistent "
                            "with its decision_intent and was excluded")
            continue
        effective.append(row)
    return effective, warnings


def derive_workflow_state(positions) -> Tuple[str, str]:
    """Map the distinct ``(decision_intent, decision_status)`` positions to the computed states.

    ``positions`` is an ordered, de-duplicated sequence of tuples. Zero -> awaiting; exactly one
    (however many rows expressed it) -> that decision's state; more than one materially different
    position -> ``conflicting_decisions``, which this layer never resolves automatically.
    """
    S = InternalReportReviewWorkflowState
    if not positions:
        return S.AWAITING_REVIEWER_DECISION, ComputedPacketDecisionState.AWAITING_DECISION
    if len(positions) > 1:
        return S.CONFLICTING_DECISIONS, ComputedPacketDecisionState.CONFLICTED
    intent, status = positions[0]
    return INTENT_WORKFLOW_STATES[intent], status


# --------------------------------------------------------------------------- public entry point


def summarize_internal_report_review_workflow(
    request, *, session_factory=None
) -> InternalReportReviewWorkflowResult:
    """Summarize one internal report review workflow, read-only.

    ``request`` is an :class:`InternalReportReviewWorkflowRequest`. ``session_factory`` is a
    zero-arg callable returning a SQLAlchemy ``Session``; it is **required** and is never defaulted
    from the environment, so a caller without one is denied before any connection is opened.

    Loads the stored ``Engagement``, the Phase 37 report draft, the Phase 38 review packet, and the
    Phase 39 packet decision rows; validates them; and returns a deterministic computed workflow
    state. It writes nothing, updates no packet or report-draft row, approves nothing for client
    use, and echoes no stored content.

    Expected governance failures are typed blockers, not exceptions.
    """
    result = InternalReportReviewWorkflowResult()

    # --- 1. Request pre-flight (DB-free; no connection opened on denial) ---
    denial = evaluate_internal_report_review_workflow_request(request)
    if denial is not None:
        result.outcome = InternalReportReviewWorkflowOutcome.DENIED
        result.reason_code = denial[0]
        result.reasons = sanitize_messages([denial[1]])
        return result

    result.owner_id = request.owner_id
    result.client_id = request.client_id
    result.engagement_id = request.engagement_id
    result.authorization_scope = request.authorization_scope
    result.internal_assessment_report_draft_id = request.internal_assessment_report_draft_id
    result.internal_report_review_packet_id = request.internal_report_review_packet_id
    result.strict_mode = bool(request.strict_mode)

    # --- 2. No injected session factory -> fail closed (never reach for an ambient DSN) ---
    if session_factory is None:
        result.outcome = InternalReportReviewWorkflowOutcome.DENIED
        result.reason_code = "missing_session_factory"
        result.reasons = ["no session_factory was injected; this layer never falls back to an "
                          "environment database URL"]
        return result

    # --- 3. Read-only load + validation ---
    try:
        session = session_factory()
    except Exception:  # pragma: no cover - defensive; never echoes the exception
        result.outcome = InternalReportReviewWorkflowOutcome.FAILED
        result.reason_code = "session_unavailable"
        result.reasons = ["could not open a database session (detail withheld)"]
        return result

    try:
        _summarize_with_session(session, request, result)
    except Exception:
        result.outcome = InternalReportReviewWorkflowOutcome.FAILED
        result.permitted = False
        result.reason_code = "read_failed"
        result.reasons = ["a read failed while loading the internal report review chain "
                          "(detail withheld); nothing was written"]
        result.workflow_state = None
        result.computed_packet_decision_state = ComputedPacketDecisionState.NOT_COMPUTED
    finally:
        try:
            session.close()
        except Exception:  # pragma: no cover - close failures are not reportable state
            pass

    return result


def _summarize_with_session(session, request, result) -> None:
    """Do the read-only work. Raises only on real read failures (handled by the caller)."""
    from peak.db.models import (
        Engagement,
        InternalAssessmentReportDraftRecord,
        InternalReportReviewPacketRecord,
    )

    result.database_connection_made = True
    result.sql_execution_made = True

    trace = InternalReportReviewWorkflowTrace(
        engagement_ref=request.engagement_id,
        report_draft_ref=request.internal_assessment_report_draft_id,
        review_packet_ref=request.internal_report_review_packet_id,
    )
    result.trace = trace

    # 3a. Stored Engagement is the authorization subject.
    engagement = session.get(Engagement, request.engagement_id)
    blocker = _stored_engagement_blocker(engagement, request)
    if blocker is not None:
        return _block(result, blocker)

    # 3b. Stored Phase 37 report draft.
    draft = session.get(InternalAssessmentReportDraftRecord,
                        request.internal_assessment_report_draft_id)
    blocker = _stored_report_draft_blocker(draft, request)
    if blocker is not None:
        return _block(result, blocker)
    result.report_plan_id = getattr(draft, "report_plan_id", None)
    result.plan_fingerprint = getattr(draft, "plan_fingerprint", None)
    trace.report_plan_id = result.report_plan_id
    trace.plan_fingerprint = result.plan_fingerprint
    trace.report_draft_payload_fingerprint = getattr(draft, "payload_fingerprint", None)

    # 3c. Stored Phase 38 review packet.
    packet = session.get(InternalReportReviewPacketRecord,
                         request.internal_report_review_packet_id)
    blocker = _stored_review_packet_blocker(packet, request, draft)
    if blocker is not None:
        return _block(result, blocker)
    trace.packet_payload_fingerprint = getattr(packet, "payload_fingerprint", None)
    trace.stored_packet_reviewer_decision_status = _safe_label(
        getattr(packet, "reviewer_decision_status", None),
        {PACKET_NOT_DECIDED, DECISION_STATUS_RECORDED, DECISION_STATUS_NEEDS_FOLLOWUP})
    trace.stored_packet_reviewer_decision_record_id = getattr(
        packet, "reviewer_decision_record_id", None)

    # 3d. Phase 39 decision rows for this exact chain.
    rows = _load_decision_rows(session, request, draft)
    effective, row_warnings = _classify_decision_rows(rows)
    result.warnings.extend(sanitize_messages(row_warnings))
    trace.decision_records_found = len(rows)
    trace.decision_records_considered = len(effective)
    trace.decision_records_skipped = len(rows) - len(effective)

    decision_ids = [str(getattr(row, "id", "")) for row in effective]
    intents = [_safe_label(getattr(row, "decision_intent", None), ALLOWED_DECISION_INTENTS)
               for row in effective]
    statuses = [_safe_label(getattr(row, "decision_status", None),
                            {DECISION_STATUS_RECORDED, DECISION_STATUS_NEEDS_FOLLOWUP})
                for row in effective]
    result.decision_record_ids = decision_ids
    result.decision_intents = intents
    result.decision_statuses = statuses
    result.decision_record_count = len(effective)
    trace.decision_record_refs = list(decision_ids)

    # 3e. Distinct materially different decision positions, in first-seen order.
    positions: List[Tuple[str, str]] = []
    for pair in zip(intents, statuses):
        if pair not in positions:
            positions.append(pair)
    trace.distinct_decision_positions = len(positions)

    workflow_state, packet_decision_state = derive_workflow_state(positions)

    # 3f. Reconcile the packet row's own decision columns (never repaired by writing).
    effective_status = packet_decision_state if len(positions) == 1 else None
    blocker = _packet_decision_linkage_blocker(packet, decision_ids, effective_status)
    if blocker is not None:
        return _block(result, blocker)

    result.workflow_state = workflow_state
    result.computed_packet_decision_state = packet_decision_state
    result.outcome = InternalReportReviewWorkflowOutcome.SUMMARIZED
    result.permitted = True

    if workflow_state == InternalReportReviewWorkflowState.CONFLICTING_DECISIONS:
        result.reason_code = "conflicting_decisions"
        result.reasons.append(
            f"{len(positions)} materially different packet decision positions were located for "
            "this review packet; Phase 40 does not resolve competing decisions automatically")
    elif workflow_state == InternalReportReviewWorkflowState.AWAITING_REVIEWER_DECISION:
        result.reason_code = "awaiting_reviewer_decision"
        result.reasons.append(
            "no packet decision record was located for this review packet; the state is derived "
            "from the packet decision table, not from the packet row")
    else:
        result.reason_code = "workflow_state_computed"
        result.reasons.append(
            "computed from the located packet decision record(s); the Phase 38 packet row was "
            "not updated and still carries its own stored decision columns")

    # 3g. Strict mode: a warning makes the summary non-permitted; the state is still reported.
    if request.strict_mode and result.warnings:
        result.permitted = False
        result.outcome = InternalReportReviewWorkflowOutcome.BLOCKED
        result.reason_code = "strict_mode_warning"
        result.reasons.append(
            "strict_mode: the summary is not permitted because the workflow produced a warning")


def _block(result, blocker: Tuple[str, str, str]) -> None:
    """Record a typed blocker. The computed decision state stays uncomputed."""
    workflow_state, reason_code, message = blocker
    result.outcome = InternalReportReviewWorkflowOutcome.BLOCKED
    result.permitted = False
    result.workflow_state = workflow_state
    result.reason_code = reason_code
    result.reasons.append(sanitize_text(message))
