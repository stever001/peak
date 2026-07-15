#!/usr/bin/env python3
"""Phase 15 QA / review-gate check.

Stdlib-only. Verifies the QA / Review Gate scaffold: the files exist and import/compile, a
valid in-memory synthetic ``approve_internal`` request is permitted and returns
**internal-reliance-only** state (`approved_internal`, authoritative for internal use, but
never client-facing and never a capsule candidate) with **no side effects**, governance
rejects the disallowed cases, the package makes no network/database/LLM imports, the docs
carry the required no-side-effect language, and the repo stays source-only.

Phase 15 makes no live LLM/AgentNet/MCP/resolver/database/network call, creates no
client-facing output, and stores no review records.

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
    "peak/review/__init__.py",
    "peak/review/contracts.py",
    "peak/review/governance.py",
    "peak/review/review_gate.py",
    "docs/QA_REVIEW_GATE.md",
    "docs/REVIEW_DECISION_MODEL.md",
]

PY_FILES = [
    "peak/review/__init__.py",
    "peak/review/contracts.py",
    "peak/review/governance.py",
    "peak/review/review_gate.py",
]

DOCS = ["docs/QA_REVIEW_GATE.md", "docs/REVIEW_DECISION_MODEL.md"]

REQUIRED_PHRASES = [
    "production-shaped",
    "no-side-effect",
    "approve_internal means internal reliance only",
    "client-facing approval remains separate",
    "financial impact verification remains separate",
    "capsule publication remains separate",
    "no live LLM",
    "no AgentNet call",
    "no database write",
    "no stored review records",
]

# Network imports must not appear in the review package.
NETWORK_IMPORT_RE = re.compile(
    r"\b(?:requests|socket|urllib|httpx|aiohttp|ftplib|smtplib|telnetlib)\b"
)
NETWORK_HTTP_RE = re.compile(r"\bhttp\b")
# Database imports must not be required.
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
    """Build in-memory synthetic review-request builders (no stored data)."""
    from peak.review.contracts import (
        ReviewChecklistResult,
        ReviewDecisionRequest,
        ReviewSubjectReference,
    )

    def subject(**over):
        base = dict(
            subject_record_id="evid_1", subject_record_type="normalized_evidence_record",
            owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
            source_reference_id="src_1", current_output_status="draft",
            current_review_status="needs_review", current_lifecycle_status="active",
            authoritative=False, client_facing_approved=False, capsule_candidate_ready=False,
        )
        base.update(over)
        return ReviewSubjectReference(**base)

    def checklist(**over):
        base = dict(
            source_traceable=True, scope_valid=True, evidence_complete=True,
            confidence_acceptable=True, no_contradiction_flags=True,
            no_client_facing_claims=True, no_financial_verification_claim=True,
            no_capsule_publication_request=True, required_human_review_completed=True,
            warnings=[], missing_items=[],
        )
        base.update(over)
        return ReviewChecklistResult(**base)

    def req(**over):
        base = dict(
            owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
            requested_by="qa_reviewer_a", reviewer_role="qa_reviewer",
            authorization_scope="engagement_authorized",
            requested_decision="approve_internal", subject=subject(),
            checklist=checklist(), decision_notes="looks good", lifecycle_status="active",
        )
        base.update(over)
        return ReviewDecisionRequest(**base)

    return subject, checklist, req


def main() -> int:
    print("Peak Phase 15 QA / review-gate check")
    print("=" * 48)
    failures: list = []

    # 1. Required files exist.
    print("\n1. Review-gate scaffold files")
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

    subject = checklist = req = None

    # 4. Valid approve_internal request → internal-reliance-only, no side effects.
    print("\n4. approve_internal is production-shaped but no-side-effect")
    if review is not None:
        from peak.review.review_gate import evaluate_review_gate

        subject, checklist, req = _synthetic()
        result = evaluate_review_gate(req())
        dec = result.decision
        checks = {
            "permitted == True": result.permitted is True,
            "decision present": dec is not None,
            "next_review_status == approved_internal": dec is not None
            and dec.next_review_status == "approved_internal",
            "authoritative == True": dec is not None and dec.authoritative is True,
            "client_facing_approved == False": dec is not None
            and dec.client_facing_approved is False,
            "capsule_candidate_ready == False": dec is not None
            and dec.capsule_candidate_ready is False,
            "database_write_made == False": result.database_write_made is False,
            "llm_call_made == False": result.llm_call_made is False,
            "agentnet_call_made == False": result.agentnet_call_made is False,
            "network_call_made == False": result.network_call_made is False,
            "capsule_publication_made == False": result.capsule_publication_made is False,
            "client_facing_output_created == False": result.client_facing_output_created is False,
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
        from peak.review.governance import evaluate_review_request as gov

        cases = {
            "missing owner_id": req(owner_id=None),
            "missing client_id": req(client_id=None),
            "missing engagement_id": req(engagement_id=None),
            "missing requested_by": req(requested_by=None),
            "missing reviewer_role": req(reviewer_role=None),
            "mismatched subject scope": req(subject=subject(client_id="client_b")),
            "prohibited: client_facing_approve": req(requested_decision="client_facing_approve"),
            "prohibited: publish_capsule": req(requested_decision="publish_capsule"),
            "prohibited: verify_financial_impact": req(
                requested_decision="verify_financial_impact"
            ),
            "prohibited: approve_authoritative_external": req(
                requested_decision="approve_authoritative_external"
            ),
            "revoked request lifecycle": req(lifecycle_status="revoked"),
            "archived subject lifecycle": req(
                subject=subject(current_lifecycle_status="archived")
            ),
            "approve_internal w/ incomplete checklist": req(
                checklist=checklist(evidence_complete=False)
            ),
            "approve_internal w/ no checklist": req(checklist=None),
        }
        for label, request in cases.items():
            if not gov(request).permitted:
                print(f"  [{PASS}] rejected: {label}")
            else:
                failures.append(f"governance did not reject: {label}")
                print(f"  [{FAIL}] governance did not reject: {label}")

    # 6. reject is permitted even with an incomplete checklist.
    print("\n6. reject permitted with incomplete checklist")
    if review is not None:
        from peak.review.governance import evaluate_review_request as gov

        reject_req = req(
            requested_decision="reject",
            checklist=checklist(
                evidence_complete=False, missing_items=["evidence_complete"]
            ),
        )
        gov_result = gov(reject_req)
        if gov_result.permitted:
            print(f"  [{PASS}] reject permitted despite incomplete checklist")
        else:
            failures.append("reject rejected despite incomplete checklist")
            print(f"  [{FAIL}] reject rejected: {gov_result.reasons}")
        if gov_result.warnings:
            print(f"  [{PASS}] reject surfaced warnings for missing items")
        else:
            failures.append("reject did not surface warnings for missing items")
            print(f"  [{FAIL}] reject did not surface warnings")

    # 7. No network / database / LLM imports or credentials in the package.
    print("\n7. No network / database / LLM imports in peak/review/")
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
    print("\n8. No-side-effect doc language")
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
