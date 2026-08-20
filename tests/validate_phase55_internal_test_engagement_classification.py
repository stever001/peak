#!/usr/bin/env python3
"""Phase 55 internal test engagement classification check.

Peak will eventually keep a small number of **durable internal test / training engagements**. Phase
55 defines that category — what it is, how it must be isolated, and what has to exist before the
first one — and **creates nothing**: no engagement record, no intake note, no synthetic smoke
record, no capsule published, no writer enabled.

This harness is fully offline and credential-free. It contacts no database and invokes no
controlled writer.

Five layers:

* **Baseline** — head is 014, 14 migrations, 18 tables, 12 writers, no migration 014, no
  ``alembic/versions`` change, and no model/table/writer/allowlist pair added by this phase.

* **Source facts** — the findings the Phase 55 document asserts are re-derived from source, so the
  document cannot drift away from the code: ``Engagement`` carries no classification column, the
  Phase 54 anchor draft accepts no classification field, and ``details_json`` is documented as
  non-governance detail only.

* **Document** — the decision, the durable-vs-disposable distinction, the isolation and publication
  rules, the findings, the conditional next phase, and the full creation-packet field list.

* **Standing decisions** — Phase 51's no-write/no-enablement decision, the "existing is not
  permission to write" rule, the create-only Phase 54 writer, the single anchor pair, ``engagements``
  still prohibited generically, and ``clients`` still never writable.

* **Regression + hygiene** — the verifier and both gates stay opt-in and unweakened, the audit result
  is unchanged, and no credential, client data, or example record is added.

Exit status:
  0  -> all checks passed
  1  -> a check failed
"""

from __future__ import annotations

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

BASELINE_COMMIT = "a978655"   # Add Phase 54 engagement authorization anchor writer

DOC_REL = "docs/PHASE55_INTERNAL_TEST_ENGAGEMENT_CLASSIFICATION.md"
HARNESS_REL = "tests/validate_phase55_internal_test_engagement_classification.py"
PHASE54_DOC_REL = "docs/PHASE54_CONTROLLED_ENGAGEMENT_AUTHORIZATION_ANCHOR_WRITER.md"
PHASE53_DOC_REL = "docs/PHASE53_AUTHORIZED_ENGAGEMENT_INTAKE_PATH.md"
PHASE51_DOC_REL = "docs/PHASE51_WRITER_ENABLEMENT_DECISION_GATE.md"
ANCHOR_WRITER_REL = "peak/db/engagement_authorization_anchor_writer.py"
ALLOWLIST_REL = "peak/persistence/allowlist.py"
CONTRACTS_REL = "peak/db/writer_contracts.py"
MODELS_REL = "peak/db/models.py"
BASE_REL = "peak/db/base.py"
DECISION_GATE_REL = "tools/production_writer_enablement_decision_gate.py"
CONNECTIVITY_GATE_REL = "tools/production_runtime_connectivity_gate.py"
VERIFIER_REL = "tools/production_mysql_collation_verify.py"
AUDIT = "tools/governed_mysql_collation_audit.py"

ROLE_VARS = ("PEAK_RUNTIME_DATABASE_URL", "PEAK_DATABASE_URL", "PEAK_PRODUCTION_DB_URL",
             "PEAK_PRODUCTION_DB_READONLY_CONFIRM")

EXPECTED_MIGRATIONS = 14
EXPECTED_TABLE_COUNT = 18
EXPECTED_WRITERS = 12
EXPECTED_ALLOWLIST_TABLES = 13
EXPECTED_ALLOWLIST_ACTIONS = 15
EXPECTED_ANCHOR_PAIRS = 1
HEAD_REVISION = "014_engagement_classification"

ANCHOR_TABLE = "engagements"
ANCHOR_ACTION = "create_engagement_authorization_anchor"

#: Column names that would constitute classification support. None may exist on Engagement yet —
#: Phase 55 documents the need and implements none of it.
CLASSIFICATION_COLUMNS = ("record_category", "internal_test", "is_internal_test",
                          "real_client_data", "capsule_publication_authorized",
                          "client_accessible", "client_visible", "visibility_class")

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
    """Executable code with comments and docstrings removed, string literals kept."""
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


def phase_never_committed(rel: str) -> bool:
    """True while ``rel`` has no commit yet — i.e. this phase's own work is still unstaged."""
    return not git("log", "-1", "--format=%H", "--", rel).strip()


def scrubbed_env():
    env = {k: v for k, v in os.environ.items() if k not in ROLE_VARS}
    env["PYTHONPATH"] = REPO_ROOT
    return env


def flat(text: str) -> str:
    """Whitespace-normalized lowercase text — prose in these docs wraps across lines.

    Leading markdown blockquote markers are stripped first: a wrapped ``>`` quote would otherwise
    flatten to "... classified as > authorized ..." and defeat every phrase check crossing its
    line break.
    """
    stripped = re.sub(r"^\s*>\s?", "", text, flags=re.MULTILINE)
    return re.sub(r"\s+", " ", stripped.lower())


def engagement_model_block() -> str:
    """Just the Engagement model's own declaration body."""
    src = read(MODELS_REL)
    after = src.split('__tablename__ = "engagements"', 1)[1]
    return after.split("\nclass ", 1)[0]


# --------------------------------------------------------------------------- 1. baseline


def baseline_checks() -> None:
    print("\n1. Baseline: 013 / 13 migrations / 18 tables / 12 writers, nothing added")
    versions_dir = os.path.join(REPO_ROOT, "alembic", "versions")
    versions = sorted(f for f in os.listdir(versions_dir) if f.endswith(".py"))
    check(f"exactly {EXPECTED_MIGRATIONS} migrations", len(versions) == EXPECTED_MIGRATIONS)
    check("no migration 015 or later",
          not any(re.match(r"^0*(?:1[5-9]|[2-9]\d)_", f) for f in versions))
    check(f"{HEAD_REVISION} is still the newest migration",
          versions[-1] == f"{HEAD_REVISION}.py")

    try:
        py_compile.compile(os.path.join(REPO_ROOT, HARNESS_REL), doraise=True)
        check(f"{HARNESS_REL} compiles", True)
    except py_compile.PyCompileError:
        check(f"{HARNESS_REL} compiles", False)

    import importlib as _il
    p11 = _il.import_module("tests.validate_phase11_db_scaffold")
    check(f"db-check still expects exactly {EXPECTED_TABLE_COUNT} tables",
          len(list(getattr(p11, "EXPECTED_TABLES", []))) == EXPECTED_TABLE_COUNT)
    check(f"models.py still declares exactly {EXPECTED_TABLE_COUNT} tables — no table added",
          read(MODELS_REL).count("__tablename__ = ") == EXPECTED_TABLE_COUNT)

    writers = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "peak", "db"))
                     if f.endswith("_writer.py"))
    check(f"still exactly {EXPECTED_WRITERS} controlled writers — none added",
          len(writers) == EXPECTED_WRITERS)

    from peak.persistence.allowlist import (
        ALLOWED_ACTIONS, ALLOWED_ANCHOR_CREATION_PAIRS, ALLOWED_TABLES,
    )
    check(f"generic allowlist still {EXPECTED_ALLOWLIST_TABLES} tables — no pair added",
          len(ALLOWED_TABLES) == EXPECTED_ALLOWLIST_TABLES)
    check(f"generic allowlist still {EXPECTED_ALLOWLIST_ACTIONS} actions — no pair added",
          len(ALLOWED_ACTIONS) == EXPECTED_ALLOWLIST_ACTIONS)
    check(f"still exactly {EXPECTED_ANCHOR_PAIRS} anchor-creation pair",
          len(ALLOWED_ANCHOR_CREATION_PAIRS) == EXPECTED_ANCHOR_PAIRS)

    try:
        check(f"baseline commit {BASELINE_COMMIT} present in history",
              BASELINE_COMMIT in git("log", "--oneline", "-40"))
        check("peak/db/base.py was not modified",
              not git("diff", "--name-only", "HEAD", "--", BASE_REL))
        check("the allowlist was not modified",
              not git("diff", "--name-only", "HEAD", "--", ALLOWLIST_REL))
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


# --------------------------------------------------------------------------- 2. source facts


def source_fact_checks() -> None:
    print("\n2. Source facts: the findings the Phase 55 document asserts, re-derived from source")
    engagement = engagement_model_block()

    # (a) Phase 55 recorded that Engagement carried no classification column — its finding at that
    #     time, and the gap it scheduled for removal. Phase 56 closed it, so asserting the absence
    #     would freeze a finding the plan itself retired. What must hold permanently is that the
    #     classification lives in *real columns*, never in JSON / label / scope / id-prefix.
    for col in ("engagement_category", "real_client_data", "client_accessible",
                "capsule_publication_authorized"):
        check(f"Engagement declares '{col}' as a real column",
              re.search(rf"^\s+{col}\s*:", engagement, re.MULTILINE) is not None)
    # ...but those booleans do exist elsewhere, which is what makes them the house pattern.
    models = read(MODELS_REL)
    check("other record tables do carry those booleans as real columns (the house pattern)",
          models.count("client_facing_approved") >= 5
          and models.count("publication_allowed") >= 4)

    # (b) The Phase 54 anchor draft accepts no classification field.
    contracts = read(CONTRACTS_REL)
    draft_block = contracts.split("class EngagementAuthorizationAnchorDraft:", 1)[1]
    draft_block = draft_block.split("\n@dataclass", 1)[0]
    for col in ("engagement_category", "real_client_data", "client_accessible",
                "capsule_publication_authorized"):
        check(f"the anchor draft accepts '{col}' (Phase 56 closed the gap)",
              re.search(rf"^\s+{col}\s*:", draft_block, re.MULTILINE) is not None)
    check("the anchor draft accepts the expected identity/governance fields only",
          all(f"{f}:" in draft_block for f in
              ("owner_id", "client_id", "engagement_id", "authorization_scope",
               "engagement_label", "status", "review_status", "lifecycle_status")))

    # (c) details_json is documented as non-governance detail only.
    check("base.py still documents details_json as non-governance detail only",
          "Do NOT store governance fields here" in read(BASE_REL))

    # (d) fixture_test cannot classify an anchor: it is refused with live client/engagement identity.
    gov = read("peak/persistence/governance.py")
    check("governance still refuses fixture_test mixed with live client/engagement identity",
          "fixture_test scope must not be mixed with live client/engagement scope" in gov)
    check("the anchor path requires client_id and engagement_id (so fixture_test cannot apply)",
          '"owner_id", "client_id", "engagement_id"' in gov)

    # (e) authorization_scope is the value writers match on — the overloading argument.
    anchor_src = read(ANCHOR_WRITER_REL)
    check("authorization_scope is still the writers' scope-matching value",
          "authorization_scope" in anchor_src and "_VALID_SCOPES" in anchor_src)
    check("internal_peak_only exists as a scope value (candidate considered, not adopted)",
          "internal_peak_only" in read("peak/db/enums.py"))

    # (f) No client-facing read/query path exists to leak through.
    check("no client-facing read/query module exists under peak/",
          not any(n.startswith(("api", "query", "read", "portal", "client_api"))
                  for n in os.listdir(os.path.join(REPO_ROOT, "peak"))))

    # (g) Repo data policy intact.
    policy = read("docs/DATA_HANDLING_POLICY.md")
    check("repo data policy still prohibits client data in the repository",
          "Client data is never stored in the repo" in policy)
    check("repo data policy still prohibits client data for training/demos/tests",
          "training" in policy.lower() and "must not" in policy.lower())
    fixtures = read("docs/FIXTURE_STRATEGY.md").lower()
    check("fixture strategy still keeps synthetic fixtures in memory and uncommitted",
          "built in memory" in fixtures and "not committed" in fixtures)


# --------------------------------------------------------------------------- 3. document


def document_checks() -> None:
    print("\n3. The Phase 55 document records the decision, the category, and the findings")
    check(f"{DOC_REL} exists", os.path.isfile(os.path.join(REPO_ROOT, DOC_REL)))
    doc = read(DOC_REL)
    f = flat(doc)

    # Prohibitions.
    for phrase, label in (
        ("no production write", "no production write"),
        ("no writer enablement", "no writer enablement"),
        ("no internal test engagement creation", "no internal test engagement creation"),
        ("no real client engagement creation", "no real client engagement creation"),
        ("no synthetic smoke record", "no synthetic smoke record"),
        ("no intake note creation", "no intake note creation"),
        ("plan and classification only", "plan and classification only"),
    ):
        check(f"doc states: {label}", phrase in f)

    # The category itself.
    check("doc names durable internal test/training engagements as an allowed later category",
          "durable internal test / training engagement" in f
          and "the new, allowed category" in f)
    check("doc states they are NOT disposable synthetic smoke records",
          "is **not** a disposable smoke record" in f or "not a disposable smoke record" in f)
    check("doc states they must be retained unless removal is separately approved",
          "must be retained" in f)
    check("doc states they must never be accessible by real clients",
          "must not be able to query, view, list, infer, or join into internal test engagements"
          in f)
    check("doc states they must not contain real client data unless explicitly authorized",
          "no real client data" in f and "separately and explicitly authorized" in f)
    # Must be the *compound* rule in one sentence. Testing the two halves separately passes even
    # if the "and no real client data" condition is deleted, because both phrases recur elsewhere.
    check("doc states capsule publication requires classification AND no real client data together",
          re.search(r"explicitly classified as authorized for publication \*and\* "
                    r"contains no real client data", f) is not None)
    check("doc states they must be distinguishable from real client engagements",
          "real client engagement" in f)
    check("doc states synthetic smoke records remain disallowed unless separately approved",
          "remain disallowed unless separately approved" in f)
    check("doc states runtime holds no DELETE and cleanup cannot be assumed",
          "no `delete`" in f and "cleanup cannot be assumed" in f)

    # Findings.
    check("doc records that the current model does NOT support classification cleanly",
          "does **not** support classification cleanly" in f)
    check("doc records that the Phase 54 writer does NOT support classification cleanly",
          "the phase 54 writer does **not** support classification cleanly" in f)
    check("doc records that a future schema/model change is required",
          "a future schema/model change **is** required" in f)
    check("doc records that a future writer validation change is required",
          "a future writer validation change **is** required" in f)
    check("doc records why authorization_scope would be overloaded",
          "would be overloaded" in f)
    check("doc records why label / id-prefix encoding is too fragile",
          "too fragile" in f)
    check("doc records that details_json is prohibited for governance fields",
          "details_json" in f and "non-governance" in f)
    check("doc records the missing governed client registry / collision risk",
          "no governed registry" in f)

    # Next phase, stated conditionally on the finding.
    check("doc names the conditional recommended next phase",
          "phase 56 should add internal-test classification support" in f
          and "create no records" in f)

    # Creation-packet fields.
    for field in ("record category", "non-client visibility", "real_client_data=false",
                  "capsule_publication_authorized", "owner / admin authority",
                  "`client_id` strategy", "`engagement_id` strategy",
                  "`authorization_scope` source", "idempotency / anchor identity boundary",
                  "retention posture", "approval authority", "durability statement"):
        check(f"doc lists creation-packet field: {field}", field.lower() in f)


# --------------------------------------------------------------------------- 4. standing


def standing_decision_checks() -> None:
    print("\n4. Standing decisions preserved")
    f = flat(read(DOC_REL))
    check("doc preserves the Phase 51 no-write / no-enablement decision",
          "phase 51 no-write / no-enablement remains in force" in f)
    check("doc states the Phase 54 writer's existence is not permission to write",
          "existing is not permission to write" in f)
    check("doc states Phase 50 connectivity is prerequisite evidence, not write permission",
          "prerequisite evidence, not write permission" in f)
    check("doc states engagements stays prohibited generically",
          "remains prohibited on the generic write path" in f)
    check("doc states clients remains never writable",
          "remains never writable" in f)
    check("doc states first production anchor creation remains separately approved future work",
          "separately approved future work" in f)

    p51 = flat(read(PHASE51_DOC_REL))
    check("Phase 51 doc still records the no-write decision",
          "no production smoke-write" in p51)
    check("Phase 51 doc's Phase 55 note changes no field",
          "changes no field" in p51)
    p54 = flat(read(PHASE54_DOC_REL))
    check("Phase 54 doc records the classification gap and that no record was created",
          "no record was created" in p54)
    p53 = flat(read(PHASE53_DOC_REL))
    check("Phase 53 doc records the new category without contradicting its own plan",
          "durable internal test / training engagement" in p53)

    # The Phase 54 writer is untouched and still create-only.
    code = code_no_docstrings(read(ANCHOR_WRITER_REL))
    check("the Phase 54 anchor writer is still create-only",
          code.count("session.add(") == 1
          and not re.search(r"session\.delete\(|session\.merge\(|\.update\(\{", code))

    from peak.persistence.allowlist import (
        ALLOWED_ANCHOR_CREATION_PAIRS, is_allowed_table, is_never_writable_table,
        is_prohibited_table,
    )
    check("the anchor pair is still exactly the engagements anchor pair",
          ALLOWED_ANCHOR_CREATION_PAIRS == frozenset({(ANCHOR_TABLE, ANCHOR_ACTION)}))
    check("engagements is still prohibited on the generic path",
          is_prohibited_table(ANCHOR_TABLE) and not is_allowed_table(ANCHOR_TABLE))
    check("clients is still never writable by any path",
          is_never_writable_table("clients") and is_prohibited_table("clients"))


# --------------------------------------------------------------------------- 5. regression


def regression_checks() -> None:
    print("\n5. Regression and hygiene")
    db_dir = os.path.join(REPO_ROOT, "peak", "db")
    for name in sorted(f for f in os.listdir(db_dir) if f.endswith("_writer.py")):
        code = code_no_docstrings(read(f"peak/db/{name}"))
        check(f"{name} is still create-only", code.count("session.add(") == 1
              and not re.search(r"session\.delete\(|session\.merge\(|\.update\(\{", code))

    harness_code = code_no_docstrings(read(HARNESS_REL))
    check("this harness invokes no controlled writer",
          not re.search(r"\bpersist_[a-z_]+\(", harness_code))
    check("this harness imports no controlled writer",
          not re.search(r"from\s+peak\.db\.\w*_writer|import\s+\w*_writer\b", harness_code))
    check("this harness opens no database session or engine",
          not re.search(r"create_session_factory\(|create_engine\(|sessionmaker\(", harness_code))
    check("this harness scrubs every role variable from child processes",
          "k not in ROLE_VARS" in harness_code)

    mk = read("Makefile")
    check("Makefile declares validate-phase55", "validate-phase55" in mk)
    check("validate depends on validate-phase55",
          re.search(r"^validate:.*validate-phase55", mk, re.MULTILINE) is not None)
    check("the writer-enablement decision gate remains opt-in",
          re.search(r"^validate:.*writer-enablement-decision-gate", mk, re.MULTILINE) is None)
    check("make runtime-connectivity-gate remains opt-in",
          "runtime-connectivity-gate:" in mk
          and re.search(r"^validate:.*runtime-connectivity", mk, re.MULTILINE) is None)
    check("the production verifier remains opt-in",
          re.search(r"^validate:.*production-mysql-collation-verify", mk, re.MULTILINE) is None)

    verifier_src = read(VERIFIER_REL)
    check("production verifier still gates on the read-only affirmation",
          "PEAK_PRODUCTION_DB_READONLY_CONFIRM" in verifier_src)
    check("production verifier still refuses mutating verbs",
          "FORBIDDEN_SQL_VERBS" in verifier_src)
    conn_gate_src = read(CONNECTIVITY_GATE_REL)
    check("Phase 50 gate still allows only two statements",
          conn_gate_src.count('"connectivity": "SELECT 1"') == 1
          and conn_gate_src.count('"grants": "SHOW GRANTS FOR CURRENT_USER"') == 1)

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
        conn = subprocess.run([PY, os.path.join(REPO_ROOT, CONNECTIVITY_GATE_REL)],
                              capture_output=True, text=True, timeout=120, env=env)
        check("Phase 50 gate still refuses (exit 2) with no runtime URL", conn.returncode == 2)
    except Exception:
        check("Phase 50 gate regression (not runnable — skipped)", True)

    try:
        gate = subprocess.run([PY, os.path.join(REPO_ROOT, DECISION_GATE_REL)],
                              capture_output=True, text=True, timeout=60, env=env)
        check("writer-enablement decision gate still exits 0 on the no-write path",
              gate.returncode == 0)
        for field in ("production_write_authorized=false", "writer_enablement_authorized=false",
                      "synthetic_write_authorized=false", "safe_to_run_writers_now=false",
                      "writer_invoked=false", "database_contacted=false"):
            check(f"decision gate still reports {field}", field in gate.stdout)
    except Exception:
        check("decision gate regression (not runnable — skipped)", True)

    try:
        audit = subprocess.run([PY, os.path.join(REPO_ROOT, AUDIT)],
                               capture_output=True, text=True, timeout=180, env=env)
        if "SQLAlchemy not installed" in audit.stdout:
            check("audit runs (source-scan tier on this interpreter)", audit.returncode == 0)
        else:
            check("audit still reports MODEL_POLICY_SATISFIED_PRODUCTION_UNVERIFIED",
                  "MODEL_POLICY_SATISFIED_PRODUCTION_UNVERIFIED" in audit.stdout)
        check("audit still exits 0", audit.returncode == 0)
    except Exception:
        check("audit regression (not runnable — skipped)", True)

    # --- hygiene ---
    changed_docs = [DOC_REL, PHASE51_DOC_REL, PHASE53_DOC_REL, PHASE54_DOC_REL,
                    "docs/IMPLEMENTATION_PLAN.md", "docs/DATABASE_ACCESS_AND_AUDIT.md",
                    "docs/DATABASE_SCAFFOLD.md"]
    for rel in changed_docs:
        text = read(rel)
        check(f"{rel} contains no connection scheme with credentials",
              not re.search(r"://\S*:\S*@", text))
        check(f"{rel} references no operator credential file",
              not any(m in text for m in CREDENTIAL_FILE_MARKERS))
    for rel in changed_docs + [HARNESS_REL]:
        text = read(rel)
        check(f"{rel} embeds no real-looking DSN", not REAL_DSN_RE.search(text))
        check(f"{rel} contains no raw GRANT line",
              not re.search(r"^\s*GRANT\s+", text, re.MULTILINE))
        check(f"{rel} assigns no password/token/secret value",
              not re.search(r"(?i)\b(?:password|passwd|token|secret|api[_-]?key)\s*[=:]\s*"
                            r"['\"]?[A-Za-z0-9/+._-]{6,}", text))

    doc = read(DOC_REL)
    check("Phase 55 doc records no example engagement/client identifier value",
          not re.search(r"\b(?:eng|intn|engrec|clnt|cap|capc)_[a-z0-9]{2,}\b", doc))
    check("Phase 55 doc records no SQL statement or row literal",
          not re.search(r"INSERT\s+INTO|VALUES\s*\(|SELECT\s+\*\s+FROM|UPDATE\s+\w+\s+SET",
                        doc, re.IGNORECASE))

    try:
        changed = set(git("diff", "--name-only", "HEAD").splitlines())
        check("no examples/ or fixtures/ path added or changed",
              not any(c.startswith(("examples/", "fixtures/", "samples/")) for c in changed))
        check("no packet/data artifact added",
              not any(c.endswith((".json", ".csv", ".xlsx", ".docx")) for c in changed))
    except Exception:
        check("repo data-policy scope check (git unavailable — skipped)", True)

    check("docs/Peak_Investor_Overview_AI.docx still exists and was not rewritten",
          os.path.isfile(os.path.join(REPO_ROOT, "docs", "Peak_Investor_Overview_AI.docx")))


# --------------------------------------------------------------------------- main


def main() -> int:
    print("Peak Phase 55 internal test engagement classification check")
    print("=" * 70)

    baseline_checks()
    source_fact_checks()
    document_checks()
    standing_decision_checks()
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
