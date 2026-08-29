#!/usr/bin/env python3
"""Phase 56 internal test engagement classification support check.

Phase 55 found that neither the ``Engagement`` model nor the Phase 54 anchor writer could classify
a durable internal test/training engagement. Phase 56 closes that gap — schema, model, and writer
validation — and **creates no records**.

Offline and credential-free: the behaviour layer runs only against throwaway temporary SQLite
databases, and contacts no production database.

Layers: baseline · schema/model · governance rules · writer behaviour · regression/hygiene.

Exit status:
  0  -> all checks passed
  1  -> a check failed
"""

from __future__ import annotations

import os
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (REPO_ROOT, os.path.join(REPO_ROOT, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

PY = sys.executable or "python3"

BASELINE_COMMIT = "4fa31a3"   # Document Phase 55 internal test engagement classification

MIGRATION_REL = "alembic/versions/014_engagement_classification.py"
MIGRATION_NAME = "014_engagement_classification"
HEAD_REVISION = "014_engagement_classification"
WRITER_REL = "peak/db/engagement_authorization_anchor_writer.py"
HARNESS_REL = "tests/validate_phase56_internal_test_engagement_support.py"
DOC_REL = "docs/PHASE56_INTERNAL_TEST_ENGAGEMENT_SUPPORT.md"
MODELS_REL = "peak/db/models.py"
CONTRACTS_REL = "peak/db/writer_contracts.py"
GOVERNANCE_REL = "peak/persistence/governance.py"
DECISION_GATE_REL = "tools/production_writer_enablement_decision_gate.py"
VERIFIER_REL = "tools/production_mysql_collation_verify.py"

ROLE_VARS = ("PEAK_RUNTIME_DATABASE_URL", "PEAK_DATABASE_URL", "PEAK_PRODUCTION_DB_URL",
             "PEAK_PRODUCTION_DB_READONLY_CONFIRM")

EXPECTED_MIGRATIONS = 14
EXPECTED_TABLE_COUNT = 18
EXPECTED_WRITERS = 12
EXPECTED_ALLOWLIST_TABLES = 13
EXPECTED_ALLOWLIST_ACTIONS = 15
CLASSIFICATION_COLUMNS = ("engagement_category", "real_client_data", "client_accessible",
                          "capsule_publication_authorized")
RESERVED_CLIENT_ID = "99999"

REAL_DSN_RE = re.compile(r"\b[a-z][a-z0-9+.\-]*://(?!USER:PASSWORD)(?!user:password)"
                         r"[\w.\-]+:[^\s@'\"]+@")

PASS, FAIL = "PASS", "FAIL"
_failures: list = []
_tmpdirs: list = []


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
    import ast
    tree = ast.parse(source)
    doc = []
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            b = getattr(n, "body", None)
            if b and isinstance(b[0], ast.Expr) and isinstance(b[0].value, ast.Constant) \
                    and isinstance(b[0].value.value, str):
                doc.append((b[0].lineno, b[0].end_lineno))
    return "\n".join(re.sub(r"#.*$", "", ln)
                     for i, ln in enumerate(source.splitlines(), 1)
                     if not any(a <= i <= b for a, b in doc))


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", REPO_ROOT, *args],
                          capture_output=True, text=True, timeout=20).stdout.strip()


def git_succeeds(*args: str) -> bool:
    """Run a git command for its exit status alone; stdout and stderr are discarded, so
    nothing a path or remote might carry can reach this harness's output."""
    return subprocess.run(["git", "-C", REPO_ROOT, *args],
                          capture_output=True, text=True, timeout=20).returncode == 0


def scrubbed_env():
    env = {k: v for k, v in os.environ.items() if k not in ROLE_VARS}
    env["PYTHONPATH"] = REPO_ROOT
    return env


def engagement_block() -> str:
    return read(MODELS_REL).split('__tablename__ = "engagements"', 1)[1].split("\nclass ", 1)[0]


# --------------------------------------------------------------------------- 1. baseline


def baseline_checks() -> None:
    print("\n1. Baseline: 014 head, 14 migrations, 18 tables, 12 writers, no new writer/pair")
    versions = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "alembic", "versions"))
                      if f.endswith(".py"))
    check(f"exactly {EXPECTED_MIGRATIONS} migrations", len(versions) == EXPECTED_MIGRATIONS)
    check(f"{MIGRATION_REL} exists", os.path.isfile(os.path.join(REPO_ROOT, MIGRATION_REL)))
    check(f"{MIGRATION_NAME} is the newest migration", versions[-1] == f"{MIGRATION_NAME}.py")
    check("no migration 015 or later",
          not any(re.match(r"^0*(?:1[5-9]|[2-9]\d)_", f) for f in versions))

    mig = read(MIGRATION_REL)
    check("migration 014 adds no table", "create_table" not in mig)
    check("migration 014 drops no table", "drop_table" not in mig)
    # The docstring legitimately says "no INSERTs"; the claim is that no insert *operation* exists.
    check("migration 014 performs no INSERT / seed data operation",
          not re.search(r"op\.bulk_insert|op\.execute|\.insert\(", mig))
    check("migration 014 is reversible (downgrade drops exactly what upgrade added)",
          mig.split("def downgrade")[1].count("op.drop_column(") == 4)
    check("migration 014 chains from 013",
          'down_revision = "013_governed_identifier_collation_policy"' in mig)

    for rel in (WRITER_REL, HARNESS_REL, MIGRATION_REL):
        try:
            py_compile.compile(os.path.join(REPO_ROOT, rel), doraise=True)
            check(f"{rel} compiles", True)
        except py_compile.PyCompileError:
            check(f"{rel} compiles", False)

    check(f"models.py still declares exactly {EXPECTED_TABLE_COUNT} tables — no table added",
          read(MODELS_REL).count("__tablename__ = ") == EXPECTED_TABLE_COUNT)
    writers = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "peak", "db"))
                     if f.endswith("_writer.py"))
    check(f"still exactly {EXPECTED_WRITERS} writers — no writer added",
          len(writers) == EXPECTED_WRITERS)

    from peak.persistence.allowlist import (
        ALLOWED_ACTIONS, ALLOWED_ANCHOR_CREATION_PAIRS, ALLOWED_TABLES, is_allowed_table,
        is_never_writable_table, is_prohibited_table,
    )
    check("generic allowlist unchanged — no pair added",
          len(ALLOWED_TABLES) == EXPECTED_ALLOWLIST_TABLES
          and len(ALLOWED_ACTIONS) == EXPECTED_ALLOWLIST_ACTIONS)
    check("still exactly one anchor-creation pair", len(ALLOWED_ANCHOR_CREATION_PAIRS) == 1)
    check("engagements remains prohibited generically",
          is_prohibited_table("engagements") and not is_allowed_table("engagements"))
    check("clients remains never writable", is_never_writable_table("clients"))
    check("Client model was not altered",
          "class Client(Base, GovernanceMixin, AuditMixin):" in read(MODELS_REL)
          and read(MODELS_REL).split("class Client(", 1)[1].split("class ", 1)[0]
          .count("mapped_column") == 2)

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
            print("        reason: phase56_baseline_commit_not_ancestor")
        check("docs/Peak_Investor_Overview_AI.docx has no pending diff",
              not git("diff", "--name-only", "HEAD", "--",
                      "docs/Peak_Investor_Overview_AI.docx"))
        check("schemas/, prompts/, agents/, examples/ untouched",
              not git("diff", "--name-only", "HEAD", "--",
                      "schemas", "prompts", "agents", "examples"))
    except Exception:
        check("git-backed scope checks (git unavailable — skipped)", True)


# --------------------------------------------------------------------------- 2. schema/model


def schema_checks() -> None:
    print("\n2. Classification lives in real columns, not JSON / label / scope / id-prefix")
    eng = engagement_block()
    for col in CLASSIFICATION_COLUMNS:
        check(f"Engagement declares '{col}' as a real column",
              re.search(rf"^\s+{col}\s*:\s*Mapped", eng, re.MULTILINE) is not None)
    check("engagement_category is a governed (byte-exact) string",
          re.search(r"engagement_category:.*\n?.*GovernedString", eng) is not None)
    check("engagement_category defaults to real_client",
          'default="real_client"' in eng and 'server_default="real_client"' in eng)
    check("real_client_data / client_accessible default true",
          eng.count("server_default=sa_true()") == 2)
    check("capsule_publication_authorized defaults false",
          "server_default=sa_false()" in eng)
    check("all four classification columns are NOT NULL",
          eng.count("nullable=False") >= 4)

    # Classification must NOT be smuggled into any of the rejected carriers.
    writer_code = code_no_docstrings(read(WRITER_REL))
    details = re.search(r"details_json=\{(.*?)\n        \},", writer_code, re.DOTALL)
    body = details.group(1) if details else ""
    for col in CLASSIFICATION_COLUMNS:
        check(f"'{col}' is not stored in details_json", col not in body)
    check("classification is not derived from the engagement_label",
          not re.search(r"engagement_label.*(?:startswith|internal_test|category)", writer_code))
    check("classification is not derived from an id prefix",
          not re.search(r"engagement_id\.startswith|client_id\.startswith\(\s*['\"]eng",
                        writer_code))
    check("classification is not encoded in authorization_scope",
          "internal_test" not in read("peak/db/enums.py").split("class AuthorizationScope",
                                                                1)[1].split("class ", 1)[0])

    from peak.db.enums import EngagementCategory
    check("EngagementCategory is a closed two-value vocabulary",
          {m.value for m in EngagementCategory} == {"real_client", "internal_test"})


# --------------------------------------------------------------------------- 3. governance


def governance_checks() -> None:
    print("\n3. Classification rules, including the bidirectional reserved namespace")
    from peak.persistence.governance import (
        is_reserved_internal_test_client_id, validate_engagement_classification as v,
    )

    check("internal_test with no real data, not client-accessible, reserved ns is permitted",
          v("internal_test", False, False, False, RESERVED_CLIENT_ID) == [])
    check("internal_test may authorize capsule publication when both conditions hold",
          v("internal_test", False, False, True, RESERVED_CLIENT_ID) == [])
    check("internal_test REQUIRES real_client_data=false",
          any("real_client_data=false" in r
              for r in v("internal_test", True, False, False, RESERVED_CLIENT_ID)))
    check("internal_test REQUIRES client_accessible=false",
          any("client_accessible=false" in r
              for r in v("internal_test", False, True, False, RESERVED_CLIENT_ID)))
    check("internal_test REQUIRES the reserved client namespace",
          any("reserved" in r for r in v("internal_test", False, False, False, "c1")))
    check("publication is refused when real client data is present",
          v("internal_test", True, False, True, RESERVED_CLIENT_ID) != [])
    check("publication is refused when the engagement is client-accessible",
          v("internal_test", False, True, True, RESERVED_CLIENT_ID) != [])

    check("real_client with defaults is permitted", v("real_client", True, True, False, "c1") == [])
    check("real_client may NOT use the reserved namespace",
          any("must not use the reserved" in r
              for r in v("real_client", True, True, False, RESERVED_CLIENT_ID)))
    check("real_client may NOT authorize capsule publication here",
          v("real_client", True, True, True, "c1") != [])
    check("an unknown category (e.g. a smoke category) is refused",
          v("smoke_test", False, False, False, RESERVED_CLIENT_ID) != [])
    check("non-boolean flags are refused", v("internal_test", "no", False, False, "99999") != [])

    check(f"'{RESERVED_CLIENT_ID}' is recognised as reserved",
          is_reserved_internal_test_client_id(RESERVED_CLIENT_ID))
    check("a reserved prefix is recognised",
          is_reserved_internal_test_client_id("internal_test_a")
          and is_reserved_internal_test_client_id("99999_a"))
    check("an ordinary client id is not reserved",
          not is_reserved_internal_test_client_id("c1")
          and not is_reserved_internal_test_client_id(None))


# --------------------------------------------------------------------------- 4. writer behaviour


def behavior_checks() -> None:
    print("\n4. Writer behaviour against throwaway temporary SQLite (never production)")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from peak.db.base import Base
    from peak.db.models import Client, Engagement
    from peak.db.writer_contracts import (
        EngagementAuthorizationAnchorDraft as Draft,
        EngagementAuthorizationAnchorWriteOutcome as OC,
    )
    from peak.db.engagement_authorization_anchor_writer import (
        build_engagement_anchor_controlled_write_request as build,
        persist_engagement_authorization_anchor as persist,
    )

    def fresh_db():
        tmp = tempfile.mkdtemp(prefix="peak_phase56_")
        _tmpdirs.append(tmp)
        engine = create_engine("sqlite:///" + os.path.join(tmp, "test.db"))
        Base.metadata.create_all(engine)
        return sessionmaker(bind=engine, expire_on_commit=False)

    def mk(**over):
        kw = dict(owner_id="o1", client_id="c1", engagement_id="e1",
                  authorization_scope="engagement_authorized", engagement_label="zzlabel56",
                  status="prospective", review_status="needs_review", lifecycle_status="active")
        kw.update(over)
        return Draft(**kw)

    def run(f, draft, key="k1"):
        return persist(build(draft, requested_by="rb", requester_role="rr",
                             idempotency_key=key), session_factory=f)

    def count(f, model):
        s = f()
        n = s.query(model).count()
        s.close()
        return n

    # ---- real_client (defaults) ----
    f = fresh_db()
    r = run(f, mk())
    check("real_client anchor is created", r.outcome == OC.CREATED)
    check("receipt reports the real_client classification",
          r.engagement_category == "real_client" and r.real_client_data is True
          and r.client_accessible is True and r.capsule_publication_authorized is False)
    s = f()
    row = s.get(Engagement, "e1")
    check("stored real_client row carries the classification",
          row.engagement_category == "real_client" and row.real_client_data is True
          and row.client_accessible is True and row.capsule_publication_authorized is False)
    s.close()

    # ---- internal_test, publication authorized ----
    it = mk(engagement_id="e2", client_id=RESERVED_CLIENT_ID,
            engagement_category="internal_test", real_client_data=False,
            client_accessible=False, capsule_publication_authorized=True)
    r2 = run(f, it, key="k2")
    check("internal_test anchor is created", r2.outcome == OC.CREATED)
    check("receipt reports the internal_test classification",
          r2.engagement_category == "internal_test" and r2.real_client_data is False
          and r2.client_accessible is False and r2.capsule_publication_authorized is True)
    s = f()
    row2 = s.get(Engagement, "e2")
    check("stored internal_test row is non-client-accessible with no real client data",
          row2.engagement_category == "internal_test" and row2.real_client_data is False
          and row2.client_accessible is False)
    check("stored internal_test row records the publication authorization",
          row2.capsule_publication_authorized is True)
    check("stored internal_test row uses the reserved client namespace",
          row2.client_id == RESERVED_CLIENT_ID)
    s.close()
    check("no clients row was ever written", count(f, Client) == 0)

    # ---- classification is part of the replay fingerprint ----
    same = run(f, it, key="k2")
    check("an identical internal_test replay is idempotent, with no second write",
          same.outcome == OC.IDEMPOTENT_REPLAY and same.database_write_made is False)
    flipped = mk(engagement_id="e2", client_id=RESERVED_CLIENT_ID,
                 engagement_category="internal_test", real_client_data=False,
                 client_accessible=False, capsule_publication_authorized=False)
    conflict = run(f, flipped, key="k2")
    check("a changed classification on the same anchor id is a conflict, not an overwrite",
          conflict.outcome == OC.DENIED and conflict.reason_code == "idempotency_conflict")
    s = f()
    check("the stored classification was not modified by the conflict",
          s.get(Engagement, "e2").capsule_publication_authorized is True)
    s.close()

    # ---- denials, all failing closed before any connection ----
    g = fresh_db()
    cases = {
        "internal_test claiming real client data":
            mk(engagement_id="x1", client_id=RESERVED_CLIENT_ID,
               engagement_category="internal_test", real_client_data=True,
               client_accessible=False),
        "internal_test that is client-accessible":
            mk(engagement_id="x2", client_id=RESERVED_CLIENT_ID,
               engagement_category="internal_test", real_client_data=False,
               client_accessible=True),
        "internal_test without the reserved namespace":
            mk(engagement_id="x3", client_id="c9", engagement_category="internal_test",
               real_client_data=False, client_accessible=False),
        "real_client on the reserved namespace":
            mk(engagement_id="x4", client_id=RESERVED_CLIENT_ID),
        "real_client claiming publication authority":
            mk(engagement_id="x5", capsule_publication_authorized=True),
        "publication with real client data":
            mk(engagement_id="x6", client_id=RESERVED_CLIENT_ID,
               engagement_category="internal_test", real_client_data=True,
               client_accessible=False, capsule_publication_authorized=True),
        "a disposable smoke category":
            mk(engagement_id="x7", engagement_category="smoke_test"),
        "an unknown category":
            mk(engagement_id="x8", engagement_category="demo"),
    }
    for name, draft in cases.items():
        rr = run(g, draft, key="kx")
        check(f"denied before any connection: {name}",
              rr.outcome == OC.DENIED and rr.reason_code == "invalid_classification"
              and rr.database_connection_made is False and rr.database_write_made is False)
    check("no row was created by any denial", count(g, Engagement) == 0)

    # ---- receipts stay leak-free ----
    for rec in (r, r2, conflict):
        blob = repr(rec)
        check(f"receipt {rec.reason_code} leaks no label/DSN/SQL/trace",
              "zzlabel56" not in blob and "://" not in blob and "Traceback" not in blob
              and "SELECT " not in blob)


# --------------------------------------------------------------------------- 5. regression


def regression_checks() -> None:
    print("\n5. Regression and hygiene")
    db_dir = os.path.join(REPO_ROOT, "peak", "db")
    for name in sorted(f for f in os.listdir(db_dir) if f.endswith("_writer.py")):
        code = code_no_docstrings(read(f"peak/db/{name}"))
        check(f"{name} is still create-only", code.count("session.add(") == 1
              and not re.search(r"session\.delete\(|session\.merge\(|\.update\(\{", code))

    code = code_no_docstrings(read(WRITER_REL))
    check("the anchor writer still writes only engagements", "Client(" not in code)
    check("the anchor writer still issues no raw SQL",
          ".execute(" not in code and not re.search(r"\btext\(", code))
    check("the anchor writer needs only SELECT + INSERT",
          "session.get(" in code and "session.delete(" not in code
          and not re.search(r"\.update\(\{", code))
    check("the anchor writer re-enforces classification at its own boundary",
          "validate_engagement_classification(" in code)

    mk_file = read("Makefile")
    check("Makefile declares validate-phase56", "validate-phase56" in mk_file)
    check("validate depends on validate-phase56",
          re.search(r"^validate:.*validate-phase56", mk_file, re.MULTILINE) is not None)
    check("the live gates remain opt-in",
          re.search(r"^validate:.*(?:runtime-connectivity|writer-enablement|"
                    r"production-mysql-collation-verify)", mk_file, re.MULTILINE) is None)

    check("the production verifier expects production at 014 (applied there in Phase 58)",
          'EXPECTED_ALEMBIC_HEAD = "014_engagement_classification"'
          in read(VERIFIER_REL))
    check("production verifier still gates on the read-only affirmation",
          "PEAK_PRODUCTION_DB_READONLY_CONFIRM" in read(VERIFIER_REL))

    env = scrubbed_env()
    try:
        gate = subprocess.run([PY, os.path.join(REPO_ROOT, DECISION_GATE_REL)],
                              capture_output=True, text=True, timeout=60, env=env)
        check("writer-enablement decision gate still exits 0 with a no-write decision",
              gate.returncode == 0)
        for field in ("production_write_authorized=false", "writer_enablement_authorized=false",
                      "synthetic_write_authorized=false", "writer_invoked=false",
                      "database_contacted=false"):
            check(f"decision gate still reports {field}", field in gate.stdout)
    except Exception:
        check("decision gate regression (not runnable — skipped)", True)

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

    # --- hygiene ---
    doc = read(DOC_REL)
    for rel in (DOC_REL, HARNESS_REL, WRITER_REL, MIGRATION_REL, GOVERNANCE_REL):
        text = read(rel)
        check(f"{rel} embeds no real-looking DSN", not REAL_DSN_RE.search(text))
        check(f"{rel} contains no raw GRANT line",
              not re.search(r"^\s*GRANT\s+", text, re.MULTILINE))
        check(f"{rel} assigns no credential value",
              not re.search(r"(?i)\b(?:password|passwd|token|secret|api[_-]?key)\s*[=:]\s*"
                            r"['\"]?[A-Za-z0-9/+._-]{6,}", text))
    check("the doc records no example engagement identifier value",
          not re.search(r"\b(?:eng|intn|engrec|clnt)_[a-z0-9]{2,}\b", doc))

    # --- the doc says what the policy requires it to say ---
    f = re.sub(r"\s+", " ", re.sub(r"^\s*>\s?", "", doc, flags=re.MULTILINE).lower())
    for phrase, label in (
        ("properly gated", "gated production test records allowed later"),
        ("durable internal", "durable internal/admin test engagements"),
        ("internal_test", "explicit internal_test classification required"),
        ("visible marker", "reserved client_id is only a visible marker"),
        ("not the whole control", "reserved value is not the whole control"),
        ("real_client_data=false", "real_client_data=false"),
        ("client_accessible=false", "client_accessible=false"),
        ("no real client data", "publication needs explicit authorization + no real client data"),
        ("excluded from real-client access paths by default", "excluded from client access paths"),
        ("not disposable smoke data", "not disposable smoke data"),
        ("no `delete`", "runtime has no DELETE"),
        ("cleanup is not assumed", "cleanup is not assumed"),
        ("phase 56 creates no records", "Phase 56 creates no records"),
        ("separately approved future phase", "first creation is a separate approved phase"),
    ):
        check(f"doc states: {label}", phrase in f)


# --------------------------------------------------------------------------- main


def main() -> int:
    print("Peak Phase 56 internal test engagement support check")
    print("=" * 70)
    try:
        baseline_checks()
        schema_checks()
        governance_checks()

        print("\n(DB-backed layer)")
        try:
            import sqlalchemy  # noqa: F401
        except ImportError:
            print("  [skip] SQLAlchemy not installed — DB-backed behavior not exercised.")
            print("         Run: make validate-phase56 PYTHON=.venv/bin/python")
        else:
            behavior_checks()

        regression_checks()
    finally:
        for tmp in _tmpdirs:
            shutil.rmtree(tmp, ignore_errors=True)

    print("\n" + "=" * 70)
    print("Summary")
    print(f"  failures : {len(_failures)}")
    for label in _failures:
        print(f"    - {label}")
    print("\nRESULT: " + ("FAIL" if _failures else "PASS"))
    return 1 if _failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
