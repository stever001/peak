#!/usr/bin/env python3
"""Phase 10 database-plan doc check.

Lightweight, stdlib-only. Confirms the Phase 10 database-planning docs exist with their
required headings/phrases, that the repo stays source-only (no data artifacts, no SQL
migrations, no DB config files), and that AgentNet is not described as implemented.

Exit status:
  0  -> all checks passed
  1  -> a doc/marker is missing, a forbidden artifact exists, or AgentNet is over-claimed
"""

from __future__ import annotations

import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REQUIRED_DOCS = [
    "docs/DATABASE_IMPLEMENTATION_PLAN.md",
    "docs/DATABASE_RECORD_MODEL.md",
    "docs/DATABASE_ACCESS_AND_AUDIT.md",
    "docs/DATABASE_TO_RESOLVER_MAPPING.md",
]

# Per-doc required markers (lowercased substrings).
PER_DOC = {
    "docs/DATABASE_IMPLEMENTATION_PLAN.md": [
        "purpose and scope", "this is a plan, not an implementation",
        "system of record", "staged implementation plan",
        "phase 11", "phase 12", "phase 13",
    ],
    "docs/DATABASE_RECORD_MODEL.md": [
        "agentrunrecord", "capsulepublicationcandidate", "sourceingestionrecord",
        "capsule-ready", "reviewrecord", "financialimpactestimate",
    ],
    "docs/DATABASE_ACCESS_AND_AUDIT.md": [
        "owner_id", "client_id", "engagement_id", "agent_run_id",
        "audit fields", "human review", "no agent may",
    ],
    "docs/DATABASE_TO_RESOLVER_MAPPING.md": [
        "capsule readiness criteria", "public-but-segregated", "private resolver",
        "no publication implementation", "no uncontrolled publication",
    ],
}

# Phrases required somewhere across the combined Phase 10 doc text.
REQUIRED_PHRASES = [
    "source-only",
    "controlled database",
    "private resolver capsule",
    "public-but-segregated",
    "private resolver",
    "no client data in git",
    "training",                 # "...examples, fixtures, demos, training..."
    "human review gate",
    "agent permission limits",
]

# Source-only / no-artifact discipline.
FORBIDDEN_PATHS = ["examples", "docs/REDACTION_GUIDE.md"]
# Database implementation must not appear this phase.
# Note: alembic.ini is an allowed source asset from Phase 11 (Alembic migration config,
# no data/credentials — the URL comes from the environment), so it is NOT forbidden.
DB_CONFIG_NAMES = {
    "database.yml", "database.yaml", "knexfile.js", "ormconfig.json",
    "my.cnf", "postgresql.conf", "schema.prisma", "sequelize.config.js",
}
DB_FILE_EXTS = (".sql", ".sqlite", ".sqlite3", ".db")

# AgentNet over-claim scan.
SCAN_DOCS = REQUIRED_DOCS
SCAN_SKIP = {
    os.path.abspath(__file__),
    os.path.abspath(os.path.join(REPO_ROOT, "tests", "validate_phase8_architecture.py")),
    os.path.abspath(os.path.join(REPO_ROOT, "tests", "validate_phase9_governance.py")),
}
AGENTNET_OVERCLAIM = (
    "agentnet is integrated", "agentnet integration is complete",
    "agentnet integration complete", "agentnet integration is done",
    "agentnet is live", "agentnet grounding is live", "fully integrated with agentnet",
)
AGENTNET_NEGATORS = ("not", "never", "no ", "cannot", "n't", "without")

PASS, FAIL = "PASS", "FAIL"


def read(rel):
    with open(os.path.join(REPO_ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def main() -> int:
    print("Peak Phase 10 database-plan doc check")
    print("=" * 37)
    failures: list[str] = []

    # 1. Docs exist + per-doc markers.
    print("\n1. Database-plan docs")
    combined = ""
    for rel in REQUIRED_DOCS:
        path = os.path.join(REPO_ROOT, rel)
        if not os.path.isfile(path):
            failures.append(f"{rel}: MISSING")
            print(f"  [{FAIL}] {rel}: file not found")
            continue
        text = read(rel).lower()
        combined += "\n" + text
        missing = [m for m in PER_DOC[rel] if m not in text]
        if missing:
            failures.append(f"{rel}: missing " + ", ".join(missing))
            print(f"  [{FAIL}] {rel}: missing " + ", ".join(missing))
        else:
            print(f"  [{PASS}] {rel}: all {len(PER_DOC[rel])} markers present")

    # 2. Required phrases across the doc set.
    print("\n2. Required strategic/governance phrases")
    for phrase in REQUIRED_PHRASES:
        if phrase in combined:
            print(f"  [{PASS}] '{phrase}'")
        else:
            failures.append(f"missing phrase: {phrase}")
            print(f"  [{FAIL}] missing phrase: '{phrase}'")

    # 3. Source-only discipline + no DB implementation artifacts.
    print("\n3. Source-only / no DB implementation")
    for rel in FORBIDDEN_PATHS:
        if os.path.exists(os.path.join(REPO_ROOT, rel)):
            failures.append(f"forbidden path exists: {rel}")
            print(f"  [{FAIL}] forbidden path exists: {rel}")
        else:
            print(f"  [{PASS}] absent: {rel}")

    artifacts, sqls, configs = [], [], []
    for dp, dirs, files in os.walk(REPO_ROOT):
        if ".git" in dp.split(os.sep):
            continue
        if os.path.basename(dp) == "migrations":
            configs.append(os.path.relpath(dp, REPO_ROOT) + "/ (migrations dir)")
        for f in files:
            low = f.lower()
            if f.endswith(".example.json") or f.endswith(".example.md") or "redacted" in f:
                artifacts.append(os.path.relpath(os.path.join(dp, f), REPO_ROOT))
            if low.endswith(DB_FILE_EXTS):
                sqls.append(os.path.relpath(os.path.join(dp, f), REPO_ROOT))
            if low in DB_CONFIG_NAMES:
                configs.append(os.path.relpath(os.path.join(dp, f), REPO_ROOT))
    for label, hits in (("data artifact", artifacts), ("SQL/db file", sqls), ("DB config", configs)):
        if hits:
            for h in hits:
                failures.append(f"forbidden {label}: {h}")
                print(f"  [{FAIL}] forbidden {label}: {h}")
        else:
            print(f"  [{PASS}] no {label}s found")

    # 4. AgentNet not described as implemented.
    print("\n4. AgentNet not described as implemented")
    offenders = []
    for rel in SCAN_DOCS:
        p = os.path.join(REPO_ROOT, rel)
        if not os.path.isfile(p) or os.path.abspath(p) in SCAN_SKIP:
            continue
        norm = re.sub(r"\s+", " ", read(rel).lower())
        for phrase in AGENTNET_OVERCLAIM:
            start = 0
            while (idx := norm.find(phrase, start)) != -1:
                start = idx + len(phrase)
                if not any(n in norm[max(0, idx - 60):idx] for n in AGENTNET_NEGATORS):
                    offenders.append(f"{rel}: '{phrase}'")
    if offenders:
        for o in offenders:
            failures.append(f"AgentNet over-claim: {o}")
            print(f"  [{FAIL}] AgentNet over-claim at {o}")
    else:
        print(f"  [{PASS}] AgentNet described only as intended/not-implemented")

    print("\n" + "=" * 37)
    print("Summary")
    print(f"  failures : {len(failures)}")
    if failures:
        print(f"\nRESULT: {FAIL} ({len(failures)} issue(s))")
        return 1
    print(f"\nRESULT: {PASS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
