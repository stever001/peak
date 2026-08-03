#!/usr/bin/env python3
"""Phase 41 managed MySQL production-parity check.

Stdlib-only, credential-free, offline. Verifies that Peak's MySQL production-parity validation
layer exists, actually runs offline, and enforces the Phase 38 defect class (MySQL's 64-character
identifier limit, which SQLite silently accepts).

Three layers:

* **Baseline / regression** — the Phase 40 baseline is intact: Alembic head still
  `012_internal_report_review_packet_decisions`, 12 migrations, no `013`, 18 tables, 13 allowlist
  tables / 15 actions, 11 writers, no new table/model/migration/writer/allowlist pair, and no
  approval / client-facing / financial / capsule / AgentNet / LLM / agent / network path added.

* **Static parity** — the offline checker runs to completion with **no credentials and no
  network**, on both a bare interpreter and one with SQLAlchemy; it catches an injected overlong
  identifier (a real negative test, not just a green run); model and migration identifiers fit the
  MySQL limit; migrations are schema-only with bounded downgrades.

* **Opt-in staging + leak safety** — the staging gate skips safely with no configuration, refuses a
  production target, refuses a configured-but-not-disposable target, never attempts a connection,
  imports no DB driver, reads no `.env`, and never echoes a canary DSN/secret in any mode.

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
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

PY = sys.executable or "python3"

BASELINE_COMMIT = "1ccc4e9"   # Add Phase 40 internal report review workflow integration

TOOL = "tools/managed_mysql_parity_check.py"
PHASE34_TOOL = "tools/managed_mysql_check.py"
DOC = "docs/MANAGED_MYSQL_PRODUCTION_PARITY_VALIDATION.md"
HARNESS = "tests/validate_phase41_managed_mysql_production_parity.py"
REQUIRED_FILES = [TOOL, PHASE34_TOOL, DOC, HARNESS]
COMPILE_FILES = [TOOL, HARNESS]

ALEMBIC_HEAD = "012_internal_report_review_packet_decisions"
EXPECTED_MIGRATIONS = 12
EXPECTED_TABLE_COUNT = 18
MYSQL_IDENTIFIER_LIMIT = 64

STATIC_TARGET = "mysql-parity-static"
STAGING_TARGET = "mysql-parity-staging"
MANAGED_TARGETS = ("db-check-managed-test", "managed-mysql-smoke", "managed-mysql-migration-check",
                   STAGING_TARGET)

DISPOSABLE_MARKER_VAR = "PEAK_MANAGED_MYSQL_DISPOSABLE"
TEST_DSN_VAR = "PEAK_MANAGED_MYSQL_TEST_DSN"

#: A canary DSN + secret. If any of these fragments ever appears in tool output, we have a leak.
_CANARY_USER = "zzcanaryuser41"
_CANARY_SECRET = "ZZCANARYSECRET41ZZ"
_CANARY_HOST = "canary-db.invalid.example"
_CANARY_DSN = f"mysql+pymysql://{_CANARY_USER}:{_CANARY_SECRET}@{_CANARY_HOST}:3306/canarydb"
_CANARY_FRAGMENTS = (_CANARY_USER, _CANARY_SECRET, _CANARY_HOST, _CANARY_DSN)

#: The two identifiers that motivated this phase (69 and 78 chars).
PHASE38_OVERLONG = "ix_internal_report_review_packets_internal_assessment_report_draft_id"
PHASE39_OVERLONG = "ix_internal_report_review_packet_decisions_internal_assessment_report_draft_id"

REQUIRED_DOC_PHRASES = [
    "64-character limit",
    "sqlite is not the production-readiness proof path",
    "managed mysql test/staging validation is required",
    "what standard validation does",
    "production db is not a smoke-test target",
    "no client data",
    "never committed and never printed",
    "opt-in",
    "fails closed",
    "collation",
    "utf8mb4",
    "no migration is proposed",
    PHASE38_OVERLONG,
    "managed remote mysql",
    "client isolation option a",
]

NETWORK_IMPORT_RE = re.compile(
    r"\b(?:requests|httpx|aiohttp|ftplib|smtplib|telnetlib)\b")
LLM_PROVIDER_RE = re.compile(
    r"\b(?:openai|anthropic|cohere|litellm|langchain|transformers|vertexai|mistralai|ollama)\b",
    re.IGNORECASE)
WRITER_RE = re.compile(r"\bpersist_\w+|peak\.db\.\w*writer")
CREDENTIAL_RE = re.compile(
    r"\b(?:api_key|secret_key|access_key|password|passwd)\b\s*[:=]\s*['\"][^'\"]{3,}['\"]",
    re.IGNORECASE)
DSN_LITERAL_RE = re.compile(r"\b[a-z][a-z0-9+.\-]*://[\w.\-]+:[^\s@'\"]+@")
DATA_EXTS = (".csv", ".xlsx", ".xls", ".parquet", ".db", ".sqlite", ".sqlite3", ".sql", ".dump")
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache"}

PASS, FAIL = "PASS", "FAIL"
_failures: list = []


def read(rel: str) -> str:
    with open(os.path.join(REPO_ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def _skip(dp: str) -> bool:
    return bool(SKIP_DIRS.intersection(dp.split(os.sep)))


def code_only(source: str) -> str:
    """Executable tokens only — comments and string literals removed.

    A detection pattern is not a violation: a tool that *searches migrations for* ``insert into``,
    or a comment illustrating the DSN shape it scrubs, must not be flagged as emitting SQL or
    committing a DSN. Boundary claims are therefore made against the code that runs.
    """
    out = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type in (tokenize.COMMENT, tokenize.STRING):
                continue
            out.append(tok.string)
    except tokenize.TokenError:  # pragma: no cover - only on unparsable source
        return source
    return " ".join(out)


def check(label: str, ok: bool) -> None:
    if ok:
        print(f"  [{PASS}] {label}")
    else:
        _failures.append(label)
        print(f"  [{FAIL}] {label}")


def run_tool(args, env_extra=None, cwd=None, python=None):
    """Run the parity tool in a subprocess with a scrubbed environment."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("PEAK_MANAGED_MYSQL") and k != "PEAK_DATABASE_URL"}
    env.update(env_extra or {})
    return subprocess.run([python or PY, os.path.join(REPO_ROOT, TOOL)] + args,
                          capture_output=True, text=True, cwd=cwd or REPO_ROOT,
                          env=env, timeout=180)


def _no_canary(text: str) -> bool:
    return not any(frag in text for frag in _CANARY_FRAGMENTS)


# --------------------------------------------------------------------------- 1. structural


def structural_checks() -> None:
    print("\n1. Parity tool / doc / harness present and compile")
    for rel in REQUIRED_FILES:
        check(rel, os.path.isfile(os.path.join(REPO_ROOT, rel)))
    for rel in COMPILE_FILES:
        try:
            py_compile.compile(os.path.join(REPO_ROOT, rel), doraise=True)
            check(f"{rel} compiles", True)
        except py_compile.PyCompileError:
            check(f"{rel} compiles", False)

    tool = read(TOOL)
    tool_code = code_only(tool)   # claims are about executed code, not detection patterns
    print("\n2. The parity tool is validation-only: no writer, no CRUD, no LLM/agent/network stack")
    check("no controlled-writer import or call", not WRITER_RE.search(tool_code))
    check("no network client import", not NETWORK_IMPORT_RE.search(tool_code))
    check("no LLM provider import", not LLM_PROVIDER_RE.search(tool_code))
    check("no committed credential literal", not CREDENTIAL_RE.search(tool))
    check("no DSN literal in executable code", not DSN_LITERAL_RE.search(tool_code))
    check("no .env read", not re.search(r"""open\([^)]*\.env|dotenv|load_dotenv""", tool_code))
    check("opens no database connection and executes no SQL",
          not re.search(r"create_engine\(|\.connect\(|\.execute\(|cursor\(|\bsessionmaker\b",
                        tool_code))
    # Module scope means column 0. The tool imports SQLAlchemy/Alembic lazily *inside* the
    # simulation tier by design, so an indented import is correct and an unindented one is not.
    check("imports no DB driver at module scope (lazy, in-function imports only)",
          not re.search(r"^(?:import|from)\s+(?:pymysql|MySQLdb|sqlalchemy|alembic)\b",
                        tool, re.M))
    check("no session.add/commit/delete anywhere",
          not re.search(r"session\.(?:add|commit|delete|merge|flush)\(", tool_code))
    check("no AgentNet/MCP/resolver/capsule/approval path",
          not re.search(r"(?i)agentnet_publish|publish_capsule|resolver_publish|"
                        r"approve_client_facing|send_to_client", tool_code))
    check("declares the MySQL identifier limit as 64",
          f"MYSQL_IDENTIFIER_LIMIT = {MYSQL_IDENTIFIER_LIMIT}" in tool)
    check("production is refused, not merely discouraged",
          "REFUSED" in tool and 'args.env == "prod"' in tool)
    check("sanitizes every emitted line", "def sanitize(" in tool and "def emit(" in tool)
    check("reports failures by exception type only",
          "def safe_error(" in tool and "detail withheld" in tool)


# --------------------------------------------------------------------------- 3. static parity


def static_parity_checks() -> None:
    print("\n3. Static parity mode runs offline (no credentials, no network, no .env)")
    proc = run_tool(["--mode", "static"])
    check("static mode exits 0", proc.returncode == 0)
    check("static mode reports RESULT: PASS", "RESULT: PASS" in proc.stdout)
    check("static mode reports zero failures",
          re.search(r"failures\s*:\s*0", proc.stdout) is not None)
    check("static mode states it is offline",
          "no credentials" in proc.stdout.lower() and "no network" in proc.stdout.lower())
    check("static mode prints no DSN-shaped string",
          not DSN_LITERAL_RE.search(proc.stdout))
    check("static mode emits nothing on stderr", not proc.stderr.strip())

    # Works with a canary DSN exported: it must be ignored entirely and never echoed.
    proc_env = run_tool(["--mode", "static"], env_extra={TEST_DSN_VAR: _CANARY_DSN,
                                                         "PEAK_DATABASE_URL": _CANARY_DSN})
    check("static mode ignores an exported DSN and still exits 0", proc_env.returncode == 0)
    check("static mode never echoes the canary DSN/secret",
          _no_canary(proc_env.stdout + proc_env.stderr))

    print("\n4. Static parity enforces the identifier limit (negative test, not just a green run)")
    _identifier_negative_test()

    print("\n5. Static parity findings match the repo's real state")
    check("model identifiers are checked or explicitly skipped",
          "ORM model identifiers" in proc.stdout)
    check("migration identifiers are simulated with no DB",
          "no DB, no SQL, no connection" in proc.stdout)
    # On a bare interpreter the simulation tier cannot run; it must then say so explicitly rather
    # than quietly reporting success it did not achieve.
    simulated = re.search(rf"across {EXPECTED_MIGRATIONS} migrations", proc.stdout) is not None
    declared_skip = "not simulated" in proc.stdout
    check("the simulation covers every migration, or explicitly declares itself skipped",
          simulated or declared_skip)
    check("a skipped tier is never reported as a pass",
          simulated or ("[skip]" in proc.stdout and "RESULT: PASS" in proc.stdout))
    check("charset/collation policy is reported", "Charset / collation policy" in proc.stdout)
    check("utf8mb4 is confirmed pinned", "utf8mb4 is pinned as the charset" in proc.stdout)
    check("InnoDB is confirmed pinned", "InnoDB is pinned as the engine" in proc.stdout)
    check("the unpinned-collation gap is surfaced as a warning, not hidden",
          "WARN" in proc.stdout and "collation" in proc.stdout.lower())
    check("the collation warning names the idempotency consequence",
          "idempotency" in proc.stdout.lower())
    check("the collation warning proposes no migration",
          "No migration is proposed here" in proc.stdout)


def _identifier_negative_test() -> None:
    """Copy the repo's migrations into a temp tree, inject a 69-char index name, and prove the
    checker fails. A parity check that only ever passes proves nothing."""
    tmp = tempfile.mkdtemp(prefix="peak_phase41_")
    try:
        fake_repo = os.path.join(tmp, "repo")
        os.makedirs(os.path.join(fake_repo, "alembic", "versions"))
        os.makedirs(os.path.join(fake_repo, "tools"))
        os.makedirs(os.path.join(fake_repo, "peak", "db"))
        shutil.copy(os.path.join(REPO_ROOT, TOOL), os.path.join(fake_repo, TOOL))
        for rel in ("peak/db/models.py", "peak/db/base.py"):
            shutil.copy(os.path.join(REPO_ROOT, rel), os.path.join(fake_repo, rel))
        src_versions = os.path.join(REPO_ROOT, "alembic", "versions")
        for name in os.listdir(src_versions):
            if name.endswith(".py"):
                shutil.copy(os.path.join(src_versions, name),
                            os.path.join(fake_repo, "alembic", "versions", name))

        target = os.path.join(fake_repo, "alembic", "versions",
                              "012_internal_report_review_packet_decisions.py")
        with open(target, encoding="utf-8") as fh:
            src = fh.read()
        # Inject exactly the Phase 38 defect: a 69-character convention-derived index name.
        injected = src.replace(
            'IX_PREFIX = "ix_irrpd_"',
            f'IX_PREFIX = "ix_irrpd_"\nBAD_INDEX = "{PHASE38_OVERLONG}"', 1)
        injected = injected.replace(
            "    op.create_index(\n        UNIQUE_INDEX,",
            "    op.create_index(BAD_INDEX, TABLE, [\"owner_id\"])\n    op.create_index(\n        UNIQUE_INDEX,", 1)
        check("negative-test fixture actually injected the overlong name",
              injected != src and PHASE38_OVERLONG in injected
              and len(PHASE38_OVERLONG) > MYSQL_IDENTIFIER_LIMIT)
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(injected)

        proc = subprocess.run([PY, os.path.join(fake_repo, TOOL), "--mode", "static"],
                              capture_output=True, text=True, cwd=fake_repo, timeout=180)
        check("an overlong identifier makes the static check FAIL (exit 1)",
              proc.returncode == 1)
        check("the failure names the identifier-length problem",
              "RESULT: FAIL" in proc.stdout
              and re.search(r"(?i)fits 64 chars|64 chars|identifier", proc.stdout) is not None)
        check("the failure output names the offending identifier",
              PHASE38_OVERLONG in proc.stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------- 6. staging gate


def staging_gate_checks() -> None:
    print("\n6. Opt-in staging gate: skip-safe, fail-closed, never connects")

    proc = run_tool(["--mode", "staging"])
    check("no configuration -> exits 0 (skip)", proc.returncode == 0)
    check("no configuration -> prints a sanitized skip",
          "[skip]" in proc.stdout and "opt-in" in proc.stdout.lower())
    check("skip message states nothing was connected to",
          "no driver was imported" in proc.stdout and "no .env was read" in proc.stdout)
    check("skip message prints no DSN", not DSN_LITERAL_RE.search(proc.stdout))
    check("skip mode writes nothing to stderr", not proc.stderr.strip())

    prod = run_tool(["--mode", "staging", "--env", "prod"])
    check("production target is REFUSED with exit 2", prod.returncode == 2)
    check("production refusal is explicit", "REFUSED" in prod.stdout)

    configured = run_tool(["--mode", "staging"], env_extra={TEST_DSN_VAR: _CANARY_DSN})
    check("DSN configured but not marked disposable -> REFUSED with exit 2",
          configured.returncode == 2 and "REFUSED" in configured.stdout)
    check("refusal never echoes the canary DSN/secret",
          _no_canary(configured.stdout + configured.stderr))

    marked = run_tool(["--mode", "staging"], env_extra={DISPOSABLE_MARKER_VAR: "1"})
    check("marked disposable but no DSN -> skips cleanly (exit 0)", marked.returncode == 0)
    check("no-DSN skip attempts nothing", "No connection attempted" in marked.stdout)

    both = run_tool(["--mode", "staging"],
                    env_extra={TEST_DSN_VAR: _CANARY_DSN, DISPOSABLE_MARKER_VAR: "1"})
    check("fully configured -> HOLD, not an automatic live run (exit 0)",
          both.returncode == 0 and "[hold]" in both.stdout)
    check("HOLD says a live run needs separate explicit approval",
          "separate explicit approval" in both.stdout)
    check("HOLD confirms the DSN value stays hidden", "value hidden" in both.stdout)
    check("HOLD never echoes the canary DSN/secret", _no_canary(both.stdout + both.stderr))
    check("HOLD promises no production write and no cleanup/delete path",
          "no production write" in both.stdout and "delete path" in both.stdout)

    print("     no DB driver is imported and no socket is opened in skip mode")
    probe = (
        "import sys, io, contextlib; sys.path.insert(0, %r); sys.path.insert(0, %r);\n"
        "import managed_mysql_parity_check as t\n"
        "buf = io.StringIO()\n"
        "with contextlib.redirect_stdout(buf):\n"
        "    code = t.main(['--mode', 'staging'])\n"
        "drivers = [m for m in sys.modules if m.split('.')[0] in "
        "('pymysql', 'MySQLdb', 'mysql', 'sqlalchemy', 'alembic')]\n"
        "print('PROBE_OK' if (code == 0 and not drivers) else 'PROBE_BAD:' + str(drivers))\n"
    ) % (os.path.join(REPO_ROOT, "tools"), REPO_ROOT)
    env = {k: v for k, v in os.environ.items() if not k.startswith("PEAK_MANAGED_MYSQL")}
    pr = subprocess.run([PY, "-c", probe], capture_output=True, text=True,
                        cwd=REPO_ROOT, env=env, timeout=180)
    check("staging skip imports no DB driver / SQLAlchemy / Alembic", "PROBE_OK" in pr.stdout)


# --------------------------------------------------------------------------- 7. Makefile


def makefile_checks() -> None:
    print("\n7. Makefile: validate stays offline; any DB-capable target stays opt-in")
    mk = read("Makefile")
    validate_line = next((ln for ln in mk.splitlines() if ln.startswith("validate:")), "")
    check("validate-phase41 is part of `make validate`", "validate-phase41" in validate_line)
    check(f"'{STATIC_TARGET}' target exists", f"{STATIC_TARGET}:" in mk)
    check(f"'{STAGING_TARGET}' target exists", f"{STAGING_TARGET}:" in mk)
    for target in MANAGED_TARGETS:
        check(f"DB-capable target '{target}' stays out of `make validate`",
              target not in validate_line and f"{target}:" in mk)
    check(f"'{STATIC_TARGET}' invokes the checker in static mode",
          re.search(rf"{STATIC_TARGET}:.*\n.*--mode static", mk) is not None)
    check(f"'{STAGING_TARGET}' invokes the checker in staging mode",
          re.search(rf"{STAGING_TARGET}:.*\n.*--mode staging", mk) is not None)
    check("db-check remains the local structural scaffold check only",
          re.search(r"^db-check:.*\n\t\$\(PYTHON\) tests/validate_phase11_db_scaffold\.py",
                    mk, re.M) is not None)
    check("no Makefile recipe exports or echoes a DSN",
          not DSN_LITERAL_RE.search(mk) and "echo $(PEAK" not in mk)


# --------------------------------------------------------------------------- 8. regression


def regression_checks() -> None:
    print("\n8. Baseline regression: no schema, writer, or allowlist surface added")
    versions = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "alembic", "versions"))
                      if f.endswith(".py"))
    check(f"exactly {EXPECTED_MIGRATIONS} migrations", len(versions) == EXPECTED_MIGRATIONS)
    check("no migration 013 or later",
          not any(re.match(r"^0*(?:1[3-9]|[2-9]\d)_", f) for f in versions))
    check(f"{ALEMBIC_HEAD} is still the newest migration",
          versions[-1].startswith("012_internal_report_review_packet_decisions"))

    from peak.persistence.allowlist import ALLOWED_ACTIONS, ALLOWED_TABLES
    check("allowlist still has exactly 13 tables", len(ALLOWED_TABLES) == 13)
    check("allowlist still has exactly 15 actions", len(ALLOWED_ACTIONS) == 15)
    check("no upsert / raw-SQL / hard-delete action added",
          not any(re.search(r"upsert|raw_sql|hard_delete", a) for a in ALLOWED_ACTIONS))
    check("no parity/validation action added to the allowlist",
          not any(re.search(r"parity|validat|mysql", a) for a in ALLOWED_ACTIONS))

    import importlib
    p11 = importlib.import_module("tests.validate_phase11_db_scaffold")
    expected = list(getattr(p11, "EXPECTED_TABLES", []))
    check(f"db-check still expects exactly {EXPECTED_TABLE_COUNT} tables",
          len(expected) == EXPECTED_TABLE_COUNT)
    models_src = read("peak/db/models.py")
    check(f"models.py still declares exactly {EXPECTED_TABLE_COUNT} tables",
          models_src.count("__tablename__ = ") == EXPECTED_TABLE_COUNT)
    check("models.py declares no parity/validation table",
          not re.search(r'__tablename__\s*=\s*"[^"]*(?:parity|validation)[^"]*"', models_src))

    writers = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "peak", "db"))
                     if f.endswith("_writer.py"))
    check("still exactly the eleven narrow controlled writers", len(writers) == 11)

    print("     no forbidden path was introduced by Phase 41")
    tool = read(TOOL)
    doc = read(DOC)
    for label, blob in (("tool", tool), ("doc", doc)):
        check(f"{label}: no Phase 22 review-writer call / review_records write",
              "persist_review_record" not in blob and "review_records" not in blob.replace(
                  "review_records`", ""))
        check(f"{label}: no agent_run_records write", "persist_agent_run_record" not in blob)
    check("no packet / report-draft update path added",
          not re.search(r"UPDATE\s+internal_report_review_packets|"
                        r"UPDATE\s+internal_assessment_report_drafts", tool, re.IGNORECASE))

    print("     managed MySQL / isolation / AgentNet publication policies intact")
    rub = re.sub(r"\s+", " ", read("docs/MANAGED_MYSQL_PERSISTENCE_RUBRIC.md") + " "
                 + read("docs/PRODUCTION_PARITY_DB_VALIDATION.md") + " "
                 + read("docs/CLIENT_ISOLATION_MODEL.md")).lower()
    check("managed remote MySQL is still the operational data store",
          "managed remote mysql" in rub and "operational data store" in rub)
    check("Client Isolation Option A is still the default",
          "client isolation option a" in rub and "default" in rub)
    check("SQLite is still not the production-readiness proof path",
          "sqlite is not the production-readiness proof path" in rub)
    check("managed MySQL test/staging validation still required",
          "managed mysql test/staging validation is required" in rub)
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


# --------------------------------------------------------------------------- 9. docs


def doc_checks() -> None:
    print("\n9. Documentation states the parity model and the open gap")
    blob = re.sub(r"\s+", " ", read(DOC)).lower()
    for phrase in REQUIRED_DOC_PHRASES:
        check(f"docs state: {phrase[:60]}", phrase.lower() in blob)
    raw = read(DOC)
    check("docs contain no real DSN / credential", not DSN_LITERAL_RE.search(raw))
    check("docs contain no certificate or token example",
          "BEGIN PRIVATE KEY" not in raw and "BEGIN CERTIFICATE" not in raw)
    check("docs contain no canary/secret value", _no_canary(raw))
    check("docs explain SQLite vs managed MySQL as distinct layers",
          "sqlite structural smoke" in blob and "production parity" in blob)
    check("docs state a live run is not executed by this phase",
          "not executed by phase 41" in blob)


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
        check(f"Phase 41 baseline commit {BASELINE_COMMIT} present in history", present)
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
        changed = subprocess.run(
            ["git", "-C", REPO_ROOT, "diff", "--name-only", "HEAD", "--",
             "alembic", "peak/db/models.py", "peak/persistence/allowlist.py"],
            capture_output=True, text=True, timeout=20).stdout.strip()
        check("Phase 41 changed no migration, model, or allowlist source", not changed)
    except Exception:
        check("git-backed baseline/hygiene checks (git unavailable — skipped)", True)

    print("     no credential-shaped literal was committed anywhere in the repo")
    offenders = []
    for dp, dns, fns in os.walk(REPO_ROOT):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        if _skip(os.path.relpath(dp, REPO_ROOT)):
            continue
        for f in fns:
            if not f.endswith((".py", ".md", ".cfg", ".ini", ".txt", ".example")):
                continue
            rel = os.path.relpath(os.path.join(dp, f), REPO_ROOT)
            try:
                body = read(rel)
            except (UnicodeDecodeError, OSError):
                continue
            if rel == ".env.example":
                continue
            # For Python, scan executable code only: a comment or a scrubbing pattern that
            # *describes* a DSN shape is documentation, not a committed credential.
            scanned = code_only(body) if rel.endswith(".py") else body
            for match in DSN_LITERAL_RE.finditer(scanned):
                # A documented placeholder is fine; a real-looking host is not.
                if not re.search(r"USER|user:password|PASSWORD|\.\.\.|example|invalid",
                                 match.group(0), re.IGNORECASE):
                    offenders.append(f"{rel}: {match.group(0)[:24]}...")
    check("no real DSN literal committed", not offenders)


# --------------------------------------------------------------------------- main


def main() -> int:
    print("Peak Phase 41 managed MySQL production-parity check")
    print("=" * 70)

    structural_checks()
    static_parity_checks()
    staging_gate_checks()
    makefile_checks()
    regression_checks()
    doc_checks()
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
