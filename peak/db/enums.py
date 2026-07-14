"""Governance state enums for the controlled database.

**Source of truth:** the Phase 9 schema contracts
(schemas/governance-state.schema.json, authorization-scope.schema.json,
review-status.schema.json, lifecycle-status.schema.json) and docs/GOVERNANCE_STATES.md.
These Python enums mirror those canonical values for app-side use; they must stay in
sync with the schemas (the Phase 11 validator checks this alignment). Values are stored
as strings in the database (see peak/db/base.py).
"""

from __future__ import annotations

from enum import Enum


class AuthorizationScope(str, Enum):
    engagement_authorized = "engagement_authorized"
    internal_peak_only = "internal_peak_only"
    client_private = "client_private"
    client_facing_candidate = "client_facing_candidate"
    client_facing_approved = "client_facing_approved"
    methodology_candidate = "methodology_candidate"
    peak_methodology = "peak_methodology"
    fixture_test = "fixture_test"
    revoked = "revoked"


class ReviewStatus(str, Enum):
    draft = "draft"
    needs_review = "needs_review"
    consultant_reviewed = "consultant_reviewed"
    qa_reviewed = "qa_reviewed"
    approved_internal = "approved_internal"
    client_facing_approved = "client_facing_approved"
    rejected = "rejected"
    superseded = "superseded"
    archived = "archived"


class LifecycleStatus(str, Enum):
    active = "active"
    pending = "pending"
    draft = "draft"
    superseded = "superseded"
    revoked = "revoked"
    archived = "archived"
    deleted_reference_only = "deleted_reference_only"


class EvidenceStatus(str, Enum):
    collected = "collected"
    source_labeled = "source_labeled"
    needs_verification = "needs_verification"
    verified = "verified"
    disputed = "disputed"
    superseded = "superseded"
    excluded = "excluded"
    archived = "archived"


class FinancialImpactStatus(str, Enum):
    not_assessed = "not_assessed"
    reported = "reported"
    estimated = "estimated"
    calculated = "calculated"
    finance_review_needed = "finance_review_needed"
    finance_reviewed = "finance_reviewed"
    verified = "verified"
    rejected = "rejected"
    client_facing_approved = "client_facing_approved"


class ResolverCapsuleStatus(str, Enum):
    draft_capsule = "draft_capsule"
    private_client_capsule = "private_client_capsule"
    reviewed_private = "reviewed_private"
    active_private = "active_private"
    methodology_candidate = "methodology_candidate"
    approved_methodology = "approved_methodology"
    superseded = "superseded"
    revoked = "revoked"
    archived = "archived"


class SourceSystemAccessStatus(str, Enum):
    not_requested = "not_requested"
    requested = "requested"
    granted = "granted"
    partial = "partial"
    denied = "denied"
    expired = "expired"
    revoked = "revoked"


class ClientFacingApprovalStatus(str, Enum):
    not_client_facing = "not_client_facing"
    client_facing_candidate = "client_facing_candidate"
    requires_review = "requires_review"
    approved_for_client = "approved_for_client"
    rejected_for_client = "rejected_for_client"
    withdrawn = "withdrawn"


def values(enum_cls) -> list[str]:
    """Return the string values of an enum class (helper for validation)."""
    return [m.value for m in enum_cls]
