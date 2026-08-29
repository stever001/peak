#!/usr/bin/env python3
"""Phase 62 internal test source/evidence request plan check.

Phase 61 recorded an ``approve_internal`` review decision on the internal_test intake note. Phase 62
translates that decision into a concrete source/evidence **request plan** and names the writer and
path Phase 63 should exercise. It is **planning-only**: no production connection, no writer
invocation, no environment read, and **no production record**.

This harness is offline and credential-free. It reads repository files and the pure allowlist /
contract modules; it opens no database, builds no engine, and spawns no operator utility.

Layers: baseline · writer contracts · plan doc · request coverage · doc propagation · isolation.

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
for _p in (REPO_ROOT, os.path.join(REPO_ROOT, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

BASELINE_COMMIT = "227c119"   # Add Phase 61 internal test intake review decision

DOC_REL = "docs/PHASE62_INTERNAL_TEST_SOURCE_EVIDENCE_REQUEST_PLAN.md"
HARNESS_REL = "tests/validate_phase62_internal_test_source_evidence_request_plan.py"
MODELS_REL = "peak/db/models.py"
WRITER_REL = "peak/db/source_ingestion_writer.py"
ALLOWLIST_REL = "peak/persistence/allowlist.py"
TAXONOMY_REL = "docs/PEAK_INTAKE_QUESTION_TAXONOMY_V0.md"

#: Every file Phase 62 is permitted to add or modify. Declared explicitly rather than derived
#: from ``git diff``: a pending-diff scan would go empty the moment this phase is committed, so
#: the content checks below would silently pass by scanning nothing. This list is scanned whether
#: the phase is staged, committed, or long since merged.
PHASE_FILES = (
    DOC_REL,
    HARNESS_REL,
    "Makefile",
    "docs/IMPLEMENTATION_PLAN.md",
    "docs/DATABASE_ACCESS_AND_AUDIT.md",
    "docs/DATABASE_SCAFFOLD.md",
    "docs/PHASE61_INTERNAL_TEST_INTAKE_REVIEW_DECISION.md",
    TAXONOMY_REL,
)

ROLE_VARS = ("PEAK_RUNTIME_DATABASE_URL", "PEAK_DATABASE_URL", "PEAK_PRODUCTION_DB_URL",
             "PEAK_PRODUCTION_DB_READONLY_CONFIRM")

EXPECTED_MIGRATIONS = 14
EXPECTED_TABLE_COUNT = 18
EXPECTED_WRITERS = 12
EXPECTED_ALLOWLIST_TABLES = 13
EXPECTED_ALLOWLIST_ACTIONS = 15
HEAD_REVISION = "014_engagement_classification"

MIN_REQUESTS = 8

ANCHOR_ID = "internal_test_001"
RESERVED_CLIENT_ID = "99999"
SCOPE = "internal_peak_only"

# Records that must NOT exist from this chain after Phase 62.
NO_RECORD_IDS = ("ing_", "evid_")

REAL_DSN_RE = re.compile(r"\b[a-z][a-z0-9+.\-]*://(?!USER:PASSWORD)(?!user:password)"
                         r"[\w.\-]+:[^\s@'\"]+@")
# The detector below must not flag its own name list, so the list lives on one marked line and
# every self-scan drops marked lines before matching. See scannable().
SENTINEL_MARK = "sentinel-name-list"
CLIENT_LIKE_NAMES = ("acme", "contoso", "initech", "globex", "northwind")  # sentinel-name-list
CLIENT_LIKE_RE = re.compile(r"(?i)\b(" + "|".join(CLIENT_LIKE_NAMES) + r")\b")

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
    """This module's executable code, with every string literal and comment blanked out.

    The self-isolation checks below assert that certain names never appear in this harness.
    Those same names appear in the check *labels*, which are string literals — so a naive scan
    would flag the very assertion that proves the absence.

    String and comment tokens are overwritten with spaces **in place** rather than dropped and
    re-joined: re-joining would insert whitespace between tokens, so a dotted expression like
    ``os.environ.get(...)`` would never match a literal-substring or regex scan and the check
    would silently pass on code that violates it.
    """
    import io
    import tokenize

    skip = {tokenize.STRING, tokenize.COMMENT}
    for name in ("FSTRING_START", "FSTRING_MIDDLE", "FSTRING_END"):
        tok_type = getattr(tokenize, name, None)
        if tok_type is not None:
            skip.add(tok_type)

    lines = source.splitlines()
    spans = [(tok.start, tok.end)
             for tok in tokenize.generate_tokens(io.StringIO(source).readline)
             if tok.type in skip]
    for (row1, col1), (row2, col2) in reversed(spans):  # reversed: earlier spans stay valid
        if row1 == row2:
            line = lines[row1 - 1]
            lines[row1 - 1] = line[:col1] + " " * (col2 - col1) + line[col2:]
        else:
            lines[row1 - 1] = lines[row1 - 1][:col1]
            for i in range(row1, row2 - 1):
                lines[i] = ""
            lines[row2 - 1] = " " * col2 + lines[row2 - 1][col2:]
    return "\n".join(lines)


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", REPO_ROOT, *args],
                          capture_output=True, text=True, timeout=20).stdout.strip()


def git_succeeds(*args: str) -> bool:
    """Run a git command for its exit status alone; stdout and stderr are discarded, so
    nothing a path or remote might carry can reach this harness's output."""
    return subprocess.run(["git", "-C", REPO_ROOT, *args],
                          capture_output=True, text=True, timeout=20).returncode == 0


def scannable(blob: str) -> str:
    """A file's text with the sentinel name list removed, for content scans.

    Only lines carrying the sentinel marker are dropped — one line in this harness. Everything
    else, including every string literal, is scanned at full strength.
    """
    return "\n".join(ln for ln in blob.splitlines() if SENTINEL_MARK not in ln)


def flat(text: str) -> str:
    """Lowercased, whitespace-collapsed, blockquote-stripped text for phrase matching."""
    return re.sub(r"\s+", " ", re.sub(r"^\s*>\s?", "", text, flags=re.MULTILINE)).lower()


def request_blocks(doc: str) -> "list[tuple[str, str]]":
    """Split the plan's per-request subsections into (heading, body) pairs."""
    parts = re.split(r"(?m)^###\s+(R\d+\s+—[^\n]*)$", doc)
    return [(parts[i].strip(), parts[i + 1]) for i in range(1, len(parts) - 1, 2)]


# --------------------------------------------------------------------------- 1. baseline


def baseline_checks() -> None:
    print("\n1. Baseline: head 014, 14 migrations, 18 tables, 12 writers, nothing added")
    # Ancestry, not recency. This asserted membership in a bounded `git log ... -40` window,
    # which is a *sliding window*, not a history check: the baseline falls out of range as later
    # phases land, failing on commits whose content has nothing to do with this phase. The
    # invariant meant here is that the baseline is still reachable from HEAD, which
    # `merge-base --is-ancestor` states directly and which never expires. Widening the window
    # would only move the expiry date.
    is_ancestor = git_succeeds("merge-base", "--is-ancestor", BASELINE_COMMIT, "HEAD")
    check(f"baseline commit {BASELINE_COMMIT} is in history", is_ancestor)
    if not is_ancestor:
        print("        reason: phase62_baseline_commit_not_ancestor")

    versions = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "alembic", "versions"))
                      if f.endswith(".py"))
    check(f"exactly {EXPECTED_MIGRATIONS} migrations", len(versions) == EXPECTED_MIGRATIONS)
    check(f"{HEAD_REVISION} is still the newest migration",
          versions[-1] == f"{HEAD_REVISION}.py")
    check("no migration 015 or later — Phase 62 adds no migration",
          not any(re.match(r"^0*(?:1[5-9]|[2-9]\d)_", f) for f in versions))
    # Pathspec narrowed to match the label: it read "alembic", which also covered
    # alembic/env.py and froze that file against every later phase.
    check("no migration file was added or modified by this phase",
          not git("diff", "--name-only", "HEAD", "--", "alembic/versions"))

    try:
        py_compile.compile(os.path.join(REPO_ROOT, HARNESS_REL), doraise=True)
        check(f"{HARNESS_REL} compiles", True)
    except py_compile.PyCompileError:
        check(f"{HARNESS_REL} compiles", False)

    check(f"models.py still declares exactly {EXPECTED_TABLE_COUNT} tables",
          read(MODELS_REL).count("__tablename__ = ") == EXPECTED_TABLE_COUNT)
    check("peak/db/models.py was not modified by this phase — no model added",
          not git("diff", "--name-only", "HEAD", "--", MODELS_REL))

    writers = sorted(f for f in os.listdir(os.path.join(REPO_ROOT, "peak", "db"))
                     if f.endswith("_writer.py"))
    check(f"still exactly {EXPECTED_WRITERS} writers — no writer added",
          len(writers) == EXPECTED_WRITERS)
    check("no controlled writer was modified by this phase",
          not [c for c in git("diff", "--name-only", "HEAD", "--", "peak").splitlines()
               if c.endswith("_writer.py")])
    check("the allowlist module was not modified by this phase — no allowlist pair added",
          not git("diff", "--name-only", "HEAD", "--", ALLOWLIST_REL))

    from peak.persistence.allowlist import (
        ALLOWED_ACTIONS, ALLOWED_ANCHOR_CREATION_PAIRS, ALLOWED_TABLES, is_allowed_table,
        is_never_writable_table, is_prohibited_table,
    )
    check("generic allowlist unchanged — no new writer/model/allowlist pair",
          len(ALLOWED_TABLES) == EXPECTED_ALLOWLIST_TABLES
          and len(ALLOWED_ACTIONS) == EXPECTED_ALLOWLIST_ACTIONS)
    check("still exactly one anchor-creation pair", len(ALLOWED_ANCHOR_CREATION_PAIRS) == 1)
    check("engagements remains prohibited generically",
          is_prohibited_table("engagements") and not is_allowed_table("engagements"))
    check("clients remains never writable by any controlled path",
          is_never_writable_table("clients"))
    check("source_system_references is still unreachable — the documented gap is real, not closed",
          "source_system_references" not in ALLOWED_TABLES)

    check("docs/Peak_Investor_Overview_AI.docx has no pending diff",
          not git("diff", "--name-only", "HEAD", "--", "docs/Peak_Investor_Overview_AI.docx"))
    check("docs/Peak_Investor_Overview_AI.docx is still tracked and untouched",
          "docs/Peak_Investor_Overview_AI.docx" in git("ls-files", "docs"))


# --------------------------------------------------------------------------- 2. writer contracts


def writer_contract_checks() -> None:
    print("\n2. The recommended Phase 63 path exists and is metadata-only by contract")
    from peak.ingestion.contracts import (
        SOURCE_INGESTION_ACTION, SOURCE_INGESTION_TABLE, SourceIngestionDraft,
    )
    from peak.persistence.allowlist import is_allowed_action, is_allowed_table

    check("source_ingestion_records is an allowed controlled-write table",
          is_allowed_table(SOURCE_INGESTION_TABLE))
    check("create_source_ingestion_record is an allowed controlled-write action",
          is_allowed_action(SOURCE_INGESTION_ACTION))

    fields = set(SourceIngestionDraft.__dataclass_fields__)
    check("the draft carries the packet reference persisted as source_reference_id",
          "packet_reference_id" in fields)
    check("the draft carries packet metadata only (schema, source type, location, hash)",
          {"packet_schema_name", "packet_schema_version", "packet_source_type",
           "packet_location_reference", "packet_hash"} <= fields)
    check("the draft carries the review-gate and posture flags",
          {"output_status", "review_status", "lifecycle_status", "authoritative",
           "client_facing_approved", "capsule_candidate_ready"} <= fields)
    check("the draft has no packet payload / raw content field",
          not ({"packet_payload", "raw_packet_content", "raw_content", "payload"} & fields))

    src = read(WRITER_REL)
    check("the writer refuses a draft carrying payload or secret-like attributes",
          "prohibited_packet_content" in src and "FORBIDDEN_CONTENT_ATTRS" in src)
    check("the writer anchors on the stored engagement and compares stored scope",
          "stored_scope_mismatch" in src and "SUPPORTED_SUBJECT_TYPES" in src)

    # Evidence follows source ingestion: the evidence record asserts characterization.
    ev = read(MODELS_REL)
    check("evidence_references asserts collection status and reliability (so it follows a source)",
          re.search(r"evidence_status[^\n]*default=\"collected\"", ev) is not None
          and "reliability" in ev)


# --------------------------------------------------------------------------- 3. plan doc


def plan_doc_checks() -> None:
    print("\n3. The Phase 62 plan states its decision, its limits, and its next path")
    doc_exists = os.path.isfile(os.path.join(REPO_ROOT, DOC_REL))
    check(f"{DOC_REL} exists", doc_exists)
    if not doc_exists:
        check("plan content checks (skipped: the doc is missing)", False)
        return

    doc = read(DOC_REL)
    f = flat(doc)
    for phrase, label in (
        ("planning-only", "the phase decision is planning-only"),
        ("no production write", "no production write is authorized"),
        ("no production record", "no production record was created"),
        ("source/evidence collection is the next step",
         "source/evidence collection is the next step after Phase 61"),
        ("report drafting and capsule publication are not yet authorized",
         "report drafting and capsule publication are not yet authorized"),
        ("internal/admin only", "the request plan is internal/admin only"),
        ("no real client data", "no real client data"),
        ("no client-facing output", "no client-facing output"),
        ("no source ingestion record was created",
         "no source ingestion record was created in Phase 62"),
        ("no evidence reference was created", "no evidence reference was created"),
        ("source_ingestion_records", "the Phase 63 target table is named"),
        ("create_source_ingestion_record", "the Phase 63 target action is named"),
        ("peak/db/source_ingestion_writer.py", "the Phase 63 writer path is named"),
        (ANCHOR_ID, "the engagement authorization anchor is named"),
        (SCOPE, "the authorization scope is named"),
        ("evidence and source collection precede analysis",
         "collection precedes analysis, report drafting, and capsule publication"),
        ("source_system_references", "the unwritable-request gap is documented"),
        ("not implemented in phase 62", "the narrowest future change is not implemented here"),
        ("same evidence request structure",
         "future real-client forms lead to the same request structure"),
    ):
        check(f"plan states: {label}", phrase in f)

    check("plan includes a sanitized first source-ingestion packet shape",
          "packet shape (sanitized)" in f
          and all(k in f for k in ("packet_reference_id", "packet_schema_name",
                                   "packet_source_type", "packet_location_reference",
                                   "packet_hash", "idempotency_key")))
    check("the proposed packet shape leaves server-controlled fields unset",
          "source_ingestion_record_id : none" in f and "created_at : none" in f)
    check("the proposed packet shape is review-gated and non-authoritative",
          all(k in f for k in ("output_status : draft", "review_status : needs_review",
                               "lifecycle_status : active", "authoritative : false",
                               "client_facing_approved : false",
                               "capsule_candidate_ready : false")))
    check("the plan names the fields the draft must never carry",
          "must never carry" in f and "packet_payload" in f)

    check("plan embeds no real-looking DSN", not REAL_DSN_RE.search(doc))
    check("plan prints no environment value",
          not re.search(r"(?m)^\s*(?:export\s+)?PEAK_\w+\s*=\s*\S", doc))
    check("plan contains no obviously client-like organisation name",
          not CLIENT_LIKE_RE.search(doc))


# --------------------------------------------------------------------------- 4. request coverage


def request_coverage_checks() -> None:
    print(f"\n4. At least {MIN_REQUESTS} requests, each mapped to categories and a deliverable")
    if not os.path.isfile(os.path.join(REPO_ROOT, DOC_REL)):
        check("request coverage checks (skipped: the doc is missing)", False)
        return

    doc = read(DOC_REL)
    blocks = request_blocks(doc)
    check(f"the plan defines at least {MIN_REQUESTS} source/evidence requests",
          len(blocks) >= MIN_REQUESTS)

    # Every request the phase brief names must be present.
    f = flat(doc)
    for phrase, label in (
        ("inventory export by sku", "current inventory export by SKU/location"),
        ("sku/item master export", "SKU/item master export"),
        ("adjustment history with reason codes", "adjustment history with reason codes"),
        ("cycle count or physical count results", "cycle or physical count results"),
        ("receiving and putaway records", "receiving and putaway records"),
        ("fulfillment exception data", "stockout/backorder or fulfilment exception data"),
        ("sop and process documentation", "SOP/process documentation"),
        ("system-of-record and data-export map", "system-of-record and data-export map"),
    ):
        check(f"the plan requests: {label}", phrase in f)

    required_fields = (
        ("purpose", "**Purpose:**"),
        ("Taxonomy V0 categories", "**Taxonomy V0 categories:**"),
        ("downstream deliverable", "**Downstream deliverable:**"),
        ("priority", "**Priority:**"),
        ("expected evidence type", "**Expected evidence type:**"),
        ("AI/AgentNet/capsule readiness", "**AI/AgentNet/capsule readiness:**"),
        ("internal_test-only safety", "**Safe for internal_test only:**"),
    )
    missing_field: list = []
    no_category: list = []
    bad_priority: list = []
    for heading, body in blocks:
        rid = heading.split(" ")[0]
        for label, marker in required_fields:
            if marker not in body:
                missing_field.append(f"{rid}:{label}")
        cat = re.search(r"\*\*Taxonomy V0 categories:\*\*(.+?)(?=\n- \*\*)", body, re.S)
        if not cat or not re.search(r"\b(0[1-9]|1[0-4])\b", cat.group(1)):
            no_category.append(rid)
        pri = re.search(r"\*\*Priority:\*\*\s*(required|important|optional)", body)
        if not pri:
            bad_priority.append(rid)

    check("every request states purpose, categories, deliverable, priority, evidence type, "
          "readiness, and internal_test safety",
          not missing_field)
    if missing_field:
        print("        missing: " + ", ".join(missing_field[:12]))
    check("every request maps to at least one numbered Intake Taxonomy V0 category",
          not no_category)
    check("every request carries a required / important / optional priority", not bad_priority)
    check("the requests span more than one priority level",
          len(set(re.findall(r"\*\*Priority:\*\*\s*(required|important|optional)", doc))) > 1)


# --------------------------------------------------------------------------- 5. doc propagation


def doc_propagation_checks() -> None:
    print("\n5. The surrounding docs record Phase 62 and what it does not authorize")
    targets = ("docs/IMPLEMENTATION_PLAN.md", "docs/DATABASE_ACCESS_AND_AUDIT.md",
               "docs/DATABASE_SCAFFOLD.md",
               "docs/PHASE61_INTERNAL_TEST_INTAKE_REVIEW_DECISION.md", TAXONOMY_REL)
    for rel in targets:
        blob = flat(read(rel))
        name = os.path.basename(rel)
        check(f"{name} records Phase 62", "phase 62" in blob)
        check(f"{name} states Phase 62 creates no production record",
              "no production record" in blob)
        check(f"{name} states Phase 63 should create the first source ingestion record",
              "phase 63" in blob and "source ingestion record" in blob)
        check(f"{name} states collection precedes report drafting and capsule publication",
              "precede" in blob and "capsule publication" in blob)

    plan = flat(read("docs/IMPLEMENTATION_PLAN.md"))
    check("IMPLEMENTATION_PLAN.md states the Phase 63 write is conditional on the contract",
          "if the inspected writer contract supports it" in plan)
    check("the taxonomy states future real-client forms lead to the same request structure",
          "same evidence request structure" in flat(read(TAXONOMY_REL)))

    mk = read("Makefile")
    check("Makefile declares validate-phase62", "validate-phase62" in mk)
    check("validate depends on validate-phase62",
          re.search(r"^validate:.*validate-phase62", mk, re.MULTILINE) is not None)
    check("the live gates remain opt-in",
          re.search(r"^validate:.*(?:runtime-connectivity|writer-enablement|"
                    r"production-mysql-collation-verify)", mk, re.MULTILINE) is None)


# --------------------------------------------------------------------------- 6. isolation


def isolation_checks() -> None:
    print("\n6. Phase 62 contacts no production, creates no record, and adds no fixture")
    src = read(HARNESS_REL)
    code = code_only(src)
    check("this harness creates no engine and opens no database connection",
          "create_engine" not in code and "create_session_factory" not in code)
    check("this harness imports no writer and invokes no persist_* function",
          not re.search(r"persist_\w+\s*\(", code) and "peak.db.source_ingestion_writer" not in code)
    check("this harness reads no role/environment variable",
          not re.search(r"os\.environ(?:\.get)?\s*[\[(]", code))
    check("this harness names the role variables only as a scrub list, never reading one",
          all(v in src for v in ROLE_VARS))
    check("this harness embeds no real-looking DSN", not REAL_DSN_RE.search(src))
    check("this harness resolves no home-directory path", "expanduser" not in code)

    # Phase 62 touches only documentation, this harness, and the Makefile. Asserted against the
    # declared file list and the repository's actual state, so it still holds after the commit.
    check("this phase's files are only docs, this harness, and the Makefile",
          all(c.startswith("docs/") or c == HARNESS_REL or c == "Makefile"
              for c in PHASE_FILES))
    missing = [c for c in PHASE_FILES if not os.path.isfile(os.path.join(REPO_ROOT, c))]
    check("every declared Phase 62 file is present in the repository", not missing)
    if missing:
        print("        missing: " + ", ".join(missing))
    check("the plan document and this harness are both among this phase's files",
          DOC_REL in PHASE_FILES and HARNESS_REL in PHASE_FILES)
    check("this phase declares no writer, model, allowlist, migration, or tool file",
          not [c for c in PHASE_FILES
               if c.startswith(("peak/", "tools/", "alembic/")) or c.endswith("_writer.py")])
    # Scoped to Phase 62's own claim — that *this* phase shipped no operator utility. It must not
    # forbid a source-ingestion operator outright: Phase 63 is the phase authorized to add one,
    # and the plan above recommends exactly that.
    check("no Phase 62 operator/record-creation utility was added",
          not [t for t in os.listdir(os.path.join(REPO_ROOT, "tools"))
               if "phase62" in t.lower()])
    # Scoped to Phase 62's own body. A later phase may append an addendum that cites the record
    # *it* created — that is the plan being executed, not Phase 62 having written something. The
    # claim under test is that Phase 62 itself created no source or evidence record.
    own_body = re.split(r"(?m)^##\s+\d+\.\s+Phase 6[3-9]\b", read(DOC_REL))[0]
    check("Phase 62's own sections cite no stored source or evidence record id",
          not any(re.search(rf"\b{p}[0-9a-f]{{8,}}\b", own_body) for p in NO_RECORD_IDS))

    # No fixtures / examples / sample packets, and no Phase 60 note body.
    tracked = git("ls-files").splitlines()
    check("no fixtures/examples/sample-packet directory was added",
          not [t for t in tracked
               if re.match(r"^(fixtures|examples|samples|sample_packets)/", t)])
    check("no sample or fixture packet file is tracked anywhere in the repository",
          not [t for t in tracked
               if re.search(r"(?i)(fixture|sample|example)[^/]*\.(json|ya?ml|csv|txt)$", t)])
    check("no intake note body file is tracked in the repository",
          not [t for t in tracked if "internal_test_intake_note" in t and t.endswith(".txt")])
    check("this phase adds no .txt artifact, so no note body could ride along",
          not [c for c in PHASE_FILES if c.endswith(".txt")])

    # No secrets / client data / pseudo-client data in anything this phase touched.
    for rel in [c for c in PHASE_FILES if c.endswith((".md", ".py"))]:
        blob = read(rel)
        name = os.path.basename(rel)
        check(f"{name} contains no obviously client-like organisation name",
              not CLIENT_LIKE_RE.search(scannable(blob)))
        check(f"{name} embeds no real-looking DSN", not REAL_DSN_RE.search(blob))
        check(f"{name} embeds no secret-like assignment",
              not re.search(r"(?i)(password|api[_-]?key|secret|private[_-]?key|access[_-]?key)"
                            r"\s*[:=]\s*[\"']?[A-Za-z0-9/+_\-]{8,}", blob))


# --------------------------------------------------------------------------- main


def main() -> int:
    print("Peak Phase 62 internal test source/evidence request plan check")
    print("=" * 70)

    baseline_checks()
    try:
        import sqlalchemy  # noqa: F401
    except ImportError:
        print("\n  [skip] SQLAlchemy not installed — writer-contract layer not exercised.")
        print("         Run: make validate-phase62 PYTHON=.venv/bin/python")
    else:
        writer_contract_checks()
    plan_doc_checks()
    request_coverage_checks()
    doc_propagation_checks()
    isolation_checks()

    print("\n" + "=" * 70)
    print("Summary")
    print(f"  failures : {len(_failures)}")
    for label in _failures:
        print(f"    - {label}")
    print("\nRESULT: " + ("FAIL" if _failures else "PASS"))
    return 1 if _failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
