#!/usr/bin/env python3
"""Production MySQL collation verification — READ-ONLY (Phase 43).

Answers the one question Phase 42 could not settle from source: **is the collation risk live in
the real deployed Peak production database?**

Phase 42 classified 308 string columns and found 211 governed columns with **no collation pinned
anywhere**, so the server's default decides comparison semantics. Whether that default is
case-insensitive cannot be read from the repository. This tool reads it from the running server.

**Read-only, by construction.**

* Every statement it can issue is a **hard-coded constant** in :data:`READ_ONLY_QUERIES`. There is
  no code path that accepts SQL from a CLI argument, an environment variable, a file, or any other
  caller-supplied source.
* Every statement is checked against :func:`assert_read_only` immediately before execution: it must
  be one of the hard-coded constants, must begin with ``SELECT`` or ``SHOW``, and must contain no
  mutating verb. A statement failing any of those is refused, not executed.
* It issues no ``INSERT``/``UPDATE``/``DELETE``/``ALTER``/``DROP``/``TRUNCATE``/``CREATE``/
  ``REPLACE``/``GRANT``/``REVOKE``/``LOCK``/``CALL``/``LOAD``/``OUTFILE``, no ``SET``, no
  multi-statement execution, no migration, and no cleanup or delete path.

**Fail-closed gating.** It connects only when the operator has *explicitly* affirmed a read-only
production inspection **and** a connection setting is available out-of-band. With neither it skips
and exits 0, importing no database driver and reading no ``.env``. With a DSN but no affirmation it
**refuses** and exits 2 without connecting.

**No secrets, no client data.** It never prints a DSN, username, password, host, port, database
name, certificate, token, environment value, or ``.env`` content, and never emits a production row
value — collision probes report **counts only**. Failures are reported by sanitized category, never
by raw driver exception text, which routinely embeds the connection string.

**It changes nothing and decides nothing.** It reports, classifies the risk, and recommends a next
step. Migration ``013`` is **not** implemented, proposed as code, or executed here.

See docs/PRODUCTION_MYSQL_COLLATION_VERIFICATION.md.

Exit status:
  0  -> verification ran, or skipped safely because it was not configured
  1  -> the tool itself failed safely (sanitized), or verification was inconclusive
  2  -> refused: production-shaped configuration without an explicit read-only affirmation
"""

from __future__ import annotations

import argparse
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(REPO_ROOT, "tools")
for _p in (REPO_ROOT, TOOLS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# --------------------------------------------------------------------------- configuration

#: The operator must set this to affirm: "this is a READ-ONLY inspection of production."
READONLY_CONFIRM_VAR = "PEAK_PRODUCTION_DB_READONLY_CONFIRM"
#: Connection settings, in precedence order. Values are read but **never** printed or logged.
PRODUCTION_DSN_VARS = ("PEAK_PRODUCTION_DB_URL", "PEAK_DATABASE_URL")
_AFFIRMATIVE = ("1", "true", "yes", "on")

# --------------------------------------------------------------------------- query allowlist

#: Verbs that must never appear in any statement this tool issues.
FORBIDDEN_SQL_VERBS = (
    "insert", "update", "delete", "alter", "drop", "truncate", "create", "replace",
    "grant", "revoke", "lock", "unlock", "call", "load", "outfile", "infile",
    "rename", "commit", "rollback", "set ", "prepare", "execute", "handler", "do ",
)

#: **The complete set of statements this tool can issue.** Nothing is built from user input.
#: ``{}`` placeholders are filled only with values this module itself controls (a table name from
#: the expected-table constant, or a collation name read back from INFORMATION_SCHEMA and
#: re-validated against :data:`_SAFE_IDENTIFIER_RE`).
READ_ONLY_QUERIES = {
    "server_version": "SELECT VERSION()",
    "current_database": "SELECT DATABASE()",
    "database_charset_collation": (
        "SELECT DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME "
        "FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = DATABASE()"
    ),
    "table_collations": (
        "SELECT TABLE_NAME, TABLE_COLLATION FROM INFORMATION_SCHEMA.TABLES "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME"
    ),
    "column_collations": (
        "SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, CHARACTER_SET_NAME, COLLATION_NAME "
        "FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() "
        "AND DATA_TYPE IN ('char', 'varchar', 'text', 'tinytext', 'mediumtext', 'longtext') "
        "ORDER BY TABLE_NAME, COLUMN_NAME"
    ),
    "alembic_version": "SELECT version_num FROM alembic_version",
    # Empirical cross-check on literals only — touches no table and no row.
    "collation_case_probe": "SELECT ('a' COLLATE {collation}) = ('A' COLLATE {collation})",
    # Opt-in aggregate probe. Returns a single COUNT; never a row, id, or key value.
    "case_variant_group_count": (
        "SELECT COUNT(*) FROM (SELECT 1 FROM `{table}` "
        "GROUP BY owner_id, client_id, engagement_id, LOWER(idempotency_key) "
        "HAVING COUNT(*) > 1) AS peak_probe"
    ),
}

_SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_]{1,64}$")

# --------------------------------------------------------------------------- expectations

#: The head expected **in production**. Deliberately still 013: Phase 56 added migration 014
#: to the repository but it has **not** been applied to production, so expecting 014 here
#: would misreport the live posture. Move this only when 014 is actually applied.
EXPECTED_ALEMBIC_HEAD = "013_governed_identifier_collation_policy"
EXPECTED_TABLE_COUNT = 18
REQUIRED_CHARSET = "utf8mb4"

#: Collation-name suffixes that denote deterministic (case-sensitive) comparison.
DETERMINISTIC_SUFFIXES = ("_bin", "_as_cs", "_cs")
#: Suffixes that denote case-insensitive comparison — unsafe for governed columns.
CASE_INSENSITIVE_SUFFIXES = ("_ci", "_ai_ci")

# --------------------------------------------------------------------------- result vocabulary

SKIPPED_NOT_CONFIGURED = "skipped_not_configured"
REFUSED_NOT_CONFIRMED_READONLY = "refused_not_confirmed_readonly"
VERIFIED_SAFE = "verified_safe_no_remediation_required"
VERIFIED_RISK_LIVE = "verified_risk_live_remediation_required"
VERIFIED_INCONCLUSIVE = "verified_inconclusive"
FAILED_SAFELY = "failed_safely"

ALL_OUTCOMES = (SKIPPED_NOT_CONFIGURED, REFUSED_NOT_CONFIRMED_READONLY, VERIFIED_SAFE,
                VERIFIED_RISK_LIVE, VERIFIED_INCONCLUSIVE, FAILED_SAFELY)

PROBE_NOT_RUN = "not_run_opt_in"
PROBE_COMPLETED = "completed_counts_only"
PROBE_UNAVAILABLE = "unavailable_on_this_server"

# --------------------------------------------------------------------------- sanitation

_SECRET_PATTERNS = (
    re.compile(r"\b[a-zA-Z][a-zA-Z0-9+.\-]*://\S+"),
    re.compile(r"(?i)\b(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key)\b"
               r"\s*[:=]\s*\S+"),
    re.compile(r"(?i)-----BEGIN [A-Z ]*(?:PRIVATE KEY|CERTIFICATE)-----[\s\S]*?"
               r"-----END [A-Z ]*(?:PRIVATE KEY|CERTIFICATE)-----"),
    re.compile(r"\b[\w.\-]+:[^\s@/]+@[\w.\-]+"),
)
_WITHHELD = "[secret withheld]"


def sanitize(text) -> str:
    """Scrub anything DSN- or credential-shaped before it can reach output."""
    out = str(text)
    for pattern in _SECRET_PATTERNS:
        out = pattern.sub(_WITHHELD, out)
    return out


def emit(line: str = "") -> None:
    print(sanitize(line))


def safe_error(exc: BaseException) -> str:
    """Report a failure by exception *type* only. Driver messages embed the DSN."""
    return f"{type(exc).__name__} (detail withheld)"


# --------------------------------------------------------------------------- read-only guard


class UnsafeQueryRefused(RuntimeError):
    """Raised when a statement is not provably one of the hard-coded read-only queries."""


def assert_read_only(sql: str) -> str:
    """Refuse anything that is not a hard-coded, read-only statement. Returns the statement.

    Three independent conditions, all required:
      1. it derives from :data:`READ_ONLY_QUERIES` (identity, not resemblance);
      2. it begins with ``SELECT`` or ``SHOW``;
      3. it contains no mutating verb and no statement separator.
    """
    if not isinstance(sql, str) or not sql.strip():
        raise UnsafeQueryRefused("empty statement refused")
    text = sql.strip()

    if not re.match(r"^(?:SELECT|SHOW)\b", text, re.IGNORECASE):
        raise UnsafeQueryRefused("statement does not begin with SELECT/SHOW")
    if ";" in text.rstrip(";"):
        raise UnsafeQueryRefused("multi-statement execution refused")

    low = text.lower()
    for verb in FORBIDDEN_SQL_VERBS:
        if re.search(rf"(?<![a-z_]){re.escape(verb.strip())}(?![a-z_])", low):
            raise UnsafeQueryRefused(f"forbidden verb '{verb.strip()}' refused")

    if not _derives_from_allowlist(text):
        raise UnsafeQueryRefused("statement is not in the hard-coded read-only allowlist")
    return text


def _derives_from_allowlist(text: str) -> bool:
    """True when ``text`` is an allowlisted query, or one of the two templated ones filled in."""
    for name, template in READ_ONLY_QUERIES.items():
        if text == template:
            return True
        if "{" not in template:
            continue
        pattern = re.escape(template)
        pattern = pattern.replace(re.escape("{collation}"), r"[A-Za-z0-9_]{1,64}")
        pattern = pattern.replace(re.escape("{table}"), r"[A-Za-z0-9_]{1,64}")
        if re.fullmatch(pattern, text):
            return True
    return False


def safe_identifier(value) -> str:
    """Validate an identifier this module read back from the server before reusing it in SQL."""
    text = str(value)
    if not _SAFE_IDENTIFIER_RE.match(text):
        raise UnsafeQueryRefused("identifier failed the safe-identifier check")
    return text


# --------------------------------------------------------------------------- result contract


class VerificationResult:
    """Sanitized outcome of one production verification run. Carries no values, only findings."""

    def __init__(self) -> None:
        self.outcome = SKIPPED_NOT_CONFIGURED
        self.reason_code = None
        self.reasons: list = []
        self.warnings: list = []
        # Behavior flags — what this run actually did.
        self.production_connection_attempted = False
        self.production_connection_made = False
        self.readonly_queries_only = True
        self.queries_issued: list = []          # query *names*, never SQL text with values
        # Permanent falses — this tool has no code path that could set them true.
        self.schema_mutation_made = False
        self.data_write_made = False
        self.migration_executed = False
        self.cleanup_delete_made = False
        self.secrets_printed = False
        # Findings.
        self.server_version_family = None       # major.minor only; never a full build string
        self.database_charset = None
        self.database_collation = None
        self.alembic_head_matches = None
        self.tables_found = None
        self.governed_columns_checked = 0
        self.governed_columns_at_risk = 0
        self.governed_columns_deterministic = 0
        self.idempotency_boundaries_checked = 0
        self.idempotency_boundaries_at_risk = 0
        self.collision_probe_status = PROBE_NOT_RUN
        self.collision_probe_group_counts: dict = {}
        self.case_insensitive_collations: list = []
        self.recommended_next_step = None

    def as_lines(self) -> list:
        return [
            f"outcome                        : {self.outcome}",
            f"reason_code                    : {self.reason_code}",
            f"production_connection_attempted: {self.production_connection_attempted}",
            f"production_connection_made     : {self.production_connection_made}",
            f"readonly_queries_only          : {self.readonly_queries_only}",
            f"schema_mutation_made           : {self.schema_mutation_made}",
            f"data_write_made                : {self.data_write_made}",
            f"migration_executed             : {self.migration_executed}",
            f"cleanup_delete_made            : {self.cleanup_delete_made}",
            f"secrets_printed                : {self.secrets_printed}",
            f"governed_columns_checked       : {self.governed_columns_checked}",
            f"governed_columns_at_risk       : {self.governed_columns_at_risk}",
            f"idempotency_boundaries_checked : {self.idempotency_boundaries_checked}",
            f"idempotency_boundaries_at_risk : {self.idempotency_boundaries_at_risk}",
            f"collision_probe_status         : {self.collision_probe_status}",
            f"recommended_next_step          : {self.recommended_next_step}",
        ]


# --------------------------------------------------------------------------- classification


def is_deterministic_collation(collation) -> bool:
    if not collation:
        return False
    return str(collation).lower().endswith(DETERMINISTIC_SUFFIXES)


def is_case_insensitive_collation(collation) -> bool:
    if not collation:
        return False
    return str(collation).lower().endswith(CASE_INSENSITIVE_SUFFIXES)


def governed_column_names():
    """The governed column names Phase 42 classified, reused rather than re-derived."""
    from governed_mysql_collation_audit import (
        DETERMINISTIC_REQUIRED, IDEMPOTENCY_BOUNDARY, classify,
    )
    return DETERMINISTIC_REQUIRED, IDEMPOTENCY_BOUNDARY, classify


# --------------------------------------------------------------------------- verification core


def verify_with_cursor(cursor, result: VerificationResult, *, run_collision_probe: bool = False,
                       expected_tables=None) -> VerificationResult:
    """Run the read-only verification against an open DB-API cursor.

    Separated from connection handling so the full query path is exercisable in tests with a fake
    cursor — no production database required to prove the tool issues only read-only statements.
    """
    deterministic_required, idempotency_boundary, classify = governed_column_names()

    def run(name: str, **fmt):
        template = READ_ONLY_QUERIES[name]
        sql = template.format(**fmt) if fmt else template
        assert_read_only(sql)
        result.queries_issued.append(name)
        cursor.execute(sql)
        return cursor.fetchall()

    # --- server + database identity (no host, no user, no DSN) ---
    try:
        rows = run("server_version")
        raw = str(rows[0][0]) if rows and rows[0] else ""
        match = re.match(r"(\d+\.\d+)", raw)
        result.server_version_family = match.group(1) if match else None
    except Exception as exc:  # noqa: BLE001
        result.warnings.append(f"server version unavailable ({safe_error(exc)})")

    try:
        rows = run("database_charset_collation")
        if rows and rows[0]:
            result.database_charset = str(rows[0][0])
            result.database_collation = str(rows[0][1])
    except Exception as exc:  # noqa: BLE001
        result.warnings.append(f"database charset/collation unavailable ({safe_error(exc)})")

    # --- alembic head ---
    try:
        rows = run("alembic_version")
        heads = [str(r[0]) for r in rows or []]
        result.alembic_head_matches = heads == [EXPECTED_ALEMBIC_HEAD]
        if not result.alembic_head_matches:
            result.warnings.append(
                f"production alembic head does not match the expected {EXPECTED_ALEMBIC_HEAD} "
                f"({len(heads)} head(s) present)")
    except Exception as exc:  # noqa: BLE001
        result.warnings.append(f"alembic_version unreadable ({safe_error(exc)})")

    # --- tables ---
    table_collations = {}
    try:
        for row in run("table_collations") or []:
            table_collations[str(row[0])] = str(row[1]) if row[1] else ""
        result.tables_found = len(table_collations)
    except Exception as exc:  # noqa: BLE001
        result.warnings.append(f"table collations unreadable ({safe_error(exc)})")

    if expected_tables:
        missing = sorted(set(expected_tables) - set(table_collations))
        extra = sorted(set(table_collations) - set(expected_tables) - {"alembic_version"})
        if missing:
            result.warnings.append(f"{len(missing)} expected table(s) absent from production: "
                                   + ", ".join(missing))
        if extra:
            result.warnings.append(f"{len(extra)} unexpected extra table(s) present: "
                                   + ", ".join(extra))

    # --- columns: the actual question ---
    at_risk_names = set()
    boundary_tables = set()
    boundary_column_risk: dict = {}
    insensitive = set()
    try:
        rows = run("column_collations") or []
    except Exception as exc:  # noqa: BLE001
        result.warnings.append(f"column collations unreadable ({safe_error(exc)})")
        rows = []
        result.outcome = VERIFIED_INCONCLUSIVE

    for row in rows:
        table, column, data_type, charset, collation = (str(row[0]), str(row[1]), str(row[2]),
                                                        str(row[3] or ""), str(row[4] or ""))
        policy_class = classify(column, "Text" if data_type.endswith("text") else "String")
        if policy_class not in deterministic_required:
            continue
        result.governed_columns_checked += 1
        if is_deterministic_collation(collation):
            result.governed_columns_deterministic += 1
        else:
            result.governed_columns_at_risk += 1
            at_risk_names.add(f"{table}.{column}")
            if is_case_insensitive_collation(collation):
                insensitive.add(collation)
        # A table is an idempotency *boundary* only if it actually carries idempotency_key — the
        # composite UNIQUE exists on those tables alone. owner_id/client_id/engagement_id appear
        # far more widely, so keying off them would overstate the boundary count and would aim the
        # collision probe at tables that have no such column.
        if column == "idempotency_key":
            boundary_tables.add(table)
        if column in idempotency_boundary and not is_deterministic_collation(collation):
            boundary_column_risk.setdefault(table, set()).add(column)
        if charset and charset.lower() != REQUIRED_CHARSET:
            result.warnings.append(
                f"{table}.{column} uses charset '{charset}', not '{REQUIRED_CHARSET}'")

    # Only boundary tables count, and only their at-risk boundary columns matter.
    boundary_at_risk = {t for t in boundary_tables if boundary_column_risk.get(t)}
    result.idempotency_boundaries_checked = len(boundary_tables)
    result.idempotency_boundaries_at_risk = len(boundary_at_risk)
    result.case_insensitive_collations = sorted(insensitive)

    # --- empirical cross-check: does the server really compare 'a' == 'A' under this collation? ---
    for collation in sorted(insensitive | {result.database_collation or ""} - {""}):
        try:
            name = safe_identifier(collation)
        except UnsafeQueryRefused:
            continue
        try:
            probe = run("collation_case_probe", collation=name)
            if probe and probe[0] and int(probe[0][0]) == 1:
                result.reasons.append(
                    f"server confirms collation '{name}' compares 'a' equal to 'A' "
                    "(case-insensitive)")
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"collation case probe unavailable ({safe_error(exc)})")

    # --- opt-in aggregate collision probe: counts only, never a row value ---
    if run_collision_probe and boundary_tables:
        result.collision_probe_status = PROBE_COMPLETED
        for table in sorted(boundary_tables):
            try:
                name = safe_identifier(table)
                rows = run("case_variant_group_count", table=name)
                result.collision_probe_group_counts[name] = int(rows[0][0]) if rows and rows[0] \
                    else 0
            except Exception as exc:  # noqa: BLE001
                result.collision_probe_status = PROBE_UNAVAILABLE
                result.warnings.append(f"collision probe unavailable ({safe_error(exc)})")
                break

    _classify_outcome(result, at_risk_names)
    return result


def _classify_outcome(result: VerificationResult, at_risk_names) -> None:
    """Decide the verdict and the recommended next step. Recommends; never acts."""
    if result.outcome == VERIFIED_INCONCLUSIVE or result.governed_columns_checked == 0:
        result.outcome = VERIFIED_INCONCLUSIVE
        result.reason_code = "no_governed_columns_readable"
        result.recommended_next_step = (
            "re-run with an account that can read INFORMATION_SCHEMA.COLUMNS for this schema; "
            "do not proceed to migration 013 on inconclusive evidence")
        return

    if result.governed_columns_at_risk:
        result.outcome = VERIFIED_RISK_LIVE
        result.reason_code = "governed_columns_non_deterministic"
        result.reasons.append(
            f"{result.governed_columns_at_risk} of {result.governed_columns_checked} governed "
            "column(s) do not use a deterministic collation in production")
        if result.idempotency_boundaries_at_risk:
            result.reasons.append(
                f"{result.idempotency_boundaries_at_risk} controlled-writer idempotency "
                "boundary table(s) are affected — the UNIQUE (owner_id, client_id, "
                "engagement_id, idempotency_key) constraint is not case-sensitive there")
        result.recommended_next_step = (
            "GO for migration 013 (013_governed_identifier_collation_policy): the risk is live. "
            "Migration 013 is implemented in source control but is NOT executed by this tool — "
            "production execution requires explicit approval, a backup, and a maintenance "
            "window. See docs/GOVERNED_MYSQL_COLLATION_POLICY.md")
    else:
        result.outcome = VERIFIED_SAFE
        result.reason_code = "all_governed_columns_deterministic"
        result.reasons.append(
            f"all {result.governed_columns_checked} governed column(s) already use a "
            "deterministic collation in production")
        result.recommended_next_step = (
            "NO-GO for migration 013: no remediation required. Keep the Phase 42 policy rule so "
            "future governed columns state their collation explicitly")


# --------------------------------------------------------------------------- connection gating


def _expected_tables():
    try:
        from peak.db.models import ALL_MODELS
        return sorted(m.__tablename__ for m in ALL_MODELS)
    except ImportError:
        return None


def run_verification(*, run_collision_probe: bool = False) -> tuple:
    """Gate, connect (read-only), verify. Returns ``(result, exit_code)``."""
    result = VerificationResult()

    confirmed = os.environ.get(READONLY_CONFIRM_VAR, "").strip().lower() in _AFFIRMATIVE
    dsn_var = next((v for v in PRODUCTION_DSN_VARS if os.environ.get(v)), None)

    # 1. Nothing configured -> skip. No driver import, no network, no .env read.
    if not confirmed and not dsn_var:
        result.outcome = SKIPPED_NOT_CONFIGURED
        result.reason_code = "no_production_connection_configured"
        result.reasons.append(
            "no production connection setting and no read-only affirmation are configured")
        return result, 0

    # 2. A connection setting exists but the operator has not affirmed read-only -> refuse.
    if dsn_var and not confirmed:
        result.outcome = REFUSED_NOT_CONFIRMED_READONLY
        result.reason_code = "readonly_affirmation_missing"
        result.reasons.append(
            f"a production connection setting is present but {READONLY_CONFIRM_VAR} is not set; "
            "refusing to connect")
        return result, 2

    # 3. Affirmed but no connection setting -> skip; nothing to inspect.
    if confirmed and not dsn_var:
        result.outcome = SKIPPED_NOT_CONFIGURED
        result.reason_code = "no_production_connection_configured"
        result.reasons.append(
            "read-only inspection was affirmed but no production connection setting is available")
        return result, 0

    # 4. Both present -> connect read-only.
    result.production_connection_attempted = True
    try:
        import sqlalchemy
    except ImportError:
        result.outcome = FAILED_SAFELY
        result.reason_code = "driver_unavailable"
        result.reasons.append("SQLAlchemy is not installed; cannot perform read-only inspection")
        return result, 1

    dsn = os.environ[dsn_var]  # read, never printed
    connection = None
    try:
        engine = sqlalchemy.create_engine(dsn, pool_pre_ping=True)
        connection = engine.connect()
        result.production_connection_made = True
        cursor = _SqlAlchemyCursor(connection, sqlalchemy)
        verify_with_cursor(cursor, result, run_collision_probe=run_collision_probe,
                           expected_tables=_expected_tables())
    except UnsafeQueryRefused as exc:
        result.outcome = FAILED_SAFELY
        result.reason_code = "unsafe_query_refused"
        result.readonly_queries_only = True
        result.reasons.append(f"refused to issue a statement: {exc}")
        return result, 1
    except Exception as exc:  # noqa: BLE001
        result.outcome = FAILED_SAFELY
        result.reason_code = "connection_or_query_failed"
        result.reasons.append(f"read-only inspection failed ({safe_error(exc)})")
        return result, 1
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:  # pragma: no cover - close failures are not reportable state
                pass

    return result, (0 if result.outcome in (VERIFIED_SAFE, VERIFIED_RISK_LIVE) else 1)


class _SqlAlchemyCursor:
    """Minimal DB-API-shaped adapter so the verification core stays driver-agnostic."""

    def __init__(self, connection, sqlalchemy_module) -> None:
        self._connection = connection
        self._sa = sqlalchemy_module
        self._rows: list = []

    def execute(self, sql: str):
        assert_read_only(sql)          # second, independent check at the boundary
        self._rows = list(self._connection.execute(self._sa.text(sql)))
        return self

    def fetchall(self):
        return self._rows


# --------------------------------------------------------------------------- reporting


def render(result: VerificationResult, *, verbose: bool = False) -> None:
    emit("Peak production MySQL collation verification — READ-ONLY")
    emit("=" * 62)

    if result.outcome == SKIPPED_NOT_CONFIGURED:
        emit(f"[skip] {result.reason_code}")
        for line in result.reasons:
            emit(f"       {line}")
        emit("       Nothing was connected to, no driver was imported, and no .env was read.")
        emit("       To run a READ-ONLY production verification, export both (out-of-band;")
        emit("       never committed, never printed):")
        emit(f"         1. {PRODUCTION_DSN_VARS[0]}   # or {PRODUCTION_DSN_VARS[1]}")
        emit(f"         2. {READONLY_CONFIRM_VAR}=1")
        emit("       See docs/PRODUCTION_MYSQL_COLLATION_VERIFICATION.md.")
    elif result.outcome == REFUSED_NOT_CONFIRMED_READONLY:
        emit(f"REFUSED: {result.reason_code}")
        for line in result.reasons:
            emit(f"         {line}")
        emit(f"         Set {READONLY_CONFIRM_VAR}=1 to affirm this is a READ-ONLY inspection.")
        emit("         No connection was attempted.")
    else:
        emit(f"[{'ok' if result.outcome == VERIFIED_SAFE else 'finding'}] {result.outcome}")
        if result.server_version_family:
            emit(f"  server version family : {result.server_version_family}")
        if result.database_charset:
            emit(f"  database charset      : {result.database_charset}")
        if result.database_collation:
            emit(f"  database collation    : {result.database_collation}")
        if result.tables_found is not None:
            emit(f"  base tables found     : {result.tables_found} "
                 f"(expected {EXPECTED_TABLE_COUNT} + alembic_version)")
        if result.alembic_head_matches is not None:
            emit(f"  alembic head matches  : {result.alembic_head_matches}")
        emit(f"  governed columns      : {result.governed_columns_checked} checked, "
             f"{result.governed_columns_deterministic} deterministic, "
             f"{result.governed_columns_at_risk} at risk")
        emit(f"  idempotency boundaries: {result.idempotency_boundaries_checked} checked, "
             f"{result.idempotency_boundaries_at_risk} at risk")
        if result.case_insensitive_collations:
            emit("  case-insensitive collations in use: "
                 + ", ".join(result.case_insensitive_collations))
        emit(f"  collision probe       : {result.collision_probe_status}")
        for table, count in sorted(result.collision_probe_group_counts.items()):
            emit(f"    {table}: {count} case-variant group(s)  [count only; no values]")
        for line in result.reasons:
            emit(f"  - {line}")

    for line in result.warnings:
        emit(f"  [warn] {line}")

    emit("")
    emit("Result contract")
    for line in result.as_lines():
        emit(f"  {line}")
    if verbose and result.queries_issued:
        emit("")
        emit("Read-only queries issued (names only):")
        for name in result.queries_issued:
            emit(f"  - {name}")
    emit("")
    emit("This tool performs no schema mutation, no data write, no migration, and no cleanup or")
    emit("delete path. Migration 013 is implemented in source control but is NOT executed by this")
    emit("tool; production execution remains a separately approved operation.")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="READ-ONLY production MySQL collation verification. Issues only hard-coded "
                    "SELECT/SHOW metadata queries; accepts no SQL from the caller.")
    parser.add_argument("--collision-probe", action="store_true",
                        help="Additionally run bounded COUNT-only aggregates on the idempotency "
                             "boundary tables. Emits counts only, never row values.")
    parser.add_argument("--verbose", action="store_true",
                        help="List the names of the read-only queries issued.")
    args = parser.parse_args(argv)

    result, code = run_verification(run_collision_probe=args.collision_probe)
    render(result, verbose=args.verbose)
    return code


if __name__ == "__main__":
    sys.exit(main())
