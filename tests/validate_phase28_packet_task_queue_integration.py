#!/usr/bin/env python3
"""Phase 28 packet -> task queue orchestration integration check.

Three layers:

* **Structural (always, stdlib-only):** the orchestration files + integration doc exist and
  compile; the Phase 23 ingestion and Phase 26 task_queue packages stay DB-free; the orchestrator
  imports no live LLM / MockLLM / executor / AgentNet / MCP / resolver / connector / network
  module and no *top-level* SQLAlchemy / peak.db (the Phase 27 writer is lazy-imported); the
  Phase 27 commit is present in recent history; **no Phase 28 migration** was added (head stays
  006_agent_task_queue_records); the docs carry the required language; the repo stays source-only.

* **Plan-only (always, stdlib-only):** default packet processing derives Phase 13 tasks, runs the
  Phase 26 readiness planner, exposes queue drafts / assessments / plan-only write requests, keeps
  every side-effect flag false, executes nothing, writes no agent_run_records, and leaks no raw
  payload; and no persistence stage silently escalates plan-only mode.

* **DB-backed (when SQLAlchemy is importable):** controlled task queue persistence through the
  Phase 27 writer only — create, replay, conflict, stored-Engagement authorization — plus a
  regression check that source-ingestion (Phase 24) and evidence (Phase 18/21) persistence still
  work. Skipped with instructions if SQLAlchemy is absent (still exits 0).

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
    "peak/orchestration/governance.py",
    "docs/PACKET_TO_TASK_QUEUE_ORCHESTRATION_INTEGRATION.md",
]
ORCH_FILES = [
    "peak/orchestration/__init__.py",
    "peak/orchestration/contracts.py",
    "peak/orchestration/governance.py",
    "peak/orchestration/packet_processor.py",
]
PHASE23_FILES = [
    "peak/ingestion/contracts.py", "peak/ingestion/governance.py",
    "peak/ingestion/packet_mapper.py",
]
PHASE26_FILES = [
    "peak/task_queue/__init__.py", "peak/task_queue/contracts.py",
    "peak/task_queue/governance.py", "peak/task_queue/task_queue_mapper.py",
]
DOCS = ["docs/PACKET_TO_TASK_QUEUE_ORCHESTRATION_INTEGRATION.md"]
REQUIRED_PHRASES = [
    "phase 28 integrates the queue path into orchestration",
    "orchestrator preflight is not authoritative",
    "stored engagement authorization remains authoritative",
    "identity matching is necessary but not sufficient",
    "agent task queue persistence is not execution",
    "no new table, no migration",
    "skipped_plan_only",
    "skipped_missing_session_factory",
    "plan-only queue readiness is allowed",
    "agent_run_records",
]

DB_IMPORT_RE = re.compile(r"\b(?:sqlalchemy|alembic|pymysql)\b|\bpeak\.db\b", re.IGNORECASE)
LLM_PROVIDER_RE = re.compile(
    r"\b(?:openai|anthropic|cohere|litellm|langchain|transformers|vertexai|mistralai|ollama)\b",
    re.IGNORECASE,
)
EXEC_IMPORT_RE = re.compile(r"\b(?:mock_llm|MockLLM|MockAgentExecutor)\b")
CONNECTOR_RE = re.compile(
    r"\b(?:agentnet|mcp_connector|mcp|resolver_client|resolver|connector)\b", re.IGNORECASE)
NETWORK_RE = re.compile(
    r"\b(?:requests|socket|urllib|httpx|aiohttp|ftplib|smtplib|telnetlib|http\.client)\b")
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

    print("\n3. Phase 23 ingestion + Phase 26 task_queue stay DB-free (regression)")
    for rel in PHASE23_FILES + PHASE26_FILES:
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
        check(f"{rel}: no AgentNet/MCP/resolver/connector import",
              not [ln for ln in imports if CONNECTOR_RE.search(ln)])
        check(f"{rel}: no network import",
              not [ln for ln in imports if NETWORK_RE.search(ln)])
        check(f"{rel}: no top-level DB import (Phase 27 writer lazy)",
              not [ln for ln in _toplevel_import_lines(text) if DB_IMPORT_RE.search(ln)])

    print("\n5. Baseline: Phase 27 present, no Phase 28 migration")
    try:
        log = subprocess.check_output(
            ["git", "-C", REPO_ROOT, "log", "--oneline", "-8"], text=True)
        check("Phase 27 commit present in recent history",
              "Phase 27" in log or "ec416ef" in log)
    except Exception:
        check("Phase 27 commit present (git unavailable — skipped)", True)
    versions = sorted(v for v in os.listdir(os.path.join(REPO_ROOT, "alembic", "versions"))
                      if v.endswith(".py"))
    check("the Phase 27 agent-task-queue migration (006) is present",
          any(v.startswith("006_agent_task_queue_records") for v in versions))
    # Phase 28 is an orchestration-integration phase: it introduced no migration of its own.
    # (Later phases legitimately add migrations, so this checks for a Phase-28-specific one,
    # not a fixed global count.)
    p28 = [v for v in versions if any(t in v.lower() for t in ("phase28", "task_queue_integration",
                                                               "orchestration_integration"))]
    check("no Phase 28 migration added", not p28)

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
    "stored_record_created", "agent_execution_made", "mock_agent_execution_made",
    "llm_call_made", "agentnet_call_made", "resolver_call_made", "network_call_made",
    "client_facing_output_created", "financial_verification_made", "capsule_publication_made",
)


def _make_request(agent_tasks=None, extra_payload=None, **over):
    from peak.ingestion.contracts import EngagementPacketReference, PacketIngestionRequest

    if agent_tasks is None:
        agent_tasks = [
            {"agent_name": "evidence_normalization_worker", "requested_action": "normalize"},
            {"agent_name": "discovery_planning_agent", "requested_action": "plan"},
        ]
    ref_over = over.pop("ref_over", {})
    ref = EngagementPacketReference(
        packet_reference_id="pkt_1", owner_id="owner_1", client_id="client_a",
        engagement_id="eng_x", packet_schema_name="engagement-packet",
        packet_schema_version="1.0", packet_source_type="consultant_upload",
        packet_location_reference="controlled://engagement/eng_x/packet_1",
        packet_hash="sha256:abc", captured_by="consultant_a",
        captured_at="2026-07-18T09:00:00Z", authorization_scope="engagement_authorized",
        lifecycle_status="active",
    )
    for k, v in ref_over.items():
        setattr(ref, k, v)
    payload = {"requested_agent_tasks": agent_tasks}
    if extra_payload:
        payload.update(extra_payload)
    base = dict(
        owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
        requested_by="consultant_a", requester_role="consultant",
        authorization_scope="engagement_authorized", packet_reference=ref,
        packet_payload=payload, requested_ingestion_action="prepare_packet_ingestion_plan",
        source_phase="phase28", idempotency_key="idem-p28-1", lifecycle_status="active",
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
        STAGE_AGENT_TASK_QUEUE_READINESS, STAGE_AGENT_TASK_QUEUE_PERSISTENCE,
        process_engagement_packet,
    )
    from peak.task_queue.contracts import AgentTaskQueueDraft, AgentExecutionReadinessAssessment

    print("\n8. Plan-only integration (default)")
    r = process_engagement_packet(_make_request())
    check("permitted True", r.permitted is True)
    check("orchestration_outcome planned", r.orchestration_outcome == OrchestrationOutcome.PLANNED)
    check("agent_task_count == 2 (both known agents)", r.agent_task_count == 2)
    check("readiness stage completed",
          any(s.stage == STAGE_AGENT_TASK_QUEUE_READINESS and s.outcome == StageOutcome.COMPLETED
              for s in r.stage_results))
    check("task_queue_readiness_result present", r.task_queue_readiness_result is not None)
    check("task_queue_drafts present (2)", len(r.task_queue_drafts) == 2)
    check("drafts are Phase 26 AgentTaskQueueDraft objects",
          all(isinstance(d, AgentTaskQueueDraft) for d in r.task_queue_drafts))
    check("readiness assessments present (2)", len(r.task_queue_readiness_assessments) == 2)
    check("assessments are Phase 26 objects",
          all(isinstance(a, AgentExecutionReadinessAssessment)
              for a in r.task_queue_readiness_assessments))
    check("controlled write requests present (2)",
          len(r.task_queue_controlled_write_requests) == 2)
    check("cwrs target agent_task_queue_records/create_agent_task_queue_record",
          all(getattr(c, "target_table", None) == "agent_task_queue_records"
              and getattr(c, "requested_action", None) == "create_agent_task_queue_record"
              for c in r.task_queue_controlled_write_requests))
    check("draft/blocked/cwr counts", r.task_queue_draft_count == 2
          and r.task_queue_blocked_count == 0
          and r.task_queue_controlled_write_request_count == 2)
    check("drafts are review-gated + not-executed",
          all(d.output_status == "draft" and d.review_status == "needs_review"
              and d.execution_status == "not_executed" and d.execution_allowed is False
              and d.requires_human_review is True and d.agent_task_queue_record_id is None
              for d in r.task_queue_drafts))
    check("persistence stage skipped_not_requested",
          any(s.stage == STAGE_AGENT_TASK_QUEUE_PERSISTENCE
              and s.outcome == StageOutcome.SKIPPED_NOT_REQUESTED for s in r.stage_results))
    check("no task queue write receipts in plan-only", not r.task_queue_write_receipts)
    _assert_no_side_effects("plan-only", r)
    check("NO raw packet sentinel leaked", _SENTINEL not in _blob(r))
    # sentinel planted in an unmapped payload field must not surface
    rs = process_engagement_packet(_make_request(extra_payload={"unmapped_blob": _SENTINEL}))
    check("sentinel in unmapped payload not leaked", _SENTINEL not in _blob(rs))

    print("\n9. No silent escalation")
    f_dummy = lambda: None  # noqa: E731 - never called in these skip paths
    opts = OrchestrationStageOptions(plan_only=False, include_agent_task_queue_persistence=False)
    r2 = process_engagement_packet(_make_request(), options=opts, session_factory=f_dummy)
    check("persistence not included -> skipped_not_requested",
          any(s.stage == STAGE_AGENT_TASK_QUEUE_PERSISTENCE
              and s.outcome == StageOutcome.SKIPPED_NOT_REQUESTED for s in r2.stage_results))
    check("not-included: no writer receipts", not r2.task_queue_write_receipts)
    opts = OrchestrationStageOptions(plan_only=True, include_agent_task_queue_persistence=True)
    r3 = process_engagement_packet(_make_request(), options=opts)
    check("plan_only + persistence -> skipped_plan_only",
          any(s.stage == STAGE_AGENT_TASK_QUEUE_PERSISTENCE
              and s.outcome == StageOutcome.SKIPPED_PLAN_ONLY for s in r3.stage_results))
    check("plan_only escalation: db_write_made still False", r3.database_write_made is False)
    opts = OrchestrationStageOptions(plan_only=False, include_agent_task_queue_persistence=True)
    r4 = process_engagement_packet(_make_request(), options=opts, session_factory=None)
    check("persistence w/o session_factory -> skipped_missing_session_factory",
          any(s.stage == STAGE_AGENT_TASK_QUEUE_PERSISTENCE
              and s.outcome == StageOutcome.SKIPPED_MISSING_SESSION_FACTORY
              for s in r4.stage_results))
    check("missing session_factory does not fail packet", r4.permitted is True)
    _assert_no_side_effects("missing-session", r4)

    print("\n10. Readiness disabled")
    opts = OrchestrationStageOptions(include_agent_task_queue_readiness=False)
    r5 = process_engagement_packet(_make_request(), options=opts)
    check("readiness skipped_not_requested",
          any(s.stage == STAGE_AGENT_TASK_QUEUE_READINESS
              and s.outcome == StageOutcome.SKIPPED_NOT_REQUESTED for s in r5.stage_results))
    check("no drafts when readiness disabled", r5.task_queue_draft_count == 0)

    print("\n11. Mixed / blocked tasks (Phase 26 blocks in-band)")
    # An evidence-dependent agent (qa) with no evidence wired -> blocked_missing_evidence.
    r6 = process_engagement_packet(_make_request(agent_tasks=[
        {"agent_name": "evidence_normalization_worker", "requested_action": "normalize"},
        {"agent_name": "internal_qa_governance_agent", "requested_action": "qa"},
    ]))
    check("packet still planned (not denied)", r6.orchestration_outcome == OrchestrationOutcome.PLANNED)
    check("one task blocked by Phase 26", r6.task_queue_blocked_count == 1)
    check("blocked task creates no write request", r6.task_queue_controlled_write_request_count == 1)
    check("only the valid task drafted", r6.task_queue_draft_count == 1)

    print("\n12. Unknown agents filtered upstream at Phase 23 (never reach queue)")
    r7 = process_engagement_packet(_make_request(agent_tasks=[
        {"agent_name": "evidence_normalization_worker", "requested_action": "normalize"},
        {"agent_name": "nonexistent_agent"},
    ]))
    check("unknown agent absent from derived tasks", r7.agent_task_count == 1)
    check("unknown agent produced no draft", r7.task_queue_draft_count == 1)

    print("\n13. Denials still deny the whole packet")
    rl = process_engagement_packet(_make_request(lifecycle_status="revoked"))
    check("revoked lifecycle denied", rl.orchestration_outcome == OrchestrationOutcome.DENIED)
    _assert_no_side_effects("denied-packet", rl)


# --------------------------------------------------------------------------- DB-backed


def db_backed_checks() -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from peak.db.base import Base
    from peak.db.models import (
        AgentRunRecord, AgentTaskQueueRecord, Engagement, EvidenceReference, ReviewRecord,
        SourceIngestionRecord,
    )
    from peak.orchestration import (
        OrchestrationOutcome, OrchestrationStageOptions, StageOutcome,
        STAGE_AGENT_TASK_QUEUE_PERSISTENCE, process_engagement_packet,
    )

    tmpdirs: list = []

    def fresh_db():
        tmp = tempfile.mkdtemp(prefix="peak_phase28_")
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
        plan_only=False, include_agent_task_queue_persistence=True)

    print("\n14. Controlled task queue persistence (Phase 27 writer only)")
    f = fresh_db()
    seed(f)
    r = process_engagement_packet(_make_request(), options=persist_opts, session_factory=f)
    check("orchestration persisted", r.orchestration_outcome == OrchestrationOutcome.PERSISTED)
    check("queue persistence stage completed",
          any(s.stage == STAGE_AGENT_TASK_QUEUE_PERSISTENCE and s.outcome == StageOutcome.COMPLETED
              for s in r.stage_results))
    check("persisted count == valid drafts (2)", r.task_queue_persisted_count == 2)
    check("two write receipts attached", len(r.task_queue_write_receipts) == 2)
    check("receipts target agent_task_queue_records/create_agent_task_queue_record",
          all(w.target_table == "agent_task_queue_records"
              and w.target_action == "create_agent_task_queue_record"
              for w in r.task_queue_write_receipts))
    check("exactly two agent_task_queue_records rows", count(f, AgentTaskQueueRecord) == 2)
    check("DB flags reflect writer calls",
          r.database_connection_made and r.sql_execution_made and r.database_write_made
          and r.stored_record_created)
    check("execution/LLM/AgentNet/network flags stay False",
          r.agent_execution_made is False and r.mock_agent_execution_made is False
          and r.llm_call_made is False and r.agentnet_call_made is False
          and r.resolver_call_made is False and r.network_call_made is False)
    check("no client-facing / financial / capsule",
          r.client_facing_output_created is False and r.financial_verification_made is False
          and r.capsule_publication_made is False)
    check("NO agent_run_records created", count(f, AgentRunRecord) == 0)
    check("no unrelated rows (source/evidence/review)",
          count(f, SourceIngestionRecord) == 0 and count(f, EvidenceReference) == 0
          and count(f, ReviewRecord) == 0)

    print("\n15. Idempotent replay")
    r2 = process_engagement_packet(_make_request(), options=persist_opts, session_factory=f)
    check("replay outcome persisted", r2.orchestration_outcome == OrchestrationOutcome.PERSISTED)
    check("replay_count == 2", r2.task_queue_replay_count == 2)
    check("persisted_count == 0 on replay", r2.task_queue_persisted_count == 0)
    check("no new rows on replay", count(f, AgentTaskQueueRecord) == 2)

    print("\n16. Conflict (same key, different fingerprint)")
    f2 = fresh_db()
    seed(f2)
    process_engagement_packet(_make_request(), options=persist_opts, session_factory=f2)
    # Same agents/order (same per-task keys) but a changed requested_action -> new fingerprint.
    conflict_tasks = [
        {"agent_name": "evidence_normalization_worker", "requested_action": "DIFFERENT"},
        {"agent_name": "discovery_planning_agent", "requested_action": "plan"},
    ]
    rc = process_engagement_packet(_make_request(agent_tasks=conflict_tasks),
                                   options=persist_opts, session_factory=f2)
    check("conflict reported", rc.task_queue_conflict_count >= 1)
    check("conflict -> orchestration partial",
          rc.orchestration_outcome == OrchestrationOutcome.PARTIAL)
    check("conflict wrote no extra row for the conflicting task",
          count(f2, AgentTaskQueueRecord) == 2)

    print("\n17. Stored-Engagement authorization stays inside Phase 27 writer")
    f3 = fresh_db()
    seed(f3, authorization_scope="internal_peak_only")  # differs from request scope
    r3 = process_engagement_packet(_make_request(), options=persist_opts, session_factory=f3)
    check("writer denied stored-scope mismatch",
          all(w.reason_code == "stored_scope_mismatch" for w in r3.task_queue_write_receipts))
    check("no rows on scope mismatch", count(f3, AgentTaskQueueRecord) == 0)
    check("orchestration partial on writer denial",
          r3.orchestration_outcome == OrchestrationOutcome.PARTIAL)

    print("\n18. Regression: source + evidence persistence still work")
    f4 = fresh_db()
    seed(f4)
    reg_opts = OrchestrationStageOptions(
        plan_only=False, include_source_ingestion_persistence=True,
        include_evidence_normalization=True, include_evidence_persistence=True)
    reg_req = _make_request(extra_payload={
        "evidence_items": [{"id": "ev1", "text": "pallets blocking dock"}],
    })
    rr = process_engagement_packet(reg_req, options=reg_opts, session_factory=f4)
    check("source ingestion row created (Phase 24)", count(f4, SourceIngestionRecord) == 1)
    check("evidence rows created (Phase 18/21)", count(f4, EvidenceReference) >= 1)
    check("regression orchestration persisted",
          rr.orchestration_outcome == OrchestrationOutcome.PERSISTED)
    check("queue persistence not requested here -> no queue rows",
          count(f4, AgentTaskQueueRecord) == 0)
    check("regression: no agent_run_records", count(f4, AgentRunRecord) == 0)

    for tmp in tmpdirs:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    print("Peak Phase 28 packet -> task queue orchestration integration check")
    print("=" * 52)
    structural_checks()
    plan_only_checks()

    print("\n(DB-backed layer)")
    try:
        import sqlalchemy  # noqa: F401
    except ImportError:
        print("  [skip] SQLAlchemy not installed — controlled-persistence not exercised.")
        print("         Run: make validate-phase28 PYTHON=.venv/bin/python")
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
