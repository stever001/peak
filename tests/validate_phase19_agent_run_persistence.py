#!/usr/bin/env python3
"""Phase 19 agent-run-persistence-mapping check.

Stdlib-only. Verifies the Agent Run Persistence Mapping scaffold: the files exist and
import/compile, a valid in-memory Phase 13 agent task result + run draft + stored subject
snapshot maps to a **no-side-effect** controlled write plan targeting ``agent_run_records`` /
``create_agent_run_record`` (production-shaped but review-gated draft, no DB connection, no
SQL, no stored record), governance rejects the disallowed cases — including a
``request.authorization_scope`` that does not match the subject's
``stored_authorization_scope`` — the package makes no network/database/SQLAlchemy/peak.db/LLM
imports, the docs carry the required mapping language, and the repo stays source-only.

Phase 19 is **DB-aware but not DB-writing**: no live database connection, no SQL execution,
no stored records, no live LLM/AgentNet/MCP/resolver/network call, and no client-facing
output.

Exit status:
  0  -> all checks passed
  1  -> a check failed
"""

from __future__ import annotations

import os
import py_compile
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REQUIRED_FILES = [
    "peak/agents/persistence_contracts.py",
    "peak/agents/persistence_governance.py",
    "peak/agents/agent_run_mapper.py",
    "docs/AGENT_RUN_PERSISTENCE_MAPPING.md",
    "docs/AGENT_RUN_WRITE_PLAN_POLICY.md",
]

# Only the new Phase 19 files are scanned for forbidden imports.
PY_FILES = [
    "peak/agents/persistence_contracts.py",
    "peak/agents/persistence_governance.py",
    "peak/agents/agent_run_mapper.py",
]

DOCS = ["docs/AGENT_RUN_PERSISTENCE_MAPPING.md", "docs/AGENT_RUN_WRITE_PLAN_POLICY.md"]

REQUIRED_PHRASES = [
    "DB-aware but not DB-writing",
    "write plans are not writes",
    "production-shaped",
    "review-gated",
    "future controlled DB writer",
    "idempotency_key",
    "stored_authorization_scope",
    "owner/client/engagement matching is necessary but not sufficient",
    "agent execution still does not write directly to the DB",
    "no live database connection",
    "no SQL execution",
    "no stored records",
    "no client-facing output",
    "no financial verification",
    "no capsule publication",
]

# Network imports must not appear in the new files.
NETWORK_IMPORT_RE = re.compile(
    r"\b(?:requests|socket|urllib|httpx|aiohttp|ftplib|smtplib|telnetlib)\b"
)
NETWORK_HTTP_RE = re.compile(r"\bhttp\b")
# Database / ORM / peak.db imports must not appear.
DB_IMPORT_RE = re.compile(r"\b(?:sqlalchemy|alembic|pymysql)\b", re.IGNORECASE)
PEAK_DB_RE = re.compile(r"\bpeak\.db\b|from\s+\.+db\b")
# Live LLM provider libs / credentials must not appear anywhere in the files.
LLM_PROVIDER_RE = re.compile(
    r"\b(?:openai|anthropic|cohere|litellm|langchain|transformers|vertexai|mistralai|ollama)\b",
    re.IGNORECASE,
)
CREDENTIAL_RE = re.compile(
    r"\b(?:api_key|secret_key|access_key|openai_api_key|anthropic_api_key)\b", re.IGNORECASE
)

DB_FILE_EXTS = (".db", ".sqlite", ".sqlite3", ".sql")
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache"}

PASS, FAIL = "PASS", "FAIL"


def _skip(dirpath: str) -> bool:
    return bool(SKIP_DIRS.intersection(dirpath.split(os.sep)))


def read(rel: str) -> str:
    with open(os.path.join(REPO_ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def _import_lines(text: str):
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("import ") or s.startswith("from "):
            yield s


def _synthetic():
    """Build in-memory synthetic agent-run-persistence-request builders (no stored data)."""
    from peak.agents.contracts import AgentRunDraft, AgentTaskRequest, AgentTaskResult
    from peak.agents.persistence_contracts import (
        AgentRunPersistenceRequest,
        AgentRunPersistenceSubjectSnapshot,
    )

    def task_request(**over):
        base = dict(
            agent_name="evidence_normalization_worker", workflow="evidence",
            owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
            requested_action="normalize_evidence", input_record_ids=["raw_1"],
            prompt_contract_path="prompts/evidence/extract-evidence-findings.prompt.md",
            authorization_scope="engagement_authorized", review_status="needs_review",
            lifecycle_status="draft",
        )
        base.update(over)
        return AgentTaskRequest(**base)

    def task_result(**over):
        base = dict(
            permitted=True, status="planned", output_status="draft",
            review_status="needs_review", lifecycle_status="draft", reasons=[], warnings=[],
            prompt_contract_path="prompts/evidence/extract-evidence-findings.prompt.md",
            resolver_context_used=False, llm_call_made=False, agentnet_call_made=False,
            database_write_made=False, client_facing_output_created=False,
        )
        base.update(over)
        return AgentTaskResult(**base)

    def run_draft(**over):
        base = dict(
            agent_run_id=None, agent_name="evidence_normalization_worker", workflow="evidence",
            owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
            input_record_ids=["raw_1"],
            prompt_contract_path="prompts/evidence/extract-evidence-findings.prompt.md",
            resolver_context_requested=False, resolver_context_used=False,
            llm_call_made=False, agentnet_call_made=False, database_write_made=False,
            output_record_ids=[], output_status="draft", review_status="needs_review",
            lifecycle_status="draft", warnings=[], reasons=[], created_at=None, created_by=None,
        )
        base.update(over)
        return AgentRunDraft(**base)

    def snapshot(**over):
        base = dict(
            subject_record_id="eng_x", subject_record_type="engagement_record",
            owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
            stored_authorization_scope="engagement_authorized",
            stored_output_status="active", stored_review_status="approved_internal",
            stored_lifecycle_status="active", source_reference_id="src_1",
        )
        base.update(over)
        return AgentRunPersistenceSubjectSnapshot(**base)

    def req(**over):
        base = dict(
            owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
            requested_by="consultant_a", requester_role="consultant",
            authorization_scope="engagement_authorized",
            agent_task_request=task_request(), agent_task_result=task_result(),
            agent_run_draft=run_draft(), subject_snapshot=snapshot(),
            requested_persistence_action="prepare_agent_run_record_write_plan",
            source_phase="phase13", idempotency_key="idem-run-1", lifecycle_status="active",
        )
        base.update(over)
        return AgentRunPersistenceRequest(**base)

    return task_request, task_result, run_draft, snapshot, req


def main() -> int:
    print("Peak Phase 19 agent-run-persistence-mapping check")
    print("=" * 48)
    failures: list = []

    # 1. Required files exist.
    print("\n1. Agent-run-persistence scaffold files")
    for rel in REQUIRED_FILES:
        if os.path.isfile(os.path.join(REPO_ROOT, rel)):
            print(f"  [{PASS}] {rel}")
        else:
            failures.append(f"{rel}: MISSING")
            print(f"  [{FAIL}] {rel}: file not found")

    # 2. Python files compile.
    print("\n2. Python files compile")
    for rel in PY_FILES:
        try:
            py_compile.compile(os.path.join(REPO_ROOT, rel), doraise=True)
            print(f"  [{PASS}] {rel} compiles")
        except py_compile.PyCompileError:
            failures.append(f"{rel}: compile error")
            print(f"  [{FAIL}] {rel}: compile error")

    # 3. Package import.
    print("\n3. Package import")
    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)
    agents = None
    try:
        import peak.agents as agents  # noqa: F401
        print(f"  [{PASS}] peak.agents imports")
    except Exception as exc:
        failures.append(f"peak.agents import failed: {exc}")
        print(f"  [{FAIL}] peak.agents import failed: {exc}")

    task_request = task_result = run_draft = snapshot = req = None

    # 4. Valid mapping → no-side-effect controlled write plan.
    print("\n4. Agent run mapping is DB-aware but not DB-writing")
    if agents is not None:
        from peak.agents.agent_run_mapper import prepare_agent_run_persistence

        task_request, task_result, run_draft, snapshot, req = _synthetic()
        mapping = prepare_agent_run_persistence(req())
        draft = mapping.agent_run_persistence_draft
        cwr = mapping.controlled_write_request
        cwres = mapping.controlled_write_result
        plan = getattr(cwres, "write_plan", None)
        checks = {
            "permitted == True": mapping.permitted is True,
            "draft present": draft is not None,
            "draft.agent_run_record_id is None": draft is not None
            and draft.agent_run_record_id is None,
            "draft.created_at is None": draft is not None and draft.created_at is None,
            "draft.output_status == draft": draft is not None and draft.output_status == "draft",
            "draft.review_status == needs_review": draft is not None
            and draft.review_status == "needs_review",
            "cwr.target_table == agent_run_records": cwr is not None
            and cwr.target_table == "agent_run_records",
            "cwr.requested_action == create_agent_run_record": cwr is not None
            and cwr.requested_action == "create_agent_run_record",
            "plan.requires_controlled_db_writer == True": plan is not None
            and plan.requires_controlled_db_writer is True,
            "database_write_made == False": mapping.database_write_made is False,
            "database_connection_made == False": mapping.database_connection_made is False,
            "sql_execution_made == False": mapping.sql_execution_made is False,
            "stored_record_created == False": mapping.stored_record_created is False,
            "llm_call_made == False": mapping.llm_call_made is False,
            "agentnet_call_made == False": mapping.agentnet_call_made is False,
            "network_call_made == False": mapping.network_call_made is False,
            "capsule_publication_made == False": mapping.capsule_publication_made is False,
            "client_facing_output_created == False": mapping.client_facing_output_created is False,
            "draft.network_call_made == False": draft is not None
            and draft.network_call_made is False,
            "draft.capsule_publication_made == False": draft is not None
            and draft.capsule_publication_made is False,
        }
        for label, ok in checks.items():
            if ok:
                print(f"  [{PASS}] {label}")
            else:
                failures.append(f"result: {label} failed")
                print(f"  [{FAIL}] result: {label} failed")

    # 5. Governance rejections.
    print("\n5. Governance rejections")
    if agents is not None:
        from peak.agents.persistence_governance import (
            evaluate_agent_run_persistence_request as gov,
        )

        def rq(**over):
            r = req()
            for k, v in over.items():
                setattr(r, k, v)
            return r

        cases = {
            "missing owner_id": rq(owner_id=None),
            "missing client_id": rq(client_id=None),
            "missing engagement_id": rq(engagement_id=None),
            "missing requested_by": rq(requested_by=None),
            "missing requester_role": rq(requester_role=None),
            "missing authorization_scope": rq(authorization_scope=None),
            "missing agent_task_request": rq(agent_task_request=None),
            "missing agent_task_result": rq(agent_task_result=None),
            "missing agent_run_draft": rq(agent_run_draft=None),
            "missing subject_snapshot": rq(subject_snapshot=None),
            "missing idempotency_key": rq(idempotency_key=None),
            "wrong persistence action": rq(requested_persistence_action="write_now"),
            "subject owner mismatch": rq(subject_snapshot=snapshot(owner_id="owner_2")),
            "subject client mismatch": rq(subject_snapshot=snapshot(client_id="client_b")),
            "subject engagement mismatch": rq(subject_snapshot=snapshot(engagement_id="eng_y")),
            "task_request owner mismatch": rq(agent_task_request=task_request(owner_id="owner_2")),
            "task_request client mismatch": rq(agent_task_request=task_request(client_id="client_b")),
            "task_request engagement mismatch": rq(
                agent_task_request=task_request(engagement_id="eng_y")
            ),
            "stored scope mismatch": rq(
                subject_snapshot=snapshot(stored_authorization_scope="internal_peak_only")
            ),
            "missing stored scope": rq(subject_snapshot=snapshot(stored_authorization_scope=None)),
            "request lifecycle revoked": rq(lifecycle_status="revoked"),
            "subject lifecycle archived": rq(
                subject_snapshot=snapshot(stored_lifecycle_status="archived")
            ),
            "unpermitted task_result": rq(agent_task_result=task_result(permitted=False)),
            "task_result db_write flag": rq(agent_task_result=task_result(database_write_made=True)),
            "task_result llm flag": rq(agent_task_result=task_result(llm_call_made=True)),
            "task_result agentnet flag": rq(agent_task_result=task_result(agentnet_call_made=True)),
            "task_result client_facing flag": rq(
                agent_task_result=task_result(client_facing_output_created=True)
            ),
            "task_result wrong output_status": rq(
                agent_task_result=task_result(output_status="reviewed")
            ),
            "task_result wrong review_status": rq(
                agent_task_result=task_result(review_status="approved_internal")
            ),
        }
        for label, request in cases.items():
            if not gov(request).permitted:
                print(f"  [{PASS}] rejected: {label}")
            else:
                failures.append(f"governance did not reject: {label}")
                print(f"  [{FAIL}] governance did not reject: {label}")

    # 6. Denied request produces no plan (fully side-effect-free denial).
    print("\n6. Denial is side-effect-free")
    if agents is not None:
        from peak.agents.agent_run_mapper import prepare_agent_run_persistence

        denied_req = req()
        denied_req.subject_snapshot = snapshot(stored_authorization_scope="internal_peak_only")
        denied = prepare_agent_run_persistence(denied_req)
        denial_checks = {
            "permitted == False": denied.permitted is False,
            "agent_run_persistence_draft is None": denied.agent_run_persistence_draft is None,
            "controlled_write_request is None": denied.controlled_write_request is None,
            "controlled_write_result is None": denied.controlled_write_result is None,
            "database_write_made == False": denied.database_write_made is False,
            "database_connection_made == False": denied.database_connection_made is False,
            "sql_execution_made == False": denied.sql_execution_made is False,
            "stored_record_created == False": denied.stored_record_created is False,
            "has a denial reason": bool(denied.reasons),
        }
        for label, ok in denial_checks.items():
            if ok:
                print(f"  [{PASS}] {label}")
            else:
                failures.append(f"denial: {label} failed")
                print(f"  [{FAIL}] denial: {label} failed")

    # 7. No network / database / ORM / peak.db / LLM imports in the new files.
    print("\n7. No network / database / SQLAlchemy / peak.db / LLM imports")
    net_hits, db_hits, llm_hits = [], [], []
    for rel in PY_FILES:
        text = read(rel)
        for line in _import_lines(text):
            if NETWORK_IMPORT_RE.search(line) or NETWORK_HTTP_RE.search(line):
                net_hits.append(f"{rel}: {line}")
            if DB_IMPORT_RE.search(line) or PEAK_DB_RE.search(line):
                db_hits.append(f"{rel}: {line}")
        if LLM_PROVIDER_RE.search(text) or CREDENTIAL_RE.search(text):
            llm_hits.append(rel)
    for label, hits in (("network import", net_hits),
                        ("database/ORM/peak.db import", db_hits),
                        ("LLM provider/credential", llm_hits)):
        if hits:
            for h in hits:
                failures.append(f"{label}: {h}")
                print(f"  [{FAIL}] {label}: {h}")
        else:
            print(f"  [{PASS}] no {label}s")

    # 8. Doc language.
    print("\n8. Mapping doc language")
    doc_blob = re.sub(r"\s+", " ", "\n".join(read(rel) for rel in DOCS)).lower()
    for phrase in REQUIRED_PHRASES:
        if phrase.lower() in doc_blob:
            print(f"  [{PASS}] phrase present: '{phrase}'")
        else:
            failures.append(f"missing doc phrase: {phrase}")
            print(f"  [{FAIL}] missing doc phrase: '{phrase}'")

    # 9. Source-only discipline.
    print("\n9. Source-only discipline")
    if os.path.exists(os.path.join(REPO_ROOT, "examples")):
        failures.append("examples/ exists")
        print(f"  [{FAIL}] examples/ exists")
    else:
        print(f"  [{PASS}] no examples/ directory")
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
    for label, hits in (("data artifact", artifacts), ("database file", dbfiles)):
        if hits:
            for h in hits:
                failures.append(f"forbidden {label}: {h}")
                print(f"  [{FAIL}] forbidden {label}: {h}")
        else:
            print(f"  [{PASS}] no {label}s found (except allowed .env.example)")

    print("\n" + "=" * 48)
    print("Summary")
    print(f"  failures : {len(failures)}")
    if failures:
        print(f"\nRESULT: {FAIL} ({len(failures)} issue(s))")
        return 1
    print(f"\nRESULT: {PASS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
