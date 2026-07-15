#!/usr/bin/env python3
"""Phase 13 agent-execution-harness check.

Stdlib-only. Verifies the Peak internal **agent execution harness scaffold**: the files
exist and import/compile, the registry lists exactly the 10 known agents/workers with
complete metadata, the mock executor governs a task without any live call and defaults
output to draft/needs_review, governance rejects the disallowed cases, the package makes
no network or database imports, the docs describe AgentNet as not-yet-implemented, and the
repo stays source-only.

Phase 13 makes no live LLM/AgentNet/MCP/resolver/database/network call and creates no
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
    "peak/agents/__init__.py",
    "peak/agents/contracts.py",
    "peak/agents/registry.py",
    "peak/agents/governance.py",
    "peak/agents/executor.py",
    "peak/agents/mock_llm.py",
    "docs/AGENT_EXECUTION_HARNESS.md",
    "docs/AGENT_RUN_RECORDS.md",
]

PY_FILES = [
    "peak/agents/__init__.py",
    "peak/agents/contracts.py",
    "peak/agents/registry.py",
    "peak/agents/governance.py",
    "peak/agents/executor.py",
    "peak/agents/mock_llm.py",
]

EXPECTED_AGENTS = {
    "evidence_normalization_worker",
    "internal_qa_governance_agent",
    "new_client_intake_agent",
    "discovery_planning_agent",
    "interview_structuring_assistant",
    "walkaround_observation_worker",
    "quick_win_identification_agent",
    "initial_report_generation_agent",
    "next_phase_proposal_agent",
    "consultant_copilot",
}

BOUNDARY_DOCS = ["docs/AGENT_EXECUTION_HARNESS.md", "docs/AGENT_RUN_RECORDS.md"]

# Each harness doc must positively state AgentNet is not yet implemented. (Repo-wide
# over-claim scanning is handled by the Phase 8/9 guards across all docs.)
AGENTNET_NOT_IMPLEMENTED = "agentnet integration is not complete"

# Network imports must not appear in the agents package.
NETWORK_IMPORT_RE = re.compile(
    r"\b(?:requests|socket|urllib|httpx|aiohttp|ftplib|smtplib|telnetlib)\b"
)
NETWORK_HTTP_RE = re.compile(r"\bhttp\b")
# Database imports must not be required by the agents package.
DB_IMPORT_RE = re.compile(r"\b(?:sqlalchemy|alembic)\b")

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


def main() -> int:
    print("Peak Phase 13 agent-execution-harness check")
    print("=" * 43)
    failures: list = []

    # 1. Required files exist.
    print("\n1. Harness scaffold files")
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

    # 3. Package import + registry.
    print("\n3. Package import + registry")
    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)
    agents = None
    try:
        import peak.agents as agents  # noqa: F401
        print(f"  [{PASS}] peak.agents imports")
    except Exception as exc:
        failures.append(f"peak.agents import failed: {exc}")
        print(f"  [{FAIL}] peak.agents import failed: {exc}")

    if agents is not None:
        known = set(getattr(agents, "KNOWN_AGENTS", ()))
        if known == EXPECTED_AGENTS:
            print(f"  [{PASS}] registry lists exactly the 10 known agents")
        else:
            failures.append(f"registry mismatch: {sorted(known ^ EXPECTED_AGENTS)}")
            print(f"  [{FAIL}] registry mismatch: {sorted(known ^ EXPECTED_AGENTS)}")

        # Every entry has the required metadata (non-empty).
        incomplete = []
        for entry in agents.list_agents():
            for attr in ("workflow", "purpose", "default_output_status", "default_review_status"):
                val = getattr(entry, attr, None)
                if not val:
                    incomplete.append(f"{entry.agent_name}.{attr}")
        if incomplete:
            failures.append(f"registry entries missing metadata: {incomplete}")
            print(f"  [{FAIL}] registry entries missing metadata: {incomplete}")
        else:
            print(f"  [{PASS}] every registry entry has workflow/purpose/output/review defaults")

        # Referenced prompt contracts (non-None) must exist.
        missing_contracts = []
        for entry in agents.list_agents():
            p = entry.prompt_contract_path
            if p and not os.path.isfile(os.path.join(REPO_ROOT, p)):
                missing_contracts.append(f"{entry.agent_name} -> {p}")
        if missing_contracts:
            failures.append(f"missing prompt contracts: {missing_contracts}")
            print(f"  [{FAIL}] missing prompt contracts: {missing_contracts}")
        else:
            print(f"  [{PASS}] all referenced prompt contracts exist")

    # 4. Executor is inert + defaults draft/needs_review.
    print("\n4. Mock executor is inert")
    if agents is not None:
        from peak.agents.contracts import AgentTaskRequest
        from peak.agents.executor import MockAgentExecutor

        def valid(**over):
            base = dict(
                agent_name="evidence_normalization_worker",
                owner_id="owner_peak_1",
                engagement_id="eng_synthetic",
                authorization_scope="engagement_authorized",
                review_status="needs_review",
                lifecycle_status="active",
                resolver_context_allowed=True,
                requested_action="normalize evidence",
            )
            base.update(over)
            return AgentTaskRequest(**base)

        ex = MockAgentExecutor()
        r = ex.execute(valid())
        checks = {
            "permitted": r.permitted is True,
            "llm_call_made == False": r.llm_call_made is False,
            "agentnet_call_made == False": r.agentnet_call_made is False,
            "database_write_made == False": r.database_write_made is False,
            "client_facing_output_created == False": r.client_facing_output_created is False,
            "output_status == draft": r.output_status == "draft",
            "review_status == needs_review": r.review_status == "needs_review",
        }
        for label, ok in checks.items():
            if ok:
                print(f"  [{PASS}] {label}")
            else:
                failures.append(f"executor: {label} failed")
                print(f"  [{FAIL}] executor: {label} failed")

    # 5. Governance rejections.
    print("\n5. Governance rejections")
    if agents is not None:
        from peak.agents.governance import evaluate_agent_task

        cases = {
            "unknown agent_name": valid(agent_name="does_not_exist"),
            "missing owner_id": valid(owner_id=None),
            "revoked lifecycle": valid(lifecycle_status="revoked"),
            "archived lifecycle": valid(lifecycle_status="archived"),
            "client_facing_output_requested": valid(client_facing_output_requested=True),
            "llm_execution_allowed": valid(llm_execution_allowed=True),
        }
        for label, req in cases.items():
            if not evaluate_agent_task(req).permitted:
                print(f"  [{PASS}] rejected: {label}")
            else:
                failures.append(f"governance did not reject: {label}")
                print(f"  [{FAIL}] governance did not reject: {label}")

    # 6. No network / database imports in the package.
    print("\n6. No network / database imports in peak/agents/")
    net_hits, db_hits = [], []
    for rel in PY_FILES:
        for line in _import_lines(read(rel)):
            if NETWORK_IMPORT_RE.search(line) or NETWORK_HTTP_RE.search(line):
                net_hits.append(f"{rel}: {line}")
            if DB_IMPORT_RE.search(line) or "peak.db" in line or re.search(r"from\s+\.+db\b", line):
                db_hits.append(f"{rel}: {line}")
    if net_hits:
        for h in net_hits:
            failures.append(f"network import {h}")
            print(f"  [{FAIL}] network import {h}")
    else:
        print(f"  [{PASS}] no network imports")
    if db_hits:
        for h in db_hits:
            failures.append(f"database import {h}")
            print(f"  [{FAIL}] database import {h}")
    else:
        print(f"  [{PASS}] no database imports")

    # 7. Docs positively state AgentNet is not implemented.
    print("\n7. AgentNet not described as implemented")
    for rel in BOUNDARY_DOCS:
        norm = re.sub(r"\s+", " ", read(rel).lower())
        if AGENTNET_NOT_IMPLEMENTED in norm:
            print(f"  [{PASS}] {rel} states AgentNet integration is not complete")
        else:
            failures.append(f"{rel} missing not-implemented statement")
            print(f"  [{FAIL}] {rel} missing 'AgentNet integration is not complete'")

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

    print("\n" + "=" * 43)
    print("Summary")
    print(f"  failures : {len(failures)}")
    if failures:
        print(f"\nRESULT: {FAIL} ({len(failures)} issue(s))")
        return 1
    print(f"\nRESULT: {PASS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
