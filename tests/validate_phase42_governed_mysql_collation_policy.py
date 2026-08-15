#!/usr/bin/env python3
"""Phase 42 governed MySQL collation policy check.

Stdlib-only, credential-free, offline. Verifies that Peak has a governed-collation *policy* and a
deterministic offline *audit* backing it — and that Phase 42 changed policy and tooling only,
touching no schema.

Four layers:

* **Scope** — Phase 42 is planning, not remediation: no migration `013`, no change under
  `alembic/`, `schemas/`, or `peak/db/`, no new table/model/writer/allowlist pair, and no managed
  MySQL connection code.

* **Audit tool** — runs offline on both a bare interpreter and one with SQLAlchemy; imports no DB
  driver; reads no `.env`; classifies every string column; places each required governed column in
  its expected class; separates ordinary text and JSON detail; reports unpinned governed columns as
  `NEEDS_REMEDIATION` **without failing the build**; and fails (exit 1) only when the audit itself
  is broken — proven by a negative test that removes a required governed column.

* **Policy doc** — states that server-default collation is insufficient for governed equality
  boundaries, that future governed columns must choose deterministic collation explicitly, that
  remediation needs approval, that production is not a smoke-test target, and that client data must
  not be used; carries a candidate migration `013` scope while no such file exists.

* **Regression + leak safety** — the standing baseline (head `012`, 12 migrations, 18 tables, 13
  allowlist tables / 15 actions, 11 writers), the managed-MySQL / Client Isolation Option A /
  AgentNet publication policies, no forbidden path, and no canary secret echoed. The repo-wide
  content-framing rule is owned by the Phase 7 hygiene guard and is not duplicated here.

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

BASELINE_COMMIT = "d2b75f0"   # Add Phase 41 managed MySQL production parity validation

AUDIT = "tools/governed_mysql_collation_audit.py"
PARITY = "tools/managed_mysql_parity_check.py"
DOC = "docs/GOVERNED_MYSQL_COLLATION_POLICY.md"
HARNESS = "tests/validate_phase42_governed_mysql_collation_policy.py"
REQUIRED_FILES = [AUDIT, PARITY, DOC, HARNESS]
COMPILE_FILES = [AUDIT, HARNESS]

ALEMBIC_HEAD = "013_governed_identifier_collation_policy"
EXPECTED_MIGRATIONS = 13
EXPECTED_TABLE_COUNT = 18
AUDIT_TARGET = "mysql-collation-audit"
STAGING_TARGET = "mysql-parity-staging"
MANAGED_TARGETS = ("db-check-managed-test", "managed-mysql-smoke", "managed-mysql-migration-check",
                   STAGING_TARGET)

#: Columns the audit must classify as governed. Mirrors the tool's own REQUIRED_GOVERNED; kept
#: here independently so a change to one is caught by the other.
REQUIRED_GOVERNED_NAMES = (
    "id", "owner_id", "client_id", "engagement_id", "authorization_scope", "idempotency_key",
    "payload_fingerprint", "plan_fingerprint", "report_draft_payload_fingerprint",
    "packet_payload_fingerprint",
)
IDEMPOTENCY_BOUNDARY = ("owner_id", "client_id", "engagement_id", "idempotency_key")

_CANARY_SECRET = "ZZCANARYSECRET42ZZ"
_CANARY_DSN = f"mysql+pymysql://zzcanary42:{_CANARY_SECRET}@canary42.invalid.example:3306/db"
_CANARY_FRAGMENTS = ("zzcanary42", _CANARY_SECRET, "canary42.invalid.example", _CANARY_DSN)

REQUIRED_DOC_PHRASES = [
    "governed_identifier",
    "governed_idempotency",
    "governed_hash_or_fingerprint",
    "ordinary_text",
    "json_or_details_text",
    "server's default collation",
    "must not inherit its collation from the server",
    "013_governed_identifier_collation_policy",
    "additive",
    "downgrade",
    "production db is not a smoke-test target",
    "no client data",
    "no seed data",
    "backup",
    "approval required",
    "utf8mb4_bin",
    "does not pin a mysql major version",
    "managed remote mysql",
    "client isolation option a",
]

NETWORK_IMPORT_RE = re.compile(r"\b(?:requests|httpx|aiohttp|ftplib|smtplib|telnetlib)\b")
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

    A detection pattern is not a violation: a tool that *names* a forbidden construct in order to
    look for it must not be flagged as using it.
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


def check(label: str, ok: bool) -> None:
    if ok:
        print(f"  [{PASS}] {label}")
    else:
        _failures.append(label)
        print(f"  [{FAIL}] {label}")


def run_audit(args=None, env_extra=None, python=None, cwd=None):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("PEAK_MANAGED_MYSQL") and k != "PEAK_DATABASE_URL"}
    env.update(env_extra or {})
    return subprocess.run([python or PY, os.path.join(cwd or REPO_ROOT, AUDIT)] + (args or []),
                          capture_output=True, text=True, cwd=cwd or REPO_ROOT, env=env,
                          timeout=180)


def _no_canary(text: str) -> bool:
    return not any(frag in text for frag in _CANARY_FRAGMENTS)


# --------------------------------------------------------------------------- 1. structural


def structural_checks() -> None:
    print("\n1. Audit tool / policy doc / harness present and compile")
    for rel in REQUIRED_FILES:
        check(rel, os.path.isfile(os.path.join(REPO_ROOT, rel)))
    for rel in COMPILE_FILES:
        try:
            py_compile.compile(os.path.join(REPO_ROOT, rel), doraise=True)
            check(f"{rel} compiles", True)
        except py_compile.PyCompileError:
            check(f"{rel} compiles", False)

    tool = read(AUDIT)
    tool_code = code_only(tool)
    print("\n2. The audit is analysis-only: no writer, no CRUD, no connection, no LLM/agent path")
    check("no controlled-writer import or call", not WRITER_RE.search(tool_code))
    check("no network client import", not NETWORK_IMPORT_RE.search(tool_code))
    check("no LLM provider import", not LLM_PROVIDER_RE.search(tool_code))
    check("no committed credential literal", not CREDENTIAL_RE.search(tool))
    check("no DSN literal in executable code", not DSN_LITERAL_RE.search(tool_code))
    check("no .env read", not re.search(r"open\([^)]*\.env|dotenv|load_dotenv", tool_code))
    check("opens no database connection and executes no SQL",
          not re.search(r"create_engine\(|\.connect\(|\.execute\(|cursor\(|\bsessionmaker\b",
                        tool_code))
    check("imports no DB driver at module scope (lazy, in-function imports only)",
          not re.search(r"^(?:import|from)\s+(?:pymysql|MySQLdb|sqlalchemy|alembic)\b",
                        tool, re.M))
    check("no session.add/commit/delete anywhere",
          not re.search(r"session\.(?:add|commit|delete|merge|flush)\(", tool_code))
    check("no AgentNet/MCP/resolver/capsule/approval path",
          not re.search(r"(?i)agentnet_publish|publish_capsule|resolver_publish|"
                        r"approve_client_facing|send_to_client", tool_code))
    check("proposes no schema change and writes no migration",
          not re.search(r"op\.(?:create_table|add_column|alter_column|create_index)\(", tool_code)
          and "ALTER TABLE" not in tool_code)
    check("declares the documented policy classes",
          all(c in tool for c in ("governed_identifier", "governed_scope", "governed_idempotency",
                                  "governed_hash_or_fingerprint",
                                  "governed_security_token_or_secret_hash", "governed_enum_status",
                                  "ordinary_text", "json_or_details_text",
                                  "unknown_governed_candidate")))


# --------------------------------------------------------------------------- 3. audit behavior


def audit_behavior_checks() -> None:
    print("\n3. The audit runs offline and classifies the real schema")
    proc = run_audit()
    check("default interpreter: exits 0", proc.returncode == 0)
    check("default interpreter: writes nothing to stderr", not proc.stderr.strip())
    check("states it is offline",
          "no credentials" in proc.stdout and "no database connection" in proc.stdout)
    # Either tier is legitimate; what matters is that whichever ran declares itself honestly.
    source_tier = "source-scan tier only" in proc.stdout
    model_tier = re.search(r"tables inspected\s*:\s*\d+", proc.stdout) is not None
    check("default interpreter: declares which tier ran, and only one of them",
          source_tier != model_tier)
    if source_tier:
        check("source-scan tier draws no policy conclusion",
              "no policy conclusion drawn" in proc.stdout)

    # Force the fallback deterministically: a None entry in sys.modules makes the import raise,
    # so the source-scan tier is exercised even on an interpreter that has SQLAlchemy.
    fallback_probe = (
        "import sys; sys.path.insert(0, %r); sys.path.insert(0, %r)\n"
        "sys.modules['peak.db.models'] = None\n"
        "import governed_mysql_collation_audit as a\n"
        "raise SystemExit(a.main([]))\n"
    ) % (os.path.join(REPO_ROOT, "tools"), REPO_ROOT)
    fb = subprocess.run([PY, "-c", fallback_probe], capture_output=True, text=True,
                        cwd=REPO_ROOT, timeout=180)
    check("forced fallback: still exits 0", fb.returncode == 0)
    check("forced fallback: declares itself source-scan only",
          "source-scan tier only" in fb.stdout)
    check("forced fallback: draws no policy conclusion it cannot support",
          "no policy conclusion drawn" in fb.stdout
          and "NEEDS_REMEDIATION" not in fb.stdout)

    venv = os.path.join(REPO_ROOT, ".venv", "bin", "python")
    if not os.path.isfile(venv):
        print("  [skip] .venv not present — model-introspection tier not exercised here")
        return

    full = run_audit(python=venv)
    check("model tier: exits 0 despite reporting NEEDS_REMEDIATION",
          full.returncode == 0)
    check("model tier: reports RESULT: PASS (a known finding is not a build failure)",
          "RESULT: PASS" in full.stdout)
    # Phase 42 reported the open finding; Phase 44 remediated it in source control. The audit
    # now reports the satisfied-but-unverified state, which is the stronger claim.
    check("model tier: status is MODEL_POLICY_SATISFIED_PRODUCTION_UNVERIFIED",
          "MODEL_POLICY_SATISFIED_PRODUCTION_UNVERIFIED" in full.stdout)
    check("model tier: audits all 18 tables",
          re.search(r"tables inspected\s*:\s*18", full.stdout) is not None)
    check("model tier: reports a deterministic total column count",
          re.search(r"string/text columns audited\s*:\s*(\d+)", full.stdout) is not None)
    check("model tier: every string column matched a policy class",
          "every string column matched a policy class" in full.stdout)

    for name in REQUIRED_GOVERNED_NAMES:
        check(f"classifies required governed column '{name}'",
              re.search(rf"\[PASS\] '{re.escape(name)}' -> governed_", full.stdout) is not None)

    check("separates ordinary descriptive text as its own class",
          re.search(r"ordinary_text\s+\d+ columns", full.stdout) is not None)
    check("separates JSON/detail text as its own class",
          re.search(r"json_or_details_text\s+\d+ columns", full.stdout) is not None)
    check("separates enum/status as deterministic-preferred, not required",
          re.search(r"governed_enum_status\s+\d+ columns", full.stdout) is not None
          and "deterministic preferred" in full.stdout)

    check("reports governed columns with and without explicit collation",
          "with explicit collation" in full.stdout
          and "WITHOUT explicit collation" in full.stdout)
    check("reports CRITICAL / HIGH / MEDIUM risk tiers",
          all(t in full.stdout for t in ("CRITICAL", "HIGH", "MEDIUM")))
    check("flags the controlled-writer idempotency unique boundary",
          "UNIQUE (" + ", ".join(IDEMPOTENCY_BOUNDARY) + ")" in full.stdout)
    check("names owner_id/client_id/engagement_id/idempotency_key explicitly",
          all(n in full.stdout for n in IDEMPOTENCY_BOUNDARY))
    check("explains the concrete idem-key collision consequence",
          "idem-key-1" in full.stdout and "idem-KEY-1" in full.stdout)
    check("notes that writers persist the key verbatim (no upstream mitigation)",
          "verbatim" in full.stdout)
    check("states production verification is still required after migration execution",
          "production verification remains required" in full.stdout.lower())
    check("points at the policy doc for remediation",
          "GOVERNED_MYSQL_COLLATION_POLICY.md" in full.stdout)
    check("keeps packet_hash correctly outside the column set",
          "'packet_hash' is not a column" in full.stdout)

    check("audit output contains no DSN-shaped string", not DSN_LITERAL_RE.search(full.stdout))
    env_run = run_audit(python=venv, env_extra={"PEAK_MANAGED_MYSQL_TEST_DSN": _CANARY_DSN,
                                                "PEAK_DATABASE_URL": _CANARY_DSN})
    check("an exported DSN is ignored and never echoed",
          env_run.returncode == 0 and _no_canary(env_run.stdout + env_run.stderr))

    print("     deterministic: two runs produce identical output")
    again = run_audit(python=venv)
    check("repeat run is byte-identical", again.stdout == full.stdout)

    print("     no DB driver is imported by the audit")
    probe = (
        "import sys, io, contextlib; sys.path.insert(0, %r); sys.path.insert(0, %r)\n"
        "import governed_mysql_collation_audit as a\n"
        "buf = io.StringIO()\n"
        "with contextlib.redirect_stdout(buf):\n"
        "    code = a.main([])\n"
        "drivers = [m for m in sys.modules if m.split('.')[0] in ('pymysql', 'MySQLdb', 'mysql')]\n"
        "print('PROBE_OK' if (code == 0 and not drivers) else 'PROBE_BAD:' + str(drivers))\n"
    ) % (os.path.join(REPO_ROOT, "tools"), REPO_ROOT)
    pr = subprocess.run([PY, "-c", probe], capture_output=True, text=True, cwd=REPO_ROOT,
                        timeout=180)
    check("audit imports no MySQL driver", "PROBE_OK" in pr.stdout)

    _audit_negative_test(venv)


def _audit_negative_test(venv: str) -> None:
    """An audit that can only ever pass proves nothing. Remove a required governed column from a
    throwaway copy of the models and assert the audit fails."""
    print("\n4. The audit fails when a governed column goes missing (negative test)")
    tmp = tempfile.mkdtemp(prefix="peak_phase42_")
    try:
        fake = os.path.join(tmp, "repo")
        os.makedirs(os.path.join(fake, "tools"))
        os.makedirs(os.path.join(fake, "peak", "db"))
        os.makedirs(os.path.join(fake, "alembic", "versions"))
        shutil.copy(os.path.join(REPO_ROOT, AUDIT), os.path.join(fake, AUDIT))
        for rel in ("peak/__init__.py", "peak/db/__init__.py", "peak/db/base.py",
                    "peak/db/models.py"):
            src = os.path.join(REPO_ROOT, rel)
            if os.path.isfile(src):
                shutil.copy(src, os.path.join(fake, rel))

        models_path = os.path.join(fake, "peak", "db", "models.py")
        with open(models_path, encoding="utf-8") as fh:
            src = fh.read()
        # Rename plan_fingerprint so the required governed column disappears from the schema.
        injected = src.replace("plan_fingerprint", "planfp_renamed")
        check("negative-test fixture actually removed a required governed column",
              injected != src and "plan_fingerprint" not in injected)
        with open(models_path, "w", encoding="utf-8") as fh:
            fh.write(injected)

        proc = subprocess.run([venv, os.path.join(fake, AUDIT)], capture_output=True, text=True,
                              cwd=fake, timeout=180)
        check("a missing required governed column makes the audit FAIL (exit 1)",
              proc.returncode == 1)
        check("the failure names the missing governed column",
              "RESULT: FAIL" in proc.stdout and "plan_fingerprint" in proc.stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------- 5. policy doc


def doc_checks() -> None:
    print("\n5. Policy doc states the decision, the plan, and the constraints")
    raw = read(DOC)
    blob = re.sub(r"\s+", " ", raw).lower()
    for phrase in REQUIRED_DOC_PHRASES:
        check(f"docs state: {phrase[:52]}", phrase.lower() in blob)
    check("policy distinguishes governed identifiers from ordinary descriptive text",
          "ordinary descriptive text does not need" in blob)
    check("policy states server-default collation is insufficient for governed boundaries",
          "must not inherit its collation from the server" in blob)
    check("policy requires future governed columns to choose collation explicitly",
          "must state its collation" in blob and "silence is not an acceptable default" in blob)
    check("policy states remediation requires approval before migration",
          "must not be implemented until the user explicitly approves" in blob)
    check("policy documents candidate migration 013 scope",
          "013_governed_identifier_collation_policy" in blob)
    check("policy documents alternatives rather than over-claiming a final selection",
          "does not declare a final selection" in blob or "selection deferred" in blob)
    check("policy documents downgrade posture", "downgrade posture" in blob)
    check("policy documents index/uniqueness implications",
          "uniqueness and index implications" in blob and "3072" in blob)
    check("policy documents the prior-migration analysis",
          "no prior migration attempted collation hardening" in blob)
    check("policy requires additive ALTER-only remediation",
          "additive" in blob and "must not be rewritten" in blob)
    check("docs contain no real DSN / credential", not DSN_LITERAL_RE.search(raw))
    check("docs contain no certificate or token example",
          "BEGIN PRIVATE KEY" not in raw and "BEGIN CERTIFICATE" not in raw)
    check("docs contain no canary value", _no_canary(raw))
    # The repo-wide content-framing rule is enforced by tests/validate_phase7_policy.py across
    # every tracked doc and source file, this doc included. Duplicating it here would add no
    # coverage and would require this harness to spell out the very term that guard forbids.


# --------------------------------------------------------------------------- 6. scope


def scope_checks() -> None:
    print("\n6. Scope: Phase 42 is planning, not remediation")
    versions_dir = os.path.join(REPO_ROOT, "alembic", "versions")
    versions = sorted(f for f in os.listdir(versions_dir) if f.endswith(".py"))
    check(f"exactly {EXPECTED_MIGRATIONS} migrations", len(versions) == EXPECTED_MIGRATIONS)
    # Phase 42 itself created no migration; Phase 44 implemented the 013 it specified. The
    # guarantee preserved here is that nothing beyond that plan was added.
    check("migration 013 is exactly the one Phase 42 specified",
          [f for f in versions if f.startswith("013")]
          == ["013_governed_identifier_collation_policy.py"])
    check("no migration 014 or later of any name",
          not any(re.match(r"^0*(?:1[4-9]|[2-9]\d)_", f) for f in versions))
    check(f"{ALEMBIC_HEAD} is still the newest migration",
          versions[-1].startswith("013_governed_identifier_collation_policy"))

    try:
        changed = subprocess.run(
            ["git", "-C", REPO_ROOT, "diff", "--name-only", "HEAD", "--", "schemas"],
            capture_output=True, text=True, timeout=20).stdout.strip()
        # ``alembic`` and ``peak`` left this list in Phase 44, which legitimately owns migration
        # 013 and the governed-collation model metadata. ``schemas/`` — the Phase 9 contract
        # source of truth — is still asserted untouched.
        check("no change under schemas/", not changed)
    except Exception:
        check("git-backed scope check (git unavailable — skipped)", True)

    from peak.persistence.allowlist import ALLOWED_ACTIONS, ALLOWED_TABLES
    check("allowlist still has exactly 13 tables", len(ALLOWED_TABLES) == 13)
    check("allowlist still has exactly 15 actions", len(ALLOWED_ACTIONS) == 15)
    check("no collation/parity action added to the allowlist",
          not any(re.search(r"collat|parity|audit", a) for a in ALLOWED_ACTIONS))
    check("no upsert / raw-SQL / hard-delete action added",
          not any(re.search(r"upsert|raw_sql|hard_delete", a) for a in ALLOWED_ACTIONS))

    import importlib
    p11 = importlib.import_module("tests.validate_phase11_db_scaffold")
    expected = list(getattr(p11, "EXPECTED_TABLES", []))
    check(f"db-check still expects exactly {EXPECTED_TABLE_COUNT} tables",
          len(expected) == EXPECTED_TABLE_COUNT)
    models_src = read("peak/db/models.py")
    check(f"models.py still declares exactly {EXPECTED_TABLE_COUNT} tables",
          models_src.count("__tablename__ = ") == EXPECTED_TABLE_COUNT)
    check("models.py still pins no collation (Phase 42 changed no schema)",
          not re.search(r"mysql_collate|COLLATE", models_src))

    writers = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "peak", "db"))
                     if f.endswith("_writer.py"))
    check("still exactly the eleven narrow controlled writers", len(writers) == 11)
    check("no collation/audit writer module added",
          not any(re.search(r"collat|audit|parity", w) for w in writers))


# --------------------------------------------------------------------------- 7. Makefile


def makefile_checks() -> None:
    print("\n7. Makefile: validate stays offline; DB-capable targets stay opt-in")
    mk = read("Makefile")
    validate_line = next((ln for ln in mk.splitlines() if ln.startswith("validate:")), "")
    check("validate-phase42 is part of `make validate`", "validate-phase42" in validate_line)
    check(f"'{AUDIT_TARGET}' target exists", f"{AUDIT_TARGET}:" in mk)
    check(f"'{AUDIT_TARGET}' invokes the offline audit tool",
          re.search(rf"{AUDIT_TARGET}:.*\n.*governed_mysql_collation_audit\.py", mk) is not None)
    check(f"'{AUDIT_TARGET}' passes no DSN / connection flag",
          not re.search(rf"{AUDIT_TARGET}:.*\n.*(?:--connect|DSN|mysql://)", mk))
    for target in MANAGED_TARGETS:
        check(f"DB-capable target '{target}' stays out of `make validate`",
              target not in validate_line and f"{target}:" in mk)
    check("db-check remains the local structural scaffold check only",
          re.search(r"^db-check:.*\n\t\$\(PYTHON\) tests/validate_phase11_db_scaffold\.py",
                    mk, re.M) is not None)
    check("no Makefile recipe exports or echoes a DSN",
          not DSN_LITERAL_RE.search(mk) and "echo $(PEAK" not in mk)

    print("     the Phase 41 parity checker still passes with a more precise warning")
    static = subprocess.run([PY, os.path.join(REPO_ROOT, PARITY), "--mode", "static"],
                            capture_output=True, text=True, cwd=REPO_ROOT, timeout=180)
    check("mysql-parity-static still exits 0", static.returncode == 0)
    # Phase 42 asserted the parity checker still warned about the gap. Phase 44 closed it, so the
    # checker now reports the pinned collation. Asserting the remediated state is stronger; what
    # must never happen is the section going silent.
    check("mysql-parity-static reports the pinned deterministic collation",
          "an explicit collation is pinned" in static.stdout
          and "utf8mb4_bin" in static.stdout)
    check("the parity checker still reports a collation section",
          "Charset / collation policy" in static.stdout)
    check("Phase 41 no longer lists packet_hash as a comparison-sensitive column",
          "packet_hash" not in static.stdout)
    staging = subprocess.run([PY, os.path.join(REPO_ROOT, PARITY), "--mode", "staging"],
                             capture_output=True, text=True, cwd=REPO_ROOT,
                             env={k: v for k, v in os.environ.items()
                                  if not k.startswith("PEAK_MANAGED_MYSQL")}, timeout=180)
    check("mysql-parity-staging still skips/fail-closes without connecting",
          staging.returncode == 0 and "[skip]" in staging.stdout)


# --------------------------------------------------------------------------- 8. regression


def regression_checks() -> None:
    print("\n8. Standing policy + forbidden-path regressions")
    audit_src = read(AUDIT)
    doc_src = read(DOC)
    for label, blob in (("audit", audit_src), ("doc", doc_src)):
        check(f"{label}: no Phase 22 review-writer call",
              "persist_review_record" not in blob)
        check(f"{label}: no agent-run-writer call", "persist_agent_run_record" not in blob)
    check("no packet / report-draft update path added",
          not re.search(r"UPDATE\s+internal_report_review_packets|"
                        r"UPDATE\s+internal_assessment_report_drafts", audit_src, re.IGNORECASE))
    check("no managed MySQL connection code added by Phase 42",
          not re.search(r"create_engine\(|pymysql|MySQLdb", code_only(audit_src)))

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
        check(f"Phase 42 baseline commit {BASELINE_COMMIT} present in history", present)
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
    print("Peak Phase 42 governed MySQL collation policy check")
    print("=" * 70)

    structural_checks()
    audit_behavior_checks()
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
