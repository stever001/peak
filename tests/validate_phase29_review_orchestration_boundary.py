#!/usr/bin/env python3
"""Phase 29 Packet-Derived Review Orchestration Boundary check.

Stdlib-only; **no database** (Phase 29 is DB-free by construction). Structure:

* **Structural / baseline:** the package files + docs exist, compile, and import; the package
  imports no SQLAlchemy / Alembic / peak.db / live-or-mock LLM / AgentNet / MCP / resolver /
  connector / network module; the Phase 23 ingestion and Phase 26 task_queue packages stay DB-free;
  the Phase 28 commit is present; **no Phase 29 migration** was added (head stays
  006_agent_task_queue_records) and **no new DB table** was declared; the docs carry the required
  language; the repo stays source-only.

* **Functional:** a valid request produces review bundle drafts, review plan items, and a
  ready_for_human_review assessment — review-gated, not-approved — with every side-effect flag
  false; blocked/no-subject, identity/scope/lifecycle, intent, and content-safety denials behave;
  secret/raw values are never echoed.

* **Integration/handoff:** Phase 29 consumes safe references shaped like Phase 25/28 packet-
  processing output (receipt refs + id lists) and synthetic Phase 27-style ids, with no DB access.

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
    "peak/review_orchestration/__init__.py",
    "peak/review_orchestration/contracts.py",
    "peak/review_orchestration/governance.py",
    "peak/review_orchestration/review_planner.py",
    "docs/PACKET_DERIVED_REVIEW_ORCHESTRATION_BOUNDARY.md",
    "docs/REVIEW_ORCHESTRATION_GOVERNANCE_POLICY.md",
]
PY_FILES = [
    "peak/review_orchestration/__init__.py",
    "peak/review_orchestration/contracts.py",
    "peak/review_orchestration/governance.py",
    "peak/review_orchestration/review_planner.py",
]
PHASE23_FILES = [
    "peak/ingestion/contracts.py", "peak/ingestion/governance.py",
    "peak/ingestion/packet_mapper.py",
]
PHASE26_FILES = [
    "peak/task_queue/__init__.py", "peak/task_queue/contracts.py",
    "peak/task_queue/governance.py", "peak/task_queue/task_queue_mapper.py",
]
DOCS = [
    "docs/PACKET_DERIVED_REVIEW_ORCHESTRATION_BOUNDARY.md",
    "docs/REVIEW_ORCHESTRATION_GOVERNANCE_POLICY.md",
]
REQUIRED_PHRASES = [
    "review-planning boundary",
    '"ready for human review" never means approved',
    "db-free",
    "future persistence",
    "no new table, no migration",
    "identity matching is necessary but not sufficient",
    "review_records",
    "agent_run_records",
    "phase 26",
    "not an approval phase",
]

DB_IMPORT_RE = re.compile(r"\b(?:sqlalchemy|alembic|pymysql)\b|\bpeak\.db\b", re.IGNORECASE)
LLM_PROVIDER_RE = re.compile(
    r"\b(?:openai|anthropic|cohere|litellm|langchain|transformers|vertexai|mistralai|ollama)\b",
    re.IGNORECASE)
EXEC_IMPORT_RE = re.compile(r"\b(?:mock_llm|MockLLM|executor|MockAgentExecutor)\b")
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


def check(label: str, ok: bool) -> None:
    if ok:
        print(f"  [{PASS}] {label}")
    else:
        _failures.append(label)
        print(f"  [{FAIL}] {label}")


# --------------------------------------------------------------------------- structural


def structural_checks() -> None:
    print("\n1. Phase 29 scaffold files")
    for rel in REQUIRED_FILES:
        check(rel, os.path.isfile(os.path.join(REPO_ROOT, rel)))

    print("\n2. Python files compile")
    for rel in PY_FILES:
        try:
            py_compile.compile(os.path.join(REPO_ROOT, rel), doraise=True)
            check(f"{rel} compiles", True)
        except py_compile.PyCompileError:
            check(f"{rel} compiles", False)

    print("\n3. Phase 29 import discipline (DB-free, no exec/LLM/AgentNet/network)")
    for rel in PY_FILES:
        imports = list(_import_lines(read(rel)))
        check(f"{rel}: no DB/ORM/peak.db import",
              not [ln for ln in imports if DB_IMPORT_RE.search(ln)])
        check(f"{rel}: no LLM-provider import",
              not [ln for ln in imports if LLM_PROVIDER_RE.search(ln)])
        check(f"{rel}: no mock-LLM / executor import",
              not [ln for ln in imports if EXEC_IMPORT_RE.search(ln)])
        check(f"{rel}: no AgentNet/MCP/resolver/connector import",
              not [ln for ln in imports if CONNECTOR_RE.search(ln)])
        check(f"{rel}: no network import",
              not [ln for ln in imports if NETWORK_RE.search(ln)])

    print("\n4. Prior DB-free boundaries stay DB-free (regression)")
    for rel in PHASE23_FILES + PHASE26_FILES:
        hits = [ln for ln in _import_lines(read(rel)) if DB_IMPORT_RE.search(ln)]
        check(f"{rel}: no DB/ORM/peak.db import", not hits)

    print("\n5. Baseline: Phase 28 present, no Phase 29 migration / table")
    try:
        log = subprocess.check_output(
            ["git", "-C", REPO_ROOT, "log", "--oneline", "-8"], text=True)
        check("Phase 28 commit present in recent history",
              "Phase 28" in log or "2377320" in log)
    except Exception:
        check("Phase 28 commit present (git unavailable — skipped)", True)
    versions = sorted(v for v in os.listdir(os.path.join(REPO_ROOT, "alembic", "versions"))
                      if v.endswith(".py"))
    check("latest migration is 006_agent_task_queue_records",
          any(v.startswith("006_agent_task_queue_records") for v in versions))
    check("no 007_* migration added", not any(v.startswith("007") for v in versions))
    models = read("peak/db/models.py")
    check("no review_bundle table added to models", "review_bundle" not in models.lower())

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
    try:
        tracked = subprocess.run(
            ["git", "-C", REPO_ROOT, "ls-files", ".claude/settings.local.json"],
            capture_output=True, text=True).stdout.strip()
        check(".claude/settings.local.json is not tracked", tracked == "")
    except Exception:
        check(".claude/settings.local.json tracking check (git unavailable — skipped)", True)


# --------------------------------------------------------------------------- builders

_SENTINEL = "REVIEW-SECRET-SENTINEL-DO-NOT-LEAK"
_ALL_FLAGS = (
    "direct_database_write_made", "database_connection_made", "sql_execution_made",
    "stored_record_created", "review_approval_made", "client_facing_output_created",
    "financial_verification_made", "capsule_publication_made", "agent_execution_made",
    "mock_agent_execution_made", "llm_call_made", "agentnet_call_made", "resolver_call_made",
    "network_call_made",
)


def _request(**over):
    from peak.review_orchestration import PacketReviewOrchestrationRequest

    base = dict(
        owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
        requested_by="consultant_a", requester_role="consultant",
        authorization_scope="engagement_authorized", idempotency_key="idem-rev-1",
        packet_processing_receipt_ref="pkt_run_1",
        source_ingestion_record_ids=["ing_1"], evidence_reference_ids=["evid_1", "evid_2"],
        agent_task_queue_record_ids=["atq_1"], reviewer_role="internal_reviewer",
        review_reason="post-packet review", strict_mode=True,
        requested_action="prepare_packet_review_plan", source_phase="phase29",
        lifecycle_status="active",
    )
    base.update(over)
    return PacketReviewOrchestrationRequest(**base)


def _blob(r) -> str:
    parts = list(r.reasons) + list(r.warnings) + [str(r.reason_code)]
    if r.plan:
        parts += list(r.plan.reasons) + list(r.plan.warnings)
        for a in r.plan.readiness_assessments:
            parts += list(a.reasons) + list(a.warnings)
        for i in r.plan.review_plan_items:
            parts += list(i.reasons) + list(i.warnings)
    if r.validation_result:
        parts += list(r.validation_result.reasons)
    return " ".join(parts)


def _assert_no_side_effects(label, r) -> None:
    for flag in _ALL_FLAGS:
        check(f"{label}: {flag} False", getattr(r, flag) is False)


# --------------------------------------------------------------------------- functional


def functional_checks() -> None:
    from peak.review_orchestration import (
        OUTCOME_BLOCKED, OUTCOME_DENIED, OUTCOME_PLANNED,
        READY_FOR_HUMAN_REVIEW, BLOCKED_NO_SUBJECTS, BLOCKED_INVALID_SCOPE, BLOCKED_LIFECYCLE,
        BLOCKED_RAW_CONTENT, BLOCKED_SECRET_LIKE_CONTENT, BLOCKED_APPROVAL_INTENT,
        BLOCKED_EXECUTION_INTENT, BLOCKED_PUBLICATION_INTENT,
        BLOCKED_FINANCIAL_VERIFICATION_INTENT,
        ITEM_SOURCE_INGESTION_REVIEW, ITEM_EVIDENCE_REFERENCE_REVIEW,
        ITEM_AGENT_TASK_QUEUE_REVIEW, ITEM_PACKET_PROCESSING_REVIEW,
        ITEM_CROSS_STAGE_CONSISTENCY_REVIEW, ITEM_MISSING_EVIDENCE_REVIEW,
        ReviewBundleDraft, ReviewPlanItem, prepare_packet_review_plan,
    )

    print("\n8. Successful review planning")
    r = prepare_packet_review_plan(_request())
    check("outcome planned", r.outcome == OUTCOME_PLANNED)
    check("permitted True", r.permitted is True)
    check("one review bundle", r.review_bundle_count == 1)
    check("subject_count == 5 (1 src + 2 evid + 1 atq + 1 packet)", r.subject_count == 5)
    check("controlled_write_request_count == 0 (DB-free)", r.controlled_write_request_count == 0)
    check("readiness_assessment_count == 1", r.readiness_assessment_count == 1)
    types = {i.item_type for i in r.plan.review_plan_items}
    check("source_ingestion_review item", ITEM_SOURCE_INGESTION_REVIEW in types)
    check("evidence_reference_review item", ITEM_EVIDENCE_REFERENCE_REVIEW in types)
    check("agent_task_queue_review item", ITEM_AGENT_TASK_QUEUE_REVIEW in types)
    check("packet_processing_review item", ITEM_PACKET_PROCESSING_REVIEW in types)
    check("cross_stage_consistency_review item", ITEM_CROSS_STAGE_CONSISTENCY_REVIEW in types)
    check("all items are ReviewPlanItem + needs_review",
          all(isinstance(i, ReviewPlanItem) and i.status == "needs_review"
              for i in r.plan.review_plan_items))
    b = r.plan.review_bundles[0]
    check("bundle is ReviewBundleDraft", isinstance(b, ReviewBundleDraft))
    check("bundle has no id / created_at", b.review_bundle_id is None and b.created_at is None)
    check("bundle output_status draft", b.output_status == "draft")
    check("bundle review_status needs_review", b.review_status == "needs_review")
    check("bundle lifecycle_status draft", b.lifecycle_status == "draft")
    check("bundle posture flags all safe",
          b.authoritative is False and b.client_facing_approved is False
          and b.capsule_candidate_ready is False and b.financial_verified is False
          and b.execution_allowed is False and b.approval_allowed is False
          and b.publication_allowed is False and b.requires_human_review is True)
    check("readiness ready_for_human_review",
          r.plan.readiness_assessments[0].readiness_state == READY_FOR_HUMAN_REVIEW)
    check("readiness assessment not approved",
          r.plan.readiness_assessments[0].approval_allowed is False)
    _assert_no_side_effects("planned", r)
    check("NO secret/raw sentinel leaked", _SENTINEL not in _blob(r))

    print("\n9. Per-subject-type items")
    check("source only -> source item",
          ITEM_SOURCE_INGESTION_REVIEW in {i.item_type for i in prepare_packet_review_plan(
              _request(evidence_reference_ids=[], agent_task_queue_record_ids=[],
                       packet_processing_receipt_ref=None)).plan.review_plan_items})
    check("evidence only -> evidence item",
          ITEM_EVIDENCE_REFERENCE_REVIEW in {i.item_type for i in prepare_packet_review_plan(
              _request(source_ingestion_record_ids=[], agent_task_queue_record_ids=[],
                       packet_processing_receipt_ref=None)).plan.review_plan_items})
    check("task only -> agent_task_queue item",
          ITEM_AGENT_TASK_QUEUE_REVIEW in {i.item_type for i in prepare_packet_review_plan(
              _request(source_ingestion_record_ids=[], evidence_reference_ids=[],
                       packet_processing_receipt_ref=None)).plan.review_plan_items})
    check("packet ref only -> packet_processing item",
          {i.item_type for i in prepare_packet_review_plan(
              _request(source_ingestion_record_ids=[], evidence_reference_ids=[],
                       agent_task_queue_record_ids=[])).plan.review_plan_items}
          == {ITEM_PACKET_PROCESSING_REVIEW})

    print("\n10. Missing-evidence exception item")
    rme = prepare_packet_review_plan(_request(evidence_reference_ids=[],
                                              packet_processing_receipt_ref=None))
    check("missing_evidence_review item present",
          ITEM_MISSING_EVIDENCE_REVIEW in {i.item_type for i in rme.plan.review_plan_items})

    print("\n11. No-subject behavior")
    rstrict = prepare_packet_review_plan(
        _request(source_ingestion_record_ids=[], evidence_reference_ids=[],
                 agent_task_queue_record_ids=[], packet_processing_receipt_ref=None))
    check("strict + no subjects -> denied", rstrict.outcome == OUTCOME_DENIED)
    _assert_no_side_effects("strict-no-subjects", rstrict)
    rns = prepare_packet_review_plan(
        _request(strict_mode=False, source_ingestion_record_ids=[], evidence_reference_ids=[],
                 agent_task_queue_record_ids=[], packet_processing_receipt_ref=None))
    check("non-strict + no subjects -> blocked, permitted True",
          rns.outcome == OUTCOME_BLOCKED and rns.permitted is True)
    check("non-strict no subjects -> blocked_no_subjects",
          rns.plan.readiness_assessments[0].readiness_state == BLOCKED_NO_SUBJECTS)
    check("non-strict no subjects: no stored record claim",
          rns.stored_record_created is False and rns.review_bundle_count == 0)
    _assert_no_side_effects("non-strict-no-subjects", rns)

    print("\n12. Identity / scope / lifecycle denials")
    for attr in ("owner_id", "client_id", "engagement_id", "authorization_scope",
                 "idempotency_key"):
        check(f"missing {attr} -> denied",
              prepare_packet_review_plan(_request(**{attr: None})).outcome == OUTCOME_DENIED)
    for lc in ("revoked", "archived", "deleted_reference_only"):
        rl = prepare_packet_review_plan(_request(lifecycle_status=lc))
        check(f"lifecycle {lc} -> denied + blocked_lifecycle",
              rl.outcome == OUTCOME_DENIED
              and rl.plan.readiness_assessments[0].readiness_state == BLOCKED_LIFECYCLE)
    # structured subject ref mismatch via context
    for attr in ("owner_id", "client_id", "engagement_id", "authorization_scope"):
        rm = prepare_packet_review_plan(_request(context={"subject_refs": [{attr: "WRONG"}]}))
        check(f"structured subject {attr} mismatch -> denied blocked_invalid_scope",
              rm.outcome == OUTCOME_DENIED
              and rm.plan.readiness_assessments[0].readiness_state == BLOCKED_INVALID_SCOPE)

    print("\n13. Intent denials")
    intents = {
        "approve_review": BLOCKED_APPROVAL_INTENT,
        "client_facing_output_requested": BLOCKED_APPROVAL_INTENT,
        "execute_now": BLOCKED_EXECUTION_INTENT,
        "run_agent": BLOCKED_EXECUTION_INTENT,
        "publish_capsule": BLOCKED_PUBLICATION_INTENT,
        "verify_financial_impact": BLOCKED_FINANCIAL_VERIFICATION_INTENT,
    }
    for key, state in intents.items():
        ri = prepare_packet_review_plan(_request(context={key: True}))
        check(f"intent '{key}' -> denied ({state})",
              ri.outcome == OUTCOME_DENIED
              and ri.plan.readiness_assessments[0].readiness_state == state)
    # approval via requested_action
    ra = prepare_packet_review_plan(_request(requested_action="approve_internal"))
    check("requested_action approve_internal -> denied blocked_approval_intent",
          ra.outcome == OUTCOME_DENIED
          and ra.plan.readiness_assessments[0].readiness_state == BLOCKED_APPROVAL_INTENT)

    print("\n14. Content safety (rejected without echoing values)")
    # ad-hoc raw / secret attributes on the request
    for attr in ("packet_payload", "raw_packet_content", "raw_evidence_text",
                 "raw_interview_text", "source_bytes", "generated_output", "api_key",
                 "connection_string"):
        req = _request()
        setattr(req, attr, {"x": _SENTINEL} if attr.endswith(("payload", "content")) else _SENTINEL)
        rr = prepare_packet_review_plan(req)
        check(f"ad-hoc '{attr}' rejected", rr.outcome == OUTCOME_DENIED)
        check(f"'{attr}' value not echoed", _SENTINEL not in _blob(rr))
    # arbitrary JSON / raw text in a ref list
    rj = prepare_packet_review_plan(_request(source_ingestion_record_ids=[{"packet": "json"}]))
    check("arbitrary JSON ref -> denied blocked_raw_content",
          rj.outcome == OUTCOME_DENIED
          and rj.plan.readiness_assessments[0].readiness_state == BLOCKED_RAW_CONTENT)
    rtext = prepare_packet_review_plan(
        _request(evidence_reference_ids=["line one\nline two with raw interview text"]))
    check("multiline raw text ref -> denied blocked_raw_content",
          rtext.outcome == OUTCOME_DENIED
          and rtext.plan.readiness_assessments[0].readiness_state == BLOCKED_RAW_CONTENT)
    # secret-like context key + reviewer_role as email
    rs = prepare_packet_review_plan(_request(context={"password": _SENTINEL}))
    check("secret-like key -> denied blocked_secret_like_content",
          rs.outcome == OUTCOME_DENIED
          and rs.plan.readiness_assessments[0].readiness_state == BLOCKED_SECRET_LIKE_CONTENT)
    check("secret value not echoed", _SENTINEL not in _blob(rs))
    rre = prepare_packet_review_plan(_request(reviewer_role="reviewer@example.com"))
    check("reviewer_role email -> denied", rre.outcome == OUTCOME_DENIED)


# --------------------------------------------------------------------------- integration


def integration_checks() -> None:
    from peak.review_orchestration import OUTCOME_PLANNED, prepare_packet_review_plan

    print("\n15. Consumes Phase 25/28-shaped safe references (documented handoff)")
    # Shape mirrors a Phase 25/28 PacketProcessingReceipt handoff: a receipt ref + safe id lists.
    r = prepare_packet_review_plan(_request(
        packet_processing_receipt_ref="pktproc::idem-p28-1",
        source_ingestion_record_ids=["ing_aaaaaaaaaaaaaaaa"],
        evidence_reference_ids=["evid_bbbbbbbbbbbbbbbb"],
        agent_task_queue_record_ids=["atq_cccccccccccccccc"]))
    check("consumes Phase 25/28-shaped refs -> planned", r.outcome == OUTCOME_PLANNED)
    check("no DB access needed (all flags false)",
          all(getattr(r, f) is False for f in _ALL_FLAGS))

    print("\n16. Consumes synthetic Phase 27-style queue ids without DB")
    r2 = prepare_packet_review_plan(_request(
        source_ingestion_record_ids=[], evidence_reference_ids=[],
        packet_processing_receipt_ref=None,
        agent_task_queue_record_ids=["atq_1111111111111111", "atq_2222222222222222"]))
    check("consumes atq_ ids -> planned", r2.outcome == OUTCOME_PLANNED)

    print("\n17. Does not import Phase 27 writer / Phase 22 writer")
    joined = "\n".join(read(rel) for rel in PY_FILES)
    check("no agent_task_queue_writer import", "agent_task_queue_writer" not in joined)
    check("no review_writer import", "review_writer" not in joined)
    check("no review_records write concept in package", "review_records" not in joined)


def main() -> int:
    print("Peak Phase 29 packet-derived review orchestration boundary check")
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
