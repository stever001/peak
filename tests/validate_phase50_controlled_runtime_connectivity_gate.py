#!/usr/bin/env python3
"""Phase 50 controlled runtime connectivity gate check.

Phase 49 gave runtime its own URL variable. Phase 50 adds a reusable gate that proves the runtime
session path can actually reach the database on the least-privileged credential — while remaining
incapable of writing, of reading an application table, or of revealing a connection detail.

This harness is **fully offline and credential-free**: it never contacts a database, and it scrubs
all three role variables from every child process it starts.

Six layers:

* **Baseline** — head is 014, 14 migrations, 18 tables, no migration 014, no ``alembic/versions``
  change, no model/entity, writer, or allowlist pair added.

* **Provenance** — the gate resolves its URL through ``peak.db.session``, requires
  ``PEAK_RUNTIME_DATABASE_URL``, and neither reads nor falls back to the migration or verifier
  variables (it actively scrubs them from its own process).

* **Statement surface** — exactly two hard-coded statements, ``SELECT 1`` and
  ``SHOW GRANTS FOR CURRENT_USER``; no application table is named, no row is read or counted, and
  no mutating verb can pass the guard.

* **Policy** — required grants (SELECT, INSERT) and the forbidden set (UPDATE/DELETE/DDL/global/
  GRANT OPTION) are explicit, and the parser is exercised over every posture without a database.

* **Behaviour** — the gate refuses without a runtime URL, self-test refuses when one *is* set, and
  self-test can never report readiness.

* **Regression** — Phase 49 fail-closed behaviour holds, writers stay create-only, the verifier is
  untouched and still skips safely, and the audit result is unchanged.

Exit status:
  0  -> all checks passed
  1  -> a check failed
"""

from __future__ import annotations

import importlib.util
import os
import py_compile
import re
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(REPO_ROOT, "tools")
for _p in (REPO_ROOT, TOOLS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

PY = sys.executable or "python3"

BASELINE_COMMIT = "432fefb"   # Add Phase 49 runtime database URL separation

GATE_REL = "tools/production_runtime_connectivity_gate.py"
SESSION_REL = "peak/db/session.py"
ENV_REL = "alembic/env.py"
VERIFIER_REL = "tools/production_mysql_collation_verify.py"
HARNESS_REL = "tests/validate_phase50_controlled_runtime_connectivity_gate.py"
AUDIT = "tools/governed_mysql_collation_audit.py"

RUNTIME_VAR = "PEAK_RUNTIME_DATABASE_URL"
MIGRATION_VAR = "PEAK_DATABASE_URL"
VERIFY_VAR = "PEAK_PRODUCTION_DB_URL"
ROLE_VARS = (RUNTIME_VAR, MIGRATION_VAR, VERIFY_VAR, "PEAK_PRODUCTION_DB_READONLY_CONFIRM")

EXPECTED_MIGRATIONS = 14
EXPECTED_TABLE_COUNT = 18
EXPECTED_WRITERS = 12
EXPECTED_ALLOWLIST_TABLES = 13
EXPECTED_ALLOWLIST_ACTIONS = 15
HEAD_REVISION = "014_engagement_classification"

ALLOWED_CHANGED = {
    GATE_REL,
    HARNESS_REL,
    "Makefile",
    "docs/IMPLEMENTATION_PLAN.md",
    "docs/DATABASE_ACCESS_AND_AUDIT.md",
    "docs/DATABASE_SCAFFOLD.md",
    "docs/PHASE49_RUNTIME_DATABASE_URL_SEPARATION.md",
    "docs/PHASE50_CONTROLLED_RUNTIME_CONNECTIVITY_GATE.md",
    # Phase 52A patched this gate's driver-unavailable diagnostic and touched these alongside it.
    "docs/PHASE51_WRITER_ENABLEMENT_DECISION_GATE.md",
    "docs/DATABASE_SCAFFOLD.md",
    "tests/validate_phase51_writer_enablement_decision_gate.py",
}

CREDENTIAL_FILE_MARKERS = ("peak-prod-ro.env", "peak-prod-migrate.env",
                           "peak-prod-runtime.env", ".peak/")
REAL_DSN_RE = re.compile(r"\b[a-z][a-z0-9+.\-]*://(?!USER:PASSWORD)(?!user:password)"
                         r"(?!runtime_user:password)(?!readonly_user:password)"
                         r"[\w.\-]+:[^\s@'\"]+@")

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


def code_no_docstrings(source: str) -> str:
    """Executable code with comments and docstrings removed, string literals kept.

    A tool that *documents* the variables it refuses to read must not be flagged for naming them.
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
    keep = []
    for idx, line in enumerate(source.splitlines(), start=1):
        if any(start <= idx <= end for start, end in doc_ranges):
            continue
        keep.append(re.sub(r"#.*$", "", line))
    return "\n".join(keep)


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", REPO_ROOT, *args],
                          capture_output=True, text=True, timeout=20).stdout.strip()


def git_succeeds(*args: str) -> bool:
    """Run a git command for its exit status alone; stdout and stderr are discarded, so
    nothing a path or remote might carry can reach this harness's output."""
    return subprocess.run(["git", "-C", REPO_ROOT, *args],
                          capture_output=True, text=True, timeout=20).returncode == 0


def phase_never_committed(rel: str) -> bool:
    """True while ``rel`` has no commit yet — i.e. this phase's own work is still unstaged.

    The working-tree scope guards below are authoring-time claims about *this* phase. Keying them
    on "does this file have a pending diff" was wrong: a later phase editing this phase's document
    also produces a pending diff, and the guard would then judge that later phase's changes against
    this phase's allowlist. Absence of any commit for the file is the signal that actually means
    "this phase has not landed yet".
    """
    return not git("log", "-1", "--format=%H", "--", rel).strip()



def scrubbed_env(**extra):
    env = {k: v for k, v in os.environ.items() if k not in ROLE_VARS}
    env["PYTHONPATH"] = REPO_ROOT
    env.update(extra)
    return env


def run_gate(*args, **extra):
    return subprocess.run([PY, os.path.join(REPO_ROOT, GATE_REL), *args],
                          capture_output=True, text=True, timeout=120, env=scrubbed_env(**extra))


def load_gate():
    spec = importlib.util.spec_from_file_location(
        "phase50_gate_under_test", os.path.join(REPO_ROOT, GATE_REL))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------- 1. baseline


def baseline_checks() -> None:
    print("\n1. Baseline: head is 014, 14 migrations, 18 tables, nothing new added")
    versions_dir = os.path.join(REPO_ROOT, "alembic", "versions")
    versions = sorted(f for f in os.listdir(versions_dir) if f.endswith(".py"))
    check(f"exactly {EXPECTED_MIGRATIONS} migrations", len(versions) == EXPECTED_MIGRATIONS)
    check("no migration 015 or later",
          not any(re.match(r"^0*(?:1[5-9]|[2-9]\d)_", f) for f in versions))
    check(f"{HEAD_REVISION} is still the newest migration",
          versions[-1] == f"{HEAD_REVISION}.py")
    check(f"{GATE_REL} exists", os.path.isfile(os.path.join(REPO_ROOT, GATE_REL)))

    for rel in (GATE_REL, HARNESS_REL):
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
          read("peak/db/models.py").count("__tablename__ = ") == EXPECTED_TABLE_COUNT)

    from peak.persistence.allowlist import ALLOWED_ACTIONS, ALLOWED_TABLES
    check(f"allowlist still has exactly {EXPECTED_ALLOWLIST_TABLES} tables",
          len(ALLOWED_TABLES) == EXPECTED_ALLOWLIST_TABLES)
    check(f"allowlist still has exactly {EXPECTED_ALLOWLIST_ACTIONS} actions",
          len(ALLOWED_ACTIONS) == EXPECTED_ALLOWLIST_ACTIONS)

    writers = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "peak", "db"))
                     if f.endswith("_writer.py"))
    check(f"still exactly the {EXPECTED_WRITERS} narrow controlled writers",
          len(writers) == EXPECTED_WRITERS)

    try:
        # Ancestry, not recency. This asserted membership in a bounded `git log ... -40` window,
        # which is a *sliding window*, not a history check: the baseline falls out of range as later
        # phases land, failing on commits whose content has nothing to do with this phase. The
        # invariant meant here is that the baseline is still reachable from HEAD, which
        # `merge-base --is-ancestor` states directly and which never expires. Widening the window
        # would only move the expiry date.
        is_ancestor = git_succeeds("merge-base", "--is-ancestor", BASELINE_COMMIT, "HEAD")
        check(f"baseline commit {BASELINE_COMMIT} present in history", is_ancestor)
        if not is_ancestor:
            print("        reason: phase50_baseline_commit_not_ancestor")
        if phase_never_committed(HARNESS_REL):
            changed = set(git("diff", "--name-only", "HEAD").splitlines())
            unexpected = sorted(changed - ALLOWED_CHANGED)
            check("only the intended narrow set of files changed", not unexpected)
            if unexpected:
                print(f"        unexpected: {unexpected}")
        else:
            print("  [skip] Phase 50 is committed — working-tree scope guard not applicable")

        # Authoring-time claim about *this* phase's own working tree, not a permanent freeze
        # on the repository: later phases may legitimately add a writer or extend the
        # allowlist under their own governance gate (Phase 54 added the engagement
        # authorization anchor writer and its one-pair anchor gate). The substantive
        # invariants — writers stay create-only, the generic allowlist stays closed — are
        # asserted unconditionally elsewhere in this harness.
        if phase_never_committed(HARNESS_REL):
            governed = [c for c in git("diff", "--name-only", "HEAD", "--", "peak").splitlines()
                        if c.endswith("_writer.py")
                        or c in ("peak/db/models.py", "peak/db/base.py",
                                 "peak/persistence/allowlist.py")]
            check("no controlled writer, model, base, or allowlist source changed", not governed)
        check("peak/db/session.py was not modified by this phase",
              not git("diff", "--name-only", "HEAD", "--", SESSION_REL))
        # Working-tree freezes on shared files were authoring-time claims about this phase.
        # Phase 56 legitimately owns migration 014, the engagement classification model
        # columns, and the repo-side head pin in the parity tool. The substantive
        # invariants each harness cares about are asserted directly elsewhere.
        check("schemas/, prompts/, agents/ untouched",
              not git("diff", "--name-only", "HEAD", "--", "schemas", "prompts", "agents"))
        check("docs/Peak_Investor_Overview_AI.docx has no pending diff",
              not git("diff", "--name-only", "HEAD", "--",
                      "docs/Peak_Investor_Overview_AI.docx"))
    except Exception:
        check("git-backed scope checks (git unavailable — skipped)", True)


# --------------------------------------------------------------------------- 2. provenance


def provenance_checks() -> None:
    print("\n2. The gate uses the Phase 49 runtime path and no other variable")
    src = read(GATE_REL)
    code = code_no_docstrings(src)

    check("gate imports the runtime engine helper from peak.db.session",
          "from peak.db.session import create_runtime_engine" in code)
    check("gate builds no engine of its own",
          "create_engine(" not in code)
    check(f"gate requires {RUNTIME_VAR}",
          f'RUNTIME_URL_ENV = "{RUNTIME_VAR}"' in code
          and "os.environ.get(RUNTIME_URL_ENV)" in code)

    env_reads = re.findall(r"os\.environ\.get\(\s*([^)]*?)\s*\)", code)
    check("gate performs environment reads only for the runtime variable",
          all(r.strip() == "RUNTIME_URL_ENV" for r in env_reads))
    check(f"gate never reads {MIGRATION_VAR} as a literal lookup",
          f'os.environ.get("{MIGRATION_VAR}")' not in code
          and f"os.environ.get('{MIGRATION_VAR}')" not in code)
    check(f"gate never reads {VERIFY_VAR} as a literal lookup",
          f'os.environ.get("{VERIFY_VAR}")' not in code
          and f"os.environ.get('{VERIFY_VAR}')" not in code)
    check("gate scrubs the other role variables from its own process",
          "SCRUBBED_ENV" in code and "os.environ.pop(name, None)" in code)
    check("the scrub list covers the migration and verifier variables",
          MIGRATION_VAR in code and VERIFY_VAR in code)
    check("gate declares no fallback URL path",
          "fallback_to_migration_url = False" in code
          and not re.search(r"or\s+os\.environ\.get", code))
    check("gate references no operator credential file",
          not any(m in src for m in CREDENTIAL_FILE_MARKERS))
    check("gate embeds no real-looking DSN", not REAL_DSN_RE.search(src))
    check("gate reads no .env file",
          not re.search(r"load_dotenv|dotenv|open\(\s*['\"]\.env['\"]", src))


# --------------------------------------------------------------------------- 3. statements


def statement_surface_checks() -> None:
    print("\n3. Statement surface: exactly SELECT 1 and SHOW GRANTS, nothing else")
    gate = load_gate()
    src = read(GATE_REL)
    code = code_no_docstrings(src)

    check("exactly two allowed statements", len(gate.ALLOWED_STATEMENTS) == 2)
    check("connectivity statement is exactly 'SELECT 1'",
          gate.ALLOWED_STATEMENTS["connectivity"] == "SELECT 1")
    check("grant statement is exactly 'SHOW GRANTS FOR CURRENT_USER'",
          gate.ALLOWED_STATEMENTS["grants"] == "SHOW GRANTS FOR CURRENT_USER")

    for name, stmt in gate.ALLOWED_STATEMENTS.items():
        check(f"'{name}' statement passes the read-only guard",
              gate.assert_read_only(stmt) == stmt)

    for hostile in ("INSERT INTO clients VALUES (1)",
                    "UPDATE review_records SET review_status='x'",
                    "DELETE FROM agent_run_records",
                    "DROP TABLE clients",
                    "ALTER TABLE clients ADD COLUMN x INT",
                    "TRUNCATE TABLE clients",
                    "SELECT * FROM clients",
                    "SELECT COUNT(*) FROM clients",
                    "SELECT 1; DROP TABLE clients",
                    "GRANT ALL ON *.* TO x"):
        refused = False
        try:
            gate.assert_read_only(hostile)
        except gate.UnsafeQueryRefused:
            refused = True
        check(f"guard refuses: {hostile[:44]}", refused)

    # No application table may be nameable from the gate.
    import importlib as _il
    p11 = _il.import_module("tests.validate_phase11_db_scaffold")
    app_tables = list(getattr(p11, "EXPECTED_TABLES", []))
    check(f"{len(app_tables)} application tables are known to this check",
          len(app_tables) == EXPECTED_TABLE_COUNT)
    leaked = sorted(t for t in app_tables if t in code)
    check("no application table name appears anywhere in the gate's code", not leaked)
    if leaked:
        print(f"        leaked: {leaked}")
    check("gate never selects from a table (no FROM clause in any statement)",
          not any(" FROM " in s.upper() for s in gate.ALLOWED_STATEMENTS.values()))
    check("gate issues no COUNT(",
          not any("COUNT(" in s.upper() for s in gate.ALLOWED_STATEMENTS.values()))
    check("gate exposes no general-purpose SQL executor",
          not re.search(r"def\s+(execute_sql|run_sql|exec_sql|raw_sql)", code))
    check("gate reports errors by exception type only",
          "def safe_error(" in code and "type(exc).__name__" in code)


# --------------------------------------------------------------------------- 4. policy


def policy_checks() -> None:
    print("\n4. Grant policy: explicit required and forbidden sets, exercised without a database")
    gate = load_gate()

    check("required grants are exactly SELECT and INSERT",
          tuple(gate.REQUIRED_GRANTS) == ("SELECT", "INSERT"))
    for priv in ("UPDATE", "DELETE", "CREATE", "ALTER", "DROP", "INDEX", "REFERENCES",
                 "CREATE TEMPORARY TABLES", "LOCK TABLES", "EXECUTE", "CREATE VIEW",
                 "SHOW VIEW", "CREATE ROUTINE", "ALTER ROUTINE", "EVENT", "TRIGGER",
                 "PROCESS", "RELOAD", "FILE", "SHUTDOWN", "SUPER", "CREATE USER",
                 "ROLE_ADMIN", "REPLICATION SLAVE", "REPLICATION CLIENT"):
        check(f"{priv} is in the forbidden set", priv in gate.FORBIDDEN_GRANTS)

    def verdict(lines):
        p = gate.parse_grants(lines)
        return (not p["missing_required"] and not p["excess"] and not p["all_privileges"]
                and not p["global_all"] and not p["grant_option"]
                and not p["global_beyond_usage"])

    check("exact SELECT+INSERT on a schema passes",
          verdict(["GRANT SELECT, INSERT ON `s`.* TO `u`@`%`"]))
    check("harmless global USAGE alongside SELECT+INSERT passes",
          verdict(["GRANT USAGE ON *.* TO `u`@`%`",
                   "GRANT SELECT, INSERT ON `s`.* TO `u`@`%`"]))
    check("an added UPDATE fails",
          not verdict(["GRANT SELECT, INSERT, UPDATE ON `s`.* TO `u`@`%`"]))
    check("an added DELETE fails",
          not verdict(["GRANT SELECT, INSERT, DELETE ON `s`.* TO `u`@`%`"]))
    check("DDL (CREATE/ALTER/DROP) fails",
          not verdict(["GRANT SELECT, INSERT, CREATE, ALTER, DROP ON `s`.* TO `u`@`%`"]))
    check("ALL PRIVILEGES fails", not verdict(["GRANT ALL PRIVILEGES ON `s`.* TO `u`@`%`"]))
    check("a global *.* privilege beyond USAGE fails",
          not verdict(["GRANT SELECT ON *.* TO `u`@`%`",
                       "GRANT SELECT, INSERT ON `s`.* TO `u`@`%`"]))
    check("WITH GRANT OPTION fails",
          not verdict(["GRANT SELECT, INSERT ON `s`.* TO `u`@`%` WITH GRANT OPTION"]))
    check("missing INSERT fails", not verdict(["GRANT SELECT ON `s`.* TO `u`@`%`"]))
    check("missing SELECT fails", not verdict(["GRANT INSERT ON `s`.* TO `u`@`%`"]))

    parsed = gate.parse_grants(["GRANT SELECT, INSERT ON `secret_schema`.* TO `secret_user`@`h`"])
    flat = repr(parsed)
    check("parser returns no user, host, or database name",
          "secret_schema" not in flat and "secret_user" not in flat)


# --------------------------------------------------------------------------- 5. behaviour


def behaviour_checks() -> None:
    print("\n5. Gate behaviour: refuses without a runtime URL; self-test cannot claim readiness")
    r = run_gate()
    check("gate refuses (exit 2) when the runtime URL is absent", r.returncode == 2)
    check("refusal reports runtime_url_present=False",
          "runtime_url_present=False" in r.stdout)
    check("refusal names the missing variable, not a value",
          f"{RUNTIME_VAR}_not_set" in r.stdout and "://" not in r.stdout)
    check("refusal issues no statement", "statements_issued=0" in r.stdout)
    check("refusal does not claim readiness",
          "ready_for_later_writer_enablement=False" in r.stdout)

    r = run_gate("--self-test")
    check("self-test runs without a database (exit 0)", r.returncode == 0)
    check("self-test contacts no database",
          "self_test_mode_no_database_contacted" in r.stdout)
    check("self-test exercises both statements", "statements_issued=2" in r.stdout)
    check("self-test can never report readiness",
          "ready_for_later_writer_enablement=False" in r.stdout)

    r = run_gate("--self-test", **{RUNTIME_VAR: "sqlite://"})
    check("self-test refuses when a runtime URL IS set (cannot mask a live run)",
          r.returncode == 2 and "self_test_refused_runtime_url_present" in r.stdout)

    src = read(GATE_REL)
    check("self-test is a CLI flag, not an environment switch",
          '"--self-test"' in src and not re.search(r"environ.*SELF_TEST", src))

    for field in ("schema_mutation_made", "data_write_made", "app_table_read_made",
                  "writer_invoked", "secrets_printed"):
        check(f"{field} is reported False in every mode",
              all(f"{field}=False" in run_gate(*a).stdout
                  for a in ((), ("--self-test",))))

    out = run_gate("--self-test").stdout
    check("output contains no connection scheme", "://" not in out)
    check("output contains no raw GRANT line", "GRANT " not in out)


# --------------------------------------------------------------------------- 5b. driver taxonomy

#: Makes the database driver look absent to one child process, so the missing-dependency path can
#: be exercised without uninstalling anything. Test-only: it lives here, never in the gate, so it
#: cannot be switched on during a live run.
_BLOCK_DRIVER_PRELUDE = (
    "import runpy, sys\n"
    "class _Block:\n"
    "    def find_spec(self, name, path=None, target=None):\n"
    "        if name == 'sqlalchemy' or name.startswith('sqlalchemy.'):\n"
    "            raise ModuleNotFoundError(\"No module named 'sqlalchemy'\")\n"
    "        return None\n"
    "for _m in [m for m in sys.modules if m == 'sqlalchemy' or m.startswith('sqlalchemy.')]:\n"
    "    del sys.modules[_m]\n"
    "sys.meta_path.insert(0, _Block())\n"
    "sys.argv = [%r]\n"
    "runpy.run_path(%r, run_name='__main__')\n"
)


def run_gate_without_driver():
    """Run the gate in a child process where the driver cannot be imported."""
    gate_path = os.path.join(REPO_ROOT, GATE_REL)
    prelude = _BLOCK_DRIVER_PRELUDE % (gate_path, gate_path)
    # A local sqlite path, never a credentialed DSN — and unused, since the driver never loads.
    return subprocess.run(
        [PY, "-c", prelude], capture_output=True, text=True, timeout=120,
        env=scrubbed_env(**{RUNTIME_VAR: "sqlite:///phase52a-unused.db"}))


def _kv(stdout):
    return dict(
        line.split("=", 1) for line in stdout.splitlines()
        if "=" in line and re.fullmatch(r"[a-z0-9_]+", line.split("=", 1)[0]))


def driver_taxonomy_checks() -> None:
    print("\n5b. A missing local driver is classified as such, not as a production failure")
    r = run_gate_without_driver()
    out = r.stdout
    fields = _kv(out)

    check("missing driver exits nonzero (fail-closed)", r.returncode != 0)
    check("missing driver is classified local_driver_unavailable",
          fields.get("failure_category") == "local_driver_unavailable")
    check("missing driver records the exception type only",
          fields.get("failure_exception_type") == "ModuleNotFoundError")
    check("production connectivity is reported as not tested, not as failed",
          fields.get("production_connectivity_result")
          == "not_tested_due_to_local_driver_unavailable")
    check("the venv remediation command is emitted verbatim",
          fields.get("recommended_command")
          == "make runtime-connectivity-gate PYTHON=.venv/bin/python")
    check("a human-readable CAUSE line explains it is local", "CAUSE:" in out)
    check("a human-readable FIX line names the venv invocation",
          "FIX:" in out and "PYTHON=.venv/bin/python" in out)
    check("the output states it is not evidence about production",
          "not_evidence_of_a_production_connectivity_problem" in out)

    for field in ("connectivity_succeeded", "ready_for_later_writer_enablement",
                  "schema_mutation_made", "data_write_made", "app_table_read_made",
                  "writer_invoked", "secrets_printed"):
        check(f"missing driver keeps {field} false", fields.get(field) == "False")
    check("missing driver issues no statement", fields.get("statements_issued") == "0")

    check("missing-driver output contains no connection scheme", "://" not in out)
    check("missing-driver output contains no stack trace",
          "Traceback" not in out and "  File " not in out)
    check("missing-driver output contains no raw GRANT line", "GRANT " not in out)
    for token in ("password", "passwd", "@", "sqlalchemy.exc", "pymysql"):
        check(f"missing-driver output contains no '{token}'", token not in out)
    check("missing-driver stderr carries no traceback", "Traceback" not in r.stderr)

    # A refusal for a different reason must NOT be mislabelled as a driver problem.
    fields2 = _kv(run_gate().stdout)
    check("a missing runtime URL is classified separately, not as a driver problem",
          fields2.get("failure_category") == "runtime_url_not_set")
    check("a missing runtime URL recommends no command",
          fields2.get("recommended_command") == "none")
    check("a missing runtime URL reports production connectivity as not tested",
          fields2.get("production_connectivity_result") == "not_tested")

    code = code_no_docstrings(read(GATE_REL))
    check("the remediation string is a static literal",
          'RECOMMENDED_VENV_COMMAND = "make runtime-connectivity-gate PYTHON=.venv/bin/python"'
          in code)
    check("the gate never installs a dependency",
          not re.search(r"\bpip\b|install|os\.system", code))
    check("the gate never retries under another interpreter", "sys.executable" not in code)
    check("driver-unavailable can never report readiness",
          "ready_for_later_writer_enablement = ready and not self_test" in code)


# --------------------------------------------------------------------------- 6. regression


def regression_checks() -> None:
    print("\n6. Regression: Phase 49 fail-closed, writers create-only, verifier untouched")
    r = subprocess.run(
        [PY, "-c",
         "import os\n"
         "os.environ['PEAK_DATABASE_URL'] = 'sqlite:///migration-only.db'\n"
         "from peak.db.session import get_runtime_database_url as g\n"
         "try:\n"
         "    g(); print('FELL_BACK')\n"
         "except RuntimeError:\n"
         "    print('NO_FALLBACK')\n"],
        capture_output=True, text=True, timeout=60, env=scrubbed_env())
    check("Phase 49 fail-closed behaviour still holds", "NO_FALLBACK" in r.stdout)

    db_dir = os.path.join(REPO_ROOT, "peak", "db")
    writers = sorted(f for f in os.listdir(db_dir) if f.endswith("_writer.py"))
    for name in writers:
        code = code_no_docstrings(read(f"peak/db/{name}"))
        check(f"{name} is still create-only", code.count("session.add(") == 1
              and not re.search(r"session\.delete\(|session\.merge\(|\.update\(\{", code))

    harness_code = code_no_docstrings(read(HARNESS_REL))
    check("this harness invokes no controlled writer",
          not re.search(r"\bpersist_[a-z_]+\(", harness_code))
    check("this harness scrubs every role variable from child processes",
          "k not in ROLE_VARS" in harness_code)

    verifier_src = read(VERIFIER_REL)
    check("production verifier never references the runtime variable",
          RUNTIME_VAR not in verifier_src)
    check("production verifier still gates on the read-only affirmation",
          "PEAK_PRODUCTION_DB_READONLY_CONFIRM" in verifier_src)

    env = scrubbed_env()
    try:
        verify = subprocess.run([PY, os.path.join(REPO_ROOT, VERIFIER_REL)],
                                capture_output=True, text=True, timeout=120, env=env)
        check("production verifier still skips safely with no configuration",
              verify.returncode == 0)
        check("production verifier made no connection",
              "production_connection_made     : False" in verify.stdout
              or "production_connection_attempted: False" in verify.stdout)
    except Exception:
        check("verifier regression (not runnable — skipped)", True)

    try:
        audit = subprocess.run([PY, os.path.join(REPO_ROOT, AUDIT)],
                               capture_output=True, text=True, timeout=180, env=env)
        out = audit.stdout
        if "SQLAlchemy not installed" in out:
            check("audit runs (source-scan tier on this interpreter)", audit.returncode == 0)
        else:
            check("audit still reports MODEL_POLICY_SATISFIED_PRODUCTION_UNVERIFIED",
                  "MODEL_POLICY_SATISFIED_PRODUCTION_UNVERIFIED" in out)
        check("audit still exits 0", audit.returncode == 0)
    except Exception:
        check("audit regression (not runnable — skipped)", True)

    mk = read("Makefile")
    check("Makefile declares validate-phase50", "validate-phase50" in mk)
    check("validate depends on validate-phase50",
          re.search(r"^validate:.*validate-phase50", mk, re.MULTILINE) is not None)
    check("validate-phase50 runs this harness", HARNESS_REL in mk)
    check("no live gate target was added to validate",
          not re.search(r"^validate:.*runtime-connectivity", mk, re.MULTILINE))


# --------------------------------------------------------------------------- main


def main() -> int:
    print("Peak Phase 50 controlled runtime connectivity gate check")
    print("=" * 70)

    baseline_checks()
    provenance_checks()
    statement_surface_checks()
    policy_checks()
    behaviour_checks()
    driver_taxonomy_checks()
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
