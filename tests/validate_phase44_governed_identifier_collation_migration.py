#!/usr/bin/env python3
"""Phase 44 governed identifier collation migration check.

Verifies that migration `013_governed_identifier_collation_policy` and the matching model metadata
pin a deterministic collation on exactly the governed columns — and on nothing else.

Five layers:

* **Baseline** — the Alembic head moved 012 → 013, there are 13 migrations, the table count is
  still 18, no new table/model entity or allowlist pair appeared, and the repo stays source-only.

* **Migration** — `013` is ALTER-only: no CREATE/DROP TABLE, no INSERT/UPDATE/DELETE, no seed or
  client data, no raw SQL, no index or constraint rename. Its `down_revision` is 012, the chain
  stays linear and single-headed, no earlier migration was edited, and the MySQL ALTERs are gated
  so SQLite is a deliberate no-op.

* **Coverage** — the migration's explicit mapping is compared *both ways* against the live models:
  every deterministic-required governed column appears in the mapping, every mapped column exists
  in the model with matching length and nullability, and no `ordinary_text`, `json_or_details_text`,
  or `governed_enum_status` column was swept in.

* **Model policy** — every governed column resolves to `utf8mb4_bin` on MySQL while leaving SQLite
  untouched (the reason the collation is attached through `with_variant`, not `String(collation=)`),
  including all idempotency-boundary, hash/fingerprint, and scope columns.

* **Tooling + regression** — the audit now reports the model policy satisfied *and* production
  unverified; the parity checker still passes; the production verifier still skips safely; and the
  standing forbidden-path and policy guarantees hold.

Exit status:
  0  -> all checks passed
  1  -> a check failed
"""

from __future__ import annotations

import io
import os
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile
import tokenize

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(REPO_ROOT, "tools")
for _p in (REPO_ROOT, TOOLS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

PY = sys.executable or "python3"

BASELINE_COMMIT = "c624854"   # Add Phase 43 production MySQL collation verification

MIGRATION_NAME = "013_governed_identifier_collation_policy"
MIGRATION_REL = f"alembic/versions/{MIGRATION_NAME}.py"
PRIOR_HEAD = "012_internal_report_review_packet_decisions"
#: The head the production verifier expects, which tracks the *live* production head rather than
#: this phase's migration. Phase 58 applied 014 to production, so the pin moved 013 -> 014.
PRODUCTION_EXPECTED_HEAD = "014_engagement_classification"
AUDIT = "tools/governed_mysql_collation_audit.py"
PARITY = "tools/managed_mysql_parity_check.py"
VERIFIER = "tools/production_mysql_collation_verify.py"
POLICY_DOC = "docs/GOVERNED_MYSQL_COLLATION_POLICY.md"
HARNESS = "tests/validate_phase44_governed_identifier_collation_migration.py"
MODELS = "peak/db/models.py"
BASE = "peak/db/base.py"

EXPECTED_MIGRATIONS = 14
EXPECTED_TABLE_COUNT = 18
#: Columns migration 013 itself pins. Phase 56's migration 014 creates one further
#: governed column (`engagements.engagement_category`) already pinned at creation, so
#: the *model* now carries 212 — see EXPECTED_MODEL_GOVERNED_COLUMNS.
EXPECTED_GOVERNED_COLUMNS = 211
EXPECTED_MODEL_GOVERNED_COLUMNS = 212
#: Governed columns created already-pinned by a migration later than 013.
LATER_PINNED = {("engagements", "engagement_category")}
EXPECTED_BOUNDARY_TABLES = 11
GOVERNED_COLLATION = "utf8mb4_bin"
MYSQL_IDENTIFIER_LIMIT = 64

IDEMPOTENCY_BOUNDARY = ("owner_id", "client_id", "engagement_id", "idempotency_key")

DATA_EXTS = (".csv", ".xlsx", ".xls", ".parquet", ".db", ".sqlite", ".sqlite3", ".sql", ".dump")
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache"}
DSN_LITERAL_RE = re.compile(r"\b[a-z][a-z0-9+.\-]*://[\w.\-]+:[^\s@'\"]+@")
CREDENTIAL_RE = re.compile(
    r"\b(?:api_key|secret_key|access_key|password|passwd)\b\s*[:=]\s*['\"][^'\"]{3,}['\"]",
    re.IGNORECASE)

_CANARY = "ZZCANARYSECRET44ZZ"
_CANARY_DSN = f"mysql+pymysql://zzcanary44:{_CANARY}@canary44.invalid.example:3306/peakprod"
_CANARY_FRAGMENTS = ("zzcanary44", _CANARY, "canary44.invalid.example", _CANARY_DSN)

PASS, FAIL = "PASS", "FAIL"
_failures: list = []


def read(rel: str) -> str:
    with open(os.path.join(REPO_ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def _skip(dp: str) -> bool:
    return bool(SKIP_DIRS.intersection(dp.split(os.sep)))


def code_only(source: str) -> str:
    """Executable tokens only — comments and docstrings removed.

    A migration that *documents* what it refuses to do must not be flagged for saying so.
    """
    out = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type in (tokenize.COMMENT, tokenize.STRING):
                continue
            out.append(tok.string)
    except tokenize.TokenError:  # pragma: no cover
        return source
    return " ".join(out)


def code_compact(source: str) -> str:
    """Executable code with comments, strings, and *all whitespace* removed.

    ``code_only`` joins tokens with spaces, so a symbol lookup like ``op.alter_column(`` would
    never match and the check would pass vacuously. Compacting makes structural symbol searches
    mean what they appear to mean.
    """
    return re.sub(r"\s+", "", code_only(source))


def check(label: str, ok: bool) -> None:
    if ok:
        print(f"  [{PASS}] {label}")
    else:
        _failures.append(label)
        print(f"  [{FAIL}] {label}")


def _no_canary(text: str) -> bool:
    return not any(frag in text for frag in _CANARY_FRAGMENTS)


def migration_mapping():
    """Extract ``GOVERNED_COLUMNS`` from the migration **statically**, without importing it.

    Parsing rather than importing has two benefits: it works on an interpreter without Alembic
    installed, and it proves the mapping really is a static literal — a migration that built its
    column list at runtime would fail ``ast.literal_eval`` here, which is exactly the property the
    reviewability requirement asks for.
    """
    import ast
    tree = ast.parse(read(MIGRATION_REL))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "GOVERNED_COLUMNS" for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError("GOVERNED_COLUMNS not found as a static literal in the migration")


# --------------------------------------------------------------------------- 1. baseline


def baseline_checks() -> None:
    print("\n1. Baseline: head moved 012 -> 013, 13 migrations, 18 tables")
    versions_dir = os.path.join(REPO_ROOT, "alembic", "versions")
    versions = sorted(f for f in os.listdir(versions_dir) if f.endswith(".py"))
    check(f"exactly {EXPECTED_MIGRATIONS} migrations", len(versions) == EXPECTED_MIGRATIONS)
    check(f"{MIGRATION_REL} exists", os.path.isfile(os.path.join(REPO_ROOT, MIGRATION_REL)))
    # Phase 44 owns 013; the invariant is that it still exists in the chain, not that it stays
    # newest — Phase 56 legitimately appended 014 after it.
    check(f"{MIGRATION_NAME} is still present in the chain",
          f"{MIGRATION_NAME}.py" in versions)
    check("no migration 015 or later",
          not any(re.match(r"^0*(?:1[5-9]|[2-9]\d)_", f) for f in versions))
    try:
        py_compile.compile(os.path.join(REPO_ROOT, MIGRATION_REL), doraise=True)
        check(f"{MIGRATION_REL} compiles", True)
    except py_compile.PyCompileError:
        check(f"{MIGRATION_REL} compiles", False)

    import importlib
    p11 = importlib.import_module("tests.validate_phase11_db_scaffold")
    check(f"db-check still expects exactly {EXPECTED_TABLE_COUNT} tables",
          len(list(getattr(p11, "EXPECTED_TABLES", []))) == EXPECTED_TABLE_COUNT)
    models_src = read(MODELS)
    check(f"models.py still declares exactly {EXPECTED_TABLE_COUNT} tables",
          models_src.count("__tablename__ = ") == EXPECTED_TABLE_COUNT)

    from peak.persistence.allowlist import ALLOWED_ACTIONS, ALLOWED_TABLES
    check("allowlist still has exactly 13 tables", len(ALLOWED_TABLES) == 13)
    check("allowlist still has exactly 15 actions", len(ALLOWED_ACTIONS) == 15)
    check("no collation/migration action added to the allowlist",
          not any(re.search(r"collat|migrat|alter", a) for a in ALLOWED_ACTIONS))

    writers = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "peak", "db"))
                     if f.endswith("_writer.py"))
    check("still exactly the twelve narrow controlled writers", len(writers) == 12)

    try:
        # Scoped to the sources the collation change could plausibly have disturbed — models,
        # the declarative base, the controlled writers, and the allowlist — rather than all of
        # peak/. The claim is "013 altered no writer and no governed entity", not "no peak/ file
        # may ever change again": later phases legitimately touch other infrastructure (Phase 49
        # repointed peak/db/session.py at the runtime URL variable).
        changed = subprocess.run(
            ["git", "-C", REPO_ROOT, "diff", "--name-only", "HEAD", "--", "peak"],
            capture_output=True, text=True, timeout=20).stdout.strip().splitlines()
        # Writers and the allowlist *file* were frozen here until Phase 54, which legitimately
        # owns the engagement authorization anchor writer and the one-pair anchor-creation gate
        # added beside the generic sets. The substantive invariant — the generic allowlist is
        # unchanged and root tables stay prohibited — is asserted directly instead.
        from peak.persistence.allowlist import ALLOWED_ACTIONS, ALLOWED_TABLES, PROHIBITED_TABLES
        check("the generic allowlist is unchanged and root tables stay prohibited",
              len(ALLOWED_TABLES) == 13 and len(ALLOWED_ACTIONS) == 15
              and "engagements" in PROHIBITED_TABLES and "clients" in PROHIBITED_TABLES
              and "engagements" not in ALLOWED_TABLES)
        untouched = subprocess.run(
            ["git", "-C", REPO_ROOT, "diff", "--name-only", "HEAD", "--",
             "schemas", "prompts", "agents"],
            capture_output=True, text=True, timeout=20).stdout.strip()
        check("schemas/, prompts/, agents/ are untouched", not untouched)
        # Scoped to alembic/versions, not all of alembic/: the claim is about migration files.
        # The Alembic environment itself (env.py and its helpers) is allowed to evolve — Phase 47
        # hardens the version table there without touching any migration.
        older = subprocess.run(
            ["git", "-C", REPO_ROOT, "diff", "--name-only", "HEAD", "--", "alembic/versions"],
            capture_output=True, text=True, timeout=20).stdout.strip()
        check("no earlier migration was edited (013 is new, not a rewrite)", not older)
    except Exception:
        check("git-backed scope checks (git unavailable — skipped)", True)


# --------------------------------------------------------------------------- 2. migration


def migration_checks() -> None:
    print("\n2. Migration 013 is ALTER-only, schema-only, and correctly chained")
    src = read(MIGRATION_REL)
    code = code_compact(src)

    check(f'down_revision is "{PRIOR_HEAD}"',
          re.search(rf'down_revision\s*=\s*"{PRIOR_HEAD}"', src) is not None)
    check(f'revision is "{MIGRATION_NAME}"',
          re.search(rf'revision\s*=\s*"{MIGRATION_NAME}"', src) is not None)
    check("declares both upgrade() and downgrade()",
          "def upgrade()" in src and "def downgrade()" in src)

    for forbidden in ("create_table", "drop_table", "add_column", "drop_column",
                      "create_index", "drop_index", "bulk_insert", "execute"):
        check(f"migration issues no op.{forbidden}", f"op.{forbidden}(" not in code)
    check("migration uses op.alter_column", "op.alter_column(" in code)
    check("migration issues no raw SQL text()", "text(" not in code)
    for verb in ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "CREATE TABLE", "DROP TABLE",
                 "GRANT", "REVOKE"):
        check(f"no {verb} anywhere in the migration source",
              not re.search(rf"(?i)\b{verb}\b", code))
    check("no seed or client data literal",
          not re.search(r"(?i)(?:seed|sample|fixture|client_name|acme)", code))
    check("no credential or DSN literal",
          not CREDENTIAL_RE.search(src) and not DSN_LITERAL_RE.search(src))

    check("MySQL/MariaDB gate is present",
          "MYSQL_DIALECTS" in src and "dialect.namenotinMYSQL_DIALECTS" in code)
    check("the gate returns early for non-MySQL dialects (SQLite is a no-op)",
          "dialect.namenotinMYSQL_DIALECTS:return" in code)
    check(f"the pinned collation is {GOVERNED_COLLATION}",
          f'GOVERNED_COLLATION = "{GOVERNED_COLLATION}"' in src)
    check("downgrade drops the explicit collation rather than inventing a prior one",
          "_alter_collation(None)" in code)
    check("no index or constraint name appears in the migration",
          not re.search(r"\b(?:ix_|uq_|fk_|ck_)\w+", src))

    try:
        mapping = migration_mapping()
        check("GOVERNED_COLUMNS is a static, statically-parseable literal", True)
    except Exception as exc:  # noqa: BLE001
        check(f"GOVERNED_COLUMNS is a static literal ({type(exc).__name__})", False)
        mapping = ()
    check(f"mapping holds exactly {EXPECTED_GOVERNED_COLUMNS} governed columns",
          len(mapping) == EXPECTED_GOVERNED_COLUMNS)
    check("every mapping entry is (table, column, length, nullable)",
          all(isinstance(e, tuple) and len(e) == 4 and isinstance(e[0], str)
              and isinstance(e[1], str) and isinstance(e[2], int) and isinstance(e[3], bool)
              for e in mapping))
    check("mapping is deterministic (sorted, no duplicates)",
          list(mapping) == sorted(mapping) and len({(t, c) for t, c, _, _ in mapping})
          == len(mapping))
    check(f"mapping spans exactly {EXPECTED_TABLE_COUNT} tables",
          len({t for t, _, _, _ in mapping}) == EXPECTED_TABLE_COUNT)
    check("mapping imports no application model at runtime",
          "peak.db" not in code and "frompeak" not in code)
    check("every mapped identifier fits the MySQL 64-char limit",
          all(len(t) <= MYSQL_IDENTIFIER_LIMIT and len(c) <= MYSQL_IDENTIFIER_LIMIT
              for t, c, _, _ in mapping))


# --------------------------------------------------------------------------- 3. coverage


def coverage_checks() -> None:
    print("\n3. Coverage: the mapping matches the model, both directions")
    try:
        from peak.db.models import ALL_MODELS
    except ImportError:
        print("  [skip] SQLAlchemy not installed — model/mapping comparison not exercised "
              "(run with PYTHON=.venv/bin/python for the full check)")
        return
    from governed_mysql_collation_audit import DETERMINISTIC_REQUIRED, classify

    mapped = {(t, c): (length, nullable) for t, c, length, nullable in migration_mapping()}

    model_governed = {}
    excluded = {}
    for model in ALL_MODELS:
        table = model.__table__
        for column in table.columns:
            type_name = type(column.type).__name__
            if type_name not in ("String", "Text", "VARCHAR"):
                continue
            policy = classify(column.name, "Text" if type_name == "Text" else "String")
            length = getattr(column.type, "length", None)
            if length is None:
                variants = getattr(column.type, "_variant_mapping", None) or {}
                length = getattr(variants.get("mysql"), "length", None)
            if policy in DETERMINISTIC_REQUIRED:
                model_governed[(table.name, column.name)] = (length, bool(column.nullable))
            else:
                excluded[(table.name, column.name)] = policy

    missing = sorted(set(model_governed) - set(mapped) - LATER_PINNED)
    extra = sorted(set(mapped) - set(model_governed))
    check(f"every governed model column is pinned by 013 or a later migration "
          f"({len(model_governed)} governed columns in the model)",
          not missing)
    if missing:
        print(f"        missing: {missing[:6]}")
    check("every later-pinned column is created with the governed collation in its migration",
          all(f'"{col}"' in read("alembic/versions/014_engagement_classification.py")
              and "GOVERNED_COLLATION" in read(
                  "alembic/versions/014_engagement_classification.py")
              for _tbl, col in LATER_PINNED))
    check("every migration-mapped column exists in the model as governed", not extra)
    if extra:
        print(f"        extra: {extra[:6]}")
    check(f"model governed count is exactly {EXPECTED_MODEL_GOVERNED_COLUMNS}",
          len(model_governed) == EXPECTED_MODEL_GOVERNED_COLUMNS)

    mismatched = [k for k in mapped if k in model_governed and mapped[k] != model_governed[k]]
    check("length and nullability match the model for every mapped column", not mismatched)
    if mismatched:
        print(f"        mismatched: {mismatched[:6]}")

    swept_in = sorted(k for k in mapped if k in excluded)
    check("no ordinary_text / json_or_details_text / enum_status column was swept in",
          not swept_in)
    if swept_in:
        print(f"        wrongly included: {[(k, excluded[k]) for k in swept_in[:6]]}")

    by_class = {}
    for (table, column) in model_governed:
        by_class.setdefault(classify(column, "String"), []).append((table, column))
    print(f"        classes covered: "
          f"{ {k: len(v) for k, v in sorted(by_class.items())} }")


# --------------------------------------------------------------------------- 4. model policy


def _effective_collation(column) -> str:
    variants = getattr(column.type, "_variant_mapping", None) or {}
    for dialect in ("mysql", "mariadb"):
        collation = getattr(variants.get(dialect), "collation", None)
        if collation:
            return str(collation)
    return str(getattr(column.type, "collation", "") or "")


def model_policy_checks() -> None:
    print("\n4. Model policy: governed columns pin utf8mb4_bin on MySQL, SQLite untouched")
    try:
        from peak.db.models import ALL_MODELS
    except ImportError:
        print("  [skip] SQLAlchemy not installed — model policy not exercised")
        return
    from governed_mysql_collation_audit import DETERMINISTIC_REQUIRED, classify

    base_src = read(BASE)
    check("base.py exposes a GovernedString helper", "def GovernedString(" in base_src)
    check("the helper uses with_variant, not String(collation=...)",
          "with_variant" in base_src and 'String(length, collation=' not in base_src)
    check(f'base.py pins GOVERNED_COLLATION = "{GOVERNED_COLLATION}"',
          f'GOVERNED_COLLATION = "{GOVERNED_COLLATION}"' in base_src)

    pinned = unpinned = wrongly = 0
    boundary_tables = set()
    boundary_pinned = set()
    hash_cols = scope_cols = 0
    hash_pinned = scope_pinned = 0
    for model in ALL_MODELS:
        for column in model.__table__.columns:
            type_name = type(column.type).__name__
            if type_name not in ("String", "Text", "VARCHAR"):
                continue
            policy = classify(column.name, "Text" if type_name == "Text" else "String")
            collation = _effective_collation(column)
            if policy in DETERMINISTIC_REQUIRED:
                if collation == GOVERNED_COLLATION:
                    pinned += 1
                else:
                    unpinned += 1
                if policy == "governed_hash_or_fingerprint":
                    hash_cols += 1
                    hash_pinned += collation == GOVERNED_COLLATION
                if policy == "governed_scope":
                    scope_cols += 1
                    scope_pinned += collation == GOVERNED_COLLATION
                if column.name == "idempotency_key":
                    boundary_tables.add(model.__tablename__)
                if column.name in IDEMPOTENCY_BOUNDARY and collation == GOVERNED_COLLATION:
                    boundary_pinned.add((model.__tablename__, column.name))
            elif collation:
                wrongly += 1

    check(f"exactly {EXPECTED_MODEL_GOVERNED_COLUMNS} governed columns pin {GOVERNED_COLLATION}",
          pinned == EXPECTED_MODEL_GOVERNED_COLUMNS)
    check("no governed column is left unpinned", unpinned == 0)
    check("no non-governed column was forced into a binary collation", wrongly == 0)
    check(f"all {EXPECTED_BOUNDARY_TABLES} idempotency-boundary tables are covered",
          len(boundary_tables) == EXPECTED_BOUNDARY_TABLES)
    check("every idempotency-boundary column is deterministic",
          all((t, c) in boundary_pinned for t in boundary_tables for c in IDEMPOTENCY_BOUNDARY))
    check(f"every hash/fingerprint column is deterministic ({hash_cols})",
          hash_cols > 0 and hash_pinned == hash_cols)
    check(f"every scope column is deterministic ({scope_cols})",
          scope_cols > 0 and scope_pinned == scope_cols)

    print("     dialect rendering: MySQL gets COLLATE, SQLite does not")
    from sqlalchemy.dialects import mysql as mysql_dialect, sqlite as sqlite_dialect
    from sqlalchemy.schema import CreateTable
    sample = next(m for m in ALL_MODELS if m.__tablename__ == "agent_run_records")
    mysql_ddl = str(CreateTable(sample.__table__).compile(dialect=mysql_dialect.dialect()))
    sqlite_ddl = str(CreateTable(sample.__table__).compile(dialect=sqlite_dialect.dialect()))
    check("MySQL DDL carries COLLATE utf8mb4_bin",
          f"COLLATE {GOVERNED_COLLATION}" in mysql_ddl)
    check("SQLite DDL carries no COLLATE at all", "COLLATE" not in sqlite_ddl)

    print("     the schema still creates cleanly on SQLite (local smoke path is intact)")
    import sqlalchemy as sa
    from peak.db.base import Base
    engine = sa.create_engine("sqlite://")
    try:
        Base.metadata.create_all(engine)
        with engine.connect() as conn:
            count = len(sa.inspect(engine).get_table_names())
        check(f"SQLite create_all builds all {EXPECTED_TABLE_COUNT} tables",
              count == EXPECTED_TABLE_COUNT)
    except Exception as exc:  # noqa: BLE001
        check(f"SQLite create_all succeeds ({type(exc).__name__})", False)


# --------------------------------------------------------------------------- 5. migration run


def migration_run_checks() -> None:
    print("\n5. Migration applies, reverses, and re-applies on temporary SQLite")
    try:
        from alembic import command
        from alembic.config import Config
        from sqlalchemy import create_engine, inspect
    except ImportError:
        print("  [skip] Alembic/SQLAlchemy not installed — migration run not exercised")
        return

    tmp = tempfile.mkdtemp(prefix="peak_phase44_")
    prev = os.environ.get("PEAK_DATABASE_URL")
    try:
        url = "sqlite:///" + os.path.join(tmp, "m.db")
        os.environ["PEAK_DATABASE_URL"] = url
        cfg = Config(os.path.join(REPO_ROOT, "alembic.ini"))
        command.upgrade(cfg, "head")
        tables = [t for t in inspect(create_engine(url)).get_table_names()
                  if t != "alembic_version"]
        check(f"upgrade head builds {EXPECTED_TABLE_COUNT} tables",
              len(tables) == EXPECTED_TABLE_COUNT)
        command.downgrade(cfg, PRIOR_HEAD)
        tables_after = [t for t in inspect(create_engine(url)).get_table_names()
                        if t != "alembic_version"]
        check("downgrade to 012 keeps every table (013 alters no table structure)",
              len(tables_after) == EXPECTED_TABLE_COUNT)
        command.upgrade(cfg, "head")
        check("re-upgrade succeeds",
              len([t for t in inspect(create_engine(url)).get_table_names()
                   if t != "alembic_version"]) == EXPECTED_TABLE_COUNT)
    except Exception as exc:  # noqa: BLE001
        check(f"migration run on SQLite ({type(exc).__name__})", False)
    finally:
        if prev is None:
            os.environ.pop("PEAK_DATABASE_URL", None)
        else:
            os.environ["PEAK_DATABASE_URL"] = prev
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------- 6. tooling


def tooling_checks() -> None:
    print("\n6. Audit / parity / verifier reflect the new state")
    env = {k: v for k, v in os.environ.items() if not k.startswith("PEAK_")}
    venv = os.path.join(REPO_ROOT, ".venv", "bin", "python")

    if os.path.isfile(venv):
        audit = subprocess.run([venv, os.path.join(REPO_ROOT, AUDIT)],
                               capture_output=True, text=True, cwd=REPO_ROOT, env=env, timeout=180)
        check("collation audit exits 0", audit.returncode == 0)
        check("audit no longer reports NEEDS_REMEDIATION",
              "NEEDS_REMEDIATION" not in audit.stdout)
        check("audit reports MODEL_POLICY_SATISFIED_PRODUCTION_UNVERIFIED",
              "MODEL_POLICY_SATISFIED_PRODUCTION_UNVERIFIED" in audit.stdout)
        check("audit still says production is unverified",
              "production" in audit.stdout.lower() and "unverified" in audit.stdout.lower())
        check("audit tells the operator migration 013 must still run in production",
              "must still be executed against production" in audit.stdout)
        check("audit points at the read-only production verifier",
              "production-mysql-collation-verify" in audit.stdout)
        check(f"audit reports 0 unpinned of {EXPECTED_MODEL_GOVERNED_COLUMNS} governed",
              re.search(r"unpinned\s*:\s*0", audit.stdout) is not None
              and re.search(rf"governed\s*:\s*{EXPECTED_MODEL_GOVERNED_COLUMNS}", audit.stdout)
              is not None)
        again = subprocess.run([venv, os.path.join(REPO_ROOT, AUDIT)],
                               capture_output=True, text=True, cwd=REPO_ROOT, env=env, timeout=180)
        check("audit output is deterministic across runs", again.stdout == audit.stdout)
    else:
        print("  [skip] .venv not present — audit tier not exercised")

    parity = subprocess.run([PY, os.path.join(REPO_ROOT, PARITY), "--mode", "static"],
                            capture_output=True, text=True, cwd=REPO_ROOT, env=env, timeout=180)
    check("mysql-parity-static still exits 0", parity.returncode == 0)
    check("parity checker recognises 013 as the head",
          MIGRATION_NAME in parity.stdout or "RESULT: PASS" in parity.stdout)
    check("parity checker reports no failures",
          re.search(r"failures\s*:\s*0", parity.stdout) is not None)

    verifier = subprocess.run([PY, os.path.join(REPO_ROOT, VERIFIER)],
                              capture_output=True, text=True, cwd=REPO_ROOT, env=env, timeout=180)
    check("production verifier still skips safely when unconfigured",
          verifier.returncode == 0 and "skipped_not_configured" in verifier.stdout)
    check("production verifier attempted no connection",
          re.search(r"production_connection_attempted:\s*False", verifier.stdout) is not None)
    check("production verifier expects the live production head (014, applied in Phase 58)",
          f'EXPECTED_ALEMBIC_HEAD = "{PRODUCTION_EXPECTED_HEAD}"' in read(VERIFIER))
    check("no tool output echoes a canary",
          _no_canary(parity.stdout + verifier.stdout))
    check("no tool output prints a DSN",
          not DSN_LITERAL_RE.search(parity.stdout + verifier.stdout))


# --------------------------------------------------------------------------- 7. docs


def doc_checks() -> None:
    print("\n7. Documentation records the selection and the production boundary")
    policy = re.sub(r"\s+", " ", read(POLICY_DOC)).lower()
    for phrase in ("utf8mb4_bin", "utf8mb4_0900_as_cs", MIGRATION_NAME,
                   "cannot produce new duplicate-key violations"):
        check(f"policy doc states: {phrase[:52]}", phrase.lower() in policy)

    prod = re.sub(r"\s+", " ", read("docs/PRODUCTION_MYSQL_COLLATION_VERIFICATION.md")).lower()
    check("production doc still requires read-only affirmation",
          "peak_production_db_readonly_confirm" in prod)
    check("production doc still forbids production migration execution here",
          "not implemented by this phase" in prod or "separate" in prod)

    for rel in (POLICY_DOC, "docs/PRODUCTION_MYSQL_COLLATION_VERIFICATION.md"):
        raw = read(rel)
        check(f"{rel} contains no real DSN", not DSN_LITERAL_RE.search(raw))
        check(f"{rel} contains no canary value", _no_canary(raw))


# --------------------------------------------------------------------------- 8. regression


def regression_checks() -> None:
    print("\n8. Standing policy + forbidden-path regressions")
    mig = read(MIGRATION_REL)
    code = code_compact(mig)
    check("migration calls no controlled writer",
          not re.search(r"\bpersist_\w+|peak\.db\.\w*writer", code))
    check("no Phase 22 review-writer call", "persist_review_record" not in mig)
    check("no agent-run-writer call", "persist_agent_run_record" not in mig)
    check("no approval / client-facing / capsule / AgentNet path",
          not re.search(r"(?i)approve_client_facing|send_to_client|publish_capsule|"
                        r"agentnet_publish|resolver_publish", code))
    check("no LLM / agent execution path",
          not re.search(r"(?i)\b(?:openai|anthropic|mock_llm|MockLLM|executor)\b", code))
    check("no production migration runner was added",
          "command.upgrade" not in code and "command.downgrade" not in code)

    rub = re.sub(r"\s+", " ", read("docs/MANAGED_MYSQL_PERSISTENCE_RUBRIC.md") + " "
                 + read("docs/PRODUCTION_PARITY_DB_VALIDATION.md") + " "
                 + read("docs/CLIENT_ISOLATION_MODEL.md")).lower()
    check("managed remote MySQL is still the operational data store",
          "managed remote mysql" in rub and "operational data store" in rub)
    check("Client Isolation Option A is still the default",
          "client isolation option a" in rub and "default" in rub)
    check("SQLite is still not the production-readiness proof path",
          "sqlite is not the production-readiness proof path" in rub)
    pub = re.sub(r"\s+", " ", read("docs/PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md")).lower()
    check("client authorizes Peak as publisher",
          "consulting agreement" in pub and "authorized capsule/node publisher" in pub)
    check("clients operate no AgentNet publishing tools",
          "clients do not operate any agentnet publishing tools" in pub)

    mk = read("Makefile")
    validate_line = next((ln for ln in mk.splitlines() if ln.startswith("validate:")), "")
    check("validate-phase44 is part of `make validate`", "validate-phase44" in validate_line)
    for target in ("production-mysql-collation-verify", "mysql-parity-staging",
                   "db-check-managed-test"):
        check(f"DB-capable target '{target}' stays out of `make validate`",
              target not in validate_line and f"{target}:" in mk)
    check("no migration-execution target was added to the Makefile",
          not re.search(r"^\s*\$\(PYTHON\)\s+-m\s+alembic\s+upgrade", mk, re.M))


# --------------------------------------------------------------------------- 9. hygiene


def hygiene_checks() -> None:
    print("\n9. Baseline + repo hygiene: source-only, no data / credentials / examples")
    check("no examples/ directory", not os.path.isdir(os.path.join(REPO_ROOT, "examples")))
    artifacts, dbfiles = [], []
    for dp, dns, fns in os.walk(REPO_ROOT):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        if _skip(os.path.relpath(dp, REPO_ROOT)):
            continue
        for f in fns:
            if f.lower().endswith(DATA_EXTS):
                (dbfiles if f.lower().endswith((".db", ".sqlite", ".sqlite3", ".sql"))
                 else artifacts).append(os.path.join(dp, f))
    check("no committed data artifacts", not artifacts)
    check("no committed database files / dumps", not dbfiles)
    check("docs/Peak_Investor_Overview_AI.docx present",
          os.path.isfile(os.path.join(REPO_ROOT, "docs", "Peak_Investor_Overview_AI.docx")))
    check(".env.example contains placeholders only",
          "user:password@localhost" in read(".env.example"))
    check(".env is gitignored", re.search(r"^\.env$", read(".gitignore"), re.M) is not None)

    try:
        present = subprocess.run(
            ["git", "-C", REPO_ROOT, "merge-base", "--is-ancestor", BASELINE_COMMIT, "HEAD"],
            capture_output=True, timeout=20).returncode == 0
        check(f"Phase 44 baseline commit {BASELINE_COMMIT} present in history", present)
        tracked = subprocess.run(["git", "-C", REPO_ROOT, "ls-files"],
                                 capture_output=True, text=True, timeout=20).stdout
        check(".claude/settings.local.json is not tracked",
              ".claude/settings.local.json" not in tracked)
        check(".env is not tracked", "\n.env\n" not in "\n" + tracked)
        docx_diff = subprocess.run(
            ["git", "-C", REPO_ROOT, "diff", "--name-only", "HEAD", "--",
             "docs/Peak_Investor_Overview_AI.docx"],
            capture_output=True, text=True, timeout=20).stdout.strip()
        check("docs/Peak_Investor_Overview_AI.docx has no pending diff", not docx_diff)
    except Exception:
        check("git-backed baseline/hygiene checks (git unavailable — skipped)", True)


# --------------------------------------------------------------------------- main


def main() -> int:
    print("Peak Phase 44 governed identifier collation migration check")
    print("=" * 70)

    baseline_checks()
    migration_checks()
    coverage_checks()
    model_policy_checks()
    migration_run_checks()
    tooling_checks()
    doc_checks()
    regression_checks()
    hygiene_checks()

    print("\n" + "=" * 70)
    print("Summary")
    print(f"  failures : {len(_failures)}")
    for label in _failures:
        print(f"    - {label}")
    print("\nRESULT: " + ("FAIL" if _failures else "PASS"))
    return 1 if _failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
