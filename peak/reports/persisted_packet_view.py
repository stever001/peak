"""Persisted-state adapter for the packet-view reporting route (Phase 113).

Takes the value-safe record summaries a read-only fetch returned — plain dicts, as
:func:`peak.db.engagement_packet_reader.fetch_engagement_packet_summaries` produces them — and
composes the committed route: :func:`~peak.reports.packet_view.assemble_packet_view` →
:func:`~peak.reports.packet_view_report.build_report_inputs_from_packet_view`, plus the matching
Phase 112 planner references. Stored records therefore supply record identity, statuses, source
links, and review targets, instead of those being transcribed from phase documents.

**What persisted state supplies and what it does not.** Relationships and posture are stored and are
read: the evidence → source link, the review → evidence target, every governance status. Two things
are not stored as data a report can use:

* **``claim_scope`` is now persisted, and the persisted value wins (Phase 114).** The Phase 21
  controlled writer records a governed ``claim_scope`` from a closed vocabulary, so an evidence row
  written since then carries its own classification and needs no caller input. :class:`ClaimScopePolicy`
  remains only as the **fallback for legacy rows** that predate the field; it can never override a
  persisted scope. Either way the value must be recognised, and it is never inferred from an evidence
  id, a phase label, or narrative text. Persisted ``operational_area`` /
  ``inventory_process_area`` remain a guard used in one direction only: an item whose areas are both
  unspecified **cannot** be an ``operational_finding``, so the scope is refused for it. Naming an
  area never grants the scope — an evidence row may name an area and still attest only that a record
  exists. This is a guard, not an evidence classifier.
* **Finding summary text is not read.** The fetch never selects ``evidence_references.summary`` or
  any other narrative column, so a caller that wants summary text in the schema-shaped evidence item
  supplies it explicitly, through the same policy. Nothing here reads, generates, or paraphrases a
  row body.

Side-effect boundary: pure functions over in-memory summaries. No database connection, no
SQLAlchemy / Alembic / ``peak.db`` import, no environment read, no file or network access, no
writer, and no agent execution. Output is deterministic. See
docs/PHASE113_READ_ONLY_PERSISTED_STATE_REPORTING_PATH.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .contracts import ALLOWED_CLAIM_SCOPES, GovernedRecordReference
from .packet_view import CLAIM_SCOPE_OPERATIONAL_FINDING, PacketView, assemble_packet_view
from .packet_view_report import PacketViewReportInputs, build_report_inputs_from_packet_view

#: Persisted area values that name no operational area. Both areas unspecified means the row records
#: no operational subject, so it cannot carry an operational-finding claim.
UNSPECIFIED_AREA_VALUES = frozenset({None, "", "unspecified"})

#: The persisted keys the area guard consults. Posture metadata only; never a body.
AREA_FIELDS = ("operational_area", "inventory_process_area")

CLAIM_SCOPE_PROVENANCE = (
    "claim_scope comes from the governed persisted field where the evidence row carries one, and "
    "otherwise from the caller as controlled workflow semantics; it is never derived from stored "
    "narrative text")
SUMMARY_PROVENANCE = (
    "finding summary text is not a stored field this path reads; any summary was supplied by the "
    "caller")

RECORD_TYPE_SOURCE = "source_ingestion_records"
RECORD_TYPE_EVIDENCE = "evidence_references"
RECORD_TYPE_REVIEW = "review_records"

IDENTITY_FIELDS = ("owner_id", "client_id", "engagement_id", "authorization_scope")


@dataclass
class ClaimScopePolicy:
    """Caller-supplied semantics for what persisted state does not carry.

    ``claim_scopes`` maps an evidence id to one of
    :data:`~peak.reports.contracts.ALLOWED_CLAIM_SCOPES`. Since Phase 114 it is a **fallback for
    legacy rows only**: a row with a persisted ``claim_scope`` ignores this map entirely.
    ``summaries`` maps an evidence id to short controlled summary text, which is still not persisted
    at all. An evidence id absent from a map simply gets nothing — it is never guessed.
    """

    claim_scopes: Dict[str, str] = field(default_factory=dict)
    summaries: Dict[str, str] = field(default_factory=dict)


@dataclass
class PersistedPlannerReferences:
    """Typed Phase 36/112 references built from the same fetched summaries as the packet view."""

    source_ingestion_refs: List[GovernedRecordReference] = field(default_factory=list)
    evidence_reference_ids: List[GovernedRecordReference] = field(default_factory=list)
    review_record_ids: List[GovernedRecordReference] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


def _areas_unspecified(evidence: Dict[str, object]) -> bool:
    return all(evidence.get(f) in UNSPECIFIED_AREA_VALUES for f in AREA_FIELDS)


def resolve_claim_scope(evidence: Dict[str, object],
                        policy: Optional[ClaimScopePolicy]) -> tuple:
    """Return ``(claim_scope, note)`` for one fetched evidence summary.

    **The persisted scope wins.** When the fetched row carries a governed ``claim_scope`` (Phase
    114), that value is authoritative and the caller policy is not consulted for that row at all.
    The policy applies only to a legacy row that carries no persisted scope, so a caller can never
    override what the controlled writer recorded.

    In either case the value must be in :data:`~peak.reports.contracts.ALLOWED_CLAIM_SCOPES`, and
    an ``operational_finding`` is refused for a row whose persisted areas are both unspecified. A
    row with no scope from either source gets none — it is never guessed. Every refusal returns a
    note so the reason travels with the view instead of disappearing.
    """
    evidence_id = evidence.get("evidence_id")
    persisted = evidence.get("claim_scope")
    if persisted is not None:
        requested, origin = persisted, "persisted"
    else:
        requested, origin = (policy.claim_scopes if policy else {}).get(evidence_id), "supplied"
    if requested is None:
        return None, None
    if requested not in ALLOWED_CLAIM_SCOPES:
        return None, (f"{evidence_id}: {origin} claim scope {requested!r} is not a recognised "
                      f"scope; refused")
    if requested == CLAIM_SCOPE_OPERATIONAL_FINDING and _areas_unspecified(evidence):
        return None, (f"{evidence_id}: {origin} operational_finding refused; the stored operational "
                      f"and inventory process areas are both unspecified")
    return requested, None


def apply_claim_scope_policy(evidence_summaries, policy: Optional[ClaimScopePolicy]):
    """Return ``(adapted_summaries, notes)`` — fetched summaries with their resolved claim scope.

    The fetched dicts are copied, never mutated. ``claim_scope`` is replaced by the resolved value
    and **removed when nothing resolved**, so a persisted value that was refused cannot survive into
    the view; ``summary``, which is not persisted, is added only when the caller supplied it.
    """
    adapted, notes = [], []
    for evidence in evidence_summaries:
        item = dict(evidence)
        scope, note = resolve_claim_scope(item, policy)
        if scope is not None:
            item["claim_scope"] = scope
        else:
            item.pop("claim_scope", None)
        if note:
            notes.append(note)
        summary = (policy.summaries if policy else {}).get(item.get("evidence_id"))
        if summary is not None:
            item["summary"] = summary
        adapted.append(item)
    return adapted, notes


def build_persisted_packet_view(summaries: Dict[str, object],
                                policy: Optional[ClaimScopePolicy] = None) -> PacketView:
    """Assemble a :class:`~peak.reports.packet_view.PacketView` from fetched record summaries.

    Identity, statuses, source links, and review targets come from the fetched rows; only
    ``claim_scope`` and optional summary text come from ``policy``. Provenance of both is recorded in
    the view's warnings, so a reader of the view can see which parts persisted state did not supply.
    """
    evidence, notes = apply_claim_scope_policy(summaries.get("evidence") or [], policy)
    view = assemble_packet_view(
        summaries.get("engagement") or {},
        sources=summaries.get("sources") or [],
        evidence=evidence,
        reviews=summaries.get("reviews") or [],
    )
    view.warnings.extend(notes)
    view.warnings.append(CLAIM_SCOPE_PROVENANCE)
    view.warnings.append(SUMMARY_PROVENANCE)
    return view


def build_persisted_report_inputs(summaries: Dict[str, object],
                                  policy: Optional[ClaimScopePolicy] = None
                                  ) -> PacketViewReportInputs:
    """Fetched summaries → packet view → Phase 111 reporting inputs and the reporting task request."""
    return build_report_inputs_from_packet_view(build_persisted_packet_view(summaries, policy))


def build_persisted_planner_references(summaries: Dict[str, object],
                                       policy: Optional[ClaimScopePolicy] = None
                                       ) -> PersistedPlannerReferences:
    """Build typed planner references from the same fetched summaries the packet view uses.

    A review reference carries ``target_record_ids`` holding the record its stored ``target_id``
    names — and nothing else, so the planner's Phase 112 support stays as target-specific as the
    packet view's links. An evidence reference carries a ``claim_scope`` only when the policy granted
    one. References are emitted in sorted id order.
    """
    engagement = summaries.get("engagement") or {}
    identity = {f: engagement.get(f) for f in IDENTITY_FIELDS}
    identity["engagement_id"] = engagement.get("engagement_id")
    refs = PersistedPlannerReferences()

    for source in sorted(summaries.get("sources") or [],
                         key=lambda r: str(r.get("source_ingestion_id"))):
        refs.source_ingestion_refs.append(GovernedRecordReference(
            record_id=source.get("source_ingestion_id"), record_type=RECORD_TYPE_SOURCE, **identity))

    evidence, notes = apply_claim_scope_policy(summaries.get("evidence") or [], policy)
    refs.notes.extend(notes)
    for item in sorted(evidence, key=lambda r: str(r.get("evidence_id"))):
        refs.evidence_reference_ids.append(GovernedRecordReference(
            record_id=item.get("evidence_id"), record_type=RECORD_TYPE_EVIDENCE, **identity,
            claim_scope=item.get("claim_scope")))

    for review in sorted(summaries.get("reviews") or [], key=lambda r: str(r.get("review_id"))):
        target = review.get("target_id")
        refs.review_record_ids.append(GovernedRecordReference(
            record_id=review.get("review_id"), record_type=RECORD_TYPE_REVIEW, **identity,
            target_record_ids=[target] if target else []))
        if not target:
            refs.notes.append(f"{review.get('review_id')}: names no target; it supports no slot")

    refs.notes.append(CLAIM_SCOPE_PROVENANCE)
    return refs
