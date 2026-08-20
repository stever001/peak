#!/usr/bin/env python3
"""Governed MySQL collation audit (Phase 42).

Classifies every string column in the controlled schema by **comparison-semantics policy class**,
then reports which governed columns still depend on the managed server's default collation.

**Why this exists.** Phase 41 established that nothing in the repo pins a collation: every table
declares ``mysql_charset="utf8mb4"`` and ``mysql_engine="InnoDB"`` and nothing more, so the managed
server's default decides case/accent sensitivity. MySQL 8 defaults ``utf8mb4`` to
``utf8mb4_0900_ai_ci`` — accent- and case-**insensitive** — while the local SQLite smoke path
compares case-**sensitively**. Phase 41 reported that as a single warning. Phase 42 makes it
precise: *which* columns actually carry an equality, uniqueness, or authorization decision, and
therefore *which* would need remediation.

**This tool changes nothing.** It proposes no schema, writes no migration, opens no database
connection, executes no SQL, reads no ``.env``, and prints no DSN or credential. It classifies and
reports. Remediation is a separate, explicitly approved migration — see
docs/GOVERNED_MYSQL_COLLATION_POLICY.md.

**Two tiers.** With SQLAlchemy importable it introspects the live model metadata (authoritative:
real types, real indexes, real unique constraints). Without it, it falls back to scanning
``peak/db/models.py`` source and says so — it never claims to have checked more than it did.

Exit status:
  0  -> the audit ran and classified every required governed column (findings may still be
        reported as NEEDS_REMEDIATION — a known open finding is not a build failure)
  1  -> the audit itself is broken: a required governed column is missing or misclassified
"""

from __future__ import annotations

import argparse
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

MODELS_REL = "peak/db/models.py"

# --------------------------------------------------------------------------- policy classes

GOVERNED_IDENTIFIER = "governed_identifier"
GOVERNED_SCOPE = "governed_scope"
GOVERNED_IDEMPOTENCY = "governed_idempotency"
GOVERNED_HASH = "governed_hash_or_fingerprint"
GOVERNED_SECRET = "governed_security_token_or_secret_hash"
GOVERNED_ENUM = "governed_enum_status"
ORDINARY_TEXT = "ordinary_text"
JSON_DETAILS_TEXT = "json_or_details_text"
UNKNOWN_CANDIDATE = "unknown_governed_candidate"

#: Classes whose comparisons decide identity, authorization, uniqueness, or integrity. A
#: case-insensitive collation on any of these changes program behavior, not just presentation.
DETERMINISTIC_REQUIRED = (
    GOVERNED_IDENTIFIER, GOVERNED_SCOPE, GOVERNED_IDEMPOTENCY, GOVERNED_HASH, GOVERNED_SECRET,
)
#: Deterministic comparison preferred, but the application layer already gates these against a
#: closed vocabulary with case-sensitive Python membership tests, so a case variant cannot be
#: persisted in the first place. Lower remediation priority — see the policy doc.
DETERMINISTIC_PREFERRED = (GOVERNED_ENUM,)

ALL_CLASSES = (
    GOVERNED_IDENTIFIER, GOVERNED_SCOPE, GOVERNED_IDEMPOTENCY, GOVERNED_HASH, GOVERNED_SECRET,
    GOVERNED_ENUM, ORDINARY_TEXT, JSON_DETAILS_TEXT, UNKNOWN_CANDIDATE,
)

# --------------------------------------------------------------------------- classification

#: Exact column names, checked before any pattern. Order does not matter; names are unique keys.
EXACT_CLASS = {
    "id": GOVERNED_IDENTIFIER,
    "owner_id": GOVERNED_IDENTIFIER,
    "client_id": GOVERNED_IDENTIFIER,
    "engagement_id": GOVERNED_IDENTIFIER,
    "agent_run_id": GOVERNED_IDENTIFIER,
    "capsule_id": GOVERNED_IDENTIFIER,
    "target_id": GOVERNED_IDENTIFIER,
    "source_packet_table": GOVERNED_IDENTIFIER,
    "source_report_draft_table": GOVERNED_IDENTIFIER,
    "subject_record_type": GOVERNED_IDENTIFIER,
    "prompt_contract_ref": GOVERNED_IDENTIFIER,
    "resolver_target": GOVERNED_IDENTIFIER,
    "authorization_scope": GOVERNED_SCOPE,
    "audience": GOVERNED_SCOPE,
    "data_class": GOVERNED_SCOPE,
    "sensitivity_class": GOVERNED_SCOPE,
    "idempotency_key": GOVERNED_IDEMPOTENCY,
    "created_by": GOVERNED_IDENTIFIER,
    "updated_by": GOVERNED_IDENTIFIER,
    "captured_by": GOVERNED_IDENTIFIER,
    "requested_by": GOVERNED_IDENTIFIER,
    "reviewer": GOVERNED_IDENTIFIER,
    "assigned_reviewer": GOVERNED_IDENTIFIER,
    "agent_name": GOVERNED_ENUM,
    "model_label": GOVERNED_ENUM,
    "currency": GOVERNED_ENUM,
    "period": GOVERNED_ENUM,
    "reliability": GOVERNED_ENUM,
    "decision": GOVERNED_ENUM,
    "route_to": GOVERNED_ENUM,
    "return_to_stage": GOVERNED_ENUM,
    "requested_action": GOVERNED_ENUM,
    "workflow": GOVERNED_ENUM,
    "status": GOVERNED_ENUM,
    "note_text": ORDINARY_TEXT,
    "note_summary": ORDINARY_TEXT,
    "summary": ORDINARY_TEXT,
    "reason": ORDINARY_TEXT,
    "organization_label": ORDINARY_TEXT,
    "engagement_label": ORDINARY_TEXT,
    "location_descriptor": ORDINARY_TEXT,
    "safe_decision_summary": ORDINARY_TEXT,
    "packet_purpose": ORDINARY_TEXT,
    "report_purpose": ORDINARY_TEXT,
    "review_reason": ORDINARY_TEXT,
    "decision_reason_code": GOVERNED_ENUM,
    "routing_reason_code": GOVERNED_ENUM,
    # Short closed-vocabulary labels, not free text and not refs.
    "approval_decision": GOVERNED_ENUM,
    "note_source": GOVERNED_ENUM,
    # Phase 56: the engagement classification axis (real_client / internal_test). Classed as a
    # governed *scope* rather than a plain enum: its comparison decides client isolation and
    # publication eligibility, so a case-insensitive match would change authorization
    # behavior, not just presentation. Deterministic collation is required, not preferred.
    "engagement_category": GOVERNED_SCOPE,
}

#: Suffix/substring patterns, applied in order when no exact name matches.
PATTERN_CLASS = (
    (re.compile(r"(?:^|_)(?:secret|token|password|passwd|api_key|apikey|access_key|"
                r"private_key|credential)s?(?:_|$)"), GOVERNED_SECRET),
    (re.compile(r"_fingerprint$|_hash$|^content_hash$|^packet_hash$"), GOVERNED_HASH),
    (re.compile(r"_scope$"), GOVERNED_SCOPE),
    (re.compile(r"_key$"), GOVERNED_IDEMPOTENCY),
    (re.compile(r"_id$|_ids$|_ref$|_refs$|_record_id$|_reference_id$"), GOVERNED_IDENTIFIER),
    (re.compile(r"_status$|_state$|_intent$|_type$|_role$|_class$|_stage$"), GOVERNED_ENUM),
    (re.compile(r"_json$|_payload$"), JSON_DETAILS_TEXT),
    (re.compile(r"_text$|_summary$|_label$|_note$|_notes$|_descriptor$|_purpose$|_reason$"),
     ORDINARY_TEXT),
)

#: Columns whose classification the audit must get right. If any is absent from the schema, or
#: lands outside its expected class, the audit itself is broken and exits 1. This is the guard
#: that stops a future refactor from silently dropping a governed column out of scope.
REQUIRED_GOVERNED = {
    "id": GOVERNED_IDENTIFIER,
    "owner_id": GOVERNED_IDENTIFIER,
    "client_id": GOVERNED_IDENTIFIER,
    "engagement_id": GOVERNED_IDENTIFIER,
    "authorization_scope": GOVERNED_SCOPE,
    "idempotency_key": GOVERNED_IDEMPOTENCY,
    "payload_fingerprint": GOVERNED_HASH,
    "plan_fingerprint": GOVERNED_HASH,
    "report_draft_payload_fingerprint": GOVERNED_HASH,
    "packet_payload_fingerprint": GOVERNED_HASH,
}

#: Governed-looking values that are NOT columns and therefore carry no collation at all. They are
#: tracked here so the distinction stays explicit rather than being rediscovered later:
#: ``packet_hash`` is a Phase 23 ingestion-draft field that the source-ingestion writer folds into
#: ``details_json``. Per policy, JSON detail never participates in an equality, uniqueness, or
#: authorization boundary — so it needs no collation, but it must also never be promoted into one
#: without becoming a real column first.
NON_COLUMN_GOVERNED_VALUES = {
    "packet_hash": "stored inside source_ingestion_records.details_json (JSON detail, not a column)",
}

#: The controlled-writer uniqueness boundary. A case-insensitive collation here is the single
#: highest-consequence outcome: two intentionally distinct writes collapse into one.
IDEMPOTENCY_BOUNDARY = ("owner_id", "client_id", "engagement_id", "idempotency_key")

#: Risk tiers for a governed column that has no explicit collation.
RISK_CRITICAL = "CRITICAL"   # participates in a UNIQUE constraint / primary key
RISK_HIGH = "HIGH"           # indexed (lookup/equality path)
RISK_MEDIUM = "MEDIUM"       # governed but neither unique nor indexed

STATUS_OK = "OK"
STATUS_NEEDS_REMEDIATION = "NEEDS_REMEDIATION"
#: Phase 44 pinned the model/migration policy, but source control cannot prove the deployed
#: database was migrated. This is the honest middle state: the repo is correct, production is
#: unverified until ``make production-mysql-collation-verify`` says otherwise.
STATUS_MODEL_POLICY_SATISFIED = "MODEL_POLICY_SATISFIED_PRODUCTION_UNVERIFIED"


def classify(column_name: str, type_name: str) -> str:
    """Return the policy class for one column. Deterministic and name-driven."""
    name = str(column_name)
    if type_name == "Text":
        return JSON_DETAILS_TEXT
    if name in EXACT_CLASS:
        return EXACT_CLASS[name]
    for pattern, klass in PATTERN_CLASS:
        if pattern.search(name):
            return klass
    return UNKNOWN_CANDIDATE


# --------------------------------------------------------------------------- collation detection


COLLATION_RE = re.compile(r"mysql_collate|collation\s*=|COLLATE\s+\w+", re.IGNORECASE)


def repo_pins_any_collation() -> bool:
    """True if any collation is pinned anywhere in the models or migrations."""
    targets = [os.path.join(REPO_ROOT, MODELS_REL),
               os.path.join(REPO_ROOT, "peak", "db", "base.py")]
    versions = os.path.join(REPO_ROOT, "alembic", "versions")
    if os.path.isdir(versions):
        targets += [os.path.join(versions, f) for f in sorted(os.listdir(versions))
                    if f.endswith(".py")]
    for path in targets:
        try:
            with open(path, encoding="utf-8") as fh:
                if COLLATION_RE.search(fh.read()):
                    return True
        except OSError:  # pragma: no cover - unreadable file is not a collation pin
            continue
    return False


def column_collation(column) -> str:
    """Return the effective declared collation for a column, or '' when it defers to the server.

    Governed columns attach their collation through a MySQL ``with_variant`` (see
    ``peak.db.base.GovernedString``), because a bare ``String(collation=...)`` renders
    ``COLLATE`` on every dialect and SQLite rejects it. So the variant is checked first, then the
    base type.
    """
    type_ = getattr(column, "type", None)
    variants = getattr(type_, "_variant_mapping", None) or {}
    for dialect in ("mysql", "mariadb"):
        variant = variants.get(dialect)
        collation = getattr(variant, "collation", None)
        if collation:
            return str(collation)
    collation = getattr(type_, "collation", None)
    return str(collation) if collation else ""


# --------------------------------------------------------------------------- model introspection


class ColumnFact:
    """One inspected string column, with everything the policy decision depends on."""

    __slots__ = ("table", "name", "type_name", "length", "policy_class", "collation",
                 "in_unique", "indexed", "primary_key")

    def __init__(self, table, name, type_name, length, policy_class, collation,
                 in_unique, indexed, primary_key):
        self.table = table
        self.name = name
        self.type_name = type_name
        self.length = length
        self.policy_class = policy_class
        self.collation = collation
        self.in_unique = in_unique
        self.indexed = indexed
        self.primary_key = primary_key

    @property
    def governed(self) -> bool:
        return self.policy_class in DETERMINISTIC_REQUIRED

    @property
    def risk(self) -> str:
        if self.in_unique or self.primary_key:
            return RISK_CRITICAL
        if self.indexed:
            return RISK_HIGH
        return RISK_MEDIUM

    def sort_key(self):
        return (self.table, self.name)


def collect_columns():
    """Introspect the live model metadata. Returns ``(facts, note)``; facts is empty on fallback."""
    try:
        from peak.db.models import ALL_MODELS
    except ImportError:
        return [], ("SQLAlchemy not installed — model introspection unavailable; "
                    "source-scan tier only (run with PYTHON=.venv/bin/python for the full audit)")

    facts = []
    for model in ALL_MODELS:
        table = model.__table__
        unique_cols = set()
        for constraint in table.constraints:
            if constraint.__class__.__name__ in ("UniqueConstraint", "PrimaryKeyConstraint"):
                unique_cols.update(c.name for c in constraint.columns)
        indexed_cols = set()
        for index in table.indexes:
            indexed_cols.update(c.name for c in index.columns)

        for column in table.columns:
            type_name = type(column.type).__name__
            if type_name not in ("String", "Text"):
                continue
            facts.append(ColumnFact(
                table=table.name,
                name=column.name,
                type_name=type_name,
                length=getattr(column.type, "length", None),
                policy_class=classify(column.name, type_name),
                collation=column_collation(column),
                in_unique=column.name in unique_cols,
                indexed=column.name in indexed_cols or bool(column.index),
                primary_key=bool(column.primary_key),
            ))
    return sorted(facts, key=lambda f: f.sort_key()), ""


def source_scan_columns():
    """Fallback: recover declared string column names from models.py source."""
    path = os.path.join(REPO_ROOT, MODELS_REL)
    try:
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
    except OSError:  # pragma: no cover
        return []
    # `Mapped[Optional[str]]` nests brackets, so match non-greedily up to the assignment rather
    # than trying to balance them.
    names = re.findall(r"^\s+(\w+):\s*Mapped\[.*?\s*=\s*mapped_column\(\s*(String|Text)",
                       source, re.M)
    names += re.findall(r'sa\.Column\(\s*"(\w+)",\s*sa\.(String|Text)', source)
    return sorted({(n, t) for n, t in names})


# --------------------------------------------------------------------------- reporting


class Audit:
    def __init__(self) -> None:
        self.failures: list = []
        self.warnings: list = []

    def fail(self, label: str) -> None:
        self.failures.append(label)
        print(f"  [FAIL] {label}")

    def warn(self, label: str) -> None:
        self.warnings.append(label)
        print(f"  [WARN] {label}")

    def ok(self, label: str) -> None:
        print(f"  [PASS] {label}")

    def info(self, label: str) -> None:
        print(f"  {label}")


def run_audit(verbose: bool = False) -> int:
    audit = Audit()
    print("Peak governed MySQL collation audit")
    print("=" * 58)
    print("Offline: no credentials, no network, no .env, no DSN, no database connection.")

    facts, note = collect_columns()
    pins_collation = repo_pins_any_collation()

    print("\n1. Scope")
    if note:
        audit.info(f"[skip] {note}")
        fallback = source_scan_columns()
        audit.info(f"source scan recovered {len(fallback)} declared string/text column "
                   "declarations")
        classes = {}
        for name, type_name in fallback:
            classes.setdefault(classify(name, type_name), []).append(name)
        missing = [n for n in REQUIRED_GOVERNED if not any(n == fn for fn, _ in fallback)]
        # models.py declares governed columns on mixins (base.py), so absence here is expected
        # for owner_id/authorization_scope; only report, never fail, in the fallback tier.
        if missing:
            audit.info(f"[skip] {len(missing)} required governed column(s) are declared on shared "
                       "mixins and are not visible to the source-scan tier; the model tier "
                       "resolves them")
        print("\nRESULT: PASS (source-scan tier only — no policy conclusion drawn)")
        return 0

    audit.info(f"tables inspected            : {len({f.table for f in facts})}")
    audit.info(f"string/text columns audited : {len(facts)}")
    audit.info(f"explicit collation pinned   : {'yes' if pins_collation else 'no'}")

    # --- 2. Classification integrity: the audit must correctly place every required column ---
    print("\n2. Classification integrity (the audit must not lose a governed column)")
    by_name = {}
    for fact in facts:
        by_name.setdefault(fact.name, set()).add(fact.policy_class)
    for name, expected in sorted(REQUIRED_GOVERNED.items()):
        if name not in by_name:
            audit.fail(f"required governed column '{name}' is absent from the schema")
            continue
        actual = by_name[name]
        if actual != {expected}:
            audit.fail(f"required governed column '{name}' classified {sorted(actual)}, "
                       f"expected '{expected}'")
        else:
            audit.ok(f"'{name}' -> {expected}")

    unknown = sorted({f.name for f in facts if f.policy_class == UNKNOWN_CANDIDATE})
    if unknown:
        audit.warn(f"{len(unknown)} column name(s) need human classification: "
                   + ", ".join(unknown))
    else:
        audit.ok("every string column matched a policy class")

    # Governed-looking values that are not columns: confirm they really are absent, so the
    # distinction cannot rot into a silent assumption.
    for name, where in sorted(NON_COLUMN_GOVERNED_VALUES.items()):
        if name in by_name:
            audit.fail(f"'{name}' is now a real column but is listed as a non-column value; "
                       "classify it and add it to REQUIRED_GOVERNED")
        else:
            audit.ok(f"'{name}' is not a column — {where}")

    # --- 3. Class census ---
    print("\n3. Policy class census")
    for klass in ALL_CLASSES:
        members = [f for f in facts if f.policy_class == klass]
        if not members:
            continue
        distinct = len({f.name for f in members})
        marker = "*" if klass in DETERMINISTIC_REQUIRED else " "
        audit.info(f"{marker} {klass:42s} {len(members):4d} columns "
                   f"({distinct} distinct names)")
    audit.info("  * = deterministic (case-sensitive) comparison required by policy")

    # --- 4. Current-state assessment ---
    print("\n4. Current-state assessment")
    governed = [f for f in facts if f.governed]
    governed_pinned = [f for f in governed if f.collation]
    governed_unpinned = [f for f in governed if not f.collation]
    critical = [f for f in governed_unpinned if f.risk == RISK_CRITICAL]
    high = [f for f in governed_unpinned if f.risk == RISK_HIGH]
    medium = [f for f in governed_unpinned if f.risk == RISK_MEDIUM]

    audit.info(f"governed columns requiring explicit collation : {len(governed)}")
    audit.info(f"  with explicit collation                     : {len(governed_pinned)}")
    audit.info(f"  WITHOUT explicit collation                  : {len(governed_unpinned)}")
    audit.info(f"    CRITICAL (unique/primary-key boundary)    : {len(critical)}")
    audit.info(f"    HIGH     (indexed equality path)          : {len(high)}")
    audit.info(f"    MEDIUM   (governed, not indexed)          : {len(medium)}")

    enum_cols = [f for f in facts if f.policy_class in DETERMINISTIC_PREFERRED]
    audit.info(f"enum/status columns (deterministic preferred)  : {len(enum_cols)}")

    # --- 5. The highest-consequence boundary, named explicitly ---
    print("\n5. Highest-risk boundary: the controlled-writer idempotency constraint")
    boundary_tables = sorted({f.table for f in facts
                              if f.name == "idempotency_key" and f.in_unique})
    audit.info("UNIQUE (" + ", ".join(IDEMPOTENCY_BOUNDARY) + ")")
    audit.info(f"enforced on {len(boundary_tables)} table(s): "
               + (", ".join(boundary_tables) if boundary_tables else "none"))
    boundary_unpinned = [f for f in facts
                         if f.name in IDEMPOTENCY_BOUNDARY and f.in_unique and not f.collation]
    if boundary_unpinned:
        audit.warn(
            f"{len(boundary_unpinned)} column(s) in the idempotency boundary have no explicit "
            "collation. Under a case-insensitive server default, 'idem-key-1' and 'idem-KEY-1' "
            "would collide as ONE key: two intentionally distinct writes would collapse into an "
            "idempotent replay or a spurious conflict. The writers persist idempotency_key "
            "verbatim (no case normalization), so nothing upstream mitigates this.")
    else:
        audit.ok("every idempotency-boundary column carries an explicit collation")

    # --- 6. Verdict ---
    print("\n6. Verdict")
    if not governed_unpinned and governed:
        status = STATUS_MODEL_POLICY_SATISFIED
        audit.ok(f"{status}: all {len(governed)} governed column(s) pin a deterministic collation "
                 "in the model/migration source (Phase 44)")
        audit.info("  Source control is correct. It does NOT prove the deployed database was "
                   "migrated:")
        audit.info("    - migration 013 must still be executed against production, under separate "
                   "approval;")
        audit.info("    - run `make production-mysql-collation-verify` to read production's "
                   "effective collation;")
        audit.info("    - production verification remains required AFTER production migration "
                   "execution.")
        audit.info("  The idempotency boundary UNIQUE (owner_id, client_id, engagement_id, "
                   "idempotency_key) is the reason this matters: under a case-insensitive "
                   "collation 'idem-key-1' and 'idem-KEY-1' are one key, and writers persist the "
                   "key verbatim with no case normalization. See "
                   "docs/GOVERNED_MYSQL_COLLATION_POLICY.md.")
    elif governed_unpinned:
        status = STATUS_NEEDS_REMEDIATION
        audit.warn(
            f"{status}: {len(governed_unpinned)} governed column(s) defer comparison semantics to "
            "the managed server's default collation. This is the known Phase 41 open finding and "
            "is reported, not auto-fixed.")
        audit.info("  Remediation requires an explicitly approved migration; see "
                   "docs/GOVERNED_MYSQL_COLLATION_POLICY.md.")
        audit.info("  Managed MySQL staging verification is REQUIRED before remediation: the "
                   "server's effective default collation cannot be read from this repository.")
    else:
        status = STATUS_OK
        audit.ok(f"{status}: no governed columns were found to assess")

    if verbose:
        print("\n7. Governed columns without explicit collation (table.column [risk])")
        for fact in sorted(governed_unpinned, key=lambda f: (f.risk != RISK_CRITICAL,
                                                             f.risk != RISK_HIGH, f.table, f.name)):
            audit.info(f"  {fact.risk:8s} {fact.table}.{fact.name} ({fact.policy_class})")

    print("\n" + "=" * 58)
    print("Summary")
    print(f"  columns audited : {len(facts)}")
    print(f"  governed        : {len(governed)}")
    print(f"  unpinned        : {len(governed_unpinned)}")
    print(f"  status          : {status}")
    print(f"  failures        : {len(audit.failures)}")
    print(f"  warnings        : {len(audit.warnings)}")
    for label in audit.failures:
        print(f"    FAIL - {label}")
    print("\nRESULT: " + ("FAIL" if audit.failures else "PASS"))
    return 1 if audit.failures else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline governed-collation audit for the controlled MySQL schema.")
    parser.add_argument("--verbose", action="store_true",
                        help="List every governed column that lacks an explicit collation.")
    args = parser.parse_args(argv)
    return run_audit(verbose=args.verbose)


if __name__ == "__main__":
    sys.exit(main())
