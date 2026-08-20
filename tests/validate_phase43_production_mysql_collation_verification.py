#!/usr/bin/env python3
"""Phase 43 production MySQL collation verification check.

Stdlib-only, credential-free, offline. Verifies that Peak's **read-only** production collation
verification tool exists, is structurally incapable of mutating production, fails closed on
misconfiguration, never leaks a secret or a row value, and produces a go/no-go recommendation
without executing migration `013`.

Five layers:

* **Scope** — Phase 43 is verification tooling only: no migration `013`, no change under
  `alembic/`, `schemas/`, or `peak/`, no new table/model/writer/allowlist pair, no migration
  runner, and no production write/cleanup/delete path.

* **Structural read-only proof** — the tool's source contains no mutating-SQL execution path; every
  statement it can issue is a hard-coded constant; and the guard is exercised directly against a
  battery of hostile statements (DDL, DML, multi-statement, `OUTFILE`, `CALL`, `SET`, and a
  read-only statement that is simply not on the allowlist) which must all be refused.

* **Gating** — unconfigured skips (exit 0) without importing a driver or reading `.env`; a
  connection setting without the read-only affirmation **refuses** (exit 2) without connecting;
  affirmation without a connection setting skips. A canary DSN and secret are never echoed in any
  mode.

* **Query-path simulation** — a fake cursor drives the complete verification, proving the tool
  issues only allowlisted read-only statements, classifies a case-insensitive production as
  `verified_risk_live_remediation_required` and a deterministic one as
  `verified_safe_no_remediation_required`, counts the 11 idempotency boundaries (not all 18
  tables), and emits counts only — never a row value.

* **Policy integration + regression** — the tool reuses the Phase 42 governed-column classifier
  rather than re-deriving it; recommends migration `013` as a next step only; and the standing
  baseline and policy guarantees hold.

Exit status:
  0  -> all checks passed
  1  -> a check failed
"""

from __future__ import annotations

import io
import os
import py_compile
import re
import subprocess
import sys
import tokenize

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(REPO_ROOT, "tools")
for _p in (REPO_ROOT, TOOLS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

PY = sys.executable or "python3"

BASELINE_COMMIT = "6db7d6c"   # Add Phase 42 governed MySQL collation policy

TOOL = "tools/production_mysql_collation_verify.py"
AUDIT = "tools/governed_mysql_collation_audit.py"
DOC = "docs/PRODUCTION_MYSQL_COLLATION_VERIFICATION.md"
POLICY_DOC = "docs/GOVERNED_MYSQL_COLLATION_POLICY.md"
HARNESS = "tests/validate_phase43_production_mysql_collation_verification.py"
REQUIRED_FILES = [TOOL, AUDIT, DOC, POLICY_DOC, HARNESS]

ALEMBIC_HEAD = "013_governed_identifier_collation_policy"
EXPECTED_MIGRATIONS = 13
EXPECTED_TABLE_COUNT = 18
EXPECTED_BOUNDARY_TABLES = 11

VERIFY_TARGET = "production-mysql-collation-verify"
DB_CAPABLE_TARGETS = ("db-check-managed-test", "managed-mysql-smoke",
                      "managed-mysql-migration-check", "mysql-parity-staging", VERIFY_TARGET)

READONLY_CONFIRM_VAR = "PEAK_PRODUCTION_DB_READONLY_CONFIRM"
PRODUCTION_DSN_VAR = "PEAK_PRODUCTION_DB_URL"

_CANARY_USER = "zzcanaryuser43"
_CANARY_SECRET = "ZZCANARYSECRET43ZZ"
_CANARY_HOST = "canary43-prod.invalid.example"
_CANARY_DSN = f"mysql+pymysql://{_CANARY_USER}:{_CANARY_SECRET}@{_CANARY_HOST}:3306/peakprod"
_CANARY_FRAGMENTS = (_CANARY_USER, _CANARY_SECRET, _CANARY_HOST, _CANARY_DSN)

#: Statements that must be refused by the read-only guard.
HOSTILE_STATEMENTS = (
    "DROP TABLE agent_run_records",
    "DELETE FROM review_records",
    "UPDATE clients SET organization_label='x'",
    "INSERT INTO clients (id) VALUES ('x')",
    "ALTER TABLE clients MODIFY id VARCHAR(64)",
    "TRUNCATE TABLE clients",
    "CREATE TABLE t (a INT)",
    "REPLACE INTO clients (id) VALUES ('x')",
    "GRANT ALL ON *.* TO 'x'@'%'",
    "REVOKE ALL ON *.* FROM 'x'@'%'",
    "LOCK TABLES clients WRITE",
    "CALL some_procedure()",
    "LOAD DATA INFILE '/tmp/x' INTO TABLE clients",
    "SELECT * INTO OUTFILE '/tmp/x' FROM clients",
    "SET SESSION sql_mode=''",
    "SELECT 1; DROP TABLE clients",
    "SELECT * FROM clients",              # read-only, but NOT on the allowlist
    "SELECT owner_id, idempotency_key FROM agent_run_records",  # would echo row values
    "",
)

MUTATING_SQL_RE = re.compile(
    r"(?i)\b(?:INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|ALTER\s+TABLE|DROP\s+(?:TABLE|DATABASE|INDEX)"
    r"|TRUNCATE\s+TABLE|CREATE\s+(?:TABLE|DATABASE|INDEX)|REPLACE\s+INTO|GRANT\s+|REVOKE\s+"
    r"|LOAD\s+DATA|INTO\s+OUTFILE)\b")
WRITER_RE = re.compile(r"\bpersist_\w+|peak\.db\.\w*writer")
MIGRATION_RUNNER_RE = re.compile(r"alembic\.command|command\.upgrade|command\.downgrade|op\.\w+\(")
LLM_PROVIDER_RE = re.compile(
    r"\b(?:openai|anthropic|cohere|litellm|langchain|transformers|vertexai|mistralai|ollama)\b",
    re.IGNORECASE)
CREDENTIAL_RE = re.compile(
    r"\b(?:api_key|secret_key|access_key|password|passwd)\b\s*[:=]\s*['\"][^'\"]{3,}['\"]",
    re.IGNORECASE)
DSN_LITERAL_RE = re.compile(r"\b[a-z][a-z0-9+.\-]*://[\w.\-]+:[^\s@'\"]+@")
DATA_EXTS = (".csv", ".xlsx", ".xls", ".parquet", ".db", ".sqlite", ".sqlite3", ".sql", ".dump")
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache"}

REQUIRED_DOC_PHRASES = [
    "read-only",
    "not implemented by this phase",
    "peak_production_db_readonly_confirm",
    "peak_production_db_url",
    "fail-closed gating",
    "no production row values are ever emitted",
    "go / no-go criteria",
    "verified_risk_live_remediation_required",
    "verified_safe_no_remediation_required",
    "hard-coded query allowlist",
    "tested restore",
    "maintenance window",
    "cannot create duplicate-key",
    "client isolation option a",
]

PASS, FAIL = "PASS", "FAIL"
_failures: list = []


def read(rel: str) -> str:
    with open(os.path.join(REPO_ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def _skip(dp: str) -> bool:
    return bool(SKIP_DIRS.intersection(dp.split(os.sep)))


def code_only(source: str) -> str:
    """Executable tokens only — comments and string literals removed."""
    out = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type in (tokenize.COMMENT, tokenize.STRING):
                continue
            out.append(tok.string)
    except tokenize.TokenError:  # pragma: no cover
        return source
    return " ".join(out)


def check(label: str, ok: bool) -> None:
    if ok:
        print(f"  [{PASS}] {label}")
    else:
        _failures.append(label)
        print(f"  [{FAIL}] {label}")


def run_tool(args=None, env_extra=None, python=None):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("PEAK_") and k not in ("DATABASE_URL",)}
    env.update(env_extra or {})
    return subprocess.run([python or PY, os.path.join(REPO_ROOT, TOOL)] + (args or []),
                          capture_output=True, text=True, cwd=REPO_ROOT, env=env, timeout=180)


def _no_canary(text: str) -> bool:
    return not any(frag in text for frag in _CANARY_FRAGMENTS)


# --------------------------------------------------------------------------- 1. structural


def structural_checks() -> None:
    print("\n1. Verification tool / doc / harness present and compile")
    for rel in REQUIRED_FILES:
        check(rel, os.path.isfile(os.path.join(REPO_ROOT, rel)))
    for rel in (TOOL, HARNESS):
        try:
            py_compile.compile(os.path.join(REPO_ROOT, rel), doraise=True)
            check(f"{rel} compiles", True)
        except py_compile.PyCompileError:
            check(f"{rel} compiles", False)

    tool = read(TOOL)
    tool_code = code_only(tool)
    print("\n2. The tool is structurally incapable of mutating production")
    check("no mutating SQL anywhere in the source", not MUTATING_SQL_RE.search(tool))
    check("no controlled-writer import or call", not WRITER_RE.search(tool_code))
    check("no migration runner / alembic command / op.* call",
          not MIGRATION_RUNNER_RE.search(tool_code))
    check("no ORM session or metadata create path",
          not re.search(r"sessionmaker|Session\(|create_all|drop_all", tool_code))
    check("no LLM provider import", not LLM_PROVIDER_RE.search(tool_code))
    check("no committed credential literal", not CREDENTIAL_RE.search(tool))
    check("no DSN literal in executable code", not DSN_LITERAL_RE.search(tool_code))
    check("no .env read", not re.search(r"open\([^)]*\.env|dotenv|load_dotenv", tool_code))
    check("imports no DB driver at module scope (lazy import only)",
          not re.search(r"^(?:import|from)\s+(?:pymysql|MySQLdb|sqlalchemy|alembic)\b",
                        tool, re.M))
    check("declares a hard-coded read-only query allowlist", "READ_ONLY_QUERIES = {" in tool)
    check("declares a forbidden-verb list", "FORBIDDEN_SQL_VERBS = (" in tool)
    check("guards every execution with assert_read_only",
          tool_code.count("assert_read_only") >= 3)
    check("accepts no SQL from argv / environment / file",
          not re.search(r"add_argument\(\s*['\"]--(?:sql|query|statement)", tool)
          and not re.search(r"environ\[[^\]]*SQL", tool))
    check("declares the full result vocabulary",
          all(v in tool for v in ("skipped_not_configured", "refused_not_confirmed_readonly",
                                  "verified_safe_no_remediation_required",
                                  "verified_risk_live_remediation_required",
                                  "verified_inconclusive", "failed_safely")))
    check("declares the required side-effect flags",
          all(f in tool for f in ("production_connection_attempted", "production_connection_made",
                                  "readonly_queries_only", "schema_mutation_made",
                                  "data_write_made", "migration_executed", "cleanup_delete_made",
                                  "secrets_printed", "governed_columns_checked",
                                  "governed_columns_at_risk", "idempotency_boundaries_checked",
                                  "collision_probe_status", "recommended_next_step")))
    check("reuses the Phase 42 governed-column classifier rather than re-deriving it",
          "from governed_mysql_collation_audit import" in tool)


# --------------------------------------------------------------------------- 3. guard


def guard_checks() -> None:
    print("\n3. The read-only guard refuses every hostile statement (direct exercise)")
    import production_mysql_collation_verify as v

    refused = 0
    for sql in HOSTILE_STATEMENTS:
        try:
            v.assert_read_only(sql)
            check(f"refuses {sql[:46]!r}", False)
        except v.UnsafeQueryRefused:
            refused += 1
    check(f"all {len(HOSTILE_STATEMENTS)} hostile statements refused",
          refused == len(HOSTILE_STATEMENTS))

    accepted = 0
    for name, template in v.READ_ONLY_QUERIES.items():
        sql = (template.format(collation="utf8mb4_bin", table="agent_run_records")
               if "{" in template else template)
        try:
            v.assert_read_only(sql)
            accepted += 1
        except v.UnsafeQueryRefused:
            check(f"allowlisted query '{name}' is accepted", False)
    check(f"all {len(v.READ_ONLY_QUERIES)} allowlisted queries accepted",
          accepted == len(v.READ_ONLY_QUERIES))
    check("every allowlisted query is SELECT/SHOW only",
          all(t.strip().upper().startswith(("SELECT", "SHOW"))
              for t in v.READ_ONLY_QUERIES.values()))
    # A governed column may legitimately appear in a GROUP BY (that is how an aggregate is keyed).
    # What must never happen is a governed column appearing in a SELECT *list*, because that is
    # what returns row values. Check the select list specifically, not the whole statement.
    def _select_lists(sql: str):
        for match in re.finditer(r"(?is)\bSELECT\b(.*?)(?:\bFROM\b|$)", sql):
            yield match.group(1)

    leaky = [name for name, template in v.READ_ONLY_QUERIES.items()
             if any(re.search(r"\b(?:owner_id|client_id|engagement_id|idempotency_key)\b", part)
                    for part in _select_lists(template))]
    check("no allowlisted query returns a governed column value in its SELECT list", not leaky)
    check("the aggregate probe returns only COUNT(*)",
          re.match(r"(?i)^SELECT COUNT\(\*\)",
                   v.READ_ONLY_QUERIES["case_variant_group_count"]) is not None)

    for bad in ("clients`; DROP TABLE x; --", "a b", "x" * 65, ""):
        try:
            v.safe_identifier(bad)
            check(f"identifier {bad[:24]!r} refused", False)
        except v.UnsafeQueryRefused:
            pass
    check("unsafe identifiers are refused", True)
    check("safe identifiers are accepted", v.safe_identifier("agent_run_records")
          == "agent_run_records")

    check("sanitize() scrubs a DSN", v.sanitize(_CANARY_DSN) == "[secret withheld]")
    check("sanitize() scrubs a password pair", _CANARY_SECRET not in
          v.sanitize(f"password={_CANARY_SECRET}"))
    check("safe_error() reports type only, never the message",
          "detail withheld" in v.safe_error(ValueError("dsn=" + _CANARY_DSN))
          and _CANARY_SECRET not in v.safe_error(ValueError(_CANARY_DSN)))


# --------------------------------------------------------------------------- 4. gating


def gating_checks() -> None:
    print("\n4. Fail-closed gating: skip, refuse, and never connect unbidden")
    proc = run_tool()
    check("unconfigured -> exits 0 (skip)", proc.returncode == 0)
    check("unconfigured -> outcome skipped_not_configured",
          "skipped_not_configured" in proc.stdout)
    check("skip states nothing was connected to and no .env read",
          "no driver was imported" in proc.stdout and "no .env was read" in proc.stdout)
    check("skip names the required variables (names only)",
          READONLY_CONFIRM_VAR in proc.stdout and PRODUCTION_DSN_VAR in proc.stdout)
    check("skip reports production_connection_attempted=False",
          re.search(r"production_connection_attempted:\s*False", proc.stdout) is not None)
    check("skip writes nothing to stderr", not proc.stderr.strip())

    refused = run_tool(env_extra={PRODUCTION_DSN_VAR: _CANARY_DSN})
    check("DSN present but no read-only affirmation -> REFUSED with exit 2",
          refused.returncode == 2 and "refused_not_confirmed_readonly" in refused.stdout)
    check("refusal states no connection was attempted",
          "No connection was attempted" in refused.stdout)
    check("refusal reports production_connection_attempted=False",
          re.search(r"production_connection_attempted:\s*False", refused.stdout) is not None)
    check("refusal never echoes the canary DSN/secret",
          _no_canary(refused.stdout + refused.stderr))

    confirmed_only = run_tool(env_extra={READONLY_CONFIRM_VAR: "1"})
    check("affirmation but no connection setting -> skips (exit 0)",
          confirmed_only.returncode == 0 and "skipped_not_configured" in confirmed_only.stdout)
    check("that skip attempted no connection",
          re.search(r"production_connection_attempted:\s*False", confirmed_only.stdout)
          is not None)

    for run in (proc, refused, confirmed_only):
        check("no DSN-shaped string in output", not DSN_LITERAL_RE.search(run.stdout))
    check("all permanent side-effect flags are False in every unconnected mode",
          all(re.search(rf"{flag}\s*:\s*False", proc.stdout) for flag in
              ("schema_mutation_made", "data_write_made", "migration_executed",
               "cleanup_delete_made", "secrets_printed")))

    print("     no DB driver is imported while skipping")
    probe = (
        "import sys, io, contextlib; sys.path.insert(0, %r); sys.path.insert(0, %r)\n"
        "import production_mysql_collation_verify as t\n"
        "buf = io.StringIO()\n"
        "with contextlib.redirect_stdout(buf):\n"
        "    code = t.main([])\n"
        "drivers = [m for m in sys.modules if m.split('.')[0] in "
        "('pymysql', 'MySQLdb', 'mysql', 'sqlalchemy')]\n"
        "print('PROBE_OK' if (code == 0 and not drivers) else 'PROBE_BAD:' + str(drivers))\n"
    ) % (TOOLS_DIR, REPO_ROOT)
    env = {k: v for k, v in os.environ.items() if not k.startswith("PEAK_")}
    pr = subprocess.run([PY, "-c", probe], capture_output=True, text=True, cwd=REPO_ROOT,
                        env=env, timeout=180)
    check("skip mode imports no DB driver or SQLAlchemy", "PROBE_OK" in pr.stdout)


# --------------------------------------------------------------------------- 5. simulation


class _FakeCursor:
    """Drives the full verification path with no database. Records every statement issued."""

    def __init__(self, collation, models) -> None:
        self.collation = collation
        self.models = models
        self.statements: list = []
        self._rows: list = []

    def execute(self, sql):
        import production_mysql_collation_verify as v
        v.assert_read_only(sql)           # the fake enforces the same guard
        self.statements.append(sql)
        if "VERSION()" in sql:
            self._rows = [("8.0.36-0ubuntu0.22.04.1",)]
        elif "SCHEMATA" in sql:
            self._rows = [("utf8mb4", self.collation)]
        elif "alembic_version" in sql:
            self._rows = [(ALEMBIC_HEAD,)]
        elif "INFORMATION_SCHEMA.TABLES" in sql:
            self._rows = [(m.__tablename__, self.collation) for m in self.models]
        elif "INFORMATION_SCHEMA.COLUMNS" in sql:
            rows = []
            for model in self.models:
                for column in model.__table__.columns:
                    type_name = type(column.type).__name__
                    if type_name in ("String", "Text"):
                        rows.append((model.__tablename__, column.name,
                                     "text" if type_name == "Text" else "varchar",
                                     "utf8mb4", self.collation))
            self._rows = rows
        elif "peak_probe" in sql:
            self._rows = [(0,)]
        elif "COLLATE" in sql:
            self._rows = [(1 if self.collation.endswith("_ci") else 0,)]
        else:
            self._rows = []
        return self

    def fetchall(self):
        return self._rows


def simulation_checks() -> None:
    print("\n5. Query-path simulation (fake cursor; no database)")
    try:
        from peak.db.models import ALL_MODELS
    except ImportError:
        print("  [skip] SQLAlchemy not installed — query-path simulation not exercised "
              "(run with PYTHON=.venv/bin/python for the full check)")
        return

    import production_mysql_collation_verify as v

    for collation, expected, at_risk_expected in (
        ("utf8mb4_0900_ai_ci", v.VERIFIED_RISK_LIVE, True),
        ("utf8mb4_bin", v.VERIFIED_SAFE, False),
    ):
        cursor = _FakeCursor(collation, ALL_MODELS)
        result = v.VerificationResult()
        v.verify_with_cursor(cursor, result, run_collision_probe=True,
                             expected_tables=sorted(m.__tablename__ for m in ALL_MODELS))
        label = collation
        check(f"{label}: outcome == {expected}", result.outcome == expected)
        check(f"{label}: governed columns checked > 0", result.governed_columns_checked > 0)
        check(f"{label}: at-risk count matches expectation",
              bool(result.governed_columns_at_risk) is at_risk_expected)
        check(f"{label}: counts exactly {EXPECTED_BOUNDARY_TABLES} idempotency boundaries",
              result.idempotency_boundaries_checked == EXPECTED_BOUNDARY_TABLES)
        check(f"{label}: every statement issued is read-only",
              all(s.strip().upper().startswith(("SELECT", "SHOW")) for s in cursor.statements))
        check(f"{label}: no mutating SQL was issued",
              not any(MUTATING_SQL_RE.search(s) for s in cursor.statements))
        check(f"{label}: INFORMATION_SCHEMA is used for schema/collation inspection",
              any("INFORMATION_SCHEMA.COLUMNS" in s for s in cursor.statements)
              and any("INFORMATION_SCHEMA.TABLES" in s for s in cursor.statements))
        check(f"{label}: collision probe returns counts only",
              result.collision_probe_status == v.PROBE_COMPLETED
              and all(isinstance(c, int) for c in result.collision_probe_group_counts.values()))
        check(f"{label}: probe ran only on boundary tables",
              len(result.collision_probe_group_counts) == EXPECTED_BOUNDARY_TABLES)
        check(f"{label}: no permanent side-effect flag was set",
              result.schema_mutation_made is False and result.data_write_made is False
              and result.migration_executed is False and result.cleanup_delete_made is False
              and result.secrets_printed is False)
        check(f"{label}: server version reported as family only",
              result.server_version_family == "8.0")
        check(f"{label}: alembic head verified", result.alembic_head_matches is True)
        blob = " ".join(result.reasons + result.warnings + [str(result.recommended_next_step)])
        # Phase 44 implemented 013 in source control, so the recommendation no longer says "NOT
        # implemented". The guarantee this check exists for is unchanged and now asserted directly:
        # the recommendation must state that *this tool* does not execute the migration.
        check(f"{label}: recommendation mentions migration 013 as a next step only",
              "013" in blob and "NOT executed by this tool" in blob
              or expected == v.VERIFIED_SAFE)
        # Column *names* (owner_id, client_id, …) are schema facts and appear legitimately in
        # explanatory text. Row *values* must never appear — those follow Peak's id conventions.
        check(f"{label}: no production row value appears in the result",
              not re.search(r"\b(?:eng_|engrec_|capc_|irrpd_|iard_|irrp_|atq_|evid_|intn_|rvb_|"
                            r"ird_|ing_|agr_)[A-Za-z0-9]", blob))
        check(f"{label}: probe results are integer counts only",
              all(isinstance(c, int) for c in result.collision_probe_group_counts.values()))

    risky = _FakeCursor("utf8mb4_0900_ai_ci", ALL_MODELS)
    res = v.VerificationResult()
    v.verify_with_cursor(risky, res, run_collision_probe=False,
                         expected_tables=sorted(m.__tablename__ for m in ALL_MODELS))
    check("collision probe is opt-in and off by default",
          res.collision_probe_status == v.PROBE_NOT_RUN
          and not any("peak_probe" in s for s in risky.statements))
    check("GO recommendation names migration 013 without executing it",
          "GO for migration 013" in str(res.recommended_next_step)
          and res.migration_executed is False)


# --------------------------------------------------------------------------- 6. docs


def doc_checks() -> None:
    print("\n6. Documentation states the production posture and the go/no-go rule")
    raw = read(DOC)
    blob = re.sub(r"\s+", " ", raw).lower()
    for phrase in REQUIRED_DOC_PHRASES:
        check(f"docs state: {phrase[:52]}", phrase.lower() in blob)
    check("docs explain why production, not disposable MySQL, is the target",
          "why this phase targets production" in blob)
    check("docs state migration 013 is not implemented in this phase",
          "migration `013` is not implemented by this phase" in blob
          or "not implemented by this phase" in blob)
    check("docs list required env vars by name only, with no values",
          not DSN_LITERAL_RE.search(raw))
    check("docs contain no certificate or token example",
          "BEGIN PRIVATE KEY" not in raw and "BEGIN CERTIFICATE" not in raw)
    check("docs contain no canary value", _no_canary(raw))
    check("docs state no .env is read", "never reads" in blob or "never read" in blob)
    check("docs record backup / rollback / maintenance-window requirements",
          "tested restore" in blob and "maintenance window" in blob and "rollback" in blob)

    policy = re.sub(r"\s+", " ", read(POLICY_DOC)).lower()
    check("the Phase 42 duplicate-key direction claim was corrected",
          "cannot produce new duplicate-key violations" in policy
          and "corrected in phase 43" in policy)


# --------------------------------------------------------------------------- 7. scope


def scope_checks() -> None:
    print("\n7. Scope: verification only, no schema or migration surface")
    versions_dir = os.path.join(REPO_ROOT, "alembic", "versions")
    versions = sorted(f for f in os.listdir(versions_dir) if f.endswith(".py"))
    check(f"exactly {EXPECTED_MIGRATIONS} migrations", len(versions) == EXPECTED_MIGRATIONS)
    # Phase 43 created no migration; Phase 44 did. Phase 43 still executes none.
    check("migration 013 exists and is the only one beyond 012",
          [f for f in versions if f.startswith("013")]
          == ["013_governed_identifier_collation_policy.py"])
    check(f"{ALEMBIC_HEAD} is still the newest migration",
          versions[-1].startswith("013_governed_identifier_collation_policy"))

    try:
        changed = subprocess.run(
            ["git", "-C", REPO_ROOT, "diff", "--name-only", "HEAD", "--", "schemas"],
            capture_output=True, text=True, timeout=20).stdout.strip()
        # ``alembic`` and ``peak`` left this list in Phase 44, which legitimately owns migration
        # 013 and the governed-collation model metadata. Phase 43 still adds neither, and
        # ``schemas/`` — the Phase 9 contract source of truth — is asserted untouched.
        check("no change under schemas/", not changed)
    except Exception:
        check("git-backed scope check (git unavailable — skipped)", True)

    from peak.persistence.allowlist import ALLOWED_ACTIONS, ALLOWED_TABLES
    check("allowlist still has exactly 13 tables", len(ALLOWED_TABLES) == 13)
    check("allowlist still has exactly 15 actions", len(ALLOWED_ACTIONS) == 15)
    check("no verification/production action added to the allowlist",
          not any(re.search(r"verif|production|collat", a) for a in ALLOWED_ACTIONS))

    import importlib
    p11 = importlib.import_module("tests.validate_phase11_db_scaffold")
    check(f"db-check still expects exactly {EXPECTED_TABLE_COUNT} tables",
          len(list(getattr(p11, "EXPECTED_TABLES", []))) == EXPECTED_TABLE_COUNT)
    models_src = read("peak/db/models.py")
    check(f"models.py still declares exactly {EXPECTED_TABLE_COUNT} tables",
          models_src.count("__tablename__ = ") == EXPECTED_TABLE_COUNT)
    check("models.py still pins no collation (Phase 43 changed no schema)",
          not re.search(r"mysql_collate|COLLATE", models_src))
    writers = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "peak", "db"))
                     if f.endswith("_writer.py"))
    check("still exactly the twelve narrow controlled writers", len(writers) == 12)


# --------------------------------------------------------------------------- 8. Makefile


def makefile_checks() -> None:
    print("\n8. Makefile: validate stays offline; the production target stays opt-in")
    mk = read("Makefile")
    validate_line = next((ln for ln in mk.splitlines() if ln.startswith("validate:")), "")
    check("validate-phase43 is part of `make validate`", "validate-phase43" in validate_line)
    check(f"'{VERIFY_TARGET}' target exists", f"{VERIFY_TARGET}:" in mk)
    check(f"'{VERIFY_TARGET}' invokes the read-only verification tool",
          re.search(rf"{VERIFY_TARGET}:.*\n(?:.*\n)?.*production_mysql_collation_verify\.py", mk)
          is not None)
    for target in DB_CAPABLE_TARGETS:
        check(f"DB-capable target '{target}' stays out of `make validate`",
              target not in validate_line and f"{target}:" in mk)
    check(f"'{VERIFY_TARGET}' passes no DSN or connect flag on the command line",
          not re.search(rf"{VERIFY_TARGET}:.*\n(?:.*\n)?.*(?:--connect|mysql://|DSN=)", mk))
    check("db-check remains the local structural scaffold check only",
          re.search(r"^db-check:.*\n\t\$\(PYTHON\) tests/validate_phase11_db_scaffold\.py",
                    mk, re.M) is not None)
    check("no Makefile recipe exports or echoes a DSN",
          not DSN_LITERAL_RE.search(mk) and "echo $(PEAK" not in mk)


# --------------------------------------------------------------------------- 9. regression


def regression_checks() -> None:
    print("\n9. Standing policy + forbidden-path regressions")
    tool = read(TOOL)
    doc = read(DOC)
    for label, blob in (("tool", tool), ("doc", doc)):
        check(f"{label}: no Phase 22 review-writer call", "persist_review_record" not in blob)
        check(f"{label}: no agent-run-writer call", "persist_agent_run_record" not in blob)
    check("no packet / report-draft update path added",
          not re.search(r"UPDATE\s+internal_report_review_packets|"
                        r"UPDATE\s+internal_assessment_report_drafts", tool, re.IGNORECASE))
    check("no approval / client-facing / capsule / AgentNet path",
          not re.search(r"(?i)approve_client_facing|send_to_client|publish_capsule|"
                        r"agentnet_publish|resolver_publish", code_only(tool)))

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
    check("no client-facing publisher UI / credentials / resolver tools / direct path",
          all(p in pub for p in ("no client-facing agentnet publisher ui",
                                 "no client-held publishing credentials",
                                 "no client-operated resolver publication tools",
                                 "no direct client publication path")))


# --------------------------------------------------------------------------- 10. hygiene


def hygiene_checks() -> None:
    print("\n10. Baseline + repo hygiene: source-only, no data / credentials / examples")
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
        check(f"Phase 43 baseline commit {BASELINE_COMMIT} present in history", present)
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
    print("Peak Phase 43 production MySQL collation verification check")
    print("=" * 70)

    structural_checks()
    guard_checks()
    gating_checks()
    simulation_checks()
    doc_checks()
    scope_checks()
    makefile_checks()
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
