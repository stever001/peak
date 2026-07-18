#!/usr/bin/env python3
"""Phase 17 controlled-DB-writer-boundary check.

Stdlib-only. Verifies the Controlled DB Writer Boundary scaffold: the files exist and
import/compile, the allowlist holds the expected tables/actions and its helpers behave, a
valid in-memory controlled write request prepares a **no-side-effect** write plan (no DB
connection, no SQL, no stored record, audit ids reserved for a future writer), governance
rejects the disallowed cases — including prohibited tables/actions and a
``request.authorization_scope`` that does not match the subject's
``stored_authorization_scope`` — the package makes no network/database/SQLAlchemy/peak.db/LLM
imports, the docs carry the required boundary language, and the repo stays source-only.

Phase 17 is **DB-aware but not DB-writing**: no live database connection, no SQL execution,
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
    "peak/persistence/__init__.py",
    "peak/persistence/contracts.py",
    "peak/persistence/allowlist.py",
    "peak/persistence/governance.py",
    "peak/persistence/write_plan.py",
    "docs/CONTROLLED_DB_WRITER_BOUNDARY.md",
    "docs/CONTROLLED_WRITE_ALLOWLIST.md",
]

PY_FILES = [
    "peak/persistence/__init__.py",
    "peak/persistence/contracts.py",
    "peak/persistence/allowlist.py",
    "peak/persistence/governance.py",
    "peak/persistence/write_plan.py",
]

DOCS = ["docs/CONTROLLED_DB_WRITER_BOUNDARY.md", "docs/CONTROLLED_WRITE_ALLOWLIST.md"]

EXPECTED_TABLES = {
    "evidence_references",
    "engagement_records",
    "review_records",
    "agent_run_records",
    "source_ingestion_records",
    "agent_task_queue_records",
    "capsule_publication_candidates",
}
EXPECTED_ACTIONS = {
    "create_draft",
    "create_review_record",
    "create_agent_run_record",
    "create_source_ingestion_record",
    "create_agent_task_queue_record",
    "create_capsule_candidate_draft",
    "update_review_status",
    "update_lifecycle_status",
    "mark_superseded",
}

REQUIRED_PHRASES = [
    "DB-aware but not DB-writing",
    "no live database connection",
    "no SQL execution",
    "no stored records",
    "future controlled DB writer",
    "table/action allowlist",
    "idempotency key",
    "stored authorization scope",
    "owner/client/engagement matching is necessary but not sufficient",
    "no client-facing approval",
    "no financial verification",
    "no capsule publication",
    "raw SQL is prohibited",
    "write plans are not writes",
]

# Network imports must not appear in the persistence package.
NETWORK_IMPORT_RE = re.compile(
    r"\b(?:requests|socket|urllib|httpx|aiohttp|ftplib|smtplib|telnetlib)\b"
)
NETWORK_HTTP_RE = re.compile(r"\bhttp\b")
# Database / ORM / peak.db imports must not appear.
DB_IMPORT_RE = re.compile(r"\b(?:sqlalchemy|alembic|pymysql)\b", re.IGNORECASE)
PEAK_DB_RE = re.compile(r"\bpeak\.db\b|from\s+\.+db\b")
# Live LLM provider libs / credentials must not appear anywhere in the package.
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
    """Build in-memory synthetic controlled-write-request builders (no stored data)."""
    from peak.persistence.contracts import ControlledWriteRequest, ControlledWriteSubject

    def subject(**over):
        base = dict(
            subject_record_id="evid_1", subject_record_type="normalized_evidence_record",
            owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
            stored_authorization_scope="engagement_authorized",
            stored_output_status="draft", stored_review_status="needs_review",
            stored_lifecycle_status="active", source_reference_id="src_1",
        )
        base.update(over)
        return ControlledWriteSubject(**base)

    def req(**over):
        base = dict(
            owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
            requested_by="qa_reviewer_a", requester_role="qa_reviewer",
            authorization_scope="engagement_authorized",
            target_table="review_records", requested_action="create_review_record",
            subject=subject(), record_draft={"kind": "review_record_draft"},
            source_phase="phase16", lifecycle_status="active",
            idempotency_key="idem-abc-123",
        )
        base.update(over)
        return ControlledWriteRequest(**base)

    return subject, req


def main() -> int:
    print("Peak Phase 17 controlled-DB-writer-boundary check")
    print("=" * 48)
    failures: list = []

    # 1. Required files exist.
    print("\n1. Writer-boundary scaffold files")
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
    persistence = None
    try:
        import peak.persistence as persistence  # noqa: F401
        print(f"  [{PASS}] peak.persistence imports")
    except Exception as exc:
        failures.append(f"peak.persistence import failed: {exc}")
        print(f"  [{FAIL}] peak.persistence import failed: {exc}")

    # 4. Allowlist contents + helpers.
    print("\n4. Allowlist contents and helpers")
    if persistence is not None:
        from peak.persistence import allowlist as al

        if set(al.ALLOWED_TABLES) == EXPECTED_TABLES:
            print(f"  [{PASS}] ALLOWED_TABLES == expected set")
        else:
            failures.append(f"ALLOWED_TABLES mismatch: {set(al.ALLOWED_TABLES) ^ EXPECTED_TABLES}")
            print(f"  [{FAIL}] ALLOWED_TABLES mismatch")
        if set(al.ALLOWED_ACTIONS) == EXPECTED_ACTIONS:
            print(f"  [{PASS}] ALLOWED_ACTIONS == expected set")
        else:
            failures.append(f"ALLOWED_ACTIONS mismatch: {set(al.ALLOWED_ACTIONS) ^ EXPECTED_ACTIONS}")
            print(f"  [{FAIL}] ALLOWED_ACTIONS mismatch")
        helper_checks = {
            "is_allowed_table(review_records)": al.is_allowed_table("review_records") is True,
            "is_allowed_table(clients) False": al.is_allowed_table("clients") is False,
            "is_allowed_action(create_review_record)": al.is_allowed_action("create_review_record")
            is True,
            "is_allowed_action(publish_capsule) False": al.is_allowed_action("publish_capsule")
            is False,
            "is_prohibited_table(financial_impact_estimates)": al.is_prohibited_table(
                "financial_impact_estimates"
            )
            is True,
            "is_prohibited_action(delete_record)": al.is_prohibited_action("delete_record")
            is True,
            "is_prohibited_action(create_draft) False": al.is_prohibited_action("create_draft")
            is False,
        }
        for label, ok in helper_checks.items():
            if ok:
                print(f"  [{PASS}] {label}")
            else:
                failures.append(f"allowlist helper: {label} failed")
                print(f"  [{FAIL}] allowlist helper: {label} failed")

    subject = req = None

    # 5. Valid request → no-side-effect write plan + audit draft.
    print("\n5. Controlled write is DB-aware but not DB-writing")
    if persistence is not None:
        from peak.persistence.governance import build_controlled_write_decision
        from peak.persistence.write_plan import (
            build_controlled_write_audit_draft,
            prepare_controlled_write,
        )

        subject, req = _synthetic()
        result = prepare_controlled_write(req())
        plan = result.write_plan
        audit = build_controlled_write_audit_draft(req(), build_controlled_write_decision(req()))
        checks = {
            "permitted == True": result.permitted is True,
            "write_plan present": plan is not None,
            "requires_controlled_db_writer == True": plan is not None
            and plan.requires_controlled_db_writer is True,
            "database_write_made == False": result.database_write_made is False,
            "database_connection_made == False": result.database_connection_made is False,
            "sql_execution_made == False": result.sql_execution_made is False,
            "stored_record_created == False": result.stored_record_created is False,
            "llm_call_made == False": result.llm_call_made is False,
            "agentnet_call_made == False": result.agentnet_call_made is False,
            "network_call_made == False": result.network_call_made is False,
            "capsule_publication_made == False": result.capsule_publication_made is False,
            "client_facing_output_created == False": result.client_facing_output_created is False,
            "plan.database_write_made == False": plan is not None
            and plan.database_write_made is False,
            "plan.database_connection_made == False": plan is not None
            and plan.database_connection_made is False,
            "plan.sql_execution_made == False": plan is not None
            and plan.sql_execution_made is False,
            "plan.stored_record_created == False": plan is not None
            and plan.stored_record_created is False,
            "plan carries a write-plan-only warning": plan is not None and bool(plan.warnings),
            "audit.audit_record_id is None": audit.audit_record_id is None,
            "audit.created_at is None": audit.created_at is None,
            "audit.decision == permitted": audit.decision == "permitted",
        }
        for label, ok in checks.items():
            if ok:
                print(f"  [{PASS}] {label}")
            else:
                failures.append(f"result: {label} failed")
                print(f"  [{FAIL}] result: {label} failed")

    # 6. Governance rejections.
    print("\n6. Governance rejections")
    if persistence is not None:
        from peak.persistence.governance import evaluate_controlled_write_request as gov

        cases = {
            "missing owner_id": req(owner_id=None),
            "missing client_id": req(client_id=None),
            "missing engagement_id": req(engagement_id=None),
            "missing requested_by": req(requested_by=None),
            "missing requester_role": req(requester_role=None),
            "missing authorization_scope": req(authorization_scope=None),
            "missing target_table": req(target_table=None),
            "missing requested_action": req(requested_action=None),
            "missing subject": req(subject=None),
            "missing record_draft": req(record_draft=None),
            "missing idempotency_key": req(idempotency_key=None),
            "subject owner mismatch": req(subject=subject(owner_id="owner_2")),
            "subject client mismatch": req(subject=subject(client_id="client_b")),
            "subject engagement mismatch": req(subject=subject(engagement_id="eng_y")),
            "stored scope mismatch": req(
                subject=subject(stored_authorization_scope="internal_peak_only")
            ),
            "missing stored scope": req(subject=subject(stored_authorization_scope=None)),
            "request lifecycle revoked": req(lifecycle_status="revoked"),
            "subject lifecycle archived": req(
                subject=subject(stored_lifecycle_status="archived")
            ),
            "prohibited table clients": req(target_table="clients"),
            "prohibited table engagements": req(target_table="engagements"),
            "prohibited financial_impact_estimates": req(
                target_table="financial_impact_estimates", requested_action="create_draft"
            ),
            "prohibited resolver_capsule_records": req(
                target_table="resolver_capsule_records", requested_action="create_draft"
            ),
            "unlisted table": req(target_table="random_table"),
            "unlisted action": req(requested_action="do_something"),
            "publish-like action": req(requested_action="publish_capsule"),
            "client-facing approval action": req(requested_action="client_facing_approve_record"),
            "financial-verification action": req(requested_action="verify_financial_impact"),
            "delete-like action": req(requested_action="delete_record"),
            "raw_sql action": req(requested_action="run_raw_sql"),
            "migrate action": req(requested_action="migrate_schema"),
            "seed action": req(requested_action="seed_records"),
        }
        for label, request in cases.items():
            if not gov(request).permitted:
                print(f"  [{PASS}] rejected: {label}")
            else:
                failures.append(f"governance did not reject: {label}")
                print(f"  [{FAIL}] governance did not reject: {label}")

    # 7. Denied request produces no plan (fully side-effect-free denial).
    print("\n7. Denial is side-effect-free")
    if persistence is not None:
        from peak.persistence.write_plan import prepare_controlled_write

        denied = prepare_controlled_write(req(target_table="clients"))
        denial_checks = {
            "permitted == False": denied.permitted is False,
            "write_plan is None": denied.write_plan is None,
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

    # 8. No network / database / ORM / peak.db / LLM imports in the package.
    print("\n8. No network / database / SQLAlchemy / peak.db / LLM imports")
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

    # 9. Doc language.
    print("\n9. Boundary doc language")
    doc_blob = re.sub(r"\s+", " ", "\n".join(read(rel) for rel in DOCS)).lower()
    for phrase in REQUIRED_PHRASES:
        if phrase.lower() in doc_blob:
            print(f"  [{PASS}] phrase present: '{phrase}'")
        else:
            failures.append(f"missing doc phrase: {phrase}")
            print(f"  [{FAIL}] missing doc phrase: '{phrase}'")

    # 10. Source-only discipline.
    print("\n10. Source-only discipline")
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
