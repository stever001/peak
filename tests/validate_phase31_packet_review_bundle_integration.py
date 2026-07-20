#!/usr/bin/env python3
"""Phase 31 packet -> review bundle orchestration integration check.

Three layers:

* **Structural (always, stdlib-only):** the orchestration files + integration doc exist and
  compile; the Phase 23 ingestion, Phase 26 task_queue, and Phase 29 review_orchestration packages
  stay DB-free; the orchestrator imports no live LLM / MockLLM / executor / AgentNet / MCP /
  resolver / connector / network module, no *top-level* SQLAlchemy / peak.db (the Phase 30 writer
  is lazy-imported), and no Phase 22 review writer; the Phase 30 commit is present; **no Phase 31
  migration** was added (head stays 007_review_bundle_records); the docs carry the required
  language; the repo stays source-only.

* **Plan-only (always, stdlib-only):** default packet processing runs the Phase 29 review planner,
  exposes review bundle drafts / plan items / readiness assessments + counts, keeps every
  side-effect flag false, approves nothing, executes nothing, writes no review_records/
  agent_run_records, and leaks no raw payload; and no persistence stage silently escalates.

* **DB-backed (when SQLAlchemy is importable):** controlled review-bundle persistence through the
  Phase 30 writer only — create, replay, conflict, stored-Engagement authorization — plus a
  regression check that source (Phase 24), evidence (Phase 18/21), and task-queue (Phase 27)
  persistence still work. Skipped with instructions if SQLAlchemy is absent (still exits 0).

Exit status: 0 all passed; 1 a check failed.
"""

from __future__ import annotations

import os
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

REQUIRED_FILES = [
    "peak/orchestration/contracts.py",
    "peak/orchestration/packet_processor.py",
    "peak/orchestration/__init__.py",
    "docs/PACKET_TO_REVIEW_BUNDLE_ORCHESTRATION_INTEGRATION.md",
]
ORCH_FILES = [
    "peak/orchestration/__init__.py",
    "peak/orchestration/contracts.py",
    "peak/orchestration/governance.py",
    "peak/orchestration/packet_processor.py",
]
DBFREE_FILES = [
    "peak/ingestion/contracts.py", "peak/ingestion/governance.py", "peak/ingestion/packet_mapper.py",
    "peak/task_queue/contracts.py", "peak/task_queue/governance.py",
    "peak/task_queue/task_queue_mapper.py", "peak/task_queue/__init__.py",
    "peak/review_orchestration/contracts.py", "peak/review_orchestration/governance.py",
    "peak/review_orchestration/review_planner.py", "peak/review_orchestration/__init__.py",
]
DOCS = ["docs/PACKET_TO_REVIEW_BUNDLE_ORCHESTRATION_INTEGRATION.md"]
REQUIRED_PHRASES = [
    "phase 31 integrates the review bundle path into packet orchestration",
    "orchestrator preflight is not authoritative",
    "stored engagement authorization remains authoritative",
    "identity matching is necessary but not sufficient",
    "review bundle persistence is not review approval",
    "no new table, no migration",
    "skipped_plan_only",
    "skipped_missing_session_factory",
    "is not approved",
    "review_records",
    "agent_run_records",
]

DB_IMPORT_RE = re.compile(r"\b(?:sqlalchemy|alembic|pymysql)\b|\bpeak\.db\b", re.IGNORECASE)
LLM_PROVIDER_RE = re.compile(
    r"\b(?:openai|anthropic|cohere|litellm|langchain|transformers|vertexai|mistralai|ollama)\b",
    re.IGNORECASE)
EXEC_IMPORT_RE = re.compile(r"\b(?:mock_llm|MockLLM|MockAgentExecutor)\b")
CONNECTOR_RE = re.compile(
    r"\b(?:agentnet|mcp_connector|mcp|resolver_client)\b", re.IGNORECASE)
NETWORK_RE = re.compile(
    r"\b(?:requests|socket|urllib|httpx|aiohttp|ftplib|smtplib|telnetlib|http\.client)\b")
REVIEW_WRITER_RE = re.compile(r"\breview_writer\b|persist_review_record")
DB_FILE_EXTS = (".db", ".sqlite", ".sqlite3", ".sql")
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache"}

PASS, FAIL = "PASS", "FAIL"
_failures: list = []


def _skip(dp: str) -> bool:
    return bool(SKIP_DIRS.intersection(dp.split(os.sep)))


def read(rel: str) -> str:
    with open(os.path.join(REPO_ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def _import_lines(text: str):
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("import ") or s.startswith("from "):
            yield s


def _toplevel_import_lines(text: str):
    for line in text.splitlines():
        if line[:1] in (" ", "\t"):
            continue
        if line.startswith("import ") or line.startswith("from "):
            yield line


def check(label: str, ok: bool) -> None:
    if ok:
        print(f"  [{PASS}] {label}")
    else:
        _failures.append(label)
        print(f"  [{FAIL}] {label}")


# --------------------------------------------------------------------------- structural


def structural_checks() -> None:
    print("\n1. Files present")
    for rel in REQUIRED_FILES:
        check(rel, os.path.isfile(os.path.join(REPO_ROOT, rel)))

    print("\n2. Orchestration files compile")
    for rel in ORCH_FILES:
        try:
            py_compile.compile(os.path.join(REPO_ROOT, rel), doraise=True)
            check(f"{rel} compiles", True)
        except py_compile.PyCompileError:
            check(f"{rel} compiles", False)

    print("\n3. Phase 23/26/29 boundaries stay DB-free (regression)")
    for rel in DBFREE_FILES:
        hits = [ln for ln in _import_lines(read(rel)) if DB_IMPORT_RE.search(ln)]
        check(f"{rel}: no DB/ORM/peak.db import", not hits)

    print("\n4. Orchestrator import discipline")
    for rel in ORCH_FILES:
        text = read(rel)
        imports = list(_import_lines(text))
        check(f"{rel}: no LLM provider import",
              not [ln for ln in imports if LLM_PROVIDER_RE.search(ln)])
        check(f"{rel}: no mock-LLM / executor import",
              not [ln for ln in imports if EXEC_IMPORT_RE.search(ln)])
        check(f"{rel}: no AgentNet/MCP/resolver import",
              not [ln for ln in imports if CONNECTOR_RE.search(ln)])
        check(f"{rel}: no network import",
              not [ln for ln in imports if NETWORK_RE.search(ln)])
        check(f"{rel}: no Phase 22 review writer import",
              not [ln for ln in imports if REVIEW_WRITER_RE.search(ln)])
        check(f"{rel}: no top-level DB import (Phase 30 writer lazy)",
              not [ln for ln in _toplevel_import_lines(text) if DB_IMPORT_RE.search(ln)])

    print("\n5. Baseline: Phase 30 present, no Phase 31 migration")
    try:
        log = subprocess.check_output(
            ["git", "-C", REPO_ROOT, "log", "--oneline", "-8"], text=True)
        check("Phase 30 commit present in recent history",
              "Phase 30" in log or "6a19439" in log)
    except Exception:
        check("Phase 30 commit present (git unavailable — skipped)", True)
    versions = sorted(v for v in os.listdir(os.path.join(REPO_ROOT, "alembic", "versions"))
                      if v.endswith(".py"))
    check("latest migration is 007_review_bundle_records",
          any(v.startswith("007_review_bundle_records") for v in versions))
    check("no 008_* migration added", not any(v.startswith("008") for v in versions))
    p31 = [v for v in versions if any(t in v.lower() for t in ("phase31", "review_bundle_integration",
                                                               "review_orchestration_integration"))]
    check("no Phase 31 migration added", not p31)

    print("\n6. Doc language")
    blob = re.sub(r"\s+", " ", "\n".join(read(rel) for rel in DOCS)).lower()
    for phrase in REQUIRED_PHRASES:
        check(f"phrase present: '{phrase}'", phrase.lower() in blob)

    print("\n7. Source-only discipline")
    check("no examples/ directory", not os.path.exists(os.path.join(REPO_ROOT, "examples")))
    artifacts, dbfiles = [], []
    for dp, _, files in os.walk(REPO_ROOT):
        if _skip(dp):
            continue
        for f in files:
            rel = os.path.relpath(os.path.join(dp, f), REPO_ROOT)
            if f == ".env.example":
                continue
            if ".example." in f:
                artifacts.append(rel)
            if f.lower().endswith(DB_FILE_EXTS):
                dbfiles.append(rel)
    check("no committed data artifacts", not artifacts)
    check("no committed database files", not dbfiles)


# --------------------------------------------------------------------------- builders

_SENTINEL = "PACKET-SENTINEL-DO-NOT-LEAK"
_ALL_SIDE_EFFECT_FLAGS = (
    "database_connection_made", "sql_execution_made", "database_write_made",
    "stored_record_created", "review_approval_made", "agent_execution_made",
    "mock_agent_execution_made", "llm_call_made", "agentnet_call_made", "resolver_call_made",
    "network_call_made", "client_facing_output_created", "financial_verification_made",
    "capsule_publication_made",
)


def _make_request(agent_tasks=None, extra_payload=None, **over):
    from peak.ingestion.contracts import EngagementPacketReference, PacketIngestionRequest

    if agent_tasks is None:
        agent_tasks = [{"agent_name": "evidence_normalization_worker", "requested_action": "normalize"}]
    ref = EngagementPacketReference(
        packet_reference_id="pkt_1", owner_id="owner_1", client_id="client_a",
        engagement_id="eng_x", packet_schema_name="engagement-packet",
        packet_schema_version="1.0", packet_source_type="consultant_upload",
        packet_location_reference="controlled://engagement/eng_x/packet_1",
        packet_hash="sha256:abc", captured_by="consultant_a",
        captured_at="2026-07-20T09:00:00Z", authorization_scope="engagement_authorized",
        lifecycle_status="active",
    )
    payload = {"requested_agent_tasks": agent_tasks}
    if extra_payload:
        payload.update(extra_payload)
    base = dict(
        owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
        requested_by="consultant_a", requester_role="consultant",
        authorization_scope="engagement_authorized", packet_reference=ref,
        packet_payload=payload, requested_ingestion_action="prepare_packet_ingestion_plan",
        source_phase="phase31", idempotency_key="idem-p31-1", lifecycle_status="active",
    )
    base.update(over)
    return PacketIngestionRequest(**base)


def _blob(r) -> str:
    parts = list(r.reasons) + list(r.warnings) + [str(r.reason_code)]
    for s in r.stage_results:
        parts.append(str(s.reason))
    return " ".join(parts)


def _assert_no_side_effects(label, r) -> None:
    for flag in _ALL_SIDE_EFFECT_FLAGS:
        check(f"{label}: {flag} False", getattr(r, flag) is False)


# --------------------------------------------------------------------------- plan-only


def plan_only_checks() -> None:
    from peak.orchestration import (
        OrchestrationOutcome, OrchestrationStageOptions, StageOutcome,
        STAGE_REVIEW_ORCHESTRATION, STAGE_REVIEW_BUNDLE_PERSISTENCE,
        process_engagement_packet,
    )
    from peak.review_orchestration.contracts import ReviewBundleDraft, ReviewPlanItem

    print("\n8. Plan-only integration (default)")
    r = process_engagement_packet(_make_request())
    check("permitted True", r.permitted is True)
    check("orchestration_outcome planned", r.orchestration_outcome == OrchestrationOutcome.PLANNED)
    check("review orchestration stage completed",
          any(s.stage == STAGE_REVIEW_ORCHESTRATION and s.outcome == StageOutcome.COMPLETED
              for s in r.stage_results))
    check("review_orchestration_result present", r.review_orchestration_result is not None)
    check("review bundle drafts present (1)", r.review_bundle_count == 1
          and len(r.review_bundle_drafts) == 1)
    check("drafts are Phase 29 ReviewBundleDraft objects",
          all(isinstance(d, ReviewBundleDraft) for d in r.review_bundle_drafts))
    check("review plan items present", r.review_plan_item_count >= 1
          and all(isinstance(i, ReviewPlanItem) for i in r.review_plan_items))
    check("review readiness assessments present", r.review_readiness_assessment_count >= 1)
    check("review subject count >= 1", r.review_subject_count >= 1)
    b = r.review_bundle_drafts[0]
    check("bundle review-gated + not-approved",
          b.output_status == "draft" and b.review_status == "needs_review"
          and b.lifecycle_status == "draft" and b.approval_allowed is False
          and b.requires_human_review is True and b.review_bundle_id is None)
    check("persistence stage skipped_not_requested",
          any(s.stage == STAGE_REVIEW_BUNDLE_PERSISTENCE
              and s.outcome == StageOutcome.SKIPPED_NOT_REQUESTED for s in r.stage_results))
    check("no review bundle write receipts in plan-only", not r.review_bundle_write_receipts)
    _assert_no_side_effects("plan-only", r)
    check("NO raw packet sentinel leaked", _SENTINEL not in _blob(r))
    rs = process_engagement_packet(_make_request(extra_payload={"unmapped_blob": _SENTINEL}))
    check("sentinel in unmapped payload not leaked", _SENTINEL not in _blob(rs))

    print("\n9. No silent escalation")
    f_dummy = lambda: None  # noqa: E731 - never called in these skip paths
    opts = OrchestrationStageOptions(plan_only=False, include_review_bundle_persistence=False)
    r2 = process_engagement_packet(_make_request(), options=opts, session_factory=f_dummy)
    check("persistence not included -> skipped_not_requested",
          any(s.stage == STAGE_REVIEW_BUNDLE_PERSISTENCE
              and s.outcome == StageOutcome.SKIPPED_NOT_REQUESTED for s in r2.stage_results))
    check("not-included: no writer receipts", not r2.review_bundle_write_receipts)
    opts = OrchestrationStageOptions(plan_only=True, include_review_bundle_persistence=True)
    r3 = process_engagement_packet(_make_request(), options=opts)
    check("plan_only + persistence -> skipped_plan_only",
          any(s.stage == STAGE_REVIEW_BUNDLE_PERSISTENCE
              and s.outcome == StageOutcome.SKIPPED_PLAN_ONLY for s in r3.stage_results))
    check("plan_only escalation: db_write_made still False", r3.database_write_made is False)
    opts = OrchestrationStageOptions(plan_only=False, include_review_bundle_persistence=True)
    r4 = process_engagement_packet(_make_request(), options=opts, session_factory=None)
    check("persistence w/o session_factory -> skipped_missing_session_factory",
          any(s.stage == STAGE_REVIEW_BUNDLE_PERSISTENCE
              and s.outcome == StageOutcome.SKIPPED_MISSING_SESSION_FACTORY
              for s in r4.stage_results))
    check("missing session_factory does not fail packet", r4.permitted is True)
    _assert_no_side_effects("missing-session", r4)

    print("\n10. Review orchestration disabled")
    opts = OrchestrationStageOptions(include_review_orchestration=False)
    r5 = process_engagement_packet(_make_request(), options=opts)
    check("review orchestration skipped_not_requested",
          any(s.stage == STAGE_REVIEW_ORCHESTRATION
              and s.outcome == StageOutcome.SKIPPED_NOT_REQUESTED for s in r5.stage_results))
    check("no review bundle drafts when disabled", r5.review_bundle_count == 0)

    print("\n11. Denials still deny the whole packet")
    rl = process_engagement_packet(_make_request(lifecycle_status="revoked"))
    check("revoked lifecycle denied", rl.orchestration_outcome == OrchestrationOutcome.DENIED)
    _assert_no_side_effects("denied-packet", rl)


# --------------------------------------------------------------------------- DB-backed


def db_backed_checks() -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from peak.db.base import Base
    from peak.db.models import (
        AgentRunRecord, AgentTaskQueueRecord, Engagement, EvidenceReference, ReviewBundleRecord,
        ReviewRecord, SourceIngestionRecord,
    )
    from peak.orchestration import (
        OrchestrationOutcome, OrchestrationStageOptions, StageOutcome,
        STAGE_REVIEW_BUNDLE_PERSISTENCE, process_engagement_packet,
    )

    tmpdirs: list = []

    def fresh_db():
        tmp = tempfile.mkdtemp(prefix="peak_phase31_")
        tmpdirs.append(tmp)
        engine = create_engine("sqlite:///" + os.path.join(tmp, "test.db"))
        Base.metadata.create_all(engine)
        return sessionmaker(bind=engine, expire_on_commit=False)

    def seed(factory, **over):
        s = factory()
        base = dict(id="eng_x", client_id="client_a", owner_id="owner_1",
                    authorization_scope="engagement_authorized", lifecycle_status="active",
                    review_status="active")
        base.update(over)
        s.add(Engagement(**base))
        s.commit()
        s.close()

    def count(factory, model):
        s = factory()
        n = s.query(model).count()
        s.close()
        return n

    persist_opts = OrchestrationStageOptions(
        plan_only=False, include_review_bundle_persistence=True)

    print("\n12. Controlled review bundle persistence (Phase 30 writer only)")
    f = fresh_db()
    seed(f)
    r = process_engagement_packet(_make_request(), options=persist_opts, session_factory=f)
    check("orchestration persisted", r.orchestration_outcome == OrchestrationOutcome.PERSISTED)
    check("review persistence stage completed",
          any(s.stage == STAGE_REVIEW_BUNDLE_PERSISTENCE and s.outcome == StageOutcome.COMPLETED
              for s in r.stage_results))
    check("persisted count == drafts (1)", r.review_bundle_persisted_count == 1)
    check("one write receipt attached", len(r.review_bundle_write_receipts) == 1)
    check("receipt targets review_bundle_records/create_review_bundle_record",
          all(w.target_table == "review_bundle_records"
              and w.target_action == "create_review_bundle_record"
              for w in r.review_bundle_write_receipts))
    check("exactly one review_bundle_records row", count(f, ReviewBundleRecord) == 1)
    check("DB flags reflect writer calls",
          r.database_connection_made and r.sql_execution_made and r.database_write_made
          and r.stored_record_created)
    check("approval/execution flags stay False",
          r.review_approval_made is False and r.agent_execution_made is False
          and r.llm_call_made is False and r.agentnet_call_made is False
          and r.resolver_call_made is False and r.network_call_made is False)
    check("no client-facing / financial / capsule",
          r.client_facing_output_created is False and r.financial_verification_made is False
          and r.capsule_publication_made is False)
    check("NO review_records created", count(f, ReviewRecord) == 0)
    check("NO agent_run_records created", count(f, AgentRunRecord) == 0)

    print("\n13. Idempotent replay")
    r2 = process_engagement_packet(_make_request(), options=persist_opts, session_factory=f)
    check("replay outcome persisted", r2.orchestration_outcome == OrchestrationOutcome.PERSISTED)
    check("replay_count == 1", r2.review_bundle_replay_count == 1)
    check("persisted_count == 0 on replay", r2.review_bundle_persisted_count == 0)
    check("no new rows on replay", count(f, ReviewBundleRecord) == 1)

    print("\n14. Conflict (same review key, different fingerprint)")
    f2 = fresh_db()
    seed(f2)
    process_engagement_packet(_make_request(), options=persist_opts, session_factory=f2)
    # Same packet idempotency key (so the review-bundle key is identical) but a different agent —
    # this changes the queue-draft reference in the bundle fingerprint.
    rc = process_engagement_packet(
        _make_request(agent_tasks=[{"agent_name": "discovery_planning_agent",
                                    "requested_action": "plan"}]),
        options=persist_opts, session_factory=f2)
    check("conflict reported", rc.review_bundle_conflict_count >= 1)
    check("conflict -> orchestration partial",
          rc.orchestration_outcome == OrchestrationOutcome.PARTIAL)
    check("conflict wrote no extra row", count(f2, ReviewBundleRecord) == 1)

    print("\n15. Stored-Engagement authorization stays inside Phase 30 writer")
    f3 = fresh_db()
    seed(f3, authorization_scope="internal_peak_only")  # differs from request scope
    r3 = process_engagement_packet(_make_request(), options=persist_opts, session_factory=f3)
    check("writer denied stored-scope mismatch",
          all(w.reason_code == "stored_scope_mismatch" for w in r3.review_bundle_write_receipts)
          and len(r3.review_bundle_write_receipts) >= 1)
    check("no rows on scope mismatch", count(f3, ReviewBundleRecord) == 0)
    check("orchestration partial on writer denial",
          r3.orchestration_outcome == OrchestrationOutcome.PARTIAL)

    print("\n16. Regression: source + evidence + task-queue persistence still work")
    f4 = fresh_db()
    seed(f4)
    reg_opts = OrchestrationStageOptions(
        plan_only=False, include_source_ingestion_persistence=True,
        include_evidence_normalization=True, include_evidence_persistence=True,
        include_agent_task_queue_persistence=True, include_review_bundle_persistence=True)
    reg_req = _make_request(extra_payload={
        "evidence_items": [{"id": "ev1", "text": "pallets blocking dock"}]})
    rr = process_engagement_packet(reg_req, options=reg_opts, session_factory=f4)
    check("source ingestion row created (Phase 24)", count(f4, SourceIngestionRecord) == 1)
    check("evidence rows created (Phase 18/21)", count(f4, EvidenceReference) >= 1)
    check("task queue rows created (Phase 27)", count(f4, AgentTaskQueueRecord) >= 1)
    check("review bundle rows created (Phase 30)", count(f4, ReviewBundleRecord) >= 1)
    check("regression orchestration persisted",
          rr.orchestration_outcome == OrchestrationOutcome.PERSISTED)
    check("regression: no review_records", count(f4, ReviewRecord) == 0)
    check("regression: no agent_run_records", count(f4, AgentRunRecord) == 0)

    for tmp in tmpdirs:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    print("Peak Phase 31 packet -> review bundle orchestration integration check")
    print("=" * 52)
    structural_checks()
    plan_only_checks()

    print("\n(DB-backed layer)")
    try:
        import sqlalchemy  # noqa: F401
    except ImportError:
        print("  [skip] SQLAlchemy not installed — controlled-persistence not exercised.")
        print("         Run: make validate-phase31 PYTHON=.venv/bin/python")
    else:
        print(f"  SQLAlchemy {sqlalchemy.__version__} present — running DB-backed checks.")
        db_backed_checks()

    print("\n" + "=" * 52)
    print("Summary")
    print(f"  failures : {len(_failures)}")
    if _failures:
        print(f"\nRESULT: {FAIL} ({len(_failures)} issue(s))")
        return 1
    print(f"\nRESULT: {PASS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
