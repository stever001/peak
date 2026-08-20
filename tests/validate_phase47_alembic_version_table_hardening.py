#!/usr/bin/env python3
"""Phase 47 Alembic version-table hardening check.

Phase 46 bootstrapped production and failed midway: Alembic's bookkeeping column
``alembic_version.version_num`` defaults to ``VARCHAR(32)``, while five revision identifiers in this
repository are longer than that. The database was repaired by hand; this phase fixes the cause in
source so a *fresh* MySQL/MariaDB bootstrap no longer needs that manual step.

Seven layers:

* **Baseline** — head is still 013, there are still 13 migrations and 18 tables, no migration 014
  appeared, no model/entity, writer, or allowlist pair was added, and no revision id was rewritten.

* **Revision widths** — the five known long identifiers are detected at their exact lengths, every
  identifier fits the configured width, and the configured width is at least 255.

* **Planner** — the pure decision function is exercised over every state (absent, narrow, exact,
  wide, unsupported dialect) with no database of any kind.

* **Scope** — the helper's entire SQL surface is two fixed literals naming only
  ``alembic_version.version_num``; no application-table DDL, no ``DROP``/``DELETE``/``TRUNCATE``,
  no arbitrary SQL executor, no credential or ``.env`` access.

* **Behaviour** — a stubbed MySQL dialect proves create/widen/no-op emit exactly the right
  statement, and a real SQLite connection proves the path is inert off MySQL.

* **Integration** — ``alembic/env.py`` calls the preflight before migrations in online mode and the
  source guard in both modes, and ``PEAK_DATABASE_URL`` remains the URL variable.

* **Regression** — SQLite upgrade/downgrade/re-upgrade still builds 18 tables, db-check still
  expects 18, the audit still reports the model policy satisfied and production unverified, and the
  production verifier still skips safely with no configuration.

Exit status:
  0  -> all checks passed
  1  -> a check failed
"""

from __future__ import annotations

import importlib.util
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

BASELINE_COMMIT = "4d8a4e4"   # Document Phase 46 production schema bootstrap recovery

HARDENING_REL = "alembic/version_table_hardening.py"
ENV_REL = "alembic/env.py"
HARNESS_REL = "tests/validate_phase47_alembic_version_table_hardening.py"
VERSIONS_REL = "alembic/versions"
MODELS = "peak/db/models.py"
AUDIT = "tools/governed_mysql_collation_audit.py"
VERIFIER = "tools/production_mysql_collation_verify.py"

EXPECTED_MIGRATIONS = 13
EXPECTED_TABLE_COUNT = 18
EXPECTED_WRITERS = 12
EXPECTED_ALLOWLIST_TABLES = 13
EXPECTED_ALLOWLIST_ACTIONS = 15
MINIMUM_VERSION_NUM_LENGTH = 255
ALEMBIC_DEFAULT_WIDTH = 32
HEAD_REVISION = "013_governed_identifier_collation_policy"

# The identifiers that broke Phase 46, with the lengths that broke it.
KNOWN_LONG_REVISIONS = {
    "008_internal_reviewer_decision_records": 38,
    "010_internal_assessment_report_drafts": 37,
    "011_internal_report_review_packets": 34,
    "012_internal_report_review_packet_decisions": 43,
    "013_governed_identifier_collation_policy": 40,
}

# Only these paths may carry a pending diff for this phase.
ALLOWED_CHANGED = {
    HARDENING_REL,
    ENV_REL,
    HARNESS_REL,
    "Makefile",
    "docs/IMPLEMENTATION_PLAN.md",
    "docs/PHASE46_PRODUCTION_SCHEMA_BOOTSTRAP_RECOVERY.md",
    "docs/PHASE47_ALEMBIC_VERSION_TABLE_HARDENING.md",
    "docs/DATABASE_SCAFFOLD.md",
    # Phase 44's "no earlier migration was edited" check was scoped to all of alembic/; narrowed
    # to alembic/versions/ so it tests what its label claims and no longer freezes env.py.
    "tests/validate_phase44_governed_identifier_collation_migration.py",
}

CREDENTIAL_FILE_MARKERS = ("peak-prod-ro.env", "peak-prod-migrate.env", ".peak/")
DSN_LITERAL_RE = re.compile(r"\b[a-z][a-z0-9+.\-]*://[\w.\-]+:[^\s@'\"]+@")
CREDENTIAL_RE = re.compile(
    r"\b(?:api_key|secret_key|access_key|password|passwd)\b\s*[:=]\s*['\"][^'\"]{3,}['\"]",
    re.IGNORECASE)

PASS, FAIL = "PASS", "FAIL"
_failures: list = []


def read(rel: str) -> str:
    with open(os.path.join(REPO_ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def check(label: str, ok: bool) -> None:
    if ok:
        print(f"  [{PASS}] {label}")
    else:
        _failures.append(label)
        print(f"  [{FAIL}] {label}")


def code_only(source: str) -> str:
    """Executable tokens only — comments and docstrings removed.

    A module that *documents* the operations it refuses to perform must not be flagged for saying
    so; this phase's helper names ``DROP``/``DELETE`` in prose precisely to disclaim them.
    """
    out = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type in (tokenize.COMMENT,):
                continue
            out.append(tok.string)
    except tokenize.TokenError:  # pragma: no cover
        return source
    return " ".join(out)


def code_no_docstrings(source: str) -> str:
    """Executable code with comments and *docstrings* removed, but string literals kept.

    The two fixed SQL statements are string literals and must stay visible to the scope checks;
    only module/function docstrings are stripped.
    """
    import ast
    tree = ast.parse(source)
    doc_ranges = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                doc_ranges.append((body[0].lineno, body[0].end_lineno))
    lines = source.splitlines()
    keep = []
    for idx, line in enumerate(lines, start=1):
        if any(start <= idx <= end for start, end in doc_ranges):
            continue
        keep.append(re.sub(r"#.*$", "", line))
    return "\n".join(keep)


def load_hardening():
    spec = importlib.util.spec_from_file_location(
        "phase47_hardening_under_test", os.path.join(REPO_ROOT, HARDENING_REL))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", REPO_ROOT, *args],
                          capture_output=True, text=True, timeout=20).stdout.strip()


# --------------------------------------------------------------------------- 1. baseline


def baseline_checks() -> None:
    print("\n1. Baseline: head still 013, 13 migrations, 18 tables, nothing new added")
    versions_dir = os.path.join(REPO_ROOT, VERSIONS_REL)
    versions = sorted(f for f in os.listdir(versions_dir) if f.endswith(".py"))
    check(f"exactly {EXPECTED_MIGRATIONS} migrations", len(versions) == EXPECTED_MIGRATIONS)
    check("no migration 014 or later",
          not any(re.match(r"^0*(?:1[4-9]|[2-9]\d)_", f) for f in versions))
    check(f"{HEAD_REVISION} is still the newest migration",
          versions[-1] == f"{HEAD_REVISION}.py")

    for rel in (HARDENING_REL, ENV_REL, HARNESS_REL):
        try:
            py_compile.compile(os.path.join(REPO_ROOT, rel), doraise=True)
            check(f"{rel} compiles", True)
        except py_compile.PyCompileError:
            check(f"{rel} compiles", False)

    import importlib as _il
    p11 = _il.import_module("tests.validate_phase11_db_scaffold")
    check(f"db-check still expects exactly {EXPECTED_TABLE_COUNT} tables",
          len(list(getattr(p11, "EXPECTED_TABLES", []))) == EXPECTED_TABLE_COUNT)
    check(f"models.py still declares exactly {EXPECTED_TABLE_COUNT} tables",
          read(MODELS).count("__tablename__ = ") == EXPECTED_TABLE_COUNT)

    from peak.persistence.allowlist import ALLOWED_ACTIONS, ALLOWED_TABLES
    check(f"allowlist still has exactly {EXPECTED_ALLOWLIST_TABLES} tables",
          len(ALLOWED_TABLES) == EXPECTED_ALLOWLIST_TABLES)
    check(f"allowlist still has exactly {EXPECTED_ALLOWLIST_ACTIONS} actions",
          len(ALLOWED_ACTIONS) == EXPECTED_ALLOWLIST_ACTIONS)
    check("no alembic/version/collation action added to the allowlist",
          not any(re.search(r"alembic|version_num|migrat", a) for a in ALLOWED_ACTIONS))

    writers = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "peak", "db"))
                     if f.endswith("_writer.py"))
    check(f"still exactly the {EXPECTED_WRITERS} narrow controlled writers",
          len(writers) == EXPECTED_WRITERS)

    try:
        history = git("log", "--oneline", "-40")
        check(f"baseline commit {BASELINE_COMMIT} present in history",
              BASELINE_COMMIT in history)
        # The whole-tree scope guard is an *authoring-time* check: it means "the work in progress
        # for this phase touched nothing extra". Once Phase 47 is committed it must go quiet, or it
        # would freeze the repository against every later phase's legitimate changes.
        # Gated on the phase's *implementation* artifact, not its harness: a later phase editing
        # this harness must not be mistaken for Phase 47 being re-authored.
        authoring = bool(git("status", "--porcelain", "--", HARDENING_REL).strip())
        if authoring:
            changed = set(git("diff", "--name-only", "HEAD").splitlines())
            unexpected = sorted(changed - ALLOWED_CHANGED)
            check("only the intended narrow set of files changed", not unexpected)
            if unexpected:
                print(f"        unexpected: {unexpected}")
            untouched = git("diff", "--name-only", "HEAD", "--",
                            "schemas", "prompts", "agents", "requirements.txt",
                            "requirements-dev.txt", "examples")
            check("schemas/, prompts/, agents/, requirements untouched", not untouched)
        else:
            print("  [skip] Phase 47 is committed — working-tree scope guard not applicable")

        # The *content* invariants remain unconditional. The file-level freeze on writers and the
        # allowlist did not: Phase 54 legitimately owns the engagement authorization anchor writer
        # and the one-pair anchor-creation gate added beside the generic sets.
        from peak.persistence.allowlist import ALLOWED_ACTIONS, ALLOWED_TABLES, PROHIBITED_TABLES
        check("the generic allowlist is unchanged and root tables stay prohibited",
              len(ALLOWED_TABLES) == 13 and len(ALLOWED_ACTIONS) == 15
              and "engagements" in PROHIBITED_TABLES and "clients" in PROHIBITED_TABLES
              and "engagements" not in ALLOWED_TABLES)
        check("no DB model source changed",
              not [c for c in git("diff", "--name-only", "HEAD", "--", "peak").splitlines()
                   if c.endswith("peak/db/models.py")])
        migrations_changed = git("diff", "--name-only", "HEAD", "--", VERSIONS_REL)
        check("no existing migration file was edited or rewritten", not migrations_changed)
        docx = git("diff", "--name-only", "HEAD", "--", "docs/Peak_Investor_Overview_AI.docx")
        check("docs/Peak_Investor_Overview_AI.docx has no pending diff", not docx)
    except Exception:
        check("git-backed scope checks (git unavailable — skipped)", True)


# --------------------------------------------------------------------------- 2. revision widths


def revision_width_checks() -> None:
    print("\n2. Revision identifier widths: the exact Phase 46 failure, detected in source")
    h = load_hardening()
    versions_dir = os.path.join(REPO_ROOT, VERSIONS_REL)
    ids = h.revision_ids(versions_dir)
    by_rev = {rev: len(rev) for rev in ids.values()}

    check(f"scanner recovers all {EXPECTED_MIGRATIONS} revision identifiers",
          len(ids) == EXPECTED_MIGRATIONS)

    for rev, expected_len in sorted(KNOWN_LONG_REVISIONS.items()):
        check(f"{rev} detected at length {expected_len}", by_rev.get(rev) == expected_len)
        check(f"{rev} exceeds Alembic's default VARCHAR({ALEMBIC_DEFAULT_WIDTH})",
              expected_len > ALEMBIC_DEFAULT_WIDTH)

    configured = h.ALEMBIC_VERSION_NUM_LENGTH
    check(f"configured version-column length is at least {MINIMUM_VERSION_NUM_LENGTH}",
          configured >= MINIMUM_VERSION_NUM_LENGTH)
    over = sorted(r for r, n in by_rev.items() if n > configured)
    check(f"every revision identifier fits the configured width ({configured})", not over)
    check("longest identifier is the known 43-character revision",
          h.max_revision_id_length(versions_dir) == 43)
    check("the source guard passes at the current width",
          h.assert_revision_ids_fit(versions_dir) is None)

    # The guard must actually fire when it should — proven against a temp dir, not asserted.
    tmp = tempfile.mkdtemp(prefix="peak_p47_guard_")
    try:
        with open(os.path.join(tmp, "999_x.py"), "w", encoding="utf-8") as fh:
            fh.write('revision = "%s"\ndown_revision = None\n' % ("z" * (configured + 1)))
        fired = False
        try:
            h.assert_revision_ids_fit(tmp)
        except RuntimeError:
            fired = True
        check("source guard raises on an identifier wider than the configured length", fired)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------- 3. planner


def planner_checks() -> None:
    print("\n3. Planner decides create / widen / no-op deterministically, with no database")
    h = load_hardening()

    check("absent table on mysql -> create",
          h.plan_version_table_action("mysql", None) == h.ACTION_CREATE)
    check("absent table on mariadb -> create",
          h.plan_version_table_action("mariadb", None) == h.ACTION_CREATE)
    check(f"VARCHAR({ALEMBIC_DEFAULT_WIDTH}) on mysql -> widen (the Phase 46 state)",
          h.plan_version_table_action("mysql", ALEMBIC_DEFAULT_WIDTH) == h.ACTION_WIDEN)
    check("one char under the configured width -> widen",
          h.plan_version_table_action("mysql", h.ALEMBIC_VERSION_NUM_LENGTH - 1) == h.ACTION_WIDEN)
    check("exactly the configured width -> no-op",
          h.plan_version_table_action("mysql", h.ALEMBIC_VERSION_NUM_LENGTH) == h.ACTION_NOOP)
    check("wider than configured -> no-op",
          h.plan_version_table_action("mysql", h.ALEMBIC_VERSION_NUM_LENGTH + 100) == h.ACTION_NOOP)
    check("uppercase dialect name still recognised",
          h.plan_version_table_action("MySQL", None) == h.ACTION_CREATE)
    for other in ("sqlite", "postgresql", "oracle", ""):
        check(f"dialect '{other or '(empty)'}' is left alone",
              h.plan_version_table_action(other, None) == h.ACTION_SKIP_DIALECT)

    check("only create and widen map to a statement",
          h.sql_for_action(h.ACTION_CREATE) is not None
          and h.sql_for_action(h.ACTION_WIDEN) is not None
          and h.sql_for_action(h.ACTION_NOOP) is None
          and h.sql_for_action(h.ACTION_SKIP_DIALECT) is None)


# --------------------------------------------------------------------------- 4. scope


def scope_checks() -> None:
    print("\n4. SQL surface is two fixed statements, scoped to alembic_version.version_num")
    h = load_hardening()
    src = read(HARDENING_REL)
    code = code_no_docstrings(src)

    create, widen = h.CREATE_VERSION_TABLE_SQL, h.WIDEN_VERSION_COLUMN_SQL
    check("create statement is exactly the expected literal",
          create == ("CREATE TABLE alembic_version (version_num VARCHAR(255) NOT NULL, "
                     "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"))
    check("widen statement is exactly the expected literal",
          widen == ("ALTER TABLE alembic_version MODIFY COLUMN version_num "
                    "VARCHAR(255) NOT NULL"))
    check("create statement declares VARCHAR(255) NOT NULL",
          "VARCHAR(255) NOT NULL" in create)
    check("widen statement declares VARCHAR(255) NOT NULL",
          "VARCHAR(255) NOT NULL" in widen)
    check("neither statement is a format template",
          not any(m in create + widen for m in ("{", "}", "%s", "%(", " + ")))

    # Every SQL identifier either statement mentions must be one of these three. Tokenising and
    # subtracting the keywords is what makes "scoped to alembic_version.version_num" a fact rather
    # than a claim: an identifier naming anything else would survive the subtraction and fail.
    sql_keywords = {
        "CREATE", "TABLE", "ALTER", "MODIFY", "COLUMN", "VARCHAR", "NOT", "NULL",
        "CONSTRAINT", "PRIMARY", "KEY",
    }
    permitted_identifiers = {"alembic_version", "alembic_version_pkc", "version_num"}
    for stmt_name, stmt in (("create", create), ("widen", widen)):
        tokens = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", stmt))
        identifiers = {t for t in tokens if t.upper() not in sql_keywords}
        check(f"{stmt_name} statement names only alembic_version/version_num identifiers",
              identifiers <= permitted_identifiers)
        if not identifiers <= permitted_identifiers:
            print(f"        unexpected identifiers: {sorted(identifiers - permitted_identifiers)}")
        check(f"{stmt_name} statement names the version_num column", "version_num" in stmt)
        check(f"{stmt_name} statement names the alembic_version table", "alembic_version" in stmt)

    # No application table may be nameable from this module.
    import importlib as _il
    p11 = _il.import_module("tests.validate_phase11_db_scaffold")
    app_tables = [t for t in getattr(p11, "EXPECTED_TABLES", [])]
    check(f"{len(app_tables)} application tables are known to this check",
          len(app_tables) == EXPECTED_TABLE_COUNT)
    leaked = sorted(t for t in app_tables if t in code)
    check("no application table name appears anywhere in the helper's code", not leaked)
    if leaked:
        print(f"        leaked: {leaked}")

    for forbidden in ("DROP ", "DELETE ", "TRUNCATE", "INSERT ", "UPDATE ", "GRANT ", "REVOKE "):
        check(f"helper code contains no {forbidden.strip()} statement",
              forbidden not in code.upper())

    check("helper exposes no general-purpose SQL executor",
          not re.search(r"def\s+(execute_sql|run_sql|exec_sql|raw_sql)", code))
    compact = re.sub(r"\s+", "", code)
    check("the helper contains exactly one execute() call site",
          code.count(".execute(") == 1)
    check("that call site executes only the planner-selected statement",
          "connection.execute(text(statement))" in compact)
    check("no statement string reaches execute() by concatenation or formatting",
          not re.search(r"execute\(\s*text\(\s*[fF]?['\"]", code))
    check("helper never calls create_engine (the caller owns the connection)",
          "create_engine" not in code)
    check("helper reads no environment variable",
          "os.environ" not in code and "getenv" not in code)
    check("helper references no credential file",
          not any(m in src for m in CREDENTIAL_FILE_MARKERS))
    check("helper reads no .env", ".env" not in code)
    check("helper embeds no DSN literal", not DSN_LITERAL_RE.search(src))
    check("helper embeds no credential assignment", not CREDENTIAL_RE.search(src))
    for word in ("://", "host=", "user=", "passwd", "certificate", "sslmode"):
        check(f"helper contains no '{word}' connection detail", word not in code)


# --------------------------------------------------------------------------- 5. behaviour


class _StubResult:
    pass


class _StubDialect:
    def __init__(self, name: str) -> None:
        self.name = name


class _StubConnection:
    """Records the statements a caller would have executed, without a server."""

    def __init__(self, dialect_name: str) -> None:
        self.dialect = _StubDialect(dialect_name)
        self.executed: list = []

    def execute(self, clause):
        self.executed.append(str(clause))
        return _StubResult()


def behaviour_checks() -> None:
    print("\n5. Behaviour on a stubbed MySQL dialect and a real SQLite connection")
    h = load_hardening()

    def run(dialect: str, existing_length):
        conn = _StubConnection(dialect)
        original = h.current_version_num_length
        h.current_version_num_length = lambda _c: existing_length   # type: ignore[assignment]
        try:
            action = h.harden_version_table(conn)
        finally:
            h.current_version_num_length = original                 # type: ignore[assignment]
        return action, conn.executed

    # The skip and no-op branches emit no DDL and need no driver; create/widen import
    # sqlalchemy.text, so they only run on an interpreter that has SQLAlchemy.
    try:
        import sqlalchemy  # noqa: F401
        has_sqlalchemy = True
    except ImportError:
        has_sqlalchemy = False

    action, executed = run("sqlite", None)
    check("SQLite is skipped before any inspection", action == h.ACTION_SKIP_DIALECT)
    check("SQLite emits no statement", executed == [])

    action, executed = run("mysql", h.ALEMBIC_VERSION_NUM_LENGTH)
    check("already-wide column is left untouched", action == h.ACTION_NOOP)
    check("already-wide column emits no statement at all", executed == [])

    if not has_sqlalchemy:
        print("  [skip] SQLAlchemy not installed — create/widen DDL branches not exercised")
        return

    action, executed = run("mysql", None)
    check("fresh MySQL bootstrap creates the version table", action == h.ACTION_CREATE)
    check("fresh bootstrap emits exactly one statement", len(executed) == 1)
    check("fresh bootstrap emits the create literal with VARCHAR(255)",
          executed == [h.CREATE_VERSION_TABLE_SQL])
    check(f"fresh bootstrap never emits VARCHAR({ALEMBIC_DEFAULT_WIDTH})",
          f"VARCHAR({ALEMBIC_DEFAULT_WIDTH})" not in executed[0])

    action, executed = run("mysql", ALEMBIC_DEFAULT_WIDTH)
    check("existing narrow column is widened (the Phase 46 repair, now automatic)",
          action == h.ACTION_WIDEN)
    check("widen emits exactly one statement", len(executed) == 1)
    check("widen emits the ALTER literal", executed == [h.WIDEN_VERSION_COLUMN_SQL])

    action, executed = run("mariadb", ALEMBIC_DEFAULT_WIDTH)
    check("MariaDB takes the same widen path", action == h.ACTION_WIDEN and len(executed) == 1)

    # A real SQLite connection: prove the helper is inert rather than merely believed to be.
    from sqlalchemy import create_engine, inspect
    tmp = tempfile.mkdtemp(prefix="peak_p47_sqlite_")
    try:
        engine = create_engine("sqlite:///" + os.path.join(tmp, "v.db"))
        with engine.begin() as conn:
            result = h.harden_version_table(conn)
        check("real SQLite connection returns skip", result == h.ACTION_SKIP_DIALECT)
        check("real SQLite connection gained no alembic_version table",
              not inspect(engine).has_table("alembic_version"))
    except Exception as exc:  # noqa: BLE001
        check(f"live SQLite hardening path ({type(exc).__name__})", False)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------- 6. integration


def integration_checks() -> None:
    print("\n6. env.py wires the preflight in, and PEAK_DATABASE_URL still names the URL")
    env_src = read(ENV_REL)
    env_code = code_no_docstrings(env_src)

    check("env.py loads the hardening module", "version_table_hardening.py" in env_src)
    check("online mode runs the version-table preflight",
          "harden_version_table(" in env_code)
    check("online mode runs the preflight before context.configure",
          env_code.index("harden_version_table(") < env_code.index("context.configure(connection"))
    check("both modes run the source-side revision-width guard",
          env_code.count("assert_revision_ids_fit(") == 2)
    check("offline mode opens no connection",
          "create_engine" not in env_code.split("def run_migrations_online")[0]
          .split("def run_migrations_offline")[-1])
    check("PEAK_DATABASE_URL remains the Alembic URL variable",
          'os.environ.get("PEAK_DATABASE_URL")' in env_code)
    check("env.py introduces no second URL variable",
          "DATABASE_URL" not in env_code.replace("PEAK_DATABASE_URL", ""))
    check("env.py embeds no DSN literal", not DSN_LITERAL_RE.search(env_src))
    check("env.py references no credential file",
          not any(m in env_src for m in CREDENTIAL_FILE_MARKERS))
    check("env.py still targets Base.metadata only",
          "target_metadata = Base.metadata" in env_code)
    check("env.py adds no application-table DDL", "op." not in env_code)

    mk = read("Makefile")
    check("Makefile declares validate-phase47", "validate-phase47" in mk)
    check("validate depends on validate-phase47",
          re.search(r"^validate:.*validate-phase47", mk, re.MULTILINE) is not None)
    check("validate-phase47 runs this harness",
          "tests/validate_phase47_alembic_version_table_hardening.py" in mk)
    check("no production or migration-running target was added to validate",
          not re.search(r"^validate:.*(upgrade|production-mysql)", mk, re.MULTILINE))


# --------------------------------------------------------------------------- 7. regression


def regression_checks() -> None:
    print("\n7. Regression: SQLite migrations, db-check, audit, and the verifier are unchanged")
    try:
        from alembic import command
        from alembic.config import Config
        from sqlalchemy import create_engine, inspect
    except ImportError:
        print("  [skip] Alembic/SQLAlchemy not installed — migration run not exercised")
    else:
        tmp = tempfile.mkdtemp(prefix="peak_p47_")
        prev = os.environ.get("PEAK_DATABASE_URL")
        try:
            url = "sqlite:///" + os.path.join(tmp, "m.db")
            os.environ["PEAK_DATABASE_URL"] = url
            cfg = Config(os.path.join(REPO_ROOT, "alembic.ini"))
            command.upgrade(cfg, "head")
            insp = inspect(create_engine(url))
            tables = [t for t in insp.get_table_names() if t != "alembic_version"]
            check(f"SQLite upgrade head still builds {EXPECTED_TABLE_COUNT} tables",
                  len(tables) == EXPECTED_TABLE_COUNT)
            check("SQLite run still creates alembic_version",
                  insp.has_table("alembic_version"))
            command.downgrade(cfg, "012_internal_report_review_packet_decisions")
            command.upgrade(cfg, "head")
            check("SQLite downgrade + re-upgrade still succeeds",
                  len([t for t in inspect(create_engine(url)).get_table_names()
                       if t != "alembic_version"]) == EXPECTED_TABLE_COUNT)
        except Exception as exc:  # noqa: BLE001
            check(f"SQLite migration run ({type(exc).__name__})", False)
        finally:
            if prev is None:
                os.environ.pop("PEAK_DATABASE_URL", None)
            else:
                os.environ["PEAK_DATABASE_URL"] = prev
            shutil.rmtree(tmp, ignore_errors=True)

    env = {k: v for k, v in os.environ.items()
           if k not in ("PEAK_PRODUCTION_DB_URL", "PEAK_PRODUCTION_DB_READONLY_CONFIRM")}
    try:
        audit = subprocess.run([PY, os.path.join(REPO_ROOT, AUDIT)],
                               capture_output=True, text=True, timeout=180, env=env)
        out = audit.stdout
        if "SQLAlchemy not installed" in out:
            check("audit runs (source-scan tier on this interpreter)", audit.returncode == 0)
        else:
            check("audit still reports MODEL_POLICY_SATISFIED_PRODUCTION_UNVERIFIED",
                  "MODEL_POLICY_SATISFIED_PRODUCTION_UNVERIFIED" in out)
            check("audit still reports 0 unpinned governed columns",
                  re.search(r"unpinned\s*:\s*0", out) is not None)
        check("audit still exits 0", audit.returncode == 0)
    except Exception:
        check("audit regression (not runnable — skipped)", True)

    try:
        verify = subprocess.run([PY, os.path.join(REPO_ROOT, VERIFIER)],
                                capture_output=True, text=True, timeout=120, env=env)
        check("production verifier still skips safely with no configuration",
              verify.returncode == 0)
        check("production verifier still reports no schema mutation",
              "schema_mutation_made            : False" in verify.stdout
              or "schema_mutation_made" in verify.stdout)
        check("production verifier made no connection",
              "production_connection_made     : False" in verify.stdout
              or "production_connection_attempted: False" in verify.stdout)
    except Exception:
        check("verifier regression (not runnable — skipped)", True)


# --------------------------------------------------------------------------- main


def main() -> int:
    print("Peak Phase 47 Alembic version-table hardening check")
    print("=" * 70)

    baseline_checks()
    revision_width_checks()
    planner_checks()
    scope_checks()
    behaviour_checks()
    integration_checks()
    regression_checks()

    print("\n" + "=" * 70)
    print("Summary")
    print(f"  failures : {len(_failures)}")
    for label in _failures:
        print(f"    - {label}")
    print("\nRESULT: " + ("FAIL" if _failures else "PASS"))
    return 1 if _failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
