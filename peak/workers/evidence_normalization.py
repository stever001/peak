"""Evidence Normalization Worker — deterministic, no-side-effect (Phase 14).

Turns one ``RawEvidenceReference`` into a **production-shaped but review-gated**
``NormalizedEvidenceRecord``. Normalization is fully deterministic (keyword/dictionary
maps); there is **no live LLM call, no AgentNet call, no database read/write, no network
call, no file write, no client-facing output, and no capsule publication**. Output is
never authoritative — it defaults to ``draft`` / ``needs_review``.

See docs/EVIDENCE_NORMALIZATION_WORKER.md and docs/EVIDENCE_RECORD_LIFECYCLE.md.
"""

from __future__ import annotations

from .contracts import (
    EvidenceCompletenessFlags,
    EvidenceNormalizationRequest,
    EvidenceNormalizationResult,
    EvidenceQualitySignals,
    NormalizedEvidenceRecord,
    RawEvidenceReference,
)
from .governance import (
    build_evidence_review_gate,
    evaluate_evidence_normalization_request,
)

# source_type -> evidence_type (aligned to schemas/evidence-reference.schema.json).
_SOURCE_TYPE_TO_EVIDENCE_TYPE = {
    "stakeholder": "interview_statement",
    "site_walk": "visual_observation",
    "system": "system_export",
    "document": "document",
    "consultant": "consultant_note",
}
_PHOTO_CONTENT_TYPES = ("photo", "image", "photograph", "picture")
_MEASUREMENT_CONTENT_TYPES = ("measurement", "metric", "reading", "count_sheet")

# Ordered keyword maps — first match wins; deterministic.
_PROCESS_AREA_KEYWORDS = (
    ("receiving", ("receiv", "inbound", "goods in", "goods-in", "dock in")),
    ("shipping", ("ship", "outbound", "dispatch", "goods out")),
    ("putaway", ("putaway", "put-away", "put away")),
    ("picking", ("pick",)),
    ("packing", ("pack",)),
    ("replenishment", ("replenish",)),
    ("cycle_counting", ("cycle count", "stock take", "stocktake", "count")),
    ("returns", ("return", "rma")),
    ("storage", ("storage", "rack", "bin", "slot", "aisle", "shelv")),
    ("inventory_control", ("inventory", "sku", "stock accuracy")),
)
_OPERATIONAL_AREA_KEYWORDS = (
    ("receiving_dock", ("dock", "receiv", "inbound")),
    ("shipping_dock", ("ship", "outbound", "dispatch")),
    ("storage_area", ("rack", "aisle", "bin", "storage", "shelv")),
    ("staging_area", ("stag",)),
    ("back_office", ("office", "desk", "erp", "wms", "system")),
    ("yard", ("yard", "trailer")),
)

_UNSPECIFIED = "unspecified"
_PREVIEW_LIMIT = 240


def _text_blob(raw: RawEvidenceReference) -> str:
    """Combine the non-sensitive descriptive fields into one lowercase search string."""
    src = getattr(raw, "source_reference", None)
    parts = [
        getattr(raw, "observation_context", None),
        getattr(raw, "raw_text_preview", None),
        getattr(raw, "location_context", None),
        getattr(src, "source_location", None) if src is not None else None,
        getattr(src, "source_name", None) if src is not None else None,
    ]
    return " ".join(p for p in parts if p).lower()


def _first_keyword_match(blob: str, table) -> str:
    for label, keywords in table:
        if any(k in blob for k in keywords):
            return label
    return _UNSPECIFIED


def classify_evidence_type(raw_evidence: RawEvidenceReference) -> str:
    """Map source/content type to a schema-aligned evidence_type (deterministic)."""
    content = (getattr(raw_evidence, "content_type", None) or "").lower()
    if any(c in content for c in _PHOTO_CONTENT_TYPES):
        return "photograph"
    if any(c in content for c in _MEASUREMENT_CONTENT_TYPES):
        return "measurement"
    src = getattr(raw_evidence, "source_reference", None)
    source_type = (getattr(src, "source_type", None) or "").lower() if src is not None else ""
    return _SOURCE_TYPE_TO_EVIDENCE_TYPE.get(source_type, "other")


def derive_operational_area(raw_evidence: RawEvidenceReference) -> str:
    """Derive a coarse operational area from keyword hints (deterministic)."""
    return _first_keyword_match(_text_blob(raw_evidence), _OPERATIONAL_AREA_KEYWORDS)


def derive_inventory_process_area(raw_evidence: RawEvidenceReference) -> str:
    """Derive a coarse inventory process area from keyword hints (deterministic)."""
    return _first_keyword_match(_text_blob(raw_evidence), _PROCESS_AREA_KEYWORDS)


def assess_completeness(raw_evidence: RawEvidenceReference) -> EvidenceCompletenessFlags:
    """Flag which inputs were present (deterministic; no inference)."""
    src = getattr(raw_evidence, "source_reference", None)
    has_source_reference = src is not None and not _blank(getattr(src, "source_reference_id", None))
    has_observed_at = not _blank(getattr(raw_evidence, "observed_at", None))
    has_source_location = not _blank(getattr(raw_evidence, "location_context", None)) or (
        src is not None and not _blank(getattr(src, "source_location", None))
    )
    has_raw_text_preview = not _blank(getattr(raw_evidence, "raw_text_preview", None))
    has_capture_metadata = src is not None and (
        not _blank(getattr(src, "captured_by", None))
        or not _blank(getattr(src, "captured_at", None))
    )
    flags = {
        "source_reference": has_source_reference,
        "observed_at": has_observed_at,
        "source_location": has_source_location,
        "raw_text_preview": has_raw_text_preview,
        "capture_metadata": has_capture_metadata,
    }
    missing = [name for name, present in flags.items() if not present]
    return EvidenceCompletenessFlags(
        has_source_reference=has_source_reference,
        has_observed_at=has_observed_at,
        has_source_location=has_source_location,
        has_raw_text_preview=has_raw_text_preview,
        has_capture_metadata=has_capture_metadata,
        complete=not missing,
        missing_fields=missing,
    )


def assess_quality(raw_evidence: RawEvidenceReference) -> EvidenceQualitySignals:
    """Produce conservative, deterministic quality signals."""
    completeness = assess_completeness(raw_evidence)
    warnings: list = []
    if not completeness.has_observed_at:
        warnings.append("missing observed_at")
    if not completeness.has_source_location:
        warnings.append("missing source_location")
    if not completeness.has_raw_text_preview:
        warnings.append("missing raw_text_preview")

    present = 5 - len(completeness.missing_fields)
    if present >= 5:
        reliability = confidence = "high"
    elif present >= 3:
        reliability = confidence = "medium"
    else:
        reliability = confidence = "low"
    has_min_context = not _blank(getattr(raw_evidence, "raw_text_preview", None)) or not _blank(
        getattr(raw_evidence, "observation_context", None)
    )
    if not has_min_context:
        confidence = "low"
    return EvidenceQualitySignals(
        reliability=reliability,
        confidence_level=confidence,
        has_minimum_context=has_min_context,
        warnings=warnings,
        notes="deterministic worker signals; conservative and review-gated",
    )


def build_normalized_title(raw_evidence: RawEvidenceReference) -> str:
    """Build a conservative, non-sensitive title from source/area (deterministic)."""
    evidence_type = classify_evidence_type(raw_evidence)
    operational_area = derive_operational_area(raw_evidence)
    process_area = derive_inventory_process_area(raw_evidence)
    return f"[draft] {evidence_type} — {operational_area} / {process_area}"


def build_normalized_summary(raw_evidence: RawEvidenceReference) -> str:
    """Build a conservative summary that clearly labels itself as review-gated."""
    src = getattr(raw_evidence, "source_reference", None)
    source_type = (getattr(src, "source_type", None) or "unknown") if src is not None else "unknown"
    operational_area = derive_operational_area(raw_evidence)
    process_area = derive_inventory_process_area(raw_evidence)
    preview = (getattr(raw_evidence, "raw_text_preview", None) or "").strip()
    if len(preview) > _PREVIEW_LIMIT:
        preview = preview[:_PREVIEW_LIMIT].rstrip() + "…"
    preview_part = preview if preview else "no preview provided"
    return (
        "Worker-normalized, review-gated (non-authoritative) evidence. "
        f"Source type: {source_type}. Operational area: {operational_area}. "
        f"Inventory process area: {process_area}. Preview: {preview_part}"
    )


def normalize_evidence(request: EvidenceNormalizationRequest) -> EvidenceNormalizationResult:
    """Normalize one raw evidence reference into a review-gated record (no side effects)."""
    decision = evaluate_evidence_normalization_request(request)
    gate = build_evidence_review_gate(request)

    if not decision.permitted:
        return EvidenceNormalizationResult(
            permitted=False,
            status="rejected",
            normalized_record=None,
            output_status=gate.output_status,
            review_status=gate.review_status,
            lifecycle_status=gate.lifecycle_status,
            authoritative=False,
            client_facing_approved=False,
            database_write_made=False,
            llm_call_made=False,
            agentnet_call_made=False,
            network_call_made=False,
            capsule_publication_made=False,
            reasons=list(decision.reasons),
            warnings=list(decision.warnings),
        )

    raw = request.raw_evidence
    src = raw.source_reference
    completeness = assess_completeness(raw)
    quality = assess_quality(raw)
    observation_context = (getattr(raw, "observation_context", None) or "").strip()
    observed_condition = observation_context or "not specified"

    record = NormalizedEvidenceRecord(
        evidence_record_id=None,  # assigned later by a controlled-DB writer; nothing stored here
        owner_id=request.owner_id,
        client_id=request.client_id,
        engagement_id=request.engagement_id,
        source_reference_id=getattr(src, "source_reference_id", None),
        evidence_type=classify_evidence_type(raw),
        normalized_title=build_normalized_title(raw),
        normalized_summary=build_normalized_summary(raw),
        observed_condition=observed_condition,
        operational_area=derive_operational_area(raw),
        inventory_process_area=derive_inventory_process_area(raw),
        source_type=getattr(src, "source_type", None),
        source_location=getattr(src, "source_location", None) or getattr(raw, "location_context", None),
        confidence_level=quality.confidence_level,
        completeness_flags=completeness,
        quality_signals=quality,
        output_status=gate.output_status,
        review_status=gate.review_status,
        lifecycle_status=gate.lifecycle_status,
        authoritative=False,
        client_facing_approved=False,
        capsule_candidate_ready=False,
        warnings=list(quality.warnings),
        reasons=[],
    )

    return EvidenceNormalizationResult(
        permitted=True,
        status="normalized_draft",
        normalized_record=record,
        output_status=gate.output_status,
        review_status=gate.review_status,
        lifecycle_status=gate.lifecycle_status,
        authoritative=False,
        client_facing_approved=False,
        database_write_made=False,
        llm_call_made=False,
        agentnet_call_made=False,
        network_call_made=False,
        capsule_publication_made=False,
        reasons=[],
        warnings=list(quality.warnings),
    )


def _blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())
