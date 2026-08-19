#!/usr/bin/env python3
"""Controlled runtime connectivity gate (Phase 50) — READ-ONLY, metadata only.

Proves that the Phase 49 runtime session path can reach the database using the **least-privileged
runtime credential**, and that that credential still holds exactly the Phase 48 grant posture —
without writing anything, without touching an application table, and without ever revealing a
connection detail.

What it does, in full:

* resolves the URL through :func:`peak.db.session.create_runtime_engine`, the same path the
  application uses — not a hand-built engine, so a regression in that path fails this gate;
* issues exactly two statements: ``SELECT 1`` and ``SHOW GRANTS FOR CURRENT_USER``;
* parses the grants in memory and emits **booleans only**.

What it can never do:

* read ``PEAK_DATABASE_URL`` or ``PEAK_PRODUCTION_DB_URL`` — both are scrubbed from this process's
  environment before anything else runs, so connectivity here *proves* the runtime variable alone
  was sufficient rather than merely asserting it;
* fall back to any other variable — a missing ``PEAK_RUNTIME_DATABASE_URL`` fails closed;
* mutate schema, write data, read/count/probe an application table, or invoke a controlled writer;
* print a DSN, host, username, database name, password, token, certificate path, environment value,
  raw grant line, or row value. Failures are reported by exception *type* only, because driver
  messages routinely embed the connection string.

Exit status:
  0  -> gate passed; runtime connectivity and grant posture are as required
  1  -> gate failed (connectivity, grants, or posture)
  2  -> refused to run (missing runtime URL, or unsafe invocation)

This tool enables nothing. Pointing application writers at production remains a separate, approved
phase.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

RUNTIME_URL_ENV = "PEAK_RUNTIME_DATABASE_URL"
#: Never read. Named here only so they can be removed from this process's environment.
SCRUBBED_ENV = ("PEAK_DATABASE_URL", "PEAK_PRODUCTION_DB_URL",
                "PEAK_PRODUCTION_DB_READONLY_CONFIRM")

# --------------------------------------------------------------------------- statement allowlist

#: **The complete set of statements this tool can issue.** Neither is built from input of any kind.
ALLOWED_STATEMENTS = {
    "connectivity": "SELECT 1",
    "grants": "SHOW GRANTS FOR CURRENT_USER",
}

#: Mutating verbs, matched as whole words. ``SHOW GRANTS`` is unaffected: ``\bgrant\b`` does not
#: match the plural ``GRANTS``.
FORBIDDEN_SQL_VERBS = (
    "insert", "update", "delete", "alter", "drop", "truncate", "create", "replace",
    "grant", "revoke", "lock", "unlock", "call", "load", "outfile", "infile",
    "rename", "commit", "rollback", "prepare", "execute", "handler",
)


class UnsafeQueryRefused(RuntimeError):
    """Raised when a statement is not provably one of the two hard-coded read-only statements."""


def assert_read_only(sql: str) -> str:
    """Refuse anything that is not one of the two allowlisted statements. Returns the statement.

    Four independent conditions, all required: identity with :data:`ALLOWED_STATEMENTS` (not
    resemblance), a ``SELECT``/``SHOW`` opener, no statement separator, and no mutating verb.
    """
    if not isinstance(sql, str) or not sql.strip():
        raise UnsafeQueryRefused("empty statement refused")
    if sql not in ALLOWED_STATEMENTS.values():
        raise UnsafeQueryRefused("statement is not one of the hard-coded allowed statements")
    head = sql.strip().split(None, 1)[0].upper()
    if head not in ("SELECT", "SHOW"):
        raise UnsafeQueryRefused("statement does not begin with SELECT or SHOW")
    if ";" in sql:
        raise UnsafeQueryRefused("statement separator refused")
    lowered = sql.lower()
    for verb in FORBIDDEN_SQL_VERBS:
        if re.search(rf"\b{re.escape(verb)}\b", lowered):
            raise UnsafeQueryRefused("statement contains a mutating verb")
    return sql


def safe_error(exc: BaseException) -> str:
    """Report a failure by exception *type* only. Driver messages embed the DSN."""
    return f"{type(exc).__name__} (detail withheld)"


# --------------------------------------------------------------------------- failure taxonomy

#: No failure yet, or none of the categories below.
CATEGORY_NONE = "none"
#: The runtime URL was not supplied, so nothing was attempted.
CATEGORY_URL_NOT_SET = "runtime_url_not_set"
#: The *local* interpreter lacks a required dependency (typically the database driver). This is a
#: workstation/interpreter problem, NOT evidence about production: nothing was ever attempted
#: against the database.
CATEGORY_LOCAL_DRIVER_UNAVAILABLE = "local_driver_unavailable"
#: A connection was genuinely attempted and did not succeed. This *is* evidence about production.
CATEGORY_CONNECTION_FAILED = "connection_failed"
#: A statement was refused by the read-only guard, or failed once issued.
CATEGORY_QUERY_FAILED = "query_failed"
CATEGORY_STATEMENT_REFUSED = "statement_refused"
#: The gate refused to run at all (unsafe invocation).
CATEGORY_REFUSED = "refused"

#: Production connectivity outcomes, kept distinct from `connectivity_succeeded` so a reader can
#: tell "we tried and failed" apart from "we never got far enough to try".
PROD_NOT_TESTED = "not_tested"
PROD_NOT_TESTED_DRIVER = "not_tested_due_to_local_driver_unavailable"
PROD_SUCCEEDED = "succeeded"
PROD_FAILED = "failed"

#: Static, literal remediation string. Never built from input, never an executed command.
RECOMMENDED_VENV_COMMAND = "make runtime-connectivity-gate PYTHON=.venv/bin/python"
RECOMMENDED_NONE = "none"


def is_local_dependency_failure(exc: BaseException) -> bool:
    """True when the failure is a missing *local* import, not a database problem.

    ``ModuleNotFoundError`` subclasses ``ImportError``; both mean this interpreter could not load a
    dependency, so no connection attempt ever reached the network.
    """
    return isinstance(exc, ImportError)


# --------------------------------------------------------------------------- grant policy

REQUIRED_GRANTS = ("SELECT", "INSERT")

FORBIDDEN_GRANTS = (
    "UPDATE", "DELETE", "CREATE", "ALTER", "DROP", "INDEX", "REFERENCES",
    "CREATE TEMPORARY TABLES", "LOCK TABLES", "EXECUTE", "CREATE VIEW", "SHOW VIEW",
    "CREATE ROUTINE", "ALTER ROUTINE", "EVENT", "TRIGGER", "PROCESS", "RELOAD", "FILE",
    "SHUTDOWN", "SUPER", "CREATE USER", "ROLE_ADMIN", "CREATE TABLESPACE",
    "REPLICATION SLAVE", "REPLICATION CLIENT", "REPLICATION_APPLIER",
)

#: Global privileges that carry no authority and may appear at ``*.*`` without failing the gate.
HARMLESS_GLOBAL = {"USAGE"}

_GRANT_RE = re.compile(r"^GRANT\s+(.*?)\s+ON\s+(\S+)\s+TO\s", re.IGNORECASE | re.DOTALL)


def parse_grants(lines):
    """Parse ``SHOW GRANTS`` output into a sanitized structure. Returns booleans and priv names.

    Only privilege *names* and the global/schema scope distinction leave this function. The user,
    host, and database names in each grant line are discarded and never returned or logged.
    """
    schema_privs, global_privs = set(), set()
    all_privileges = global_all = grant_option = False
    parsed = 0

    for line in lines:
        text = str(line)
        if text.upper().startswith("GRANT ") and " ON " not in text.upper():
            continue                      # role-style grant: GRANT `role` TO `user`
        match = _GRANT_RE.match(text)
        if not match:
            continue
        parsed += 1
        priv_text, scope = match.group(1).upper(), match.group(2)
        is_global = scope.replace("`", "").strip().startswith("*.*")
        names = {re.sub(r"\s*\(.*\)$", "", p.strip()).strip()
                 for p in re.split(r",\s*(?![^(]*\))", priv_text)}
        if "ALL PRIVILEGES" in names or "ALL" in names:
            all_privileges = True
            global_all = global_all or is_global
        if "GRANT OPTION" in names or "WITH GRANT OPTION" in text.upper():
            grant_option = True
        (global_privs if is_global else schema_privs).update(names)

    effective = schema_privs | global_privs
    held = lambda priv: priv in effective or all_privileges   # noqa: E731
    return {
        "parsed": parsed,
        "missing_required": [p for p in REQUIRED_GRANTS if not held(p)],
        "excess": [p for p in FORBIDDEN_GRANTS if held(p)],
        "all_privileges": all_privileges,
        "global_all": global_all,
        "grant_option": grant_option,
        "global_beyond_usage": sorted(global_privs - HARMLESS_GLOBAL - {"GRANT OPTION"}),
    }


# --------------------------------------------------------------------------- result contract


class GateResult:
    """Every field is a boolean or a small integer. Nothing here can identify a deployment."""

    FIELDS = (
        "runtime_url_present", "used_runtime_session_path", "fallback_to_migration_url",
        "connectivity_succeeded", "grants_checked", "required_grants_present",
        "excess_grants_present", "global_privileges_present", "grant_option_present",
        "schema_mutation_made", "data_write_made", "app_table_read_made", "writer_invoked",
        "secrets_printed", "ready_for_later_writer_enablement",
        "failure_category", "failure_exception_type", "production_connectivity_result",
        "recommended_command",
    )

    def __init__(self) -> None:
        self.runtime_url_present = False
        self.used_runtime_session_path = False
        self.fallback_to_migration_url = False
        self.connectivity_succeeded = False
        self.grants_checked = False
        self.required_grants_present = False
        self.excess_grants_present = False
        self.global_privileges_present = False
        self.grant_option_present = False
        # Structural invariants: this tool has no code path that could set these True.
        self.schema_mutation_made = False
        self.data_write_made = False
        self.app_table_read_made = False
        self.writer_invoked = False
        self.secrets_printed = False
        self.ready_for_later_writer_enablement = False
        # Failure taxonomy. Every value is drawn from the constants above — never from an
        # exception message, and never from anything a driver produced.
        self.failure_category = CATEGORY_NONE
        self.failure_exception_type = CATEGORY_NONE
        self.production_connectivity_result = PROD_NOT_TESTED
        self.recommended_command = RECOMMENDED_NONE
        self.statements_issued = 0
        self.notes: list = []

    def emit(self) -> None:
        for field in self.FIELDS:
            print(f"{field}={getattr(self, field)}")
        print(f"statements_issued={self.statements_issued}")
        for note in self.notes:
            print(f"note={note}")


# --------------------------------------------------------------------------- gate


def _scrub_environment() -> None:
    """Remove the other roles' variables from *this process* before anything else runs.

    Connectivity after this point proves the runtime variable alone was sufficient. It also makes
    an accidental fallback impossible rather than merely forbidden. The parent shell is unaffected.
    """
    for name in SCRUBBED_ENV:
        os.environ.pop(name, None)


def _fake_connection():
    """A connection stand-in for ``--self-test``. Serves fixed, credential-free rows."""

    class _Result:
        def __init__(self, rows):
            self._rows = rows

        def fetchall(self):
            return self._rows

        def scalar(self):
            return self._rows[0][0] if self._rows else None

    class _Fake:
        def __init__(self):
            self.executed = []

        def execute(self, clause):
            sql = str(clause)
            self.executed.append(sql)
            if sql == ALLOWED_STATEMENTS["connectivity"]:
                return _Result([(1,)])
            return _Result([("GRANT SELECT, INSERT ON `example_schema`.* TO `example_user`@`%`",)])

    return _Fake()


def _record_setup_failure(result: "GateResult", exc: BaseException, note_prefix: str) -> None:
    """Classify a failure that occurred *before* any statement was issued.

    The distinction that matters: a missing local dependency means no connection attempt ever left
    this machine, so it is not evidence about production and must not be read as one. Only the
    exception *type* is recorded — never its message, which can embed the connection string.
    """
    result.failure_exception_type = type(exc).__name__
    if is_local_dependency_failure(exc):
        result.failure_category = CATEGORY_LOCAL_DRIVER_UNAVAILABLE
        result.production_connectivity_result = PROD_NOT_TESTED_DRIVER
        result.recommended_command = RECOMMENDED_VENV_COMMAND
        result.notes.append("local_interpreter_lacks_a_required_dependency_no_connection_attempted")
        result.notes.append("this_is_not_evidence_of_a_production_connectivity_problem")
    else:
        result.failure_category = CATEGORY_CONNECTION_FAILED
        result.production_connectivity_result = PROD_FAILED
    result.notes.append(f"{note_prefix}:{safe_error(exc)}")


def run_gate(self_test: bool = False) -> "tuple[GateResult, int]":
    result = GateResult()
    _scrub_environment()

    if self_test:
        # Refuse if a real runtime URL is present, so the mocked path can never stand in for a
        # live run — the flag is CLI-only and cannot be switched on by the environment.
        if os.environ.get(RUNTIME_URL_ENV):
            result.failure_category = CATEGORY_REFUSED
            result.production_connectivity_result = PROD_NOT_TESTED
            result.notes.append("self_test_refused_runtime_url_present")
            return result, 2
        connection = _fake_connection()
        result.runtime_url_present = False
        result.used_runtime_session_path = False
        result.notes.append("self_test_mode_no_database_contacted")
    else:
        if not os.environ.get(RUNTIME_URL_ENV):
            result.failure_category = CATEGORY_URL_NOT_SET
            result.production_connectivity_result = PROD_NOT_TESTED
            result.notes.append(f"{RUNTIME_URL_ENV}_not_set")
            return result, 2
        result.runtime_url_present = True
        try:
            from peak.db.session import create_runtime_engine
        except Exception as exc:                                    # noqa: BLE001
            _record_setup_failure(result, exc, "runtime_session_import_failed")
            return result, 1
        result.used_runtime_session_path = True
        try:
            engine = create_runtime_engine()
            connection_ctx = engine.connect()
        except Exception as exc:                                    # noqa: BLE001
            _record_setup_failure(result, exc, "connect_failed")
            return result, 1

    try:
        from sqlalchemy import text
        wrap = text
    except ImportError:
        wrap = lambda s: s                                          # noqa: E731

    def _execute(conn, key):
        stmt = assert_read_only(ALLOWED_STATEMENTS[key])
        result.statements_issued += 1
        return conn.execute(wrap(stmt) if not self_test else stmt)

    try:
        if self_test:
            conn = connection
            probe = _execute(conn, "connectivity").scalar()
            result.connectivity_succeeded = probe == 1
            rows = [r[0] for r in _execute(conn, "grants").fetchall()]
        else:
            with connection_ctx as conn:
                probe = _execute(conn, "connectivity").scalar()
                result.connectivity_succeeded = probe == 1
                rows = [r[0] for r in _execute(conn, "grants").fetchall()]
    except UnsafeQueryRefused as exc:
        result.failure_category = CATEGORY_STATEMENT_REFUSED
        result.failure_exception_type = type(exc).__name__
        result.production_connectivity_result = PROD_FAILED
        result.notes.append(f"statement_refused:{exc}")
        return result, 1
    except Exception as exc:                                        # noqa: BLE001
        result.failure_category = CATEGORY_QUERY_FAILED
        result.failure_exception_type = type(exc).__name__
        result.production_connectivity_result = PROD_FAILED
        result.notes.append(f"query_failed:{safe_error(exc)}")
        return result, 1

    parsed = parse_grants(rows)
    result.grants_checked = parsed["parsed"] > 0
    result.required_grants_present = not parsed["missing_required"]
    result.excess_grants_present = bool(parsed["excess"]) or parsed["all_privileges"]
    result.global_privileges_present = bool(parsed["global_beyond_usage"]) or parsed["global_all"]
    result.grant_option_present = parsed["grant_option"]

    # Privilege *names* are policy vocabulary from this file, not deployment detail.
    if parsed["missing_required"]:
        result.notes.append("missing_required=" + ",".join(parsed["missing_required"]))
    if parsed["excess"]:
        result.notes.append("excess=" + ",".join(parsed["excess"]))

    ready = (result.connectivity_succeeded and result.grants_checked
             and result.required_grants_present and not result.excess_grants_present
             and not result.global_privileges_present and not result.grant_option_present
             and not result.fallback_to_migration_url)
    result.ready_for_later_writer_enablement = ready and not self_test
    if result.connectivity_succeeded and not self_test:
        result.production_connectivity_result = PROD_SUCCEEDED
    return result, (0 if ready else 1)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Controlled runtime connectivity gate (read-only, metadata only).")
    parser.add_argument(
        "--self-test", action="store_true",
        help="Exercise the parsing and policy logic against a fixed in-memory stand-in. "
             "Contacts no database, and refuses to run if a runtime URL is set.")
    args = parser.parse_args(argv)

    print("Peak controlled runtime connectivity gate — READ-ONLY, metadata only")
    print("=" * 62)
    result, code = run_gate(self_test=args.self_test)
    result.emit()
    print("=" * 62)
    print("RESULT: " + ("PASS" if code == 0 else ("REFUSED" if code == 2 else "FAIL")))
    if result.failure_category == CATEGORY_LOCAL_DRIVER_UNAVAILABLE:
        # The failure this line exists for was previously reported only as
        # "connect_failed:ModuleNotFoundError", which reads like a production outage.
        print("CAUSE: the selected local Python interpreter lacks a required database "
              "dependency. No connection was attempted, so this says nothing about production.")
        print(f"FIX:   {RECOMMENDED_VENV_COMMAND}")
    print("This tool performs no schema mutation, no data write, no application-table read, and "
          "no writer execution. Enabling application writers remains a separate approved phase.")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
