#!/usr/bin/env python3
"""Phase 14 evidence-normalization-worker check.

Stdlib-only. Verifies the first production-shaped Peak worker: the files exist and
import/compile, a valid in-memory synthetic request normalizes to a **review-gated** result
(draft / needs_review, not authoritative, not client-facing, no side effects), governance
rejects the disallowed cases, the package makes no network/database/LLM imports, the docs
carry the required review-gate language, and the repo stays source-only.

Phase 14 makes no live LLM/AgentNet/MCP/resolver/database/network call and creates no
client-facing output.

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
    "peak/workers/__init__.py",
    "peak/workers/contracts.py",
    "peak/workers/evidence_normalization.py",
    "peak/workers/governance.py",
    "docs/EVIDENCE_NORMALIZATION_WORKER.md",
    "docs/EVIDENCE_RECORD_LIFECYCLE.md",
]

PY_FILES = [
    "peak/workers/__init__.py",
    "peak/workers/contracts.py",
    "peak/workers/evidence_normalization.py",
    "peak/workers/governance.py",
]

DOCS = ["docs/EVIDENCE_NORMALIZATION_WORKER.md", "docs/EVIDENCE_RECORD_LIFECYCLE.md"]

REQUIRED_PHRASES = [
    "production-shaped",
    "review-gated",
    "no live LLM call",
    "no AgentNet call",
    "no database write",
    "no client-facing output",
    "no capsule publication",
    "not authoritative merely because a worker created them",
]

# Network imports must not appear in the workers package.
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
    """Build in-memory synthetic request builders (no stored data)."""
    from peak.workers.contracts import (
        EvidenceNormalizationRequest,
        EvidenceSourceReference,
        RawEvidenceReference,
    )

    def src(**over):
        base = dict(
            source_reference_id="src_1", source_type="site_walk",
            source_name="Dock A walk", source_location="receiving dock",
            captured_by="consultant_a", captured_at="2026-07-15T10:00:00Z",
            authorization_scope="engagement_authorized",
        )
        base.update(over)
        return EvidenceSourceReference(**base)

    def raw(**over):
        base = dict(
            raw_reference_id="raw_1", source_reference=src(), content_type="note",
            observed_at="2026-07-15T10:05:00Z",
            observation_context="Pallets blocking receiving dock during inbound cycle count",
            raw_text_preview="Inbound pallets stacked in receiving lane; cycle count paused",
            location_context="receiving dock",
        )
        base.update(over)
        return RawEvidenceReference(**base)

    def req(**over):
        base = dict(
            owner_id="owner_1", client_id="client_a", engagement_id="eng_x",
            requested_by="consultant_a", workflow="evidence",
            authorization_scope="engagement_authorized", review_status="needs_review",
            lifecycle_status="active", raw_evidence=raw(), normalize_for="assessment",
        )
        base.update(over)
        return EvidenceNormalizationRequest(**base)

    return src, raw, req


def main() -> int:
    print("Peak Phase 14 evidence-normalization-worker check")
    print("=" * 48)
    failures: list = []

    # 1. Required files exist.
    print("\n1. Worker scaffold files")
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
    workers = None
    try:
        import peak.workers as workers  # noqa: F401
        print(f"  [{PASS}] peak.workers imports")
    except Exception as exc:
        failures.append(f"peak.workers import failed: {exc}")
        print(f"  [{FAIL}] peak.workers import failed: {exc}")

    # 4. Valid request → review-gated result with no side effects.
    print("\n4. Normalization is production-shaped but review-gated")
    src = raw = req = None
    if workers is not None:
        from peak.workers.evidence_normalization import normalize_evidence

        src, raw, req = _synthetic()
        result = normalize_evidence(req())
        checks = {
            "permitted": result.permitted is True,
            "output_status == draft": result.output_status == "draft",
            "review_status == needs_review": result.review_status == "needs_review",
            "authoritative == False": result.authoritative is False,
            "client_facing_approved == False": result.client_facing_approved is False,
            "database_write_made == False": result.database_write_made is False,
            "llm_call_made == False": result.llm_call_made is False,
            "agentnet_call_made == False": result.agentnet_call_made is False,
            "network_call_made == False": result.network_call_made is False,
            "capsule_publication_made == False": result.capsule_publication_made is False,
        }
        for label, ok in checks.items():
            if ok:
                print(f"  [{PASS}] {label}")
            else:
                failures.append(f"result: {label} failed")
                print(f"  [{FAIL}] result: {label} failed")
        rec = result.normalized_record
        if rec is not None and rec.capsule_candidate_ready is False:
            print(f"  [{PASS}] normalized_record.capsule_candidate_ready == False")
        else:
            failures.append("normalized_record.capsule_candidate_ready not False")
            print(f"  [{FAIL}] normalized_record.capsule_candidate_ready not False")

    # 5. Governance rejections.
    print("\n5. Governance rejections")
    if workers is not None:
        from peak.workers.governance import evaluate_evidence_normalization_request as gov

        cases = {
            "missing owner_id": req(owner_id=None),
            "missing client_id": req(client_id=None),
            "missing engagement_id": req(engagement_id=None),
            "rejected review_status": req(review_status="rejected"),
            "revoked lifecycle_status": req(lifecycle_status="revoked"),
            "archived lifecycle_status": req(lifecycle_status="archived"),
            "deleted lifecycle_status": req(lifecycle_status="deleted_reference_only"),
            "missing raw_evidence": req(raw_evidence=None),
            "missing source_reference": req(raw_evidence=raw(source_reference=None)),
            "scope mismatch": req(
                raw_evidence=raw(source_reference=src(authorization_scope="internal_peak_only"))
            ),
        }
        for label, request in cases.items():
            if not gov(request).permitted:
                print(f"  [{PASS}] rejected: {label}")
            else:
                failures.append(f"governance did not reject: {label}")
                print(f"  [{FAIL}] governance did not reject: {label}")

    # 6. No network / database / LLM imports or credentials in the package.
    print("\n6. No network / database / LLM imports in peak/workers/")
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

    # 7. Doc language.
    print("\n7. Review-gate doc language")
    doc_blob = re.sub(r"\s+", " ", "\n".join(read(rel) for rel in DOCS)).lower()
    for phrase in REQUIRED_PHRASES:
        if phrase.lower() in doc_blob:
            print(f"  [{PASS}] phrase present: '{phrase}'")
        else:
            failures.append(f"missing doc phrase: {phrase}")
            print(f"  [{FAIL}] missing doc phrase: '{phrase}'")

    # 8. Source-only discipline.
    print("\n8. Source-only discipline")
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
