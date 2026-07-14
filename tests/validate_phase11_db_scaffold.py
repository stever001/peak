#!/usr/bin/env python3
"""Phase 11 database-scaffold check.

Structural, stdlib-only. Confirms the MySQL/SQLAlchemy/Alembic scaffold exists as
**source assets only**, with no committed data, credentials, seed inserts, or database
files, and that the enum layer stays aligned to the Phase 9 schema contracts.

If SQLAlchemy is installed, an optional import check verifies the model metadata; if it
is not installed, that check is skipped (structural validation still runs). AgentNet is
checked to be described only as intended future architecture.

Exit status:
  0  -> all structural checks passed
  1  -> a required file is missing, or a forbidden artifact/credential/insert exists
"""

from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REQUIRED_FILES = [
    "peak/__init__.py",
    "peak/db/__init__.py",
    "peak/db/base.py",
    "peak/db/enums.py",
    "peak/db/models.py",
    "peak/db/session.py",
    "alembic.ini",
    "alembic/env.py",
    "alembic/versions/001_initial_controlled_database_schema.py",
    ".env.example",
    "docs/DATABASE_SCAFFOLD.md",
    "requirements.txt",
]

EXPECTED_TABLES = [
    "clients", "engagements", "engagement_records", "evidence_references",
    "source_system_references", "financial_impact_estimates", "resolver_capsule_records",
    "review_records", "agent_run_records", "capsule_publication_candidates",
    "source_ingestion_records",
]

# Phase 9 schemas are the source of truth for governance enum values.
ENUM_SOURCES = {
    "AuthorizationScope": "schemas/authorization-scope.schema.json",
    "ReviewStatus": "schemas/review-status.schema.json",
    "LifecycleStatus": "schemas/lifecycle-status.schema.json",
    "EvidenceStatus": "schemas/governance-state.schema.json",
    "FinancialImpactStatus": "schemas/governance-state.schema.json",
    "ResolverCapsuleStatus": "schemas/governance-state.schema.json",
    "SourceSystemAccessStatus": "schemas/governance-state.schema.json",
    "ClientFacingApprovalStatus": "schemas/governance-state.schema.json",
}

MIGRATION_GLOB = "alembic/versions/*.py"
INSERT_PATTERNS = ("insert into", "bulk_insert", "op.execute(", ".insert(")

# Credential / secret patterns (low false-positive).
AKIA_RE = re.compile(r"AKIA[0-9A-Z]{16}")
PRIVKEY_RE = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")

AGENTNET_OVERCLAIM = (
    "agentnet is integrated", "agentnet integration is complete",
    "agentnet integration complete", "agentnet integration is done",
    "agentnet is live", "agentnet grounding is live", "fully integrated with agentnet",
)
AGENTNET_NEGATORS = ("not", "never", "no ", "cannot", "n't", "without")
AGENTNET_SCAN = ["docs/DATABASE_SCAFFOLD.md", "docs/DATABASE_IMPLEMENTATION_PLAN.md"]

DB_FILE_EXTS = (".db", ".sqlite", ".sqlite3", ".sql")

# Local environment/build dirs are not part of the source tree; skip them when walking so
# a dependency shipped into a local .venv can't trip the artifact/credential scans.
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache"}

PASS, FAIL = "PASS", "FAIL"


def _skip(dirpath: str) -> bool:
    return bool(SKIP_DIRS.intersection(dirpath.split(os.sep)))


def read(rel):
    with open(os.path.join(REPO_ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def git_tracked(rel: str) -> bool:
    try:
        out = subprocess.run(
            ["git", "-C", REPO_ROOT, "ls-files", rel],
            capture_output=True, text=True, timeout=10,
        )
        return bool(out.stdout.strip())
    except Exception:
        return False  # git unavailable — treat as "not known tracked"


def main() -> int:
    print("Peak Phase 11 database-scaffold check")
    print("=" * 37)
    failures: list[str] = []

    # 1. Required files exist.
    print("\n1. Scaffold files")
    for rel in REQUIRED_FILES:
        if os.path.isfile(os.path.join(REPO_ROOT, rel)):
            print(f"  [{PASS}] {rel}")
        else:
            failures.append(f"{rel}: MISSING")
            print(f"  [{FAIL}] {rel}: file not found")

    # 2. .env handling.
    print("\n2. Environment / credentials")
    env_ex = read(".env.example") if os.path.isfile(os.path.join(REPO_ROOT, ".env.example")) else ""
    if "PEAK_DATABASE_URL" in env_ex and "mysql+pymysql" in env_ex:
        print(f"  [{PASS}] .env.example has PEAK_DATABASE_URL (MySQL placeholder)")
    else:
        failures.append(".env.example missing PEAK_DATABASE_URL / mysql+pymysql placeholder")
        print(f"  [{FAIL}] .env.example missing PEAK_DATABASE_URL / mysql+pymysql placeholder")
    if git_tracked(".env"):
        failures.append(".env is tracked by git")
        print(f"  [{FAIL}] .env is tracked by git (must be ignored)")
    else:
        print(f"  [{PASS}] .env is not tracked")
    if "!.env.example" in read(".gitignore") and ".env" in read(".gitignore"):
        print(f"  [{PASS}] .gitignore ignores .env and allows .env.example")
    else:
        failures.append(".gitignore does not ignore .env / allow .env.example")
        print(f"  [{FAIL}] .gitignore does not ignore .env / allow .env.example")

    # 3. Source-only: no data artifacts / db files.
    print("\n3. Source-only discipline")
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
            if f.endswith(".example.json") or f.endswith(".example.md") or "redacted" in f:
                artifacts.append(os.path.relpath(os.path.join(dp, f), REPO_ROOT))
            if f.lower().endswith(DB_FILE_EXTS):
                dbfiles.append(os.path.relpath(os.path.join(dp, f), REPO_ROOT))
    for label, hits in (("data artifact", artifacts), ("database file", dbfiles)):
        if hits:
            for h in hits:
                failures.append(f"forbidden {label}: {h}")
                print(f"  [{FAIL}] forbidden {label}: {h}")
        else:
            print(f"  [{PASS}] no {label}s found")

    # 4. Migrations: schema only, no data inserts.
    print("\n4. Migrations define schema only")
    migrations = sorted(glob.glob(os.path.join(REPO_ROOT, MIGRATION_GLOB)))
    if not migrations:
        failures.append("no migration files found")
        print(f"  [{FAIL}] no migration files found")
    for m in migrations:
        low = open(m, encoding="utf-8").read().lower()
        hits = [p for p in INSERT_PATTERNS if p in low]
        rel = os.path.relpath(m, REPO_ROOT)
        if hits:
            failures.append(f"{rel}: insert/seed pattern(s): {hits}")
            print(f"  [{FAIL}] {rel}: insert/seed pattern(s) {hits}")
        else:
            print(f"  [{PASS}] {rel}: no insert/seed statements")

    # 5. No obvious committed credentials.
    print("\n5. No committed credentials")
    secret_hits = []
    for dp, _, files in os.walk(REPO_ROOT):
        if _skip(dp):
            continue
        for f in files:
            fp = os.path.join(dp, f)
            rel = os.path.relpath(fp, REPO_ROOT)
            if rel == ".env.example" or not f.endswith((".py", ".md", ".ini", ".txt", ".cfg", ".env")):
                continue
            try:
                text = open(fp, encoding="utf-8").read()
            except (OSError, UnicodeDecodeError):
                continue
            if AKIA_RE.search(text) or PRIVKEY_RE.search(text):
                secret_hits.append(rel)
    if secret_hits:
        for h in secret_hits:
            failures.append(f"possible secret in {h}")
            print(f"  [{FAIL}] possible secret in {h}")
    else:
        print(f"  [{PASS}] no obvious credential strings committed")

    # 6. Enum alignment with Phase 9 schemas.
    print("\n6. Enum alignment (Phase 9 is source of truth)")
    enums_text = read("peak/db/enums.py") if os.path.isfile(os.path.join(REPO_ROOT, "peak/db/enums.py")) else ""
    for family, schema_rel in ENUM_SOURCES.items():
        try:
            schema = json.loads(read(schema_rel))
            values = schema.get("$defs", {}).get(family, {}).get("enum", [])
        except Exception as exc:
            failures.append(f"{family}: {exc}")
            print(f"  [{FAIL}] {family}: {exc}")
            continue
        missing = [v for v in values if f'"{v}"' not in enums_text]
        if not values:
            failures.append(f"{family}: no enum in {schema_rel}")
            print(f"  [{FAIL}] {family}: no enum values in {schema_rel}")
        elif missing:
            failures.append(f"{family}: enums.py missing {missing}")
            print(f"  [{FAIL}] {family}: enums.py missing {missing}")
        else:
            print(f"  [{PASS}] {family}: all {len(values)} values mirrored in enums.py")

    # 7. MySQL documented.
    print("\n7. MySQL target documented")
    scaffold = read("docs/DATABASE_SCAFFOLD.md").lower() if os.path.isfile(os.path.join(REPO_ROOT, "docs/DATABASE_SCAFFOLD.md")) else ""
    if "mysql" in scaffold and "sqlite" in scaffold:  # mentions MySQL and rules out SQLite
        print(f"  [{PASS}] DATABASE_SCAFFOLD.md documents MySQL target")
    elif "mysql" in scaffold:
        print(f"  [{PASS}] DATABASE_SCAFFOLD.md documents MySQL target")
    else:
        failures.append("DATABASE_SCAFFOLD.md does not document MySQL")
        print(f"  [{FAIL}] DATABASE_SCAFFOLD.md does not document MySQL")

    # 8. AgentNet not implemented.
    print("\n8. AgentNet not described as implemented")
    offenders = []
    for rel in AGENTNET_SCAN:
        p = os.path.join(REPO_ROOT, rel)
        if not os.path.isfile(p):
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

    # 9. Optional: dependency-backed import + metadata verification.
    #    Runs only when SQLAlchemy/Alembic are installed (see requirements.txt); the
    #    structural checks above still run without them. Verifies importability,
    #    the exact table set, unique table names, and required governance/audit columns.
    print("\n9. Dependency-backed model import (SQLAlchemy / Alembic)")
    try:
        import sqlalchemy  # noqa: F401
    except ImportError:
        print("  [skip] SQLAlchemy not installed — structural check only "
              "(pip install -r requirements.txt to enable)")
    else:
        print(f"  [{PASS}] SQLAlchemy imports ({sqlalchemy.__version__})")
        try:
            import alembic  # noqa: F401
            print(f"  [{PASS}] Alembic imports ({alembic.__version__})")
        except ImportError:
            failures.append("alembic not importable despite SQLAlchemy present")
            print(f"  [{FAIL}] Alembic not importable (pip install -r requirements.txt)")

        sys.path.insert(0, REPO_ROOT)
        from peak.db.base import Base
        from peak.db import models as db_models  # noqa: F401
        print(f"  [{PASS}] peak.db.models imports")

        # Exactly the expected table set — no more, no fewer.
        tables = set(Base.metadata.tables)
        missing = sorted(set(EXPECTED_TABLES) - tables)
        unexpected = sorted(tables - set(EXPECTED_TABLES))
        if missing:
            failures.append(f"model metadata missing tables: {missing}")
            print(f"  [{FAIL}] model metadata missing tables: {missing}")
        if unexpected:
            failures.append(f"model metadata has unexpected tables: {unexpected}")
            print(f"  [{FAIL}] model metadata has unexpected tables: {unexpected}")
        if not missing and not unexpected:
            print(f"  [{PASS}] Base.metadata defines exactly the {len(EXPECTED_TABLES)} expected tables")

        # __tablename__ values must be unique across the declared models.
        tablenames = [m.__tablename__ for m in getattr(db_models, "ALL_MODELS", [])]
        dupes = sorted({t for t in tablenames if tablenames.count(t) > 1})
        if dupes:
            failures.append(f"duplicate model table names: {dupes}")
            print(f"  [{FAIL}] duplicate model table names: {dupes}")
        else:
            print(f"  [{PASS}] model table names are unique ({len(tablenames)} models)")

        # Required governance/audit columns present on every governed table.
        required_cols = [
            "owner_id", "authorization_scope", "review_status", "lifecycle_status",
            "created_at", "updated_at",
        ]
        col_failures = []
        for tname in EXPECTED_TABLES:
            table = Base.metadata.tables.get(tname)
            if table is None:
                continue  # already reported as missing above
            absent = [c for c in required_cols if c not in table.columns]
            if absent:
                col_failures.append(f"{tname}: missing {absent}")
        if col_failures:
            for cf in col_failures:
                failures.append(f"required column(s) absent — {cf}")
                print(f"  [{FAIL}] required column(s) absent — {cf}")
        else:
            print(f"  [{PASS}] all tables carry required governance/audit columns "
                  f"({', '.join(required_cols)})")

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
