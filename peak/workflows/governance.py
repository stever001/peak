"""DB-free governance for the Managed Record Workflow integration layer (Phase 35).

Every check here runs **before** any narrow writer is invoked and therefore before any database
connection is opened. Pure stdlib + DB-free peak contracts — no SQLAlchemy, no Alembic, no
``peak.db`` import at module scope (the one draft type that lives in ``peak.db.writer_contracts``
is a stdlib-only dataclass and is imported lazily so this module stays importable without a driver).

Three families of check:

1. **Request pre-flight** — identity/traceability fields, non-revoked scope, valid gate mapping,
   valid workflow identity.
2. **Payload safety** — the payload must be the exact draft type its stage's narrow writer accepts;
   prohibited keys/values are denied here, before the writer is called. Only field names and marker
   *categories* are ever reported — never the offending value.
3. **Identity consistency** — every stage payload must match the workflow's
   owner/client/engagement, and its ``authorization_scope`` where the draft carries one.
   Cross-tenant / cross-engagement payloads are denied before any write.

This layer never weakens writer authorization: the narrow writers still load the stored
``Engagement`` and compare its stored ``authorization_scope`` at write time. These checks are
defense in depth, not the authorization gate.

See docs/WORKFLOW_INTEGRATION_GOVERNANCE_POLICY.md.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# DB-free Phase 32 public value classifier (categories only; never echoes a value).
from peak.reviewer_decisions.governance import classify_prohibited_value_marker

from .contracts import (
    IDEMPOTENCY_NAMESPACE,
    IDEMPOTENCY_SEPARATOR,
    MAX_IDEMPOTENCY_KEY_LEN,
    STAGE_AGENT_TASK_QUEUE,
    STAGE_EVIDENCE_REFERENCE,
    STAGE_INTAKE_NOTE,
    STAGE_PAYLOAD_ATTRS,
    STAGE_REVIEW_BUNDLE,
    STAGE_REVIEWER_DECISION,
    STAGE_SOURCE_INGESTION,
    WORKFLOW_STAGES,
)

BLOCKED_AUTHORIZATION_SCOPES = frozenset({"revoked"})
MAX_ID_LEN = 128
MAX_WORKFLOW_ID_LEN = 96

#: A safe short ref/id: no whitespace, no newlines, no quotes, bounded length.
SAFE_REF_RE = re.compile(r"^[A-Za-z0-9_.:/\-]{1,128}$")
#: Structural JSON-dump shapes. The Phase 32 classifier reports 'JSON/object' for any value that
#: merely *starts* with a bracket, which legitimately fires on worker-generated titles such as
#: "[draft] visual_observation — receiving_dock". On non-ref fields the verdict is therefore
#: narrowed to values that actually look like a dumped object/array: a balanced brace/bracket pair
#: or an embedded ``"key":`` pair. Ref/label fields keep the strict verdict (and are additionally
#: constrained by SAFE_REF_RE, which forbids brackets outright).
_JSON_KEYVALUE_RE = re.compile(r'"[^"\n]{1,64}"\s*:')
#: A safe workflow id: tighter still (no path/scheme separators).
SAFE_WORKFLOW_ID_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,96}$")

#: Prohibited payload *keys*. A stage payload carrying any attribute whose name matches one of
#: these (exactly, or as a substring for the structural markers) is denied before the writer runs.
#: Legitimate draft posture flags (``client_facing_approved``, ``publication_allowed``,
#: ``capsule_candidate_ready``, ``execution_allowed``, ``agentnet_context_allowed``, …) are part of
#: each stage's known field set and are never scanned here — only *unexpected* attributes are.
PROHIBITED_KEY_MARKERS = (
    "database_url", "db_url", "dsn", "connection_string",
    "raw_sql", "sql_statement", "sql_text",
    "source_bytes", "file_bytes", "raw_source",
    "generated_output", "agent_output", "llm_output", "llm_prompt", "prompt_text",
    "raw_evidence_text", "raw_evidence", "evidence_text",
    "raw_interview_text", "raw_interview", "interview_text",
    "raw_content", "raw_text", "raw_packet", "packet_payload", "payload",
    "final_client_report", "client_facing_output", "client_report",
    "approve_internal", "approve_client_facing", "approval_decision", "signoff", "sign_off",
    "publish_capsule", "agentnet_publish", "publish",
    "resolver_credentials", "credential", "credentials",
    "password", "passwd", "secret", "api_key", "apikey", "access_key", "private_key", "token",
    "stack_trace", "traceback",
)

#: Long-form fields that legitimately carry authorized operational prose destined for the managed
#: DB. They are **never** scanned by this layer's value classifier (ordinary prose must pass) and
#: are **never** echoed into any result. Content safety for these is enforced by the owning narrow
#: writer — Phase 34's hardened credential-disclosure scanner for ``note_text``.
PROSE_EXEMPT_FIELDS = frozenset({"note_text"})

#: Per-stage id/ref fields that must be short, safe refs (never prose, never raw content).
STAGE_REF_FIELDS = {
    STAGE_INTAKE_NOTE: ("source_ref", "source_ingestion_record_id",
                        "related_evidence_reference_id", "related_review_bundle_record_id"),
    STAGE_SOURCE_INGESTION: ("packet_reference_id", "packet_location_reference", "packet_hash"),
    STAGE_EVIDENCE_REFERENCE: ("source_reference_id",),
    STAGE_AGENT_TASK_QUEUE: ("task_input_ref", "source_ingestion_record_id",
                             "evidence_reference_ids", "packet_processing_run_ref",
                             "orchestration_ref"),
    STAGE_REVIEW_BUNDLE: ("packet_processing_receipt_ref", "source_ingestion_record_ids",
                          "evidence_reference_ids", "agent_task_queue_record_ids"),
    STAGE_REVIEWER_DECISION: ("review_bundle_ref", "review_bundle_record_id",
                              "review_bundle_draft_ref", "review_plan_item_refs",
                              "evidence_reference_ids", "source_ingestion_record_ids",
                              "agent_task_queue_record_ids"),
}

#: Per-stage safe, stable, **non-content** fields used to derive a deterministic stage
#: idempotency key when the caller supplies no explicit key. Never includes note/prose bodies.
STAGE_KEY_FIELDS = {
    STAGE_INTAKE_NOTE: ("note_type", "note_source", "captured_by", "source_ref",
                        "source_ingestion_record_id"),
    STAGE_SOURCE_INGESTION: ("packet_reference_id", "packet_schema_name", "packet_schema_version",
                             "packet_hash"),
    STAGE_EVIDENCE_REFERENCE: ("source_reference_id", "evidence_type", "operational_area",
                               "inventory_process_area"),
    STAGE_AGENT_TASK_QUEUE: ("agent_name", "workflow", "task_type", "requested_action"),
    STAGE_REVIEW_BUNDLE: ("packet_processing_receipt_ref", "reviewer_role", "review_scope"),
    STAGE_REVIEWER_DECISION: ("review_bundle_ref", "review_bundle_record_id", "reviewer_role",
                              "decision_intent"),
}

REQUIRED_IDENTITY_FIELDS = ("owner_id", "client_id", "engagement_id", "authorization_scope",
                            "requested_by", "requester_role")


@dataclass
class WorkflowGovernanceDecision:
    """Result of a DB-free governance check (no side effects, no value echo)."""

    permitted: bool = False
    reason_code: Optional[str] = None
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _deny(reason_code: str, message: str) -> WorkflowGovernanceDecision:
    return WorkflowGovernanceDecision(permitted=False, reason_code=reason_code, reasons=[message])


def _ok(warnings=None) -> WorkflowGovernanceDecision:
    return WorkflowGovernanceDecision(permitted=True, warnings=list(warnings or []))


def sanitize_text(value) -> str:
    """Return a value safe to place in a reason/warning list, or a category-only placeholder.

    Defense in depth: this layer never copies payload values into results, but writer reasons and
    caller-visible strings are re-scanned so a value that *would* carry a credential/DSN/raw-SQL/
    raw-content marker is replaced by its marker *category* instead of being echoed.
    """
    if not isinstance(value, str):
        return ""
    category = classify_prohibited_value_marker(value)
    if category is None:
        return value
    return f"[redacted: {category} marker in message]"


def sanitize_messages(values) -> List[str]:
    """Sanitize a list of reason/warning strings (see :func:`sanitize_text`)."""
    return [sanitize_text(v) for v in (values or []) if isinstance(v, str)]


def _looks_like_json_dump(value: str) -> bool:
    """True when a value really looks like a dumped object/array, not merely bracket-prefixed."""
    stripped = value.strip()
    if _JSON_KEYVALUE_RE.search(value):
        return True
    return ((stripped.startswith("{") and stripped.endswith("}"))
            or (stripped.startswith("[") and stripped.endswith("]")))


def classify_value_marker(value: str, *, strict_json: bool = True) -> Optional[str]:
    """Classify a field value, returning a marker *category* or ``None`` — never the value.

    Delegates to the public Phase 32 :func:`classify_prohibited_value_marker`. With
    ``strict_json=False`` (used for prose-ish, non-ref fields) a bare ``JSON/object`` verdict is
    narrowed by :func:`_looks_like_json_dump`, so a legitimate worker-generated title such as
    ``"[draft] visual_observation — receiving_dock"`` passes while an actual JSON dump still fails.
    Every other category (credential/secret, DB-URL/DSN, raw-SQL, raw-content) is always enforced.
    """
    category = classify_prohibited_value_marker(value)
    if category == "JSON/object" and not strict_json and not _looks_like_json_dump(value):
        return None
    return category


# --------------------------------------------------------------------------- draft types


def expected_draft_type(stage: str):
    """Return the exact draft dataclass the stage's narrow writer accepts (imported lazily).

    Lazy import keeps this module — and the whole ``peak.workflows`` package — importable without
    SQLAlchemy: only ``peak.db.writer_contracts`` is touched, which is stdlib-only by design.
    """
    if stage == STAGE_INTAKE_NOTE:
        from peak.db.writer_contracts import IntakeNoteDraft
        return IntakeNoteDraft
    if stage == STAGE_SOURCE_INGESTION:
        from peak.ingestion.contracts import SourceIngestionDraft
        return SourceIngestionDraft
    if stage == STAGE_EVIDENCE_REFERENCE:
        from peak.evidence.persistence_contracts import EvidencePersistenceDraft
        return EvidencePersistenceDraft
    if stage == STAGE_AGENT_TASK_QUEUE:
        from peak.task_queue.contracts import AgentTaskQueueDraft
        return AgentTaskQueueDraft
    if stage == STAGE_REVIEW_BUNDLE:
        from peak.review_orchestration.contracts import ReviewBundleDraft
        return ReviewBundleDraft
    if stage == STAGE_REVIEWER_DECISION:
        from peak.reviewer_decisions.contracts import InternalReviewerDecisionDraft
        return InternalReviewerDecisionDraft
    raise KeyError(stage)


def _known_field_names(stage: str) -> frozenset:
    """The declared dataclass field names for a stage's draft type."""
    draft_type = expected_draft_type(stage)
    return frozenset(getattr(draft_type, "__dataclass_fields__", {}).keys())


# --------------------------------------------------------------------------- request pre-flight


def evaluate_workflow_request(request) -> WorkflowGovernanceDecision:
    """Validate the workflow request itself. No payload is inspected here."""
    # 1. Concrete request type (reject duck-typed objects at the boundary).
    from .contracts import ManagedRecordWorkflowRequest

    if not isinstance(request, ManagedRecordWorkflowRequest):
        return _deny("invalid_request_type",
                     "request is not a ManagedRecordWorkflowRequest")

    # 2. Required identity / traceability fields.
    for attr in REQUIRED_IDENTITY_FIELDS:
        if _is_blank(getattr(request, attr, None)):
            return _deny("missing_identity_field", f"request.{attr} is required")
        value = getattr(request, attr)
        if not isinstance(value, str) or len(value) > MAX_ID_LEN:
            return _deny("invalid_identity_field",
                         f"request.{attr} must be a string of at most {MAX_ID_LEN} characters")

    # 3. Revoked scope is never workable.
    if request.authorization_scope in BLOCKED_AUTHORIZATION_SCOPES:
        return _deny("blocked_authorization_scope",
                     "authorization_scope 'revoked' is not permitted")

    # 4. Workflow id, when supplied, must be a safe short identifier.
    if not _is_blank(request.workflow_id):
        if not isinstance(request.workflow_id, str) \
                or not SAFE_WORKFLOW_ID_RE.match(request.workflow_id):
            return _deny("invalid_workflow_id",
                         "workflow_id must be a short safe identifier "
                         f"(<= {MAX_WORKFLOW_ID_LEN} chars, [A-Za-z0-9_.-])")

    # 5. Subject record id (the stored Engagement) must be safe when supplied explicitly.
    subject_id = request.subject_record_id or request.engagement_id
    if _is_blank(subject_id) or not SAFE_REF_RE.match(str(subject_id)):
        return _deny("invalid_subject_record_id",
                     "subject_record_id (or engagement_id) must be a short safe identifier")

    # 6. Gate mapping: known stage names, boolean values only.
    gates = request.persistence_gates
    if not isinstance(gates, dict):
        return _deny("invalid_persistence_gates", "persistence_gates must be a stage -> bool map")
    for stage, enabled in gates.items():
        if stage not in WORKFLOW_STAGES:
            return _deny("unknown_stage_gate",
                         f"persistence_gates contains unknown stage '{_safe_stage_name(stage)}'")
        if not isinstance(enabled, bool):
            return _deny("invalid_persistence_gates",
                         f"persistence_gates['{stage}'] must be a bool")

    # 7. Explicit stage idempotency keys: known stages, safe short strings.
    keys = request.stage_idempotency_keys
    if not isinstance(keys, dict):
        return _deny("invalid_stage_idempotency_keys",
                     "stage_idempotency_keys must be a stage -> key map")
    for stage, key in keys.items():
        if stage not in WORKFLOW_STAGES:
            return _deny("unknown_stage_idempotency_key",
                         f"stage_idempotency_keys contains unknown stage "
                         f"'{_safe_stage_name(stage)}'")
        if _is_blank(key) or not isinstance(key, str) or not SAFE_REF_RE.match(key):
            return _deny("invalid_stage_idempotency_key",
                         f"stage_idempotency_keys['{stage}'] must be a short safe key")

    # 8. strict_mode must be an explicit bool.
    if not isinstance(request.strict_mode, bool):
        return _deny("invalid_strict_mode", "strict_mode must be a bool")

    return _ok()


def _safe_stage_name(stage) -> str:
    """Render an unknown gate key without echoing an arbitrary caller value."""
    if isinstance(stage, str) and SAFE_WORKFLOW_ID_RE.match(stage):
        return stage
    return "<unsafe-stage-name>"


# --------------------------------------------------------------------------- payload safety


def evaluate_stage_payload(request, stage: str, payload) -> WorkflowGovernanceDecision:
    """Validate one stage payload before its narrow writer is invoked.

    Denies (never echoing a value) on: wrong draft type, prohibited/unexpected attribute names,
    unsafe field values, unsafe refs, and identity/authorization-scope mismatch.
    """
    warnings: List[str] = []

    # 1. Exact draft type for this stage (the narrow writer would reject anything else anyway;
    #    checking here means no DB connection is ever opened for a mistyped payload).
    try:
        draft_type = expected_draft_type(stage)
    except KeyError:
        return _deny("unknown_stage", f"unknown workflow stage '{_safe_stage_name(stage)}'")
    if not isinstance(payload, draft_type):
        return _deny("invalid_stage_payload",
                     f"{STAGE_PAYLOAD_ATTRS[stage]} is not a {draft_type.__name__}")

    known = _known_field_names(stage)
    attrs = dict(vars(payload)) if hasattr(payload, "__dict__") else {}

    # 2. Prohibited / unexpected attribute names. Declared draft fields are known-safe posture
    #    fields and are not name-scanned; anything the caller bolted on is.
    for name in sorted(attrs):
        if name in known:
            continue
        low = name.lower()
        if any(marker in low for marker in PROHIBITED_KEY_MARKERS):
            return _deny("prohibited_payload_key",
                         f"{stage} payload carries a prohibited attribute "
                         f"'{_safe_field_name(name)}'")
        warnings.append(f"{stage} payload carries an unexpected attribute "
                        f"'{_safe_field_name(name)}' (ignored by the narrow writer)")

    # 3. Value safety on declared fields (prose-exempt fields are delegated to their writer).
    ref_fields = frozenset(STAGE_REF_FIELDS.get(stage, ()))
    for name in sorted(known):
        value = getattr(payload, name, None)
        if name in PROSE_EXEMPT_FIELDS:
            continue
        for item in _string_items(value):
            category = classify_value_marker(item, strict_json=name in ref_fields)
            if category is not None:
                return _deny("prohibited_payload_value",
                             f"{stage} payload field '{name}' carries a "
                             f"{category} marker (value not echoed)")

    # 4. Stage refs must be short safe refs/ids.
    for name in ref_fields:
        value = getattr(payload, name, None)
        for item in _string_items(value):
            if not SAFE_REF_RE.match(item):
                return _deny("unsafe_stage_ref",
                             f"{stage} payload field '{name}' is not a short safe ref/id "
                             "(value not echoed)")

    # 5. Identity consistency — cross-tenant / cross-engagement payloads never reach a writer.
    for attr in ("owner_id", "client_id", "engagement_id"):
        if getattr(payload, attr, None) != getattr(request, attr, None):
            return _deny("identity_mismatch",
                         f"{stage} payload {attr} does not match the workflow {attr}")
    if "authorization_scope" in known:
        if getattr(payload, "authorization_scope", None) != request.authorization_scope:
            return _deny("authorization_scope_mismatch",
                         f"{stage} payload authorization_scope does not match the workflow "
                         "authorization_scope")

    # 6. Server-controlled fields must not be caller-supplied (the writers enforce this too).
    for attr in ("created_at", "captured_at"):
        if attr in known and getattr(payload, attr, None) is not None:
            return _deny("caller_supplied_timestamp",
                         f"{stage} payload {attr} must be None (server-controlled)")

    return _ok(warnings)


def _safe_field_name(name) -> str:
    if isinstance(name, str) and re.match(r"^[A-Za-z0-9_]{1,64}$", name):
        return name
    return "<unsafe-field-name>"


def _string_items(value):
    """Yield the string values inside a scalar / list / tuple field (one level deep)."""
    if isinstance(value, str):
        if value.strip():
            yield value
    elif isinstance(value, (list, tuple)):
        for item in value:
            if isinstance(item, str) and item.strip():
                yield item


# --------------------------------------------------------------------------- idempotency keys


def derive_stage_idempotency_key(request, stage: str, payload) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Return ``(key, source, denial_reason_code)`` for one stage.

    The rule (documented in docs/MANAGED_RECORD_WORKFLOW_INTEGRATION.md):

    * every key is namespaced ``wf35::<stage>::…`` so one string can never be reused across two
      tables/actions;
    * an explicit ``stage_idempotency_keys[stage]`` is respected as the stage-local component;
    * otherwise the key is derived deterministically from ``workflow_id`` plus a SHA-256 prefix
      over the stage's safe, stable, **non-content** fields (see ``STAGE_KEY_FIELDS``);
    * with no ``workflow_id`` and no explicit key there is nothing deterministic to derive from,
      so the stage is denied rather than given a random key.
    """
    prefix = f"{IDEMPOTENCY_NAMESPACE}{IDEMPOTENCY_SEPARATOR}{stage}{IDEMPOTENCY_SEPARATOR}"

    explicit = (request.stage_idempotency_keys or {}).get(stage)
    if not _is_blank(explicit):
        key = f"{prefix}{explicit}"
        source = "explicit"
    else:
        if _is_blank(request.workflow_id):
            return None, None, "missing_stage_idempotency_key"
        key = f"{prefix}{request.workflow_id}{IDEMPOTENCY_SEPARATOR}" \
              f"{stage_payload_fingerprint(stage, payload)}"
        source = "derived"

    if len(key) > MAX_IDEMPOTENCY_KEY_LEN:
        return None, None, "idempotency_key_too_long"
    return key, source, None


def stage_payload_fingerprint(stage: str, payload) -> str:
    """A deterministic 16-hex-char digest over a stage's safe, stable, non-content fields.

    Content fields (note bodies, summaries, prose) are deliberately excluded: the digest exists to
    make a stage key stable and collision-resistant, not to fingerprint stored content. The narrow
    writers compute their own full ``payload_fingerprint`` for replay-vs-conflict detection.
    """
    fields = STAGE_KEY_FIELDS.get(stage, ())
    material = {name: _normalize(getattr(payload, name, None)) for name in fields}
    blob = json.dumps(material, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _normalize(value):
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
