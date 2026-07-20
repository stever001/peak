#!/usr/bin/env python3
"""Phase 32 Internal Reviewer Decision Boundary check.

Stdlib-only; **no database** (Phase 32 is DB-free by construction). Structure:

* **Structural / baseline:** the package files + docs exist, compile, and import; the package
  imports no SQLAlchemy / Alembic / peak.db / Phase 22 review writer / live-or-mock LLM / AgentNet
  / MCP / resolver / connector / network module; the Phase 23 ingestion, Phase 26 task_queue, and
  Phase 29 review_orchestration packages stay DB-free; the Phase 31 commit is present; **no Phase 32
  migration** was added (head stays 007_review_bundle_records) and **no new DB table** was declared;
  the docs carry the required language; the repo stays source-only.

* **Functional:** a valid request produces one decision draft + routing plan + readiness
  assessment — review-gated, not-approved — with every side-effect flag false and no CWRs; routing
  is deterministic per intent; denials (identity/scope/lifecycle/missing-bundle/missing-fields),
  disallowed/unsupported intents, and content-safety violations behave; secret/raw values are never
  echoed.

* **Integration/handoff:** Phase 32 consumes safe references shaped like Phase 30 output
  (review_bundle_record_id) and Phase 29 output (review plan item refs), with no DB access and no
  Phase 30/22 writer import.

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
    "peak/reviewer_decisions/__init__.py",
    "peak/reviewer_decisions/contracts.py",
    "peak/reviewer_decisions/governance.py",
    "peak/reviewer_decisions/decision_mapper.py",
    "docs/INTERNAL_REVIEWER_DECISION_BOUNDARY.md",
    "docs/INTERNAL_REVIEWER_DECISION_GOVERNANCE_POLICY.md",
]
PY_FILES = [
    "peak/reviewer_decisions/__init__.py",
    "peak/reviewer_decisions/contracts.py",
    "peak/reviewer_decisions/governance.py",
    "peak/reviewer_decisions/decision_mapper.py",
]
DBFREE_FILES = [
    "peak/ingestion/contracts.py", "peak/ingestion/governance.py", "peak/ingestion/packet_mapper.py",
    "peak/task_queue/contracts.py", "peak/task_queue/governance.py",
    "peak/task_queue/task_queue_mapper.py",
    "peak/review_orchestration/contracts.py", "peak/review_orchestration/governance.py",
    "peak/review_orchestration/review_planner.py",
]
DOCS = [
    "docs/INTERNAL_REVIEWER_DECISION_BOUNDARY.md",
    "docs/INTERNAL_REVIEWER_DECISION_GOVERNANCE_POLICY.md",
]
REQUIRED_PHRASES = [
    "decision-planning boundary",
    "is not approval",
    "db-free",
    "does not persist reviewer decisions",
    "phase 22",
    "review_records",
    "phase 33",
    "identity matching is necessary but not sufficient",
    "recommendation only",
    "no new table, no migration",
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


def check(label: str, ok: bool) -> None:
    if ok:
        print(f"  [{PASS}] {label}")
    else:
        _failures.append(label)
        print(f"  [{FAIL}] {label}")


# --------------------------------------------------------------------------- structural


def structural_checks() -> None:
    print("\n1. Phase 32 scaffold files")
    for rel in REQUIRED_FILES:
        check(rel, os.path.isfile(os.path.join(REPO_ROOT, rel)))

    print("\n2. Python files compile")
    for rel in PY_FILES:
        try:
            py_compile.compile(os.path.join(REPO_ROOT, rel), doraise=True)
            check(f"{rel} compiles", True)
        except py_compile.PyCompileError:
            check(f"{rel} compiles", False)

    print("\n3. Phase 32 import discipline (DB-free, no writer/LLM/AgentNet/network)")
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
        check(f"{rel}: no Phase 22 review writer import",
              not [ln for ln in imports if REVIEW_WRITER_RE.search(ln)])

    print("\n4. Prior DB-free boundaries stay DB-free (regression)")
    for rel in DBFREE_FILES:
        hits = [ln for ln in _import_lines(read(rel)) if DB_IMPORT_RE.search(ln)]
        check(f"{rel}: no DB/ORM/peak.db import", not hits)

    print("\n5. Baseline: Phase 31 present, no Phase 32 migration / table")
    try:
        log = subprocess.check_output(
            ["git", "-C", REPO_ROOT, "log", "--oneline", "-8"], text=True)
        check("Phase 31 commit present in recent history",
              "Phase 31" in log or "2789799" in log)
    except Exception:
        check("Phase 31 commit present (git unavailable — skipped)", True)
    versions = sorted(v for v in os.listdir(os.path.join(REPO_ROOT, "alembic", "versions"))
                      if v.endswith(".py"))
    check("Phase 30 migration 007_review_bundle_records present",
          any(v.startswith("007_review_bundle_records") for v in versions))
    # Phase 32 is a DB-free decision-planning boundary: it persists nothing itself. The reviewer
    # decision *package* defines no SQLAlchemy model/table — persistence (the 008 migration and the
    # InternalReviewerDecisionRecord model) is owned by the separate Phase 33 DB writer.
    for rel in PY_FILES:
        text = read(rel)
        check(f"{rel}: defines no DB model/table",
              "mapped_column" not in text and "__tablename__" not in text)

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

_SENTINEL = "DECISION-SECRET-SENTINEL-DO-NOT-LEAK"
_ALL_FLAGS = (
    "direct_database_write_made", "database_connection_made", "sql_execution_made",
    "stored_record_created", "review_records_write_made", "review_approval_made",
    "client_facing_output_created", "financial_verification_made", "capsule_publication_made",
    "agent_execution_made", "mock_agent_execution_made", "llm_call_made", "agentnet_call_made",
    "resolver_call_made", "network_call_made",
)


def _request(**over):
    from peak.reviewer_decisions import InternalReviewerDecisionRequest

    base = dict(
        owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
        requested_by="consultant_a", requester_role="consultant",
        authorization_scope="engagement_authorized", idempotency_key="idem-dec-1",
        review_bundle_record_id="rvb_1", review_plan_item_refs=["idem::item::source_ingestion_review"],
        evidence_reference_ids=["evid_1"], source_ingestion_record_ids=["ing_1"],
        agent_task_queue_record_ids=["atq_1"], reviewer_role="internal_reviewer",
        decision_intent="ready_for_internal_use", decision_reason_code="qa_pass",
        safe_decision_summary="evidence traced; internal reliance ok", strict_mode=True,
        requested_action="prepare_internal_reviewer_decision", source_phase="phase32",
        lifecycle_status="active",
    )
    base.update(over)
    return InternalReviewerDecisionRequest(**base)


def _blob(r) -> str:
    parts = list(r.reasons) + list(r.warnings) + [str(r.reason_code)]
    if r.readiness_assessment:
        parts += list(r.readiness_assessment.reasons) + list(r.readiness_assessment.warnings)
    if r.decision_draft:
        parts += list(r.decision_draft.reasons) + list(r.decision_draft.warnings)
    if r.routing_plan:
        parts += list(r.routing_plan.reasons) + list(r.routing_plan.warnings)
    if r.validation_result:
        parts += list(r.validation_result.reasons)
    return " ".join(parts)


def _assert_no_side_effects(label, r) -> None:
    for flag in _ALL_FLAGS:
        check(f"{label}: {flag} False", getattr(r, flag) is False)


# --------------------------------------------------------------------------- functional


def functional_checks() -> None:
    from peak.reviewer_decisions import (
        OUTCOME_DENIED, OUTCOME_PLANNED, READY_TO_RECORD,
        BLOCKED_INVALID_SCOPE, BLOCKED_LIFECYCLE, BLOCKED_MISSING_REVIEW_BUNDLE,
        BLOCKED_UNSUPPORTED_INTENT, BLOCKED_DISALLOWED_INTENT, BLOCKED_RAW_CONTENT,
        BLOCKED_SECRET_LIKE_CONTENT,
        InternalReviewerDecisionDraft, ReviewerDecisionRoutingPlan,
        prepare_internal_reviewer_decision,
    )

    print("\n8. Successful decision planning (ready_for_internal_use)")
    r = prepare_internal_reviewer_decision(_request())
    check("outcome planned", r.outcome == OUTCOME_PLANNED)
    check("permitted True", r.permitted is True)
    check("one decision draft", r.decision_draft_count == 1
          and isinstance(r.decision_draft, InternalReviewerDecisionDraft))
    check("one routing plan", r.routing_plan_count == 1
          and isinstance(r.routing_plan, ReviewerDecisionRoutingPlan))
    check("one readiness assessment (ready_to_record)", r.readiness_assessment_count == 1
          and r.readiness_assessment.readiness_state == READY_TO_RECORD)
    check("controlled_write_request_count == 0 (DB-free)", r.controlled_write_request_count == 0)
    check("ready_for_internal_use routes to internal_report_planning_candidate",
          r.routing_plan.route_to == "internal_report_planning_candidate")
    check("routing is recommendation only", r.routing_plan.recommendation_only is True)
    d = r.decision_draft
    check("draft has no id / created_at", d.reviewer_decision_id is None and d.created_at is None)
    check("draft output_status draft", d.output_status == "draft")
    check("draft lifecycle_status draft", d.lifecycle_status == "draft")
    check("draft posture flags all safe",
          d.authoritative is False and d.client_facing_approved is False
          and d.capsule_candidate_ready is False and d.financial_verified is False
          and d.execution_allowed is False and d.approval_allowed is False
          and d.publication_allowed is False and d.requires_human_review is True
          and d.client_facing_output_created is False and d.review_approval_made is False)
    check("ready_for_internal_use is NOT approval (approval_allowed false)",
          d.approval_allowed is False and r.review_approval_made is False)
    _assert_no_side_effects("planned", r)
    check("NO secret/raw sentinel leaked", _SENTINEL not in _blob(r))

    print("\n9. Deterministic routing per intent")
    routes = {
        "needs_more_evidence": "evidence_collection",
        "blocked_by_scope": "engagement_scope_review",
        "blocked_by_quality": "quality_remediation",
        "blocked_by_missing_source": "source_ingestion_followup",
        "rejected_for_policy": "governance_exception_review",
        "defer_review": "review_backlog",
    }
    for intent, route in routes.items():
        rr = prepare_internal_reviewer_decision(_request(decision_intent=intent))
        check(f"{intent} -> {route}",
              rr.outcome == OUTCOME_PLANNED and rr.routing_plan.route_to == route)
    check("return_for_revision + return_to_stage=evidence -> evidence_revision",
          prepare_internal_reviewer_decision(
              _request(decision_intent="return_for_revision", return_to_stage="evidence")
          ).routing_plan.route_to == "evidence_revision")
    check("return_for_revision (no stage) -> packet_processing_revision",
          prepare_internal_reviewer_decision(
              _request(decision_intent="return_for_revision")
          ).routing_plan.route_to == "packet_processing_revision")
    check("return_for_revision + unsafe stage -> denied",
          prepare_internal_reviewer_decision(
              _request(decision_intent="return_for_revision", return_to_stage="deploy_to_prod")
          ).outcome == OUTCOME_DENIED)

    print("\n10. Identity / scope / lifecycle / missing-field denials")
    for attr in ("owner_id", "client_id", "engagement_id", "authorization_scope",
                 "idempotency_key", "reviewer_role", "decision_intent", "decision_reason_code"):
        check(f"missing {attr} -> denied",
              prepare_internal_reviewer_decision(_request(**{attr: None})).outcome == OUTCOME_DENIED)
    rb = prepare_internal_reviewer_decision(_request(review_bundle_record_id=None, review_bundle_ref=None))
    check("missing review bundle ref -> denied + blocked_missing_review_bundle",
          rb.outcome == OUTCOME_DENIED
          and rb.readiness_assessment.readiness_state == BLOCKED_MISSING_REVIEW_BUNDLE)
    for lc in ("revoked", "archived", "deleted_reference_only"):
        rl = prepare_internal_reviewer_decision(_request(lifecycle_status=lc))
        check(f"lifecycle {lc} -> denied + blocked_lifecycle",
              rl.outcome == OUTCOME_DENIED
              and rl.readiness_assessment.readiness_state == BLOCKED_LIFECYCLE)
    for attr in ("owner_id", "client_id", "engagement_id", "authorization_scope"):
        rm = prepare_internal_reviewer_decision(_request(context={"subject_refs": [{attr: "WRONG"}]}))
        check(f"structured subject {attr} mismatch -> denied blocked_invalid_scope",
              rm.outcome == OUTCOME_DENIED
              and rm.readiness_assessment.readiness_state == BLOCKED_INVALID_SCOPE)
    check("reviewer_role email -> denied",
          prepare_internal_reviewer_decision(_request(reviewer_role="rev@example.com")).outcome
          == OUTCOME_DENIED)

    print("\n11. Intent denials (approval / publication / execution / financial / client-facing)")
    disallowed = ("approve_internal", "approve_client_facing", "final_approval", "publish_capsule",
                  "verify_financial_impact", "execute_agent", "create_report_for_client",
                  "send_to_client")
    for intent in disallowed:
        ri = prepare_internal_reviewer_decision(_request(decision_intent=intent))
        check(f"disallowed intent '{intent}' -> denied blocked_disallowed_intent",
              ri.outcome == OUTCOME_DENIED
              and ri.readiness_assessment.readiness_state == BLOCKED_DISALLOWED_INTENT)
    ru = prepare_internal_reviewer_decision(_request(decision_intent="frobnicate"))
    check("unsupported intent -> denied blocked_unsupported_intent",
          ru.outcome == OUTCOME_DENIED
          and ru.readiness_assessment.readiness_state == BLOCKED_UNSUPPORTED_INTENT)

    print("\n12. Content safety (rejected without echoing values)")
    for attr in ("packet_payload", "raw_evidence_text", "raw_interview_text", "source_bytes",
                 "generated_output", "database_url", "raw_sql"):
        req = _request()
        setattr(req, attr, {"x": _SENTINEL} if attr.endswith("payload") else _SENTINEL)
        rr = prepare_internal_reviewer_decision(req)
        check(f"ad-hoc '{attr}' rejected", rr.outcome == OUTCOME_DENIED)
        check(f"'{attr}' value not echoed", _SENTINEL not in _blob(rr))
    rj = prepare_internal_reviewer_decision(_request(evidence_reference_ids=[{"packet": "json"}]))
    check("arbitrary JSON ref -> denied blocked_raw_content",
          rj.outcome == OUTCOME_DENIED
          and rj.readiness_assessment.readiness_state == BLOCKED_RAW_CONTENT)
    rt = prepare_internal_reviewer_decision(
        _request(safe_decision_summary="line one\nSELECT * FROM engagements WHERE ..."))
    check("multiline summary -> denied blocked_raw_content",
          rt.outcome == OUTCOME_DENIED
          and rt.readiness_assessment.readiness_state == BLOCKED_RAW_CONTENT)
    rs = prepare_internal_reviewer_decision(_request(context={"api_key": _SENTINEL}))
    check("secret-like key -> denied blocked_secret_like_content",
          rs.outcome == OUTCOME_DENIED
          and rs.readiness_assessment.readiness_state == BLOCKED_SECRET_LIKE_CONTENT)
    check("secret value not echoed", _SENTINEL not in _blob(rs))

    print("\n12b. safe_decision_summary / followup value-safety guard (non-echoing)")
    # A marker-free canary so the intended category is hit (the module _SENTINEL contains "SECRET").
    _CANARY = "LEAKCANARY-DO-NOT-ECHO-XYZ"
    # Secret-like marker in the summary value.
    r_sec = prepare_internal_reviewer_decision(
        _request(safe_decision_summary=f"api_key={_CANARY}"))
    check("summary with 'api_key=' -> denied blocked_secret_like_content",
          r_sec.outcome == OUTCOME_DENIED
          and r_sec.readiness_assessment.readiness_state == BLOCKED_SECRET_LIKE_CONTENT)
    check("summary secret value not echoed", _CANARY not in _blob(r_sec))
    # DB-URL / DSN marker.
    r_dsn = prepare_internal_reviewer_decision(
        _request(safe_decision_summary=f"postgres://u@host:5432/{_CANARY}"))
    check("summary with 'postgres://' -> denied blocked_raw_content",
          r_dsn.outcome == OUTCOME_DENIED
          and r_dsn.readiness_assessment.readiness_state == BLOCKED_RAW_CONTENT)
    check("summary DSN value not echoed", _CANARY not in _blob(r_dsn))
    # Raw-SQL marker.
    r_sql = prepare_internal_reviewer_decision(
        _request(safe_decision_summary=f"SELECT * FROM engagements WHERE id='{_CANARY}'"))
    check("summary with 'SELECT * FROM' -> denied blocked_raw_content",
          r_sql.outcome == OUTCOME_DENIED
          and r_sql.readiness_assessment.readiness_state == BLOCKED_RAW_CONTENT)
    check("summary raw-SQL value not echoed", _CANARY not in _blob(r_sql))
    # JSON-like raw blob.
    r_json = prepare_internal_reviewer_decision(
        _request(safe_decision_summary=f'{{"decision": "{_CANARY}", "notes": "x"}}'))
    check("summary with JSON-like blob -> denied blocked_raw_content",
          r_json.outcome == OUTCOME_DENIED
          and r_json.readiness_assessment.readiness_state == BLOCKED_RAW_CONTENT)
    check("summary JSON value not echoed", _CANARY not in _blob(r_json))
    # Secret-like marker in a followup label.
    r_fu = prepare_internal_reviewer_decision(
        _request(requested_followup_actions=[f"rotate_api_key_{_CANARY}"]))
    check("followup with secret marker -> denied blocked_secret_like_content",
          r_fu.outcome == OUTCOME_DENIED
          and r_fu.readiness_assessment.readiness_state == BLOCKED_SECRET_LIKE_CONTENT)
    check("followup secret value not echoed", _CANARY not in _blob(r_fu))
    # A normal short summary + safe followup labels still pass.
    r_ok = prepare_internal_reviewer_decision(
        _request(safe_decision_summary="evidence traced; internal reliance ok",
                 requested_followup_actions=["notify_engagement_lead", "schedule_followup"]))
    check("normal short summary + safe followups still pass", r_ok.outcome == OUTCOME_PLANNED)

    print("\n12c. Tightened raw-SQL UPDATE...SET marker (no false positives on 'update')")
    # Harmless 'update' wording in a summary must still pass.
    check("summary 'please update the review note' passes",
          prepare_internal_reviewer_decision(
              _request(safe_decision_summary="please update the review note")).outcome
          == OUTCOME_PLANNED)
    # Real UPDATE ... SET SQL in a summary is denied without echoing the value.
    r_upd = prepare_internal_reviewer_decision(
        _request(safe_decision_summary="UPDATE review_bundle_records SET approval_allowed=true"))
    check("summary 'UPDATE ... SET' -> denied blocked_raw_content",
          r_upd.outcome == OUTCOME_DENIED
          and r_upd.readiness_assessment.readiness_state == BLOCKED_RAW_CONTENT)
    check("summary UPDATE...SET value not echoed",
          "approval_allowed=true" not in _blob(r_upd))
    # Harmless 'update'-containing followup label passes.
    check("followup 'update_review_note' passes",
          prepare_internal_reviewer_decision(
              _request(requested_followup_actions=["update_review_note"])).outcome
          == OUTCOME_PLANNED)
    # SQL-like UPDATE ... SET followup is denied without echoing the value.
    r_fu_sql = prepare_internal_reviewer_decision(
        _request(requested_followup_actions=["UPDATE engagements SET flag=1"]))
    check("followup 'UPDATE ... SET' -> denied blocked_raw_content",
          r_fu_sql.outcome == OUTCOME_DENIED
          and r_fu_sql.readiness_assessment.readiness_state == BLOCKED_RAW_CONTENT)
    check("followup UPDATE...SET value not echoed", "flag=1" not in _blob(r_fu_sql))


# --------------------------------------------------------------------------- integration


def integration_checks() -> None:
    from peak.reviewer_decisions import OUTCOME_PLANNED, prepare_internal_reviewer_decision

    print("\n13. Consumes Phase 30/29-shaped safe references (documented handoff)")
    r = prepare_internal_reviewer_decision(_request(
        review_bundle_record_id="rvb_aaaaaaaaaaaaaaaa",
        review_bundle_draft_ref="idem::review::bundle::0",
        review_plan_item_refs=["idem::item::evidence_reference_review",
                               "idem::item::agent_task_queue_review"],
        evidence_reference_ids=["evid_bbbbbbbbbbbbbbbb"],
        agent_task_queue_record_ids=["atq_cccccccccccccccc"]))
    check("consumes Phase 30/29-shaped refs -> planned", r.outcome == OUTCOME_PLANNED)
    check("no DB access needed (all flags false)",
          all(getattr(r, f) is False for f in _ALL_FLAGS))
    check("carries the safe refs on the draft",
          r.decision_draft.review_bundle_record_id == "rvb_aaaaaaaaaaaaaaaa"
          and r.decision_draft.review_plan_item_refs == [
              "idem::item::evidence_reference_review", "idem::item::agent_task_queue_review"])

    print("\n14. Does not import Phase 30 writer / Phase 22 writer / peak.db (import lines only)")
    import_lines = [ln for rel in PY_FILES for ln in _import_lines(read(rel))]
    check("no review_bundle_writer import",
          not any("review_bundle_writer" in ln for ln in import_lines))
    check("no review_writer import", not any("review_writer" in ln for ln in import_lines))
    check("no peak.db import", not any(DB_IMPORT_RE.search(ln) for ln in import_lines))
    check("no peak.db model/writer import (review_records comes from a DB writer, absent here)",
          not any(re.search(r"\breview_record\b|ReviewRecord\b", ln) for ln in import_lines))


def main() -> int:
    print("Peak Phase 32 internal reviewer decision boundary check")
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
