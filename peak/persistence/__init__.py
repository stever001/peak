"""Peak controlled DB writer boundary (Phase 17).

The policy and validation boundary a *future* controlled DB writer will pass through. It
defines **what may be written** (a table/action allowlist), **which governance checks are
required** (identity, stored-scope comparison, lifecycle, prohibited effects), and **how
no-op write plans are validated** — all **DB-aware but not DB-writing**.

This package is deliberately kept out of ``peak.db`` and stays **stdlib-only**: it imports
no SQLAlchemy, no Alembic, and no ``peak.db`` session/model modules. A future live writer
may bridge these contracts to ``peak.db`` models, but Phase 17 only defines the safe
boundary.

Across the package:

- **no database connection, no database read/write, no SQL execution, no stored records**;
- **no migrations, no seed data, no deletes, no credential/secret storage**;
- **no live LLM call, no AgentNet call, no MCP/resolver call, no network call**;
- **no file write, no client-facing approval, no financial verification, no capsule publication**.

A **write plan is not a write**. See docs/CONTROLLED_DB_WRITER_BOUNDARY.md and
docs/CONTROLLED_WRITE_ALLOWLIST.md.
"""

from __future__ import annotations

from .allowlist import (
    ALLOWED_ACTIONS,
    ALLOWED_TABLES,
    PROHIBITED_ACTION_SUBSTRINGS,
    PROHIBITED_TABLES,
    is_allowed_action,
    is_allowed_table,
    is_prohibited_action,
    is_prohibited_table,
)
from .contracts import (
    PROHIBITED_EFFECTS,
    ControlledWriteAuditDraft,
    ControlledWriteDecision,
    ControlledWritePlan,
    ControlledWriteRequest,
    ControlledWriteResult,
    ControlledWriteSubject,
)
from .governance import (
    ControlledWriteGovernanceDecision,
    build_controlled_write_decision,
    evaluate_controlled_write_request,
    validate_table_action_allowlist,
    validate_write_subject_scope,
)
from .write_plan import (
    build_controlled_write_audit_draft,
    build_controlled_write_plan,
    prepare_controlled_write,
)

__all__ = [
    # allowlist
    "ALLOWED_TABLES",
    "ALLOWED_ACTIONS",
    "PROHIBITED_TABLES",
    "PROHIBITED_ACTION_SUBSTRINGS",
    "is_allowed_table",
    "is_allowed_action",
    "is_prohibited_table",
    "is_prohibited_action",
    # contracts
    "PROHIBITED_EFFECTS",
    "ControlledWriteSubject",
    "ControlledWriteRequest",
    "ControlledWriteDecision",
    "ControlledWritePlan",
    "ControlledWriteResult",
    "ControlledWriteAuditDraft",
    # governance
    "ControlledWriteGovernanceDecision",
    "evaluate_controlled_write_request",
    "validate_write_subject_scope",
    "validate_table_action_allowlist",
    "build_controlled_write_decision",
    # write plan
    "build_controlled_write_plan",
    "build_controlled_write_audit_draft",
    "prepare_controlled_write",
]
