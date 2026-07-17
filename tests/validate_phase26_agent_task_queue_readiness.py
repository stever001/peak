#!/usr/bin/env python3
"""Phase 26 Controlled Agent Task Queue / Execution Readiness Boundary check.

Stdlib-only; **no database** (Phase 26 is DB-free by construction). Structure:

* **Structural / baseline:** the package files exist and compile and import; the Phase 26
  package imports no SQLAlchemy / Alembic / ``peak.db`` / live-or-mock LLM / AgentNet / MCP /
  resolver / connector / network module; the Phase 23 ingestion package stays DB-free; the
  Phase 25 commit is present in recent history; and no Phase 26 migration was added (Alembic
  head stays ``005_source_ingestion_idem``).
* **Functional:** a valid queue request becomes review-gated, non-executed queue drafts +
  readiness assessments + plan-only Phase 17 write requests; multiple tasks get distinct
  per-task idempotency keys; known agents are accepted and unknown agents blocked; identity /
  scope / lifecycle / policy denials behave; raw-content and secret fields are rejected without
  echoing values; every side-effect flag stays ``False``.
* **Integration:** Phase 26 consumes the exact Phase 13 ``AgentTaskRequest`` objects produced
  by the Phase 23 ingestion boundary and surfaced by the Phase 25 orchestrator (plan-only),
  still with no side effects.
* **Hygiene:** the repo stays source-only; ``.claude/settings.local.json`` stays untracked.

Exit status: 0 all passed; 1 a check failed.
"""

from __future__ import annotations

import os
import py_compile
import re
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

REQUIRED_FILES = [
    "peak/task_queue/__init__.py",
    "peak/task_queue/contracts.py",
    "peak/task_queue/governance.py",
    "peak/task_queue/task_queue_mapper.py",
    "docs/AGENT_TASK_QUEUE_READINESS_BOUNDARY.md",
    "docs/AGENT_TASK_QUEUE_GOVERNANCE_POLICY.md",
]
PY_FILES = [
    "peak/task_queue/__init__.py",
    "peak/task_queue/contracts.py",
    "peak/task_queue/governance.py",
    "peak/task_queue/task_queue_mapper.py",
]
PHASE23_FILES = [
    "peak/ingestion/contracts.py",
    "peak/ingestion/governance.py",
    "peak/ingestion/packet_mapper.py",
]
DOCS = [
    "docs/AGENT_TASK_QUEUE_READINESS_BOUNDARY.md",
    "docs/AGENT_TASK_QUEUE_GOVERNANCE_POLICY.md",
]
REQUIRED_PHRASES = [
    "execution readiness",
    "not executed",
    "ready\" never means \"execute now",
    "no db",
    "no live llm",
    "no agentnet",
    "no mock",
    "review-gated",
    "a future phase 27",
    "identity matching is necessary but not sufficient",
]

# Forbidden top-level/any imports in the Phase 26 package.
DB_IMPORT_RE = re.compile(r"\b(?:sqlalchemy|alembic|pymysql)\b|\bpeak\.db\b", re.IGNORECASE)
LLM_IMPORT_RE = re.compile(
    r"\b(?:openai|anthropic|cohere|litellm|langchain|transformers|vertexai|mistralai|ollama)\b",
    re.IGNORECASE,
)
EXEC_IMPORT_RE = re.compile(r"\b(?:mock_llm|MockLLM|executor|MockAgentExecutor)\b")
CONNECTOR_RE = re.compile(r"\b(?:agentnet|mcp_connector|mcp|resolver_client|resolver)\b", re.IGNORECASE)
NETWORK_RE = re.compile(
    r"\b(?:requests|socket|urllib|httpx|aiohttp|ftplib|smtplib|telnetlib|http\.client)\b"
)
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


def check(label: str, ok: bool) -> None:
    if ok:
        print(f"  [{PASS}] {label}")
    else:
        _failures.append(label)
        print(f"  [{FAIL}] {label}")


# --------------------------------------------------------------------------- structural


def structural_checks() -> None:
    print("\n1. Phase 26 scaffold files")
    for rel in REQUIRED_FILES:
        check(rel, os.path.isfile(os.path.join(REPO_ROOT, rel)))

    print("\n2. Python files compile")
    for rel in PY_FILES:
        try:
            py_compile.compile(os.path.join(REPO_ROOT, rel), doraise=True)
            check(f"{rel} compiles", True)
        except py_compile.PyCompileError:
            check(f"{rel} compiles", False)

    print("\n3. Phase 26 import discipline (DB-free, no exec/LLM/AgentNet/network)")
    for rel in PY_FILES:
        imports = list(_import_lines(read(rel)))
        check(f"{rel}: no DB/ORM/peak.db import",
              not [ln for ln in imports if DB_IMPORT_RE.search(ln)])
        check(f"{rel}: no LLM-provider import",
              not [ln for ln in imports if LLM_IMPORT_RE.search(ln)])
        check(f"{rel}: no mock-LLM / executor import",
              not [ln for ln in imports if EXEC_IMPORT_RE.search(ln)])
        check(f"{rel}: no AgentNet/MCP/resolver import",
              not [ln for ln in imports if CONNECTOR_RE.search(ln)])
        check(f"{rel}: no network import",
              not [ln for ln in imports if NETWORK_RE.search(ln)])

    print("\n4. Phase 23 ingestion stays DB-free (regression)")
    for rel in PHASE23_FILES:
        hits = [ln for ln in _import_lines(read(rel)) if DB_IMPORT_RE.search(ln)]
        check(f"{rel}: no DB/ORM/peak.db import", not hits)

    print("\n5. Baseline: Phase 25 present, no Phase 26 migration")
    try:
        log = subprocess.check_output(
            ["git", "-C", REPO_ROOT, "log", "--oneline", "-8"], text=True
        )
        check("Phase 25 commit present in recent history",
              "Phase 25" in log or "d6fa2bb" in log)
    except Exception:
        check("Phase 25 commit present in recent history (git unavailable — skipped)", True)
    versions_dir = os.path.join(REPO_ROOT, "alembic", "versions")
    versions = sorted(v for v in os.listdir(versions_dir) if v.endswith(".py"))
    check("exactly 5 migration files (001..005)", len(versions) == 5)
    check("no 006_* migration added", not any(v.startswith("006") for v in versions))

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
    # .claude/settings.local.json must not be tracked.
    try:
        tracked = subprocess.run(
            ["git", "-C", REPO_ROOT, "ls-files", ".claude/settings.local.json"],
            capture_output=True, text=True,
        ).stdout.strip()
        check(".claude/settings.local.json is not tracked", tracked == "")
    except Exception:
        check(".claude/settings.local.json tracking check (git unavailable — skipped)", True)


# --------------------------------------------------------------------------- builders

_SENTINEL = "TASKQ-SECRET-SENTINEL-DO-NOT-LEAK"

_SIDE_EFFECT_FLAGS = (
    "direct_database_write_made",
    "database_connection_made",
    "sql_execution_made",
    "stored_record_created",
    "agent_execution_made",
    "mock_agent_execution_made",
    "llm_call_made",
    "agentnet_call_made",
    "resolver_call_made",
    "network_call_made",
    "client_facing_output_created",
    "financial_verification_made",
    "capsule_publication_made",
)


def _task(agent_name, **over):
    from peak.agents.contracts import AgentTaskRequest

    base = dict(
        agent_name=agent_name,
        owner_id="owner_1",
        client_id="client_a",
        engagement_id="eng_x",
        requested_action="normalize",
        authorization_scope="engagement_authorized",
        review_status="needs_review",
        lifecycle_status="draft",
        resolver_context_allowed=False,
        llm_execution_allowed=False,
        client_facing_output_requested=False,
    )
    base.update(over)
    return AgentTaskRequest(**base)


def _request(tasks, **over):
    from peak.task_queue import AgentTaskQueueRequest

    base = dict(
        owner_id="owner_1",
        client_id="client_a",
        engagement_id="eng_x",
        requested_by="consultant_a",
        requester_role="consultant",
        authorization_scope="engagement_authorized",
        idempotency_key="idem-q-1",
        agent_task_requests=list(tasks),
        requested_action="prepare_agent_task_queue_plan",
        source_phase="phase26",
        lifecycle_status="active",
    )
    base.update(over)
    return AgentTaskQueueRequest(**base)


def _assert_no_side_effects(label, result) -> None:
    for flag in _SIDE_EFFECT_FLAGS:
        check(f"{label}: {flag} False", getattr(result, flag) is False)


def _blob(result) -> str:
    parts = list(result.reasons) + list(result.warnings) + [str(result.reason_code)]
    if result.plan:
        parts += list(result.plan.warnings) + list(result.plan.reasons)
        for a in result.plan.readiness_assessments:
            parts += list(a.reasons) + list(a.warnings)
    if result.validation_result:
        parts += list(result.validation_result.reasons)
    return " ".join(parts)


# --------------------------------------------------------------------------- functional


def functional_checks() -> None:
    from peak.task_queue import (
        OUTCOME_BLOCKED, OUTCOME_DENIED, OUTCOME_PARTIAL, OUTCOME_PLANNED,
        QUEUED_FOR_REVIEW, READY_FOR_FUTURE_CONTROLLED_EXECUTION,
        BLOCKED_UNKNOWN_AGENT, BLOCKED_BY_POLICY, BLOCKED_INVALID_SCOPE,
        BLOCKED_LIFECYCLE, BLOCKED_MISSING_EVIDENCE,
        prepare_agent_task_queue_plan,
    )

    print("\n8. Successful readiness planning (single valid task)")
    r = prepare_agent_task_queue_plan(_request([_task("new_client_intake_agent")]))
    check("outcome planned", r.outcome == OUTCOME_PLANNED)
    check("permitted True", r.permitted is True)
    check("task_count_received == 1", r.task_count_received == 1)
    check("queue_draft_count == 1", r.queue_draft_count == 1)
    check("controlled_write_request_count == 1", r.controlled_write_request_count == 1)
    check("blocked_task_count == 0", r.blocked_task_count == 0)
    d = r.plan.queue_drafts[0]
    check("draft has no record id", d.agent_task_queue_record_id is None)
    check("draft has no created_at", d.created_at is None)
    check("draft output_status draft", d.output_status == "draft")
    check("draft review_status needs_review", d.review_status == "needs_review")
    check("draft requires_human_review True", d.requires_human_review is True)
    check("draft execution_status not_executed", d.execution_status == "not_executed")
    check("draft execution_allowed False", d.execution_allowed is False)
    check("draft llm_execution_allowed False", d.llm_execution_allowed is False)
    check("draft agentnet_context_allowed False", d.agentnet_context_allowed is False)
    check("draft resolver_context_allowed False", d.resolver_context_allowed is False)
    check("draft network_allowed False", d.network_allowed is False)
    check("draft authoritative/client_facing/capsule all False",
          not d.authoritative and not d.client_facing_approved and not d.capsule_candidate_ready)
    check("draft idempotency key deterministic per task",
          d.idempotency_key == "idem-q-1::taskq::0::new_client_intake_agent")
    check("readiness queued_for_review (no evidence wired)",
          r.plan.readiness_assessments[0].readiness_state == QUEUED_FOR_REVIEW)
    cwr = r.plan.controlled_write_requests[0]
    check("CWR targets agent_task_queue_records/create_agent_task_queue_record",
          cwr.target_table == "agent_task_queue_records"
          and cwr.requested_action == "create_agent_task_queue_record")
    check("CWR subject is the engagement", cwr.subject.subject_record_type == "engagement")
    check("CWR idempotency key matches draft", cwr.idempotency_key == d.idempotency_key)
    _assert_no_side_effects("single-task", r)

    print("\n9. Ready-for-future when evidence input is wired")
    r2 = prepare_agent_task_queue_plan(
        _request([_task("new_client_intake_agent")], evidence_reference_ids=["evid_1"])
    )
    check("readiness ready_for_future_controlled_execution",
          r2.plan.readiness_assessments[0].readiness_state
          == READY_FOR_FUTURE_CONTROLLED_EXECUTION)
    check("still execution_allowed False on draft",
          r2.plan.queue_drafts[0].execution_allowed is False)
    check("still requires_human_review True",
          r2.plan.queue_drafts[0].requires_human_review is True)

    print("\n10. Multiple valid tasks -> distinct per-task idempotency keys")
    r3 = prepare_agent_task_queue_plan(
        _request([_task("new_client_intake_agent"), _task("evidence_normalization_worker"),
                  _task("discovery_planning_agent")])
    )
    check("outcome planned", r3.outcome == OUTCOME_PLANNED)
    check("queue_draft_count == 3", r3.queue_draft_count == 3)
    keys = [d.idempotency_key for d in r3.plan.queue_drafts]
    check("per-task idempotency keys do not collide", len(set(keys)) == 3)
    check("queue_draft_count matches valid task count", r3.queue_draft_count == 3)

    print("\n11. Known / unknown agent behavior")
    r4 = prepare_agent_task_queue_plan(
        _request([_task("new_client_intake_agent"), _task("nonexistent_agent")])
    )
    check("outcome partial (one valid, one blocked)", r4.outcome == OUTCOME_PARTIAL)
    check("queue_draft_count == 1", r4.queue_draft_count == 1)
    check("blocked_task_count == 1", r4.blocked_task_count == 1)
    states = [a.readiness_state for a in r4.plan.readiness_assessments]
    check("unknown agent -> blocked_unknown_agent", BLOCKED_UNKNOWN_AGENT in states)
    check("unknown agent creates no draft",
          all(d.agent_name != "nonexistent_agent" for d in r4.plan.queue_drafts))
    r4b = prepare_agent_task_queue_plan(_request([_task("nonexistent_agent")]))
    check("all-unknown -> outcome blocked", r4b.outcome == OUTCOME_BLOCKED)
    check("all-unknown -> permitted True (request itself valid)", r4b.permitted is True)
    check("all-unknown -> no drafts", r4b.queue_draft_count == 0)

    print("\n12. Identity / scope / lifecycle denials")
    # request-level: missing scope / idempotency
    check("missing authorization_scope -> denied",
          prepare_agent_task_queue_plan(
              _request([_task("new_client_intake_agent", authorization_scope=None)],
                       authorization_scope=None)).outcome == OUTCOME_DENIED)
    check("missing idempotency_key -> denied",
          prepare_agent_task_queue_plan(
              _request([_task("new_client_intake_agent")], idempotency_key=None)).outcome
          == OUTCOME_DENIED)
    check("no tasks -> denied",
          prepare_agent_task_queue_plan(_request([])).outcome == OUTCOME_DENIED)
    check("lifecycle revoked -> denied",
          prepare_agent_task_queue_plan(
              _request([_task("new_client_intake_agent")], lifecycle_status="revoked")).outcome
          == OUTCOME_DENIED)
    check("lifecycle archived -> denied",
          prepare_agent_task_queue_plan(
              _request([_task("new_client_intake_agent")], lifecycle_status="archived")).outcome
          == OUTCOME_DENIED)
    check("lifecycle deleted_reference_only -> denied",
          prepare_agent_task_queue_plan(
              _request([_task("new_client_intake_agent")],
                       lifecycle_status="deleted_reference_only")).outcome == OUTCOME_DENIED)
    # per-task identity/scope mismatch -> blocked_invalid_scope
    for attr in ("owner_id", "client_id", "engagement_id"):
        rr = prepare_agent_task_queue_plan(
            _request([_task("new_client_intake_agent", **{attr: "WRONG"})]))
        st = rr.plan.readiness_assessments[0].readiness_state if rr.plan else None
        check(f"task {attr} mismatch -> blocked_invalid_scope",
              rr.outcome == OUTCOME_BLOCKED and st == BLOCKED_INVALID_SCOPE)
    rr = prepare_agent_task_queue_plan(
        _request([_task("new_client_intake_agent", authorization_scope="internal_peak_only")]))
    check("task scope mismatch -> blocked_invalid_scope",
          rr.plan.readiness_assessments[0].readiness_state == BLOCKED_INVALID_SCOPE)
    rr = prepare_agent_task_queue_plan(
        _request([_task("new_client_intake_agent", lifecycle_status="revoked")]))
    check("task lifecycle revoked -> blocked_lifecycle",
          rr.plan.readiness_assessments[0].readiness_state == BLOCKED_LIFECYCLE)

    print("\n13. Policy denials (per-task blocked_by_policy)")
    for flag in ("llm_execution_allowed", "resolver_context_allowed",
                 "client_facing_output_requested"):
        rr = prepare_agent_task_queue_plan(
            _request([_task("new_client_intake_agent", **{flag: True})]))
        st = rr.plan.readiness_assessments[0].readiness_state if rr.plan else None
        check(f"task {flag}=True -> blocked_by_policy", st == BLOCKED_BY_POLICY)
        _assert_no_side_effects(f"policy-{flag}", rr)
    # request-level intent keys (network / financial / capsule / live execution / mock exec)
    for key in ("request_network", "verify_financial_impact", "publish_capsule",
                "execute_now", "run_agent_now", "mock_agent_execution"):
        rr = prepare_agent_task_queue_plan(
            _request([_task("new_client_intake_agent")], context={key: True}))
        check(f"context intent key '{key}' -> denied", rr.outcome == OUTCOME_DENIED)

    print("\n14. Missing-evidence classification")
    rr = prepare_agent_task_queue_plan(_request([_task("internal_qa_governance_agent")]))
    check("evidence-dependent agent w/o evidence -> blocked_missing_evidence",
          rr.plan.readiness_assessments[0].readiness_state == BLOCKED_MISSING_EVIDENCE)
    check("blocked_missing_evidence sets missing_evidence flag",
          rr.plan.readiness_assessments[0].missing_evidence is True)
    rr2 = prepare_agent_task_queue_plan(
        _request([_task("internal_qa_governance_agent")], evidence_reference_ids=["evid_1"]))
    check("same agent WITH evidence -> ready_for_future",
          rr2.plan.readiness_assessments[0].readiness_state
          == READY_FOR_FUTURE_CONTROLLED_EXECUTION)

    print("\n15. Content safety (raw payload / evidence / source bytes / secret)")
    # raw packet payload as an ad-hoc attribute
    req = _request([_task("new_client_intake_agent")])
    req.packet_payload = {"evidence_items": [{"text": _SENTINEL}]}
    rp = prepare_agent_task_queue_plan(req)
    check("raw packet_payload field -> denied", rp.outcome == OUTCOME_DENIED)
    check("packet payload sentinel not echoed", _SENTINEL not in _blob(rp))
    # raw evidence text via context
    re_ = prepare_agent_task_queue_plan(
        _request([_task("new_client_intake_agent")], context={"raw_evidence_text": _SENTINEL}))
    check("raw evidence text field -> denied", re_.outcome == OUTCOME_DENIED)
    check("raw evidence sentinel not echoed", _SENTINEL not in _blob(re_))
    # source bytes via context
    rb = prepare_agent_task_queue_plan(
        _request([_task("new_client_intake_agent")], context={"source_bytes": _SENTINEL}))
    check("source bytes field -> denied", rb.outcome == OUTCOME_DENIED)
    check("source bytes sentinel not echoed", _SENTINEL not in _blob(rb))
    # interview text via context
    ri = prepare_agent_task_queue_plan(
        _request([_task("new_client_intake_agent")], context={"interview_text": _SENTINEL}))
    check("raw interview text field -> denied", ri.outcome == OUTCOME_DENIED)
    # secret-like key via context
    rs = prepare_agent_task_queue_plan(
        _request([_task("new_client_intake_agent")], context={"api_key": _SENTINEL}))
    check("secret-like key -> denied", rs.outcome == OUTCOME_DENIED)
    check("secret value never echoed", _SENTINEL not in _blob(rs))

    print("\n16. Side-effect flags across outcomes")
    for label, res in (
        ("planned", r), ("partial", r4), ("blocked", r4b),
        ("denied", prepare_agent_task_queue_plan(_request([]))),
    ):
        _assert_no_side_effects(label, res)


# --------------------------------------------------------------------------- integration


def integration_checks() -> None:
    from peak.task_queue import OUTCOME_PLANNED, prepare_agent_task_queue_plan

    print("\n17. Consumes Phase 23-derived AgentTaskRequest objects")
    from peak.ingestion.contracts import EngagementPacketReference, PacketIngestionRequest
    from peak.ingestion.packet_mapper import prepare_packet_ingestion

    ref = EngagementPacketReference(
        packet_reference_id="pkt_1", owner_id="owner_1", client_id="client_a",
        engagement_id="eng_x", packet_schema_name="engagement-packet",
        packet_schema_version="1.0", packet_source_type="consultant_upload",
        packet_location_reference="controlled://engagement/eng_x/packet_1",
        packet_hash="sha256:abc", captured_by="consultant_a",
        captured_at="2026-07-17T09:00:00Z", authorization_scope="engagement_authorized",
        lifecycle_status="active",
    )
    packet_req = PacketIngestionRequest(
        owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
        requested_by="consultant_a", requester_role="consultant",
        authorization_scope="engagement_authorized", packet_reference=ref,
        packet_payload={"requested_agent_tasks": [
            {"agent_name": "evidence_normalization_worker", "requested_action": "normalize"},
        ]},
        requested_ingestion_action="prepare_packet_ingestion_plan",
        source_phase="phase23", idempotency_key="idem-pkt-1", lifecycle_status="active",
    )
    ing = prepare_packet_ingestion(packet_req)
    derived = ing.ingestion_plan.agent_task_plan.agent_task_requests
    check("Phase 23 derived >=1 agent task", len(derived) >= 1)
    q = prepare_agent_task_queue_plan(_request(derived))
    check("Phase 26 plans Phase 23-derived tasks", q.outcome == OUTCOME_PLANNED)
    check("Phase 26 queued the derived task(s)", q.queue_draft_count == len(derived))
    _assert_no_side_effects("phase23-integration", q)

    print("\n18. Consumes Phase 25 orchestrator-surfaced AgentTaskRequest objects (plan-only)")
    from peak.orchestration import process_engagement_packet
    receipt = process_engagement_packet(packet_req)
    surfaced = receipt.agent_task_requests
    check("Phase 25 plan-only surfaced >=1 agent task", len(surfaced) >= 1)
    check("Phase 25 receipt made no DB write", receipt.database_write_made is False)
    q2 = prepare_agent_task_queue_plan(_request(surfaced))
    check("Phase 26 plans Phase 25-surfaced tasks", q2.outcome == OUTCOME_PLANNED)
    _assert_no_side_effects("phase25-integration", q2)


def main() -> int:
    print("Peak Phase 26 agent task queue / execution readiness check")
    print("=" * 52)
    structural_checks()
    functional_checks()
    integration_checks()
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
