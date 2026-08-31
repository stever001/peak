#!/usr/bin/env python3
"""Lab-only writer enablement decision gate (Phase 89) — OFFLINE, decision record only.

**What this is for.** Phase 88 proved the seeded lab scenario can be measured read-only. A future
phase will want to turn those measurements into Peak records *in the lab*, through the existing
create-only writers. The Phase 51 gate cannot express that: it is environment-blind and hardcodes
every authorization to ``False``, which is exactly right for production and useless for a lab
rehearsal. This module adds the missing axis — a **lab** decision, evaluated separately, that can
return true only under an explicit, narrow, and checkable set of conditions.

**Production is not on this path at all.** Every production field this module emits is ``False``,
unconditionally and structurally: there is no branch, no variable, and no argument that can make
one true. Setting every lab variable at once still leaves production denied. ``make
writer-enablement-decision-gate`` is untouched and remains the production decision of record —
this module does not import it, wrap it, or modify it.

**A positive lab decision is still not permission to write.** It says the *target* is the lab, the
*shape* is right, and the *requested writer targets* are inside the enableable set. It does not say
a write is approved. Phase 89 invokes no writer and creates no record. A future phase must
separately name the writer, the record count, the authorization scope, the idempotency keys, the
expected receipts, and the post-write verification before anything is written.

**The environment contract** (no variable is reused from another purpose):

==========================================  ================================================
``PEAK_WRITER_TARGET``                      ``lab`` — anything else denies the lab path
``PEAK_LAB_WRITER_ENABLEMENT_CONFIRM=1``    required; the exact string ``1`` and nothing else
``PEAK_LAB_WRITER_TARGET_URL``              the lab writer DSN; parsed for *shape* only
``PEAK_LAB_WRITER_TARGETS``                 comma-separated ``table/action`` requests
``PEAK_LAB_ENGAGEMENT_ANCHOR_BOOTSTRAP_CONFIRM=1``  extra; required *only* for the anchor bootstrap
==========================================  ================================================

**The anchor bootstrap (Phase 90).** Phase 89 refused the engagement authorization anchor writer
outright, which was safe but left a lab rehearsal with nothing to hang records from. It is now
reachable through a **separate branch**, never by widening the ordinary path: the anchor pair is
still absent from ``LAB_ENABLEABLE_WRITER_TARGETS``, must be requested **alone**, and needs a
second confirmation that names this writer specifically. Bootstrapping an identity/root record and
writing data records stay different authorities, so one confirmation cannot carry both.

``PEAK_LAB_CONFIRM`` is deliberately not used — Phase 82 published it as a reserved no-op, and a
gate must not share a name with something documented as doing nothing. The Phase 84 migration
variables are not reused either: migrating the lab and writing rows to the lab are different
authorities and must not be satisfiable by one confirmation. The scenario read-only variables are
not accepted as writer authorizers.

**Value-free by construction.** Nothing here reads a credential file or ``.env``, opens a
connection, imports SQLAlchemy or any writer, or logs a URL. The DSN is parsed into a username and
a schema name, both classified into fixed labels; host, port, password and query parameters are
parsed past and discarded. Output carries target labels, booleans, reason codes, schema/user
classes, and writer-target names — never a connection value.

Exit status:
  0  -> a decision was produced and is internally consistent (lab authorized or denied)
  1  -> internal inconsistency in the decision record (should not happen)
  2  -> a self-test case failed
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from typing import Mapping, Sequence
from urllib.parse import urlsplit

LAB_WRITER_GATE_VERSION = "1"

# --- environment contract -----------------------------------------------------------------

TARGET_ENV = "PEAK_WRITER_TARGET"
LAB_CONFIRM_ENV = "PEAK_LAB_WRITER_ENABLEMENT_CONFIRM"
LAB_URL_ENV = "PEAK_LAB_WRITER_TARGET_URL"
LAB_TARGETS_ENV = "PEAK_LAB_WRITER_TARGETS"
ANCHOR_BOOTSTRAP_CONFIRM_ENV = "PEAK_LAB_ENGAGEMENT_ANCHOR_BOOTSTRAP_CONFIRM"

TARGET_LAB = "lab"
TARGET_PRODUCTION = "production"

#: The only accepted confirmation value. "true", "yes", "1 " and "" all read as unconfirmed, so a
#: half-set or accidentally-inherited variable fails closed rather than open.
CONFIRM_VALUE = "1"

#: Variables that must never be accepted as lab *writer* authorizers. Each already means something
#: else, and letting any of them stand in here would make one confirmation grant two authorities.
REJECTED_AUTHORIZER_ENVS = (
    "PEAK_LAB_CONFIRM",                 # Phase 82: published as a reserved no-op
    "PEAK_ALEMBIC_TARGET",              # Phase 84: migration targeting, not row writing
    "PEAK_LAB_MIGRATION_CONFIRM",       # Phase 84: migration confirmation, not row writing
    "PEAK_PRODUCTION_MIGRATION_CONFIRM",
    "PEAK_LAB_SCENARIO_RO_URL",         # Phase 85: scenario read-only
    "PEAK_LAB_SCENARIO_LOADER_URL",     # Phase 85: scenario loader, not a Peak writer
    "PEAK_PRODUCTION_DB_URL",
    "PEAK_RUNTIME_DATABASE_URL",
    "PEAK_DATABASE_URL",
)

# --- the fixed lab identity ---------------------------------------------------------------

LAB_SCHEMA = "peak_lab"
SCENARIO_SCHEMA = "peak_lab_scenario"

#: The lab runtime role holds ``SELECT`` + ``INSERT`` and no ``DELETE`` — the right shape for
#: create-only writers, and the only role this gate accepts as a lab writer.
APPROVED_LAB_WRITER_USERS = frozenset({"peak_lab_runtime"})

GUARDED_DIALECTS = frozenset({"mysql", "mariadb"})

# --- what may be enabled, and what may not -------------------------------------------------

#: The narrow set a lab rehearsal may request. Deliberately a *subset* of the controlled
#: allowlist: appearing on ``peak.persistence.allowlist`` means a writer may plan the action,
#: which is a weaker statement than "a lab rehearsal may request it here".
#:
#: The engagement authorization anchor pair is **excluded on purpose**. It creates identity/root
#: records through the separate single-pair anchor path, and enabling it belongs to its own
#: approval rather than riding in with the data-record writers.
LAB_ENABLEABLE_WRITER_TARGETS = frozenset({
    ("source_ingestion_records", "create_source_ingestion_record"),
    ("evidence_references", "create_draft"),
    ("review_records", "create_review_record"),
})

#: The engagement authorization anchor. Phase 89 refused it outright. Phase 90 admits it through a
#: **separate bootstrap branch only** — it is deliberately still absent from
#: ``LAB_ENABLEABLE_WRITER_TARGETS`` above, so it can never be granted by the ordinary lab path,
#: and reaching it needs a second confirmation naming this writer specifically. A lab rehearsal
#: needs an anchor to hang records from; that is a bootstrap, not general writer authority.
ANCHOR_BOOTSTRAP_PAIR = ("engagements", "create_engagement_authorization_anchor")

#: Never enableable here on any path, bootstrap included — stated explicitly so the exclusion is
#: testable rather than merely implied by absence from the sets above.
NEVER_LAB_ENABLEABLE = frozenset({
    ("clients", "create_draft"),
})

# --- outcomes and reason codes -------------------------------------------------------------

OUTCOME_LAB_AUTHORIZED = "lab_write_authorized"
OUTCOME_ANCHOR_BOOTSTRAP = "lab_anchor_bootstrap_authorized"
OUTCOME_DENIED = "denied"

REASON_OK = "lab_target_confirmed_and_scoped"
REASON_TARGET_NOT_LAB = "writer_target_not_lab"
REASON_TARGET_IS_PRODUCTION = "writer_target_is_production_never_authorized_here"
REASON_NO_CONFIRM = "lab_confirmation_absent_or_not_exact_value"
REASON_URL_ABSENT = "lab_target_url_absent"
REASON_DIALECT = "lab_target_dialect_not_guarded"
REASON_SCHEMA_SCENARIO = "lab_target_schema_is_scenario_not_controlled"
REASON_SCHEMA_DEFAULT = "lab_target_schema_is_provider_default"
REASON_SCHEMA_PRODUCTION = "lab_target_schema_production_marked"
REASON_SCHEMA_NOT_LAB = "lab_target_schema_not_peak_lab"
REASON_USER_PRODUCTION = "lab_target_user_production_marked"
REASON_USER_NOT_APPROVED = "lab_target_user_not_an_approved_lab_writer_role"
REASON_NO_TARGETS = "no_writer_target_requested"
REASON_TARGET_NOT_ENABLEABLE = "writer_target_not_lab_enableable"
REASON_TARGET_NEVER_ENABLEABLE = "writer_target_never_lab_enableable"
REASON_ANCHOR_OK = "lab_anchor_bootstrap_confirmed_and_scoped"
REASON_ANCHOR_NO_BOOTSTRAP_CONFIRM = "anchor_bootstrap_confirmation_absent_or_not_exact_value"
REASON_ANCHOR_NOT_SOLE_TARGET = "anchor_bootstrap_must_be_the_only_requested_target"

FIELDS = (
    "lab_writer_gate_version",
    "writer_target",
    "outcome",
    "reason",
    "lab_write_authorized",
    "authorized_writer_targets",
    "requested_writer_targets",
    "anchor_bootstrap_authorized",
    "target_user_class",
    "target_schema_class",
    # Production axis — structurally false on every path this module can take.
    "production_write_authorized",
    "safe_to_write_production_now",
    "production_writer_enablement_authorized",
    # Structural invariants: no code path here can make any of these true.
    "database_contacted",
    "sql_issued",
    "writer_invoked",
    "records_created",
    "credential_file_read",
    "secrets_printed",
    # Carried forward so a positive lab decision cannot be mistaken for a write approval.
    "lab_write_requires_separate_phase_approval",
    "future_phase_must_name_writer_records_scope_idempotency_and_verification",
)


def _load_migration_target_guard():
    """Load the Phase 84 target guard by path, for its classification primitives.

    Reused rather than reimplemented on purpose: "what counts as production-marked, or as the
    provider's default schema" must have exactly one definition in this repository. Two copies
    would drift, and the copy that drifted would be the one guarding a write.
    """
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(here, "alembic", "migration_target_guard.py")
    spec = importlib.util.spec_from_file_location("_peak_migration_target_guard", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_writer_targets(raw: str) -> tuple:
    """Parse ``table/action,table/action`` into a sorted tuple of pairs. Malformed items drop."""
    pairs = []
    for item in (raw or "").split(","):
        item = item.strip()
        if not item or "/" not in item:
            continue
        table, action = item.split("/", 1)
        table, action = table.strip(), action.strip()
        if table and action:
            pairs.append((table, action))
    return tuple(sorted(set(pairs)))


def _deny(reason: str, target: str, requested: Sequence, user_class: str = "not_evaluated",
          schema_class: str = "not_evaluated") -> dict:
    return _record(OUTCOME_DENIED, reason, False, (), target, requested, user_class, schema_class)


def _record(outcome: str, reason: str, authorized: bool, authorized_targets: Sequence,
            target: str, requested: Sequence, user_class: str, schema_class: str,
            anchor_bootstrap: bool = False) -> dict:
    return {
        "lab_writer_gate_version": LAB_WRITER_GATE_VERSION,
        "writer_target": target or "unset",
        "outcome": outcome,
        "reason": reason,
        "lab_write_authorized": bool(authorized),
        "authorized_writer_targets": [f"{t}/{a}" for t, a in sorted(authorized_targets)],
        "requested_writer_targets": [f"{t}/{a}" for t, a in sorted(requested)],
        "anchor_bootstrap_authorized": bool(anchor_bootstrap),
        "target_user_class": user_class,
        "target_schema_class": schema_class,
        # Hardcoded. No argument, variable, or branch reaches these as True.
        "production_write_authorized": False,
        "safe_to_write_production_now": False,
        "production_writer_enablement_authorized": False,
        "database_contacted": False,
        "sql_issued": False,
        "writer_invoked": False,
        "records_created": False,
        "credential_file_read": False,
        "secrets_printed": False,
        "lab_write_requires_separate_phase_approval": True,
        "future_phase_must_name_writer_records_scope_idempotency_and_verification": True,
    }


def evaluate(env: Mapping[str, str]) -> dict:
    """Return the lab writer enablement decision for ``env``. Pure: reads only the mapping given.

    ``env`` is an ordinary mapping, so tests pass synthetic dictionaries and never touch the real
    process environment. Nothing here opens a file, resolves a host, or contacts a database.
    """
    guard = _load_migration_target_guard()

    target = (env.get(TARGET_ENV) or "").strip().lower()
    requested = parse_writer_targets(env.get(LAB_TARGETS_ENV) or "")

    # Production never travels this path, whatever else is set.
    if target == TARGET_PRODUCTION:
        return _deny(REASON_TARGET_IS_PRODUCTION, target, requested)
    if target != TARGET_LAB:
        return _deny(REASON_TARGET_NOT_LAB, target, requested)

    if (env.get(LAB_CONFIRM_ENV) or "") != CONFIRM_VALUE:
        return _deny(REASON_NO_CONFIRM, target, requested)

    url = (env.get(LAB_URL_ENV) or "").strip()
    if not url:
        return _deny(REASON_URL_ABSENT, target, requested)

    if guard.dialect_of(url) not in GUARDED_DIALECTS:
        return _deny(REASON_DIALECT, target, requested)

    identity = guard.parse_identity(url)
    username, database = identity["username"], identity["database"]
    user_class = guard.classify_user(username)
    schema_class = guard.classify_schema(database)

    low_db = database.lower()
    if low_db == SCENARIO_SCHEMA:
        return _deny(REASON_SCHEMA_SCENARIO, target, requested, user_class, schema_class)
    if schema_class == guard.SCHEMA_CLASS_PROVIDER_DEFAULT:
        return _deny(REASON_SCHEMA_DEFAULT, target, requested, user_class, schema_class)
    if schema_class == guard.SCHEMA_CLASS_PRODUCTION_MARKED:
        return _deny(REASON_SCHEMA_PRODUCTION, target, requested, user_class, schema_class)
    if low_db != LAB_SCHEMA:
        return _deny(REASON_SCHEMA_NOT_LAB, target, requested, user_class, schema_class)

    if user_class == guard.USER_CLASS_PRODUCTION_MARKED:
        return _deny(REASON_USER_PRODUCTION, target, requested, user_class, schema_class)
    if username.lower() not in APPROVED_LAB_WRITER_USERS:
        return _deny(REASON_USER_NOT_APPROVED, target, requested, user_class, schema_class)

    if not requested:
        return _deny(REASON_NO_TARGETS, target, requested, user_class, schema_class)
    # Never-enableable pairs are refused first, so no later branch — bootstrap included — can
    # reach them.
    if any(pair in NEVER_LAB_ENABLEABLE for pair in requested):
        return _deny(REASON_TARGET_NEVER_ENABLEABLE, target, requested, user_class, schema_class)

    # The anchor bootstrap branch. It is deliberately separate from the ordinary lab path and
    # cannot be reached by widening it: the anchor pair is not in LAB_ENABLEABLE_WRITER_TARGETS,
    # so the only way here is to ask for the anchor *alone* and confirm it *specifically*.
    if ANCHOR_BOOTSTRAP_PAIR in requested:
        if set(requested) != {ANCHOR_BOOTSTRAP_PAIR}:
            # Bootstrapping an identity/root record and writing data records are different
            # authorities; bundling them would let one confirmation carry both.
            return _deny(REASON_ANCHOR_NOT_SOLE_TARGET, target, requested,
                         user_class, schema_class)
        if (env.get(ANCHOR_BOOTSTRAP_CONFIRM_ENV) or "") != CONFIRM_VALUE:
            return _deny(REASON_ANCHOR_NO_BOOTSTRAP_CONFIRM, target, requested,
                         user_class, schema_class)
        return _record(OUTCOME_ANCHOR_BOOTSTRAP, REASON_ANCHOR_OK, True, requested,
                       target, requested, user_class, schema_class, anchor_bootstrap=True)

    if not set(requested) <= LAB_ENABLEABLE_WRITER_TARGETS:
        return _deny(REASON_TARGET_NOT_ENABLEABLE, target, requested, user_class, schema_class)

    return _record(OUTCOME_LAB_AUTHORIZED, REASON_OK, True, requested,
                   target, requested, user_class, schema_class)


def is_consistent(decision: Mapping[str, object]) -> bool:
    """A decision must never authorize production, and must never claim to have acted."""
    always_false = (
        "production_write_authorized", "safe_to_write_production_now",
        "production_writer_enablement_authorized", "database_contacted", "sql_issued",
        "writer_invoked", "records_created", "credential_file_read", "secrets_printed",
    )
    always_true = (
        "lab_write_requires_separate_phase_approval",
        "future_phase_must_name_writer_records_scope_idempotency_and_verification",
    )
    if not all(decision[f] is False for f in always_false):
        return False
    if not all(decision[f] is True for f in always_true):
        return False
    if set(decision) != set(FIELDS):
        return False
    # An authorized decision must carry a non-empty, in-set authorization; a denial must carry none.
    authorized = decision["lab_write_authorized"]
    granted = decision["authorized_writer_targets"]
    if authorized and not granted:
        return False
    if not authorized and granted:
        return False
    bootstrap = decision["anchor_bootstrap_authorized"]
    # The anchor pair may appear in a grant only on the bootstrap outcome, and then only alone.
    if bootstrap:
        if decision["outcome"] != OUTCOME_ANCHOR_BOOTSTRAP:
            return False
        if granted != [f"{ANCHOR_BOOTSTRAP_PAIR[0]}/{ANCHOR_BOOTSTRAP_PAIR[1]}"]:
            return False
        return True
    for item in granted:
        table, _, action = item.partition("/")
        if (table, action) in NEVER_LAB_ENABLEABLE:
            return False
        if (table, action) not in LAB_ENABLEABLE_WRITER_TARGETS:
            return False
    return True


def _emit(decision: Mapping[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(decision, indent=2, sort_keys=False))
        return
    for field in FIELDS:
        value = decision[field]
        if value is True:
            rendered = "true"
        elif value is False:
            rendered = "false"
        elif isinstance(value, list):
            rendered = ",".join(value) if value else "none"
        else:
            rendered = value
        print(f"{field}={rendered}")


# --------------------------------------------------------------------------- self-test

#: Synthetic URLs only. No host resolves, no password is real, and nothing here is ever connected
#: to — these strings exist to exercise the parser's branches.
_LAB_OK = "mysql+pymysql://peak_lab_runtime:x@synthetic.invalid:3306/peak_lab"
_CASES = (
    ("no environment at all denies", {}, False, REASON_TARGET_NOT_LAB),
    ("production target denies", {TARGET_ENV: "production"}, False, REASON_TARGET_IS_PRODUCTION),
    ("production target denies even with every lab variable set",
     {TARGET_ENV: "production", LAB_CONFIRM_ENV: "1", LAB_URL_ENV: _LAB_OK,
      LAB_TARGETS_ENV: "review_records/create_review_record"}, False, REASON_TARGET_IS_PRODUCTION),
    ("lab target without confirmation denies",
     {TARGET_ENV: "lab", LAB_URL_ENV: _LAB_OK}, False, REASON_NO_CONFIRM),
    ("lab confirmation accepts only the exact value 1",
     {TARGET_ENV: "lab", LAB_CONFIRM_ENV: "true", LAB_URL_ENV: _LAB_OK}, False, REASON_NO_CONFIRM),
    ("lab target without a URL denies",
     {TARGET_ENV: "lab", LAB_CONFIRM_ENV: "1"}, False, REASON_URL_ABSENT),
    ("scenario schema denies",
     {TARGET_ENV: "lab", LAB_CONFIRM_ENV: "1",
      LAB_URL_ENV: "mysql+pymysql://peak_lab_runtime:x@h.invalid:3306/peak_lab_scenario",
      LAB_TARGETS_ENV: "review_records/create_review_record"}, False, REASON_SCHEMA_SCENARIO),
    ("provider default schema denies",
     {TARGET_ENV: "lab", LAB_CONFIRM_ENV: "1",
      LAB_URL_ENV: "mysql+pymysql://peak_lab_runtime:x@h.invalid:3306/defaultdb",
      LAB_TARGETS_ENV: "review_records/create_review_record"}, False, REASON_SCHEMA_DEFAULT),
    ("production-marked schema denies",
     {TARGET_ENV: "lab", LAB_CONFIRM_ENV: "1",
      LAB_URL_ENV: "mysql+pymysql://peak_lab_runtime:x@h.invalid:3306/peak_production",
      LAB_TARGETS_ENV: "review_records/create_review_record"}, False, REASON_SCHEMA_PRODUCTION),
    ("some other schema denies",
     {TARGET_ENV: "lab", LAB_CONFIRM_ENV: "1",
      LAB_URL_ENV: "mysql+pymysql://peak_lab_runtime:x@h.invalid:3306/something_else",
      LAB_TARGETS_ENV: "review_records/create_review_record"}, False, REASON_SCHEMA_NOT_LAB),
    ("production-marked user denies",
     {TARGET_ENV: "lab", LAB_CONFIRM_ENV: "1",
      LAB_URL_ENV: "mysql+pymysql://peak_production_runtime:x@h.invalid:3306/peak_lab",
      LAB_TARGETS_ENV: "review_records/create_review_record"}, False, REASON_USER_PRODUCTION),
    ("the lab migration role is not a writer role",
     {TARGET_ENV: "lab", LAB_CONFIRM_ENV: "1",
      LAB_URL_ENV: "mysql+pymysql://peak_lab_migrate:x@h.invalid:3306/peak_lab",
      LAB_TARGETS_ENV: "review_records/create_review_record"}, False, REASON_USER_NOT_APPROVED),
    ("the scenario read-only role is not a writer role",
     {TARGET_ENV: "lab", LAB_CONFIRM_ENV: "1",
      LAB_URL_ENV: "mysql+pymysql://peak_lab_scenario_ro:x@h.invalid:3306/peak_lab",
      LAB_TARGETS_ENV: "review_records/create_review_record"}, False, REASON_USER_NOT_APPROVED),
    ("SQLite is not a guarded dialect here",
     {TARGET_ENV: "lab", LAB_CONFIRM_ENV: "1", LAB_URL_ENV: "sqlite:///tmp.db",
      LAB_TARGETS_ENV: "review_records/create_review_record"}, False, REASON_DIALECT),
    ("no requested writer target denies",
     {TARGET_ENV: "lab", LAB_CONFIRM_ENV: "1", LAB_URL_ENV: _LAB_OK}, False, REASON_NO_TARGETS),
    ("a writer target outside the enableable set denies",
     {TARGET_ENV: "lab", LAB_CONFIRM_ENV: "1", LAB_URL_ENV: _LAB_OK,
      LAB_TARGETS_ENV: "intake_note_records/create_intake_note_record"},
     False, REASON_TARGET_NOT_ENABLEABLE),
    ("the anchor pair alone, without the bootstrap confirmation, denies",
     {TARGET_ENV: "lab", LAB_CONFIRM_ENV: "1", LAB_URL_ENV: _LAB_OK,
      LAB_TARGETS_ENV: "engagements/create_engagement_authorization_anchor"},
     False, REASON_ANCHOR_NO_BOOTSTRAP_CONFIRM),
    ("the anchor bootstrap confirmation accepts only the exact value 1",
     {TARGET_ENV: "lab", LAB_CONFIRM_ENV: "1", LAB_URL_ENV: _LAB_OK,
      ANCHOR_BOOTSTRAP_CONFIRM_ENV: "true",
      LAB_TARGETS_ENV: "engagements/create_engagement_authorization_anchor"},
     False, REASON_ANCHOR_NO_BOOTSTRAP_CONFIRM),
    ("the anchor bootstrap cannot be mixed with a data-record target",
     {TARGET_ENV: "lab", LAB_CONFIRM_ENV: "1", LAB_URL_ENV: _LAB_OK,
      ANCHOR_BOOTSTRAP_CONFIRM_ENV: "1",
      LAB_TARGETS_ENV: ("engagements/create_engagement_authorization_anchor,"
                        "review_records/create_review_record")},
     False, REASON_ANCHOR_NOT_SOLE_TARGET),
    ("the anchor bootstrap still requires the ordinary lab confirmation",
     {TARGET_ENV: "lab", LAB_URL_ENV: _LAB_OK, ANCHOR_BOOTSTRAP_CONFIRM_ENV: "1",
      LAB_TARGETS_ENV: "engagements/create_engagement_authorization_anchor"},
     False, REASON_NO_CONFIRM),
    ("the anchor bootstrap still requires the exact peak_lab schema",
     {TARGET_ENV: "lab", LAB_CONFIRM_ENV: "1", ANCHOR_BOOTSTRAP_CONFIRM_ENV: "1",
      LAB_URL_ENV: "mysql+pymysql://peak_lab_runtime:x@h.invalid:3306/peak_lab_scenario",
      LAB_TARGETS_ENV: "engagements/create_engagement_authorization_anchor"},
     False, REASON_SCHEMA_SCENARIO),
    ("the anchor bootstrap still refuses a production-marked schema",
     {TARGET_ENV: "lab", LAB_CONFIRM_ENV: "1", ANCHOR_BOOTSTRAP_CONFIRM_ENV: "1",
      LAB_URL_ENV: "mysql+pymysql://peak_lab_runtime:x@h.invalid:3306/peak_production",
      LAB_TARGETS_ENV: "engagements/create_engagement_authorization_anchor"},
     False, REASON_SCHEMA_PRODUCTION),
    ("the anchor bootstrap still refuses an unapproved role",
     {TARGET_ENV: "lab", LAB_CONFIRM_ENV: "1", ANCHOR_BOOTSTRAP_CONFIRM_ENV: "1",
      LAB_URL_ENV: "mysql+pymysql://peak_lab_migrate:x@h.invalid:3306/peak_lab",
      LAB_TARGETS_ENV: "engagements/create_engagement_authorization_anchor"},
     False, REASON_USER_NOT_APPROVED),
    ("a complete, correctly scoped anchor bootstrap is authorized",
     {TARGET_ENV: "lab", LAB_CONFIRM_ENV: "1", ANCHOR_BOOTSTRAP_CONFIRM_ENV: "1",
      LAB_URL_ENV: _LAB_OK,
      LAB_TARGETS_ENV: "engagements/create_engagement_authorization_anchor"},
     True, REASON_ANCHOR_OK),
    ("the bootstrap confirmation does not enable ordinary data-record targets on its own",
     {TARGET_ENV: "lab", ANCHOR_BOOTSTRAP_CONFIRM_ENV: "1", LAB_URL_ENV: _LAB_OK,
      LAB_TARGETS_ENV: "review_records/create_review_record"},
     False, REASON_NO_CONFIRM),
    ("clients remains never enableable even with the bootstrap confirmation",
     {TARGET_ENV: "lab", LAB_CONFIRM_ENV: "1", ANCHOR_BOOTSTRAP_CONFIRM_ENV: "1",
      LAB_URL_ENV: _LAB_OK, LAB_TARGETS_ENV: "clients/create_draft"},
     False, REASON_TARGET_NEVER_ENABLEABLE),
    ("one enableable target inside a mixed request still denies the whole request",
     {TARGET_ENV: "lab", LAB_CONFIRM_ENV: "1", LAB_URL_ENV: _LAB_OK,
      LAB_TARGETS_ENV: "review_records/create_review_record,clients/create_draft"},
     False, REASON_TARGET_NEVER_ENABLEABLE),
    ("a complete, correctly scoped lab request is authorized",
     {TARGET_ENV: "lab", LAB_CONFIRM_ENV: "1", LAB_URL_ENV: _LAB_OK,
      LAB_TARGETS_ENV: "review_records/create_review_record"}, True, REASON_OK),
    ("all three enableable targets at once are authorized",
     {TARGET_ENV: "lab", LAB_CONFIRM_ENV: "1", LAB_URL_ENV: _LAB_OK,
      LAB_TARGETS_ENV: ("review_records/create_review_record,evidence_references/create_draft,"
                        "source_ingestion_records/create_source_ingestion_record")},
     True, REASON_OK),
)


def self_test() -> int:
    failures = 0
    print("Lab writer enablement decision gate — self-test (synthetic values only)")
    print("=" * 72)
    for label, env, expect_authorized, expect_reason in _CASES:
        d = evaluate(env)
        ok = (d["lab_write_authorized"] is expect_authorized
              and d["reason"] == expect_reason
              and is_consistent(d)
              and d["safe_to_write_production_now"] is False
              and d["production_write_authorized"] is False)
        failures += (not ok)
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
        if not ok:
            print(f"        expected authorized={expect_authorized} reason={expect_reason}")
            print(f"        got      authorized={d['lab_write_authorized']} reason={d['reason']}")

    # An authorized lab decision must never imply a production one.
    d = evaluate({TARGET_ENV: "lab", LAB_CONFIRM_ENV: "1", LAB_URL_ENV: _LAB_OK,
                  LAB_TARGETS_ENV: "review_records/create_review_record"})
    implies = d["lab_write_authorized"] and not d["safe_to_write_production_now"]
    failures += (not implies)
    print(f"  [{'PASS' if implies else 'FAIL'}] lab authorization does not imply production "
          f"authorization")

    # The anchor bootstrap must not leak into the ordinary enableable set.
    ok = ANCHOR_BOOTSTRAP_PAIR not in LAB_ENABLEABLE_WRITER_TARGETS
    failures += (not ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] the anchor pair is not in the ordinary enableable set")

    d = evaluate({TARGET_ENV: "lab", LAB_CONFIRM_ENV: "1", ANCHOR_BOOTSTRAP_CONFIRM_ENV: "1",
                  LAB_URL_ENV: _LAB_OK,
                  LAB_TARGETS_ENV: "engagements/create_engagement_authorization_anchor"})
    ok = (d["anchor_bootstrap_authorized"] is True
          and d["safe_to_write_production_now"] is False
          and d["production_write_authorized"] is False
          and d["authorized_writer_targets"] == [
              "engagements/create_engagement_authorization_anchor"])
    failures += (not ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] an authorized anchor bootstrap grants only the anchor "
          f"and leaves production denied")

    # No rejected authorizer may substitute for the real confirmation.
    for var in REJECTED_AUTHORIZER_ENVS:
        d = evaluate({TARGET_ENV: "lab", var: "1", LAB_URL_ENV: _LAB_OK,
                      LAB_TARGETS_ENV: "review_records/create_review_record"})
        ok = d["lab_write_authorized"] is False and d["reason"] == REASON_NO_CONFIRM
        failures += (not ok)
        print(f"  [{'PASS' if ok else 'FAIL'}] {var} does not substitute for the lab confirmation")

    # Output must not carry connection values.
    rendered = json.dumps(evaluate(
        {TARGET_ENV: "lab", LAB_CONFIRM_ENV: "1", LAB_URL_ENV: _LAB_OK,
         LAB_TARGETS_ENV: "review_records/create_review_record"}))
    leaked = [tok for tok in ("synthetic.invalid", "3306", ":x@", "mysql+pymysql", "://")
              if tok in rendered]
    failures += bool(leaked)
    print(f"  [{'PASS' if not leaked else 'FAIL'}] decision output carries no host, port, "
          f"password, scheme, or DSN")

    print("=" * 72)
    print(f"  cases: {len(_CASES)}   failures: {failures}")
    print("RESULT:", "PASS" if failures == 0 else "FAIL")
    return 0 if failures == 0 else 2


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Lab-only writer enablement decision gate (offline; decides, never writes).")
    parser.add_argument("--self-test", action="store_true",
                        help="Run the synthetic decision cases and exit. Contacts nothing.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of key=value lines.")
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()

    banner = (lambda *a: print(*a, file=sys.stderr)) if args.json else print
    banner("Peak lab writer enablement decision gate — OFFLINE, decision record only")
    banner("=" * 72)

    decision = evaluate(os.environ)
    _emit(decision, args.json)

    banner("=" * 72)
    if not is_consistent(decision):
        banner("RESULT: INCONSISTENT")
        return 1
    if decision["lab_write_authorized"]:
        banner("RESULT: LAB WRITE DECISION AUTHORIZED (lab only; production remains denied)")
        banner("This is a decision about the target and scope, not approval to write. Phase 89 "
               "invokes no writer. A future phase must name the writer, the records, the "
               "authorization scope, the idempotency keys, and the verification plan.")
    else:
        banner(f"RESULT: DENIED ({decision['reason']})")
    banner("Production write enablement is false on every path this tool can take. It contacts no "
           "database, issues no statement, reads no credential file, and invokes no writer.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
