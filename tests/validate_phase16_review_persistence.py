#!/usr/bin/env python3
"""Phase 16 review-persistence-boundary check.

Stdlib-only. Verifies the Review Persistence Boundary scaffold: the files exist and
import/compile, a valid in-memory permitted ``ReviewGateResult`` + ``StoredReviewSubjectSnapshot``
prepares a **no-side-effect** write plan targeting ``review_records`` (no DB write, no DB
connection, no stored review record, ids/timestamps reserved for a future writer),
governance rejects the disallowed cases — including a ``request.authorization_scope`` that
does not match the subject's ``stored_authorization_scope`` — the package makes no
network/database/LLM imports, the docs carry the required DB-aware-not-DB-writing language,
and the repo stays source-only.

Phase 16 is **DB-aware but not DB-writing**: it makes no live database read/write, no live
LLM/AgentNet/MCP/resolver/network call, creates no client-facing output, and stores no
review records.

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
    "peak/review/persistence_contracts.py",
    "peak/review/persistence_governance.py",
    "peak/review/review_record_mapper.py",
    "docs/REVIEW_PERSISTENCE_BOUNDARY.md",
    "docs/DB_BACKED_REVIEW_SCOPE_POLICY.md",
]

# New Phase 16 Python files — the "no database imports required" scan targets these.
PY_FILES = [
    "peak/review/persistence_contracts.py",
    "peak/review/persistence_governance.py",
    "peak/review/review_record_mapper.py",
]

DOCS = ["docs/REVIEW_PERSISTENCE_BOUNDARY.md", "docs/DB_BACKED_REVIEW_SCOPE_POLICY.md"]

REQUIRED_PHRASES = [
    "DB-aware but not DB-writing",
    "stored_authorization_scope",
    "request.authorization_scope",
    "owner/client/engagement matching is necessary but not sufficient",
    "future controlled DB writer",
    "no live database read/write",
    "no stored review records",
    "no client-facing approval",
    "no financial verification",
    "no capsule publication",
]

# Network imports must not appear in the review package.
NETWORK_IMPORT_RE = re.compile(
    r"\b(?:requests|socket|urllib|httpx|aiohttp|ftplib|smtplib|telnetlib)\b"
)
NETWORK_HTTP_RE = re.compile(r"\bhttp\b")
# Database imports must not be required by the new Phase 16 files.
DB_IMPORT_RE = re.compile(r"\b(?:sqlalchemy|alembic)\b")
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
    """Build in-memory synthetic persistence-request builders (no stored data)."""
    from peak.review.contracts import ReviewDecision, ReviewGateResult
    from peak.review.persistence_contracts import (
        ReviewPersistenceRequest,
        StoredReviewSubjectSnapshot,
    )

    def gate(**over):
        dec = ReviewDecision(
            permitted=True, decision="approve_internal",
            next_output_status="reviewed", next_review_status="approved_internal",
            next_lifecycle_status="active", authoritative=True,
            client_facing_approved=False, capsule_candidate_ready=False,
            reasons=[], warnings=[],
        )
        base = dict(
            permitted=True, status="evaluated", decision=dec, action_plan=None,
            database_write_made=False, llm_call_made=False, agentnet_call_made=False,
            network_call_made=False, capsule_publication_made=False,
            client_facing_output_created=False, reasons=[], warnings=[],
        )
        base.update(over)
        return ReviewGateResult(**base)

    def snapshot(**over):
        base = dict(
            subject_record_id="evid_1", subject_record_type="normalized_evidence_record",
            owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
            stored_authorization_scope="engagement_authorized",
            stored_output_status="draft", stored_review_status="needs_review",
            stored_lifecycle_status="active", stored_authoritative=False,
            stored_client_facing_approved=False, stored_capsule_candidate_ready=False,
            source_reference_id="src_1",
        )
        base.update(over)
        return StoredReviewSubjectSnapshot(**base)

    def req(**over):
        base = dict(
            owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
            requested_by="qa_reviewer_a", reviewer_role="qa_reviewer",
            authorization_scope="engagement_authorized", review_gate_result=gate(),
            subject_snapshot=snapshot(),
            requested_persistence_action="prepare_review_write_plan",
            lifecycle_status="active",
        )
        base.update(over)
        return ReviewPersistenceRequest(**base)

    return gate, snapshot, req


def main() -> int:
    print("Peak Phase 16 review-persistence-boundary check")
    print("=" * 48)
    failures: list = []

    # 1. Required files exist.
    print("\n1. Persistence-boundary scaffold files")
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
    review = None
    try:
        import peak.review as review  # noqa: F401
        print(f"  [{PASS}] peak.review imports")
    except Exception as exc:
        failures.append(f"peak.review import failed: {exc}")
        print(f"  [{FAIL}] peak.review import failed: {exc}")

    gate = snapshot = req = None

    # 4. Valid request → no-side-effect write plan.
    print("\n4. Persistence is DB-aware but not DB-writing")
    if review is not None:
        from peak.review.review_record_mapper import prepare_review_persistence

        gate, snapshot, req = _synthetic()
        result = prepare_review_persistence(req())
        plan = result.write_plan
        draft = plan.review_record_draft if plan is not None else None
        checks = {
            "permitted == True": result.permitted is True,
            "write_plan present": plan is not None,
            "target_table == review_records": plan is not None
            and plan.target_table == "review_records",
            "review_record_id is None": draft is not None and draft.review_record_id is None,
            "created_at is None": draft is not None and draft.created_at is None,
            "database_write_made == False": result.database_write_made is False,
            "database_connection_made == False": result.database_connection_made is False,
            "stored_review_record_created == False": result.stored_review_record_created is False,
            "llm_call_made == False": result.llm_call_made is False,
            "agentnet_call_made == False": result.agentnet_call_made is False,
            "network_call_made == False": result.network_call_made is False,
            "capsule_publication_made == False": result.capsule_publication_made is False,
            "client_facing_output_created == False": result.client_facing_output_created is False,
            "plan.database_write_made == False": plan is not None
            and plan.database_write_made is False,
            "plan.database_connection_made == False": plan is not None
            and plan.database_connection_made is False,
            "requires_controlled_db_writer == True": plan is not None
            and plan.requires_controlled_db_writer is True,
            "draft.client_facing_approved == False": draft is not None
            and draft.client_facing_approved is False,
            "draft.capsule_candidate_ready == False": draft is not None
            and draft.capsule_candidate_ready is False,
            "plan carries a write-plan-only warning": plan is not None and bool(plan.warnings),
        }
        for label, ok in checks.items():
            if ok:
                print(f"  [{PASS}] {label}")
            else:
                failures.append(f"result: {label} failed")
                print(f"  [{FAIL}] result: {label} failed")

    # 5. Governance rejections.
    print("\n5. Governance rejections")
    if review is not None:
        from peak.review.persistence_governance import (
            evaluate_review_persistence_request as gov,
        )

        cases = {
            "missing owner_id": req(owner_id=None),
            "missing client_id": req(client_id=None),
            "missing engagement_id": req(engagement_id=None),
            "missing requested_by": req(requested_by=None),
            "missing reviewer_role": req(reviewer_role=None),
            "missing subject_snapshot": req(subject_snapshot=None),
            "missing review_gate_result": req(review_gate_result=None),
            "subject owner mismatch": req(subject_snapshot=snapshot(owner_id="owner_2")),
            "subject client mismatch": req(subject_snapshot=snapshot(client_id="client_b")),
            "subject engagement mismatch": req(subject_snapshot=snapshot(engagement_id="eng_y")),
            "stored scope mismatch": req(
                subject_snapshot=snapshot(stored_authorization_scope="internal_peak_only")
            ),
            "missing stored scope": req(
                subject_snapshot=snapshot(stored_authorization_scope=None)
            ),
            "prohibited request lifecycle (revoked)": req(lifecycle_status="revoked"),
            "prohibited subject lifecycle (archived)": req(
                subject_snapshot=snapshot(stored_lifecycle_status="archived")
            ),
            "unpermitted gate result": req(review_gate_result=gate(permitted=False)),
            "gate result w/ database_write_made": req(
                review_gate_result=gate(database_write_made=True)
            ),
            "gate result w/ client_facing_output_created": req(
                review_gate_result=gate(client_facing_output_created=True)
            ),
            "gate result w/ capsule_publication_made": req(
                review_gate_result=gate(capsule_publication_made=True)
            ),
            "gate result w/ llm_call_made": req(review_gate_result=gate(llm_call_made=True)),
            "gate result w/ agentnet_call_made": req(
                review_gate_result=gate(agentnet_call_made=True)
            ),
            "gate result w/ network_call_made": req(
                review_gate_result=gate(network_call_made=True)
            ),
            "unknown persistence action": req(requested_persistence_action="delete_everything"),
        }
        for label, request in cases.items():
            if not gov(request).permitted:
                print(f"  [{PASS}] rejected: {label}")
            else:
                failures.append(f"governance did not reject: {label}")
                print(f"  [{FAIL}] governance did not reject: {label}")

    # 6. Rejected request produces no plan (fully side-effect-free denial).
    print("\n6. Denial is side-effect-free")
    if review is not None:
        from peak.review.review_record_mapper import prepare_review_persistence

        denied = prepare_review_persistence(
            req(subject_snapshot=snapshot(stored_authorization_scope="internal_peak_only"))
        )
        denial_checks = {
            "permitted == False": denied.permitted is False,
            "write_plan is None": denied.write_plan is None,
            "database_write_made == False": denied.database_write_made is False,
            "database_connection_made == False": denied.database_connection_made is False,
            "stored_review_record_created == False": denied.stored_review_record_created is False,
            "has a denial reason": bool(denied.reasons),
        }
        for label, ok in denial_checks.items():
            if ok:
                print(f"  [{PASS}] {label}")
            else:
                failures.append(f"denial: {label} failed")
                print(f"  [{FAIL}] denial: {label} failed")

    # 7. No network / database / LLM imports or credentials in the new Phase 16 files.
    print("\n7. No network / database / LLM imports in Phase 16 files")
    net_hits, db_hits, llm_hits = [], [], []
    for rel in PY_FILES:
        text = read(rel)
        for line in _import_lines(text):
            if NETWORK_IMPORT_RE.search(line) or NETWORK_HTTP_RE.search(line):
                net_hits.append(f"{rel}: {line}")
            if DB_IMPORT_RE.search(line) or "peak.db" in line or re.search(r"from\s+\.+db\b", line):
                db_hits.append(f"{rel}: {line}")
        if LLM_PROVIDER_RE.search(text) or CREDENTIAL_RE.search(text):
            llm_hits.append(rel)
    for label, hits in (("network import", net_hits), ("database import", db_hits),
                        ("LLM provider/credential", llm_hits)):
        if hits:
            for h in hits:
                failures.append(f"{label}: {h}")
                print(f"  [{FAIL}] {label}: {h}")
        else:
            print(f"  [{PASS}] no {label}s")

    # 8. Doc language.
    print("\n8. DB-aware-not-DB-writing doc language")
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
