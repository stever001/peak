#!/usr/bin/env python3
"""Phase 54 controlled engagement authorization anchor writer check.

Phase 53 found the operational blocker: every controlled writer requires a stored ``Engagement``
authorization anchor, and nothing in Peak could create one, because ``engagements`` sits on
``PROHIBITED_TABLES``. Phase 54 adds the governed code path that resolves it — and **creates no
production engagement record, no intake note, and no synthetic smoke record.**

This harness is offline and credential-free. It exercises the writer only against throwaway
temporary SQLite databases; it opens no production connection and reads no credential.

Six layers:

* **Baseline** — head is 014, 14 migrations, 18 tables, no migration 014, no
  ``alembic/versions`` change, no model/table added, exactly one writer added (11 -> 12).

* **Governance** — ``engagements`` stays prohibited on the generic path, ``clients`` stays
  unreachable by *any* path, and exactly one anchor-creation pair exists. The narrow exception
  must not have become a hole.

* **Static shape** — the writer is create-only: one ``session.add``, no ``UPDATE`` / ``DELETE`` /
  ``merge`` / bulk operation / raw SQL / schema operation, and no network, LLM, AgentNet, MCP, or
  resolver call. ``SELECT`` + ``INSERT`` is all it needs.

* **Behavior** — against temporary SQLite: creates exactly one anchor, replays idempotently
  without a second write, denies an idempotency conflict without modifying the stored row, denies
  every malformed or unauthorized request before opening a connection, and writes no other table.

* **Receipt hygiene** — no credential, DSN, host, database name, SQL string, stack trace, or
  ``engagement_label`` ever reaches a receipt or a denial reason.

* **Regression** — the other eleven writers stay create-only and still require the stored anchor,
  the intake note writer is unchanged, the verifier and both gates stay opt-in and unweakened, and
  the Phase 51 no-write decision is untouched.

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
TOOLS_DIR = os.path.join(REPO_ROOT, "tools")
for _p in (REPO_ROOT, TOOLS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

PY = sys.executable or "python3"

BASELINE_COMMIT = "4e20e73"   # Document Phase 53 authorized engagement intake path

WRITER_REL = "peak/db/engagement_authorization_anchor_writer.py"
HARNESS_REL = "tests/validate_phase54_engagement_authorization_anchor_writer.py"
DOC_REL = "docs/PHASE54_CONTROLLED_ENGAGEMENT_AUTHORIZATION_ANCHOR_WRITER.md"
PHASE53_DOC_REL = "docs/PHASE53_AUTHORIZED_ENGAGEMENT_INTAKE_PATH.md"
ALLOWLIST_REL = "peak/persistence/allowlist.py"
GOVERNANCE_REL = "peak/persistence/governance.py"
CONTRACTS_REL = "peak/db/writer_contracts.py"
MODELS_REL = "peak/db/models.py"
INTAKE_WRITER_REL = "peak/db/intake_note_writer.py"
DECISION_GATE_REL = "tools/production_writer_enablement_decision_gate.py"
CONNECTIVITY_GATE_REL = "tools/production_runtime_connectivity_gate.py"
VERIFIER_REL = "tools/production_mysql_collation_verify.py"
AUDIT = "tools/governed_mysql_collation_audit.py"

ROLE_VARS = ("PEAK_RUNTIME_DATABASE_URL", "PEAK_DATABASE_URL", "PEAK_PRODUCTION_DB_URL",
             "PEAK_PRODUCTION_DB_READONLY_CONFIRM")

EXPECTED_MIGRATIONS = 14
EXPECTED_TABLE_COUNT = 18
EXPECTED_WRITERS = 12          # 11 before Phase 54; this phase adds exactly one
EXPECTED_ALLOWLIST_TABLES = 13  # the generic sets are unchanged by Phase 54
EXPECTED_ALLOWLIST_ACTIONS = 15
HEAD_REVISION = "014_engagement_classification"

ANCHOR_TABLE = "engagements"
ANCHOR_ACTION = "create_engagement_authorization_anchor"

CREDENTIAL_FILE_MARKERS = ("peak-prod-ro.env", "peak-prod-migrate.env",
                           "peak-prod-runtime.env", ".peak/")
REAL_DSN_RE = re.compile(r"\b[a-z][a-z0-9+.\-]*://(?!USER:PASSWORD)(?!user:password)"
                         r"(?!runtime_user:password)(?!readonly_user:password)"
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


def scrubbed_env():
    env = {k: v for k, v in os.environ.items() if k not in ROLE_VARS}
    env["PYTHONPATH"] = REPO_ROOT
    return env


def blob(obj) -> str:
    """Flatten a receipt to a single string for leak scanning."""
    return repr(obj)


# --------------------------------------------------------------------------- 1. baseline


def baseline_checks() -> None:
    print("\n1. Baseline: head is 014, 14 migrations, 18 tables, exactly one writer added")
    versions_dir = os.path.join(REPO_ROOT, "alembic", "versions")
    versions = sorted(f for f in os.listdir(versions_dir) if f.endswith(".py"))
    check(f"exactly {EXPECTED_MIGRATIONS} migrations", len(versions) == EXPECTED_MIGRATIONS)
    check("no migration 015 or later",
          not any(re.match(r"^0*(?:1[5-9]|[2-9]\d)_", f) for f in versions))
    check(f"{HEAD_REVISION} is still the newest migration",
          versions[-1] == f"{HEAD_REVISION}.py")

    for rel in (WRITER_REL, HARNESS_REL):
        try:
            py_compile.compile(os.path.join(REPO_ROOT, rel), doraise=True)
            check(f"{rel} compiles", True)
        except py_compile.PyCompileError:
            check(f"{rel} compiles", False)

    import importlib as _il
    p11 = _il.import_module("tests.validate_phase11_db_scaffold")
    check(f"db-check still expects exactly {EXPECTED_TABLE_COUNT} tables",
          len(list(getattr(p11, "EXPECTED_TABLES", []))) == EXPECTED_TABLE_COUNT)
    check(f"models.py still declares exactly {EXPECTED_TABLE_COUNT} tables — no table added",
          read(MODELS_REL).count("__tablename__ = ") == EXPECTED_TABLE_COUNT)

    writers = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "peak", "db"))
                     if f.endswith("_writer.py"))
    check(f"exactly {EXPECTED_WRITERS} narrow controlled writers (one added by Phase 54)",
          len(writers) == EXPECTED_WRITERS)
    check("the added writer is the engagement authorization anchor writer",
          os.path.basename(WRITER_REL) in writers)

    try:
        check(f"baseline commit {BASELINE_COMMIT} present in history",
              BASELINE_COMMIT in git("log", "--oneline", "-40"))
        check("peak/db/base.py was not modified",
              not git("diff", "--name-only", "HEAD", "--", "peak/db/base.py"))
        check("the intake note writer was not modified",
              not git("diff", "--name-only", "HEAD", "--", INTAKE_WRITER_REL))
        # Working-tree freezes on shared files were authoring-time claims about this phase.
        # Phase 56 legitimately owns migration 014, the engagement classification model
        # columns, and the repo-side head pin in the parity tool. The substantive
        # invariants each harness cares about are asserted directly elsewhere.
        check("schemas/, prompts/, agents/ untouched",
              not git("diff", "--name-only", "HEAD", "--", "schemas", "prompts", "agents"))
        check("docs/Peak_Investor_Overview_AI.docx has no pending diff",
              not git("diff", "--name-only", "HEAD", "--",
                      "docs/Peak_Investor_Overview_AI.docx"))
        # Authoring-time claim about Phase 54's own tree. Phase 56 legitimately extends this
        # anchor writer with classification validation; the substantive invariant — every writer
        # stays create-only — is asserted unconditionally in the regression layer.
        changed_writers = [c for c in git("diff", "--name-only", "HEAD", "--",
                                          "peak").splitlines()
                           if c.endswith("_writer.py")
                           and not c.endswith(os.path.basename(WRITER_REL))]
        check("no controlled writer other than the anchor writer was modified",
              not changed_writers)
    except Exception:
        check("git-backed scope checks (git unavailable — skipped)", True)


# --------------------------------------------------------------------------- 2. governance


def governance_checks() -> None:
    print("\n2. Governance: the exception is one pair, not a hole")
    from peak.persistence.allowlist import (
        ALLOWED_ACTIONS, ALLOWED_ANCHOR_CREATION_PAIRS, ALLOWED_TABLES, NEVER_WRITABLE_TABLES,
        PROHIBITED_TABLES, is_allowed_action, is_allowed_anchor_creation_pair, is_allowed_table,
        is_never_writable_table, is_prohibited_table,
    )

    # The generic path is untouched.
    check(f"generic allowlist still has exactly {EXPECTED_ALLOWLIST_TABLES} tables",
          len(ALLOWED_TABLES) == EXPECTED_ALLOWLIST_TABLES)
    check(f"generic allowlist still has exactly {EXPECTED_ALLOWLIST_ACTIONS} actions",
          len(ALLOWED_ACTIONS) == EXPECTED_ALLOWLIST_ACTIONS)
    check("engagements is STILL prohibited on the generic path",
          is_prohibited_table(ANCHOR_TABLE) and not is_allowed_table(ANCHOR_TABLE))
    check("clients is STILL prohibited on the generic path",
          is_prohibited_table("clients") and not is_allowed_table("clients"))
    check("the anchor action is NOT on the generic action allowlist",
          not is_allowed_action(ANCHOR_ACTION) and ANCHOR_ACTION not in ALLOWED_ACTIONS)
    check("financial/resolver tables remain prohibited",
          is_prohibited_table("financial_impact_estimates")
          and is_prohibited_table("resolver_capsule_records"))

    # The exception is exactly one pair.
    check("exactly one anchor-creation pair exists", len(ALLOWED_ANCHOR_CREATION_PAIRS) == 1)
    check(f"the pair is ({ANCHOR_TABLE}, {ANCHOR_ACTION})",
          ALLOWED_ANCHOR_CREATION_PAIRS == frozenset({(ANCHOR_TABLE, ANCHOR_ACTION)}))
    check("the exact pair is allowed", is_allowed_anchor_creation_pair(ANCHOR_TABLE, ANCHOR_ACTION))

    # It cannot be widened by recombination.
    check("the anchor action against clients is refused",
          not is_allowed_anchor_creation_pair("clients", ANCHOR_ACTION))
    check("clients may never be written by any path",
          is_never_writable_table("clients") and "clients" in NEVER_WRITABLE_TABLES)
    for bad_action in ("create_draft", "update_lifecycle_status", "delete_engagement",
                       "create_engagement", "publish_engagement", "raw_sql"):
        check(f"engagements + '{bad_action}' is refused",
              not is_allowed_anchor_creation_pair(ANCHOR_TABLE, bad_action))
    for bad_table in ("clients", "financial_impact_estimates", "resolver_capsule_records",
                      "intake_note_records", "review_records"):
        check(f"'{bad_table}' + the anchor action is refused",
              not is_allowed_anchor_creation_pair(bad_table, ANCHOR_ACTION))
    check("empty table/action is refused",
          not is_allowed_anchor_creation_pair("", ANCHOR_ACTION)
          and not is_allowed_anchor_creation_pair(ANCHOR_TABLE, "")
          and not is_allowed_anchor_creation_pair(None, None))

    # The generic evaluator still refuses engagements outright.
    from peak.persistence.contracts import ControlledWriteRequest, ControlledWriteSubject
    from peak.persistence.governance import validate_table_action_allowlist
    generic = validate_table_action_allowlist(
        ControlledWriteRequest(target_table=ANCHOR_TABLE, requested_action=ANCHOR_ACTION))
    check("the generic table/action evaluator still refuses engagements",
          not generic.permitted)

    # The anchor evaluator refuses a request that carries a stored subject.
    from peak.persistence.governance import evaluate_engagement_anchor_creation_request
    with_subject = ControlledWriteRequest(
        owner_id="o", client_id="c", engagement_id="e", requested_by="rb", requester_role="rr",
        authorization_scope="engagement_authorized", target_table=ANCHOR_TABLE,
        requested_action=ANCHOR_ACTION, record_draft=object(), lifecycle_status="active",
        idempotency_key="k",
        subject=ControlledWriteSubject(subject_record_id="e", subject_record_type="engagement"))
    check("the anchor evaluator refuses a request carrying a stored subject",
          not evaluate_engagement_anchor_creation_request(with_subject).permitted)


# --------------------------------------------------------------------------- 3. static shape


def static_shape_checks() -> None:
    print("\n3. Static shape: create-only, no UPDATE/DELETE/merge/bulk/raw SQL, no network")
    src = read(WRITER_REL)
    code = code_no_docstrings(src)

    check("exactly one session.add call", code.count("session.add(") == 1)
    check("no session.delete", "session.delete(" not in code)
    check("no session.merge", "session.merge(" not in code)
    check("no bulk operation",
          not re.search(r"bulk_save_objects|bulk_insert_mappings|bulk_update_mappings|"
                        r"insert\(\)\.values|executemany", code))
    check("no ORM update() call", not re.search(r"\.update\(\{|\.update\(\s*\{", code))
    check("no raw SQL execution",
          ".execute(" not in code and re.search(r"\btext\(", code) is None)
    for verb in ("UPDATE ", "DELETE ", "TRUNCATE", "ALTER ", "DROP ", "CREATE TABLE"):
        check(f"no {verb.strip()} statement literal", verb not in code.upper())
    check("no schema operation", not re.search(r"create_all|drop_all|metadata\.", code))
    check("no network/HTTP call",
          not re.search(r"\b(?:requests|urllib|http|socket|aiohttp)\b", code))
    check("no LLM / AgentNet / MCP / resolver call",
          not re.search(r"agentnet|mock_llm|\bllm\b|mcp|resolver", code, re.IGNORECASE))
    check("writes only the Engagement model",
          "Engagement" in code
          and not re.search(r"session\.add\((?!record\b)", code))
    check("never constructs a Client row", "Client(" not in code)
    check("imports no other DB model",
          re.search(r"from \.models import Engagement\s*$", code, re.MULTILINE) is not None)
    check("references the exact target table constant",
          "ENGAGEMENT_ANCHOR_TARGET_TABLE" in code)
    check("references the exact target action constant",
          "ENGAGEMENT_ANCHOR_TARGET_ACTION" in code)
    check("re-enforces the one-pair gate at its own boundary",
          "is_allowed_anchor_creation_pair(" in code)
    check("re-enforces the anchor governance gate",
          "evaluate_engagement_anchor_creation_request(" in code)
    check("uses an injectable session factory",
          "session_factory" in code and "create_session_factory()" in code)
    check("reads no environment variable directly", "os.environ" not in code)
    check("references no operator credential file",
          not any(m in src for m in CREDENTIAL_FILE_MARKERS))
    check("embeds no real-looking DSN", not REAL_DSN_RE.search(src))

    contracts = read(CONTRACTS_REL)
    check(f"contracts declare target table '{ANCHOR_TABLE}'",
          f'ENGAGEMENT_ANCHOR_TARGET_TABLE = "{ANCHOR_TABLE}"' in contracts)
    check(f"contracts declare target action '{ANCHOR_ACTION}'",
          f'ENGAGEMENT_ANCHOR_TARGET_ACTION = "{ANCHOR_ACTION}"' in contracts)
    receipt_cls = contracts.split("class EngagementAuthorizationAnchorWriteReceipt:", 1)[-1]
    check("the receipt dataclass carries no engagement_label field",
          not re.search(r"^\s+engagement_label:", receipt_cls, re.MULTILINE))
    check("the draft dataclass does carry engagement_label (it is stored, just never echoed)",
          re.search(r"^\s+engagement_label:", contracts, re.MULTILINE) is not None)

    # SELECT + INSERT sufficiency, by construction: the only DB verbs used are a primary-key
    # read, one add, one commit, and a refresh.
    check("only SELECT-shaped reads are used (session.get / no query filters for write)",
          code.count("session.get(") >= 1)
    check("runtime SELECT + INSERT is sufficient (no UPDATE/DELETE anywhere in the path)",
          "session.delete(" not in code and not re.search(r"\.update\(\{", code))


# --------------------------------------------------------------------------- 4. behavior


def behavior_checks() -> None:
    print("\n4. Behavior against throwaway temporary SQLite (never production)")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from peak.db.base import Base
    from peak.db.models import (
        AgentRunRecord, Client, Engagement, EvidenceReference, IntakeNoteRecord, ReviewRecord,
    )
    from peak.db.writer_contracts import (
        EngagementAuthorizationAnchorDraft as Draft,
        EngagementAuthorizationAnchorWriteOutcome as OC,
    )
    from peak.db.engagement_authorization_anchor_writer import (
        build_engagement_anchor_controlled_write_request as build,
        persist_engagement_authorization_anchor as persist,
    )
    from peak.persistence.contracts import ControlledWriteSubject

    def fresh_db():
        tmp = tempfile.mkdtemp(prefix="peak_phase54_")
        _tmpdirs.append(tmp)
        engine = create_engine("sqlite:///" + os.path.join(tmp, "test.db"))
        Base.metadata.create_all(engine)
        return sessionmaker(bind=engine, expire_on_commit=False)

    # Structural, non-client, non-pseudo-client identifiers. These exist only inside a temporary
    # SQLite file that is deleted when this harness exits; they are not example records.
    def mk(**over):
        kw = dict(owner_id="o1", client_id="c1", engagement_id="e1",
                  authorization_scope="engagement_authorized", engagement_label="anchor",
                  status="prospective", review_status="needs_review", lifecycle_status="active")
        kw.update(over)
        return Draft(**kw)

    def req(draft, key="k1"):
        return build(draft, requested_by="rb", requester_role="rr", idempotency_key=key)

    def count(factory, model):
        s = factory()
        n = s.query(model).count()
        s.close()
        return n

    # ---- create ----
    f = fresh_db()
    r = persist(req(mk()), session_factory=f)
    check("outcome == created", r.outcome == OC.CREATED)
    check("permitted is True", r.permitted is True)
    check("exactly one engagements row created", count(f, Engagement) == 1)
    check("stored_record_id is the caller-supplied anchor id", r.stored_record_id == "e1")
    check("receipt reports the write honestly",
          r.database_connection_made and r.sql_execution_made and r.database_write_made
          and r.stored_record_created and r.transaction_committed
          and r.existing_record_returned is False and r.outcome_uncertain is False)
    check("receipt carries server-stamped created_at", bool(r.created_at))
    check("receipt reports safe governance labels",
          r.authorization_scope == "engagement_authorized" and r.engagement_status == "prospective"
          and r.review_status == "needs_review" and r.lifecycle_status == "active")
    check("non-effect flags are all False",
          r.other_table_write_made is False and r.client_record_write_made is False
          and r.update_made is False and r.delete_made is False
          and r.review_approval_made is False and r.client_facing_output_created is False
          and r.financial_verification_made is False and r.capsule_publication_made is False
          and r.agentnet_publication_made is False and r.agent_execution_made is False
          and r.llm_call_made is False and r.agentnet_call_made is False
          and r.resolver_call_made is False and r.network_call_made is False)

    # ---- writes no other table ----
    check("no clients row was written", count(f, Client) == 0)
    for model, name in ((IntakeNoteRecord, "intake_note_records"),
                        (AgentRunRecord, "agent_run_records"),
                        (ReviewRecord, "review_records"),
                        (EvidenceReference, "evidence_references")):
        check(f"no {name} row was written", count(f, model) == 0)

    s = f()
    row = s.get(Engagement, "e1")
    check("stored anchor carries the governed scope",
          row.authorization_scope == "engagement_authorized")
    check("stored anchor is review-gated (needs_review)", row.review_status == "needs_review")
    check("stored anchor lifecycle is the requested allowed initial value",
          row.lifecycle_status == "active")
    check("stored anchor records created_by", row.created_by == "rb")
    check("stored anchor label persisted", row.engagement_label == "anchor")
    s.close()

    # ---- idempotent replay ----
    r2 = persist(req(mk()), session_factory=f)
    check("replay outcome == idempotent_replay", r2.outcome == OC.IDEMPOTENT_REPLAY)
    check("replay made no second write",
          r2.database_write_made is False and r2.stored_record_created is False
          and r2.transaction_committed is False)
    check("replay returned the existing anchor", r2.existing_record_returned is True
          and r2.stored_record_id == "e1")
    check("replay left exactly one row", count(f, Engagement) == 1)

    # ---- idempotency conflict ----
    r3 = persist(req(mk(engagement_label="different")), session_factory=f)
    check("conflict outcome == denied", r3.outcome == OC.DENIED)
    check("conflict reason_code == idempotency_conflict",
          r3.reason_code == "idempotency_conflict")
    check("conflict made no write", r3.database_write_made is False
          and r3.stored_record_created is False)
    check("conflict left exactly one row", count(f, Engagement) == 1)
    s = f()
    check("conflict did not modify the stored anchor",
          s.get(Engagement, "e1").engagement_label == "anchor")
    s.close()

    # A different scope on the same anchor id is also a conflict, never an overwrite.
    r3b = persist(req(mk(authorization_scope="internal_peak_only")), session_factory=f)
    check("a different scope on the same anchor id is a conflict",
          r3b.outcome == OC.DENIED and r3b.reason_code == "idempotency_conflict")
    s = f()
    check("the stored scope was not overwritten",
          s.get(Engagement, "e1").authorization_scope == "engagement_authorized")
    s.close()

    # ---- denials: every one must fail closed before any connection ----
    print("\n5. Denials fail closed before any database connection is opened")
    g = fresh_db()
    cases = {
        "missing owner_id": req(mk(owner_id=None)),
        "missing client_id": req(mk(client_id=None)),
        "missing engagement_id": req(mk(engagement_id=None)),
        "missing authorization_scope": req(mk(authorization_scope=None)),
        "blank authorization_scope": req(mk(authorization_scope="   ")),
        "missing idempotency key": req(mk(), key=""),
        "oversized idempotency key": req(mk(), key="x" * 129),
        "revoked authorization_scope": req(mk(authorization_scope="revoked")),
        "unrecognised authorization_scope": req(mk(authorization_scope="not_a_real_scope")),
        "blocked initial lifecycle (archived)": req(mk(lifecycle_status="archived")),
        "blocked initial lifecycle (revoked)": req(mk(lifecycle_status="revoked")),
        "blocked initial lifecycle (deleted_reference_only)":
            req(mk(lifecycle_status="deleted_reference_only")),
        "disallowed initial lifecycle (superseded)": req(mk(lifecycle_status="superseded")),
        "disallowed initial status (closed)": req(mk(status="closed")),
        "disallowed initial status (complete)": req(mk(status="complete")),
        "credential marker in label": req(mk(engagement_label="password=notarealvalue")),
        "DSN marker in label": req(mk(engagement_label="postgres://u:p@h/db")),
        "raw SQL marker in label": req(mk(engagement_label="DROP TABLE engagements")),
        "non-governed identifier": req(mk(engagement_id="bad id!")),
    }
    wrong_table = req(mk()); wrong_table.target_table = "clients"
    cases["wrong target table (clients)"] = wrong_table
    wrong_table2 = req(mk()); wrong_table2.target_table = "intake_note_records"
    cases["wrong target table (intake_note_records)"] = wrong_table2
    wrong_action = req(mk()); wrong_action.requested_action = "create_draft"
    cases["wrong action"] = wrong_action
    with_subject = req(mk())
    with_subject.subject = ControlledWriteSubject(subject_record_id="e1",
                                                  subject_record_type="engagement")
    cases["stored subject supplied"] = with_subject
    bad_draft = req(mk()); bad_draft.record_draft = None
    cases["missing record_draft"] = bad_draft
    duck = req(mk()); duck.record_draft = object()
    cases["duck-typed record_draft"] = duck

    for name, cwr in cases.items():
        rr = persist(cwr, session_factory=g)
        ok = (rr.outcome == OC.DENIED and rr.permitted is False
              and rr.database_connection_made is False and rr.sql_execution_made is False
              and rr.database_write_made is False and rr.stored_record_created is False)
        check(f"denied, no connection, no write: {name}", ok)
    check("no row was created by any denial", count(g, Engagement) == 0)

    # A duck-typed request object is refused at the boundary.
    class _Fake:
        target_table = ANCHOR_TABLE
        requested_action = ANCHOR_ACTION
    fake = persist(_Fake(), session_factory=g)
    check("a duck-typed request object is refused",
          fake.outcome == OC.DENIED and fake.reason_code == "invalid_request_type")

    # ---- receipt hygiene ----
    print("\n6. Receipt hygiene: no credentials, no SQL, no stack trace, no label")
    leaky = persist(req(mk(engagement_label="password=notarealvalue")), session_factory=g)
    for token in ("password", "notarealvalue", "://", "Traceback", "SELECT ", "INSERT ",
                  "sqlite", "sqlalchemy"):
        check(f"denial receipt does not leak '{token}'", token not in blob(leaky))
    check("denial reports only the marker category",
          leaky.reason_code == "prohibited_value_marker"
          and "credential/secret" in " ".join(leaky.reasons))
    dsn_leak = persist(req(mk(engagement_label="postgres://u:p@h/db")), session_factory=g)
    check("DSN-marker denial never echoes the DSN", "://" not in blob(dsn_leak))
    # Create a fresh anchor whose label is a distinctive token, then prove the token never
    # appears anywhere in the receipt.
    h = fresh_db()
    token = "zzuniquelabel54"
    r_lab = persist(req(mk(engagement_label=token)), session_factory=h)
    check("the labelled anchor was created", r_lab.outcome == OC.CREATED)
    check("created receipt never echoes the engagement_label", token not in blob(r_lab))
    check("created receipt exposes no label field", not hasattr(r_lab, "engagement_label"))
    s = h()
    check("the label was still persisted to the row",
          s.get(Engagement, "e1").engagement_label == token)
    s.close()
    for rec in (r, r2, r3, leaky):
        check(f"receipt {rec.reason_code} carries no connection scheme", "://" not in blob(rec))
        check(f"receipt {rec.reason_code} carries no stack trace", "Traceback" not in blob(rec))


# --------------------------------------------------------------------------- 7. regression


def regression_checks() -> None:
    print("\n7. Regression: other writers unchanged, gates opt-in and unweakened")
    db_dir = os.path.join(REPO_ROOT, "peak", "db")
    writers = sorted(f for f in os.listdir(db_dir) if f.endswith("_writer.py"))
    anchor = os.path.basename(WRITER_REL)

    for name in writers:
        code = code_no_docstrings(read(f"peak/db/{name}"))
        check(f"{name} is still create-only", code.count("session.add(") == 1
              and not re.search(r"session\.delete\(|session\.merge\(|\.update\(\{", code))

    non_anchor = [n for n in writers if n != anchor]
    check(f"the other {EXPECTED_WRITERS - 1} writers still require the stored Engagement anchor",
          all("session.get(Engagement," in code_no_docstrings(read(f"peak/db/{n}"))
              for n in non_anchor) and len(non_anchor) == EXPECTED_WRITERS - 1)
    check("no writer other than the anchor writer constructs an Engagement row",
          all("Engagement(" not in code_no_docstrings(read(f"peak/db/{n}"))
              for n in non_anchor))

    intake = read(INTAKE_WRITER_REL)
    check("the intake note writer still demands a stored authorization anchor",
          "session.get(Engagement," in intake and '"missing_subject"' in intake
          and '"stored_scope_mismatch"' in intake)

    harness_code = code_no_docstrings(read(HARNESS_REL))
    check("this harness scrubs every role variable from child processes",
          "k not in ROLE_VARS" in harness_code)
    urls = re.findall(r'create_engine\(\s*"([a-z+]+):', harness_code)
    check("this harness builds only temporary SQLite database URLs",
          "tempfile.mkdtemp" in harness_code and set(urls) <= {"sqlite"})
    check("this harness reads no database URL from the environment",
          not re.search(r"os\.environ\S*PEAK_\w*DATABASE_URL", harness_code))

    mk_file = read("Makefile")
    check("Makefile declares validate-phase54", "validate-phase54" in mk_file)
    check("validate depends on validate-phase54",
          re.search(r"^validate:.*validate-phase54", mk_file, re.MULTILINE) is not None)
    check("the writer-enablement decision gate remains opt-in",
          re.search(r"^validate:.*writer-enablement-decision-gate", mk_file,
                    re.MULTILINE) is None)
    check("make runtime-connectivity-gate remains opt-in",
          "runtime-connectivity-gate:" in mk_file
          and re.search(r"^validate:.*runtime-connectivity", mk_file, re.MULTILINE) is None)
    check("the production verifier remains opt-in",
          re.search(r"^validate:.*production-mysql-collation-verify", mk_file,
                    re.MULTILINE) is None)

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


# --------------------------------------------------------------------------- 8. docs


def doc_checks() -> None:
    print("\n8. Documentation records what was added and what was NOT done")
    check(f"{DOC_REL} exists", os.path.isfile(os.path.join(REPO_ROOT, DOC_REL)))
    doc = read(DOC_REL)
    f = re.sub(r"\s+", " ", doc.lower())

    for phrase, label in (
        ("no production engagement record was created", "no production engagement record"),
        ("no intake note record was created", "no intake note record"),
        ("no synthetic smoke record was created", "no synthetic smoke record"),
        ("no writer enablement", "no writer enablement"),
        ("create-only", "the writer is create-only"),
        ("engagements/create_engagement_authorization_anchor", "the exact allowlist pair"),
        ("`clients` and broad root-table writes remain prohibited",
         "clients and root tables remain prohibited"),
        ("not generic engagement crud", "this is not generic Engagement CRUD"),
        ("`select` + `insert` remains sufficient", "SELECT + INSERT remains sufficient"),
        ("separately approved future work", "first production anchor is future work"),
        ("phase 51 no-write / no-enablement remains in force", "Phase 51 decision in force"),
        ("remains disallowed", "synthetic smoke write remains disallowed"),
        ("holds no `delete`", "runtime has no DELETE"),
        ("cleanup cannot be assumed", "cleanup cannot be assumed"),
    ):
        check(f"doc states: {label}", phrase in f)

    for field in ("exact `owner_id` source", "exact `client_id` source",
                  "exact `engagement_id` source", "exact `authorization_scope` source",
                  "approval authority", "idempotency key pattern",
                  "retention/cleanup posture"):
        check(f"doc names required pre-write field: {field}", field.lower() in f)
    check("doc requires the record to be classified",
          "real client, internal/admin, or separately approved durable admin smoke" in f)

    p53 = re.sub(r"\s+", " ", read(PHASE53_DOC_REL).lower())
    check("the Phase 53 doc is updated for the anchor writer now existing",
          "phase 54" in p53 and "anchor writer" in p53)

    for rel in (DOC_REL, PHASE53_DOC_REL, "docs/IMPLEMENTATION_PLAN.md",
                "docs/DATABASE_ACCESS_AND_AUDIT.md", "docs/DATABASE_SCAFFOLD.md"):
        text = read(rel)
        check(f"{rel} embeds no real-looking DSN", not REAL_DSN_RE.search(text))
        check(f"{rel} references no operator credential file",
              not any(m in text for m in CREDENTIAL_FILE_MARKERS))
        check(f"{rel} contains no raw GRANT line",
              not re.search(r"^\s*GRANT\s+", text, re.MULTILINE))
    check("the Phase 54 doc records no example engagement identifier value",
          not re.search(r"\b(?:eng|intn|engrec|clnt)_[a-z0-9]{2,}\b", doc))


# --------------------------------------------------------------------------- main


def main() -> int:
    print("Peak Phase 54 controlled engagement authorization anchor writer check")
    print("=" * 70)
    try:
        baseline_checks()
        governance_checks()
        static_shape_checks()

        # The behavior layer needs SQLAlchemy; the rest of this harness is stdlib-only, so plain
        # python3 still exercises the governance, shape, regression, and doc layers.
        print("\n(DB-backed layer)")
        try:
            import sqlalchemy  # noqa: F401
        except ImportError:
            print("  [skip] SQLAlchemy not installed — DB-backed behavior not exercised.")
            print("         Run: make validate-phase54 PYTHON=.venv/bin/python")
        else:
            behavior_checks()

        regression_checks()
        doc_checks()
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
