#!/usr/bin/env python3
"""Phase 12 AgentNet MCP boundary check.

Stdlib-only. Verifies the Peak-side **governance wrapper scaffold** for future use of the
existing AgentNet MCP connector: the files exist and import/compile, the known tool set is
exactly the three connector tools, governance rejects unauthorized/publication requests,
the mock boundary never claims a live call, the docs carry the required boundary language,
and the repo stays source-only with **no network call and no connector code copied**.

Phase 12 makes no live calls and no AgentNet integration is complete.

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
    "peak/agentnet/__init__.py",
    "peak/agentnet/contracts.py",
    "peak/agentnet/governance.py",
    "peak/agentnet/mock_mcp.py",
    "docs/AGENTNET_MCP_BOUNDARY.md",
    "docs/PEAK_RESOLVER_ACCESS_POLICY.md",
]

PY_FILES = [
    "peak/agentnet/__init__.py",
    "peak/agentnet/contracts.py",
    "peak/agentnet/governance.py",
    "peak/agentnet/mock_mcp.py",
]

EXPECTED_TOOLS = {"agentnet.resolve", "agentnet.resolve_history", "agentnet.validate_capsule"}

BOUNDARY_DOCS = ["docs/AGENTNET_MCP_BOUNDARY.md", "docs/PEAK_RESOLVER_ACCESS_POLICY.md"]

# Required phrases (case-insensitive) that must appear in at least one boundary doc.
REQUIRED_PHRASES = [
    "existing AgentNet MCP connector",
    "Peak governance wrapper",
    "no live calls",
    "no capsule publication",
    "AgentNet integration is not complete",
]

# Network / credential / connector markers that must NOT appear in the agentnet package.
# Matched on import statements and specific tokens so ordinary prose ("opens a socket",
# "no HTTP call") in docstrings does not false-positive.
NETWORK_IMPORT_RE = re.compile(
    r"\b(?:import|from)\s+"
    r"(?:requests|socket|urllib|http|httpx|aiohttp|ftplib|smtplib|telnetlib)\b"
)
FORBIDDEN_TOKENS = [
    "urlopen",
    "os.environ",
    "getenv",
    # Connector credential/config env-var names must not be embedded in package code.
    "AGENTNET_BASE_URL",
    "AGENTNET_API_KEY",
    "AGENTNET_TIMEOUT",
    "agentnet_connectors",  # the separate connector repo must not be imported
    "agentnet-connectors",
]

DB_FILE_EXTS = (".db", ".sqlite", ".sqlite3", ".sql")
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache"}

PASS, FAIL = "PASS", "FAIL"


def _skip(dirpath: str) -> bool:
    return bool(SKIP_DIRS.intersection(dirpath.split(os.sep)))


def read(rel: str) -> str:
    with open(os.path.join(REPO_ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def main() -> int:
    print("Peak Phase 12 AgentNet MCP boundary check")
    print("=" * 41)
    failures: list = []

    # 1. Required files exist.
    print("\n1. Boundary scaffold files")
    for rel in REQUIRED_FILES:
        if os.path.isfile(os.path.join(REPO_ROOT, rel)):
            print(f"  [{PASS}] {rel}")
        else:
            failures.append(f"{rel}: MISSING")
            print(f"  [{FAIL}] {rel}: file not found")

    # 2. Python files compile.
    print("\n2. Python files compile")
    for rel in PY_FILES:
        path = os.path.join(REPO_ROOT, rel)
        try:
            py_compile.compile(path, doraise=True)
            print(f"  [{PASS}] {rel} compiles")
        except py_compile.PyCompileError as exc:
            failures.append(f"{rel}: compile error: {exc}")
            print(f"  [{FAIL}] {rel}: compile error")

    # 3. Package imports and exposes the exact known-tool set.
    print("\n3. Package import + known tool set")
    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)
    agentnet = None
    try:
        import peak.agentnet as agentnet  # noqa: F401
        print(f"  [{PASS}] peak.agentnet imports")
    except Exception as exc:  # pragma: no cover - reported as failure
        failures.append(f"peak.agentnet import failed: {exc}")
        print(f"  [{FAIL}] peak.agentnet import failed: {exc}")

    if agentnet is not None:
        tools = set(getattr(agentnet, "KNOWN_MCP_TOOLS", ()))
        if tools == EXPECTED_TOOLS:
            print(f"  [{PASS}] KNOWN_MCP_TOOLS is exactly the 3 connector tools")
        else:
            failures.append(f"KNOWN_MCP_TOOLS mismatch: {sorted(tools)}")
            print(f"  [{FAIL}] KNOWN_MCP_TOOLS mismatch: {sorted(tools)}")

    # 4. Governance behavior.
    print("\n4. Governance guard behavior")
    if agentnet is not None:
        from peak.agentnet.contracts import ResolverContextRequest
        from peak.agentnet.governance import (
            build_tool_call_plan,
            evaluate_resolve_request,
        )

        def valid(**over):
            base = dict(
                owner_id="owner_peak_1",
                engagement_id="eng_synthetic",
                authorization_scope="engagement_authorized",
                review_status="approved_internal",
                lifecycle_status="active",
            )
            base.update(over)
            return ResolverContextRequest(**base)

        # sanity: a valid request is permitted
        if evaluate_resolve_request(valid()).permitted:
            print(f"  [{PASS}] valid request is permitted")
        else:
            failures.append("valid request unexpectedly rejected")
            print(f"  [{FAIL}] valid request unexpectedly rejected")

        # publication-like tool rejected
        pub = build_tool_call_plan(valid(requested_tool="agentnet.publish_capsule"))
        if not pub.decision.permitted and not pub.live_call_made:
            print(f"  [{PASS}] publication-like tool rejected (no live call)")
        else:
            failures.append("publication-like tool was not rejected")
            print(f"  [{FAIL}] publication-like tool was not rejected")

        # unknown tool rejected
        if not build_tool_call_plan(valid(requested_tool="agentnet.delete_all")).decision.permitted:
            print(f"  [{PASS}] unknown tool rejected")
        else:
            failures.append("unknown tool was not rejected")
            print(f"  [{FAIL}] unknown tool was not rejected")

        # missing owner_id rejected
        d_owner = evaluate_resolve_request(valid(owner_id=None))
        if not d_owner.permitted and any("owner_id" in r for r in d_owner.reasons):
            print(f"  [{PASS}] missing owner_id rejected")
        else:
            failures.append("missing owner_id was not rejected")
            print(f"  [{FAIL}] missing owner_id was not rejected")

        # revoked / archived lifecycle rejected
        rev = evaluate_resolve_request(valid(lifecycle_status="revoked")).permitted
        arc = evaluate_resolve_request(valid(lifecycle_status="archived")).permitted
        if not rev and not arc:
            print(f"  [{PASS}] revoked/archived lifecycle rejected")
        else:
            failures.append(f"lifecycle not rejected (revoked={rev}, archived={arc})")
            print(f"  [{FAIL}] lifecycle not rejected (revoked={rev}, archived={arc})")

    # 5. Mock boundary never claims a live call / active integration.
    print("\n5. Mock boundary is inert (no live call)")
    if agentnet is not None:
        from peak.agentnet.contracts import (
            CapsuleValidationRequest,
            ResolveHistoryRequest,
            ResolverContextRequest,
        )
        from peak.agentnet.mock_mcp import MockAgentNetMCPBoundary

        mock = MockAgentNetMCPBoundary()
        responses = [
            mock.resolve(ResolverContextRequest(
                owner_id="o", engagement_id="eng_x",
                authorization_scope="engagement_authorized")),
            mock.resolve_history(ResolveHistoryRequest(
                owner_id="o", client_id="client_a",
                authorization_scope="engagement_authorized")),
            mock.validate_capsule(CapsuleValidationRequest(
                owner_id="o", engagement_id="eng_x",
                authorization_scope="engagement_authorized")),
        ]
        live = [r for r in responses if getattr(r, "live_call_made", True) is not False]
        active = [r for r in responses
                  if getattr(r, "agentnet_integration_active", True) is not False]
        if not live:
            print(f"  [{PASS}] all mock responses have live_call_made = False")
        else:
            failures.append("a mock response had live_call_made != False")
            print(f"  [{FAIL}] a mock response had live_call_made != False")
        if not active:
            print(f"  [{PASS}] all mock responses have agentnet_integration_active = False")
        else:
            failures.append("a mock response had agentnet_integration_active != False")
            print(f"  [{FAIL}] a mock response had agentnet_integration_active != False")

    # 6. No network / credential / connector markers in the package.
    print("\n6. No network calls / no connector code copied")
    marker_hits = []
    for rel in PY_FILES:
        text = read(rel)
        if NETWORK_IMPORT_RE.search(text):
            marker_hits.append(f"{rel}: network import")
        for token in FORBIDDEN_TOKENS:
            if token in text:
                marker_hits.append(f"{rel}: '{token}'")
    if marker_hits:
        for h in marker_hits:
            failures.append(f"forbidden marker {h}")
            print(f"  [{FAIL}] forbidden marker {h}")
    else:
        print(f"  [{PASS}] no network imports / credential reads / connector imports")
    # Mock must state it is not an AgentNet integration.
    mock_text = read("peak/agentnet/mock_mcp.py").lower()
    if "mock" in mock_text and "not an agentnet integration" in mock_text:
        print(f"  [{PASS}] mock_mcp.py declares itself a mock, not an integration")
    else:
        failures.append("mock_mcp.py missing mock/not-an-integration disclaimer")
        print(f"  [{FAIL}] mock_mcp.py missing mock/not-an-integration disclaimer")

    # 7. Required doc phrases.
    print("\n7. Boundary doc language")
    doc_blob = "\n".join(read(rel) for rel in BOUNDARY_DOCS).lower()
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
                continue  # the only allowed *.example.* file
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

    print("\n" + "=" * 41)
    print("Summary")
    print(f"  failures : {len(failures)}")
    if failures:
        print(f"\nRESULT: {FAIL} ({len(failures)} issue(s))")
        return 1
    print(f"\nRESULT: {PASS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
