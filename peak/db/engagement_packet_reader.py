"""Read-only persisted-state fetch for packet-view reporting (Phase 113).

Retrieves the **value-safe summaries** of one engagement's controlled records — the engagement row,
its ``source_ingestion_records``, ``evidence_references``, and ``review_records`` — in exactly the
shape :func:`peak.reports.packet_view.assemble_packet_view` consumes. It is the first read path from
stored Peak state into the Phase 110–112 reporting route, so that route no longer starts from record
identity, statuses, source links, and review relationships transcribed out of phase documents.

**Read-only by construction.** Every statement is a ``select()`` over an explicit, whitelisted column
list. This module issues no ``INSERT`` / ``UPDATE`` / ``DELETE``, imports and invokes no writer,
creates no session or engine, holds no credential, and reads no environment variable — the caller
establishes and owns the connection, so the credential (and therefore the privilege) stays outside
this code.

**Whitelisted columns only, never row bodies.** Ids, identity fields, governance/posture statuses,
and relationship keys are selected by name. ``evidence_references.summary``, ``review_records.reason``,
and every other narrative column are **never selected**. From ``details_json`` only three keys are
extracted, server-side and one key at a time — ``source_reference_id`` (the evidence → source link,
which has no column of its own), ``operational_area``, and ``inventory_process_area`` — so the JSON
body never leaves the database.

**Visibility is the Phase 57 primitive, not a local filter.** The engagement must be visible in the
requested :class:`~peak.db.engagement_read_isolation.ReadMode` or the read is refused. The default is
the Phase 57 default — client-facing — so an internal test engagement is returned only when a caller
explicitly asks for it.

**Identity is reported, not silently filtered.** Records are fetched by ``engagement_id``; the packet
view independently compares each record's owner / client / engagement / scope against the engagement
and excludes any mismatch. A mismatch is therefore visible in the assembled view rather than dropped
here.

Output is plain dicts in sorted id order, so the same database state always yields the same
summaries. See docs/PHASE113_READ_ONLY_PERSISTED_STATE_REPORTING_PATH.md.
"""

from __future__ import annotations

from typing import Dict, List

from sqlalchemy import select

from .engagement_read_isolation import DEFAULT_READ_MODE, is_visible_in_mode
from .models import Engagement, EvidenceReference, ReviewRecord, SourceIngestionRecord

#: The only ``details_json`` keys this module extracts. Each is a relationship, posture, or governed
#: classification key, never a body. ``source_reference_id`` is the evidence → source link, which the
#: Phase 21 writer stores here because ``evidence_references`` has no column for it; ``claim_scope``
#: (Phase 114) is the governed claim classification the same writer stores there.
EVIDENCE_DETAIL_KEYS = ("source_reference_id", "operational_area", "inventory_process_area",
                        "claim_scope")


class EngagementNotVisible(PermissionError):
    """The engagement exists but is not visible in the requested read mode."""


def _rows(connection, statement) -> List[Dict[str, object]]:
    return [dict(row._mapping) for row in connection.execute(statement)]


def fetch_engagement_summary(connection, engagement_id: str,
                             mode: str = DEFAULT_READ_MODE,
                             include_internal_test: bool = False) -> Dict[str, object]:
    """Fetch one engagement's value-safe summary, or refuse.

    Raises ``LookupError`` if no such engagement exists and :class:`EngagementNotVisible` if it
    exists but the Phase 57 predicate for ``mode`` does not admit it. ``engagement_label`` is not
    selected; the classification columns are, because posture depends on them.
    """
    statement = select(
        Engagement.id.label("engagement_id"),
        Engagement.client_id,
        Engagement.owner_id,
        Engagement.authorization_scope,
        Engagement.engagement_category,
        Engagement.real_client_data,
        Engagement.client_accessible,
        Engagement.capsule_publication_authorized,
        Engagement.status,
        Engagement.review_status,
        Engagement.lifecycle_status,
    ).where(Engagement.id == engagement_id)
    found = _rows(connection, statement)
    if not found:
        raise LookupError(f"no engagement {engagement_id!r}")
    engagement = found[0]
    if not is_visible_in_mode(_RowView(engagement), mode=mode,
                              include_internal_test=include_internal_test):
        raise EngagementNotVisible(
            f"engagement {engagement_id!r} is not visible in read mode {mode!r}"
            f" (include_internal_test={include_internal_test})")
    return engagement


class _RowView:
    """Attribute access over a fetched summary, so the Phase 57 row predicates apply unchanged."""

    def __init__(self, summary: Dict[str, object]):
        self._summary = summary

    def __getattr__(self, name):
        return self._summary.get(name)


def fetch_source_summaries(connection, engagement_id: str) -> List[Dict[str, object]]:
    """Fetch the engagement's ``source_ingestion_records`` summaries, sorted by id.

    ``details_json`` is not read: the packet identifier lives in the ``source_reference_id`` column,
    and packet schema / locator / hash metadata is not needed to assemble or report the view.
    """
    statement = select(
        SourceIngestionRecord.id.label("source_ingestion_id"),
        SourceIngestionRecord.owner_id,
        SourceIngestionRecord.client_id,
        SourceIngestionRecord.engagement_id,
        SourceIngestionRecord.authorization_scope,
        SourceIngestionRecord.source_reference_id,
        SourceIngestionRecord.review_status,
        SourceIngestionRecord.output_status,
        SourceIngestionRecord.lifecycle_status,
    ).where(SourceIngestionRecord.engagement_id == engagement_id
            ).order_by(SourceIngestionRecord.id)
    return _rows(connection, statement)


def fetch_evidence_summaries(connection, engagement_id: str) -> List[Dict[str, object]]:
    """Fetch the engagement's ``evidence_references`` summaries, sorted by id.

    ``summary`` is never selected. The :data:`EVIDENCE_DETAIL_KEYS` are extracted from
    ``details_json`` server-side, one key at a time, so no JSON body is transferred. ``claim_scope``
    is the governed classification the Phase 21 writer persists; the areas remain posture metadata
    that can refuse an operational-finding claim scope but never grant one — see
    :mod:`peak.reports.persisted_packet_view`.
    """
    details = EvidenceReference.details_json
    statement = select(
        EvidenceReference.id.label("evidence_id"),
        EvidenceReference.owner_id,
        EvidenceReference.client_id,
        EvidenceReference.engagement_id,
        EvidenceReference.authorization_scope,
        EvidenceReference.evidence_type,
        EvidenceReference.source_type,
        EvidenceReference.reliability,
        EvidenceReference.evidence_status,
        EvidenceReference.review_status,
        EvidenceReference.output_status,
        EvidenceReference.lifecycle_status,
        EvidenceReference.sensitive_data_flag,
        details["source_reference_id"].as_string().label("source_reference_id"),
        details["operational_area"].as_string().label("operational_area"),
        details["inventory_process_area"].as_string().label("inventory_process_area"),
        details["claim_scope"].as_string().label("claim_scope"),
    ).where(EvidenceReference.engagement_id == engagement_id).order_by(EvidenceReference.id)
    return _rows(connection, statement)


def fetch_review_summaries(connection, engagement_id: str) -> List[Dict[str, object]]:
    """Fetch the engagement's ``review_records`` summaries, sorted by id.

    ``target_id`` and ``subject_record_type`` are the persisted review → evidence relationship; they
    are what makes review support target-specific downstream. ``reason`` is never selected.
    """
    statement = select(
        ReviewRecord.id.label("review_id"),
        ReviewRecord.owner_id,
        ReviewRecord.client_id,
        ReviewRecord.engagement_id,
        ReviewRecord.authorization_scope,
        ReviewRecord.target_id,
        ReviewRecord.subject_record_type,
        ReviewRecord.decision,
        ReviewRecord.review_status,
        ReviewRecord.new_status,
        ReviewRecord.authoritative,
        ReviewRecord.output_status,
        ReviewRecord.lifecycle_status,
    ).where(ReviewRecord.engagement_id == engagement_id).order_by(ReviewRecord.id)
    return _rows(connection, statement)


def fetch_engagement_packet_summaries(connection, engagement_id: str,
                                      mode: str = DEFAULT_READ_MODE,
                                      include_internal_test: bool = False
                                      ) -> Dict[str, object]:
    """Fetch every value-safe summary the packet view needs for one engagement.

    Returns ``{"engagement": {...}, "sources": [...], "evidence": [...], "reviews": [...]}`` —
    plain dicts keyed exactly as :func:`peak.reports.packet_view.assemble_packet_view` expects, so
    the reporting side needs no knowledge of this module, of SQLAlchemy, or of the schema.

    The engagement read is performed and checked **first**: if it is refused, no record query runs.
    """
    engagement = fetch_engagement_summary(connection, engagement_id, mode=mode,
                                          include_internal_test=include_internal_test)
    return {
        "engagement": engagement,
        "sources": fetch_source_summaries(connection, engagement_id),
        "evidence": fetch_evidence_summaries(connection, engagement_id),
        "reviews": fetch_review_summaries(connection, engagement_id),
    }


def summary_record_counts(summaries: Dict[str, object]) -> Dict[str, int]:
    """Count the fetched records per section — ids and counts only, never content."""
    return {
        "engagements": 1 if summaries.get("engagement") else 0,
        "source_ingestion_records": len(summaries.get("sources") or []),
        "evidence_references": len(summaries.get("evidence") or []),
        "review_records": len(summaries.get("reviews") or []),
    }
