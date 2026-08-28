"""Explicit lab/production targeting for Alembic migrations (Phase 84).

**The defect.** ``alembic/env.py`` resolves its URL from ``PEAK_DATABASE_URL`` and nothing else.
No variable name says which environment that URL points at, so an intended lab migration run in a
shell that still holds a production value migrates production instead, silently and successfully.
Phases 82 and 83 recorded this as procedural-only: the separation between the two environments was
shell discipline, with no control in source.

**Why it had to be fixed now.** The accident was survivable only because the repository and
production were both at head ``014`` with nothing further to apply, which made a misdirected
``upgrade head`` a no-op. That is an accident of timing, not a control, and it expires the moment a
migration ``015`` exists. This guard lands before that migration does.

**What this module does.** For MySQL/MariaDB URLs it requires the operator to name the target
environment and confirm it, then checks that the URL actually matches the named target before any
connection is opened:

===================================  ==========================================================
``PEAK_ALEMBIC_TARGET``              ``lab`` or ``production`` — required for MySQL/MariaDB
``PEAK_LAB_MIGRATION_CONFIRM=1``     required when the target is ``lab``
``PEAK_PRODUCTION_MIGRATION_CONFIRM=1``  required when the target is ``production``
===================================  ==========================================================

``PEAK_LAB_CONFIRM`` is deliberately **not** used: Phase 82 published it as reserved and a no-op,
so an operator may reasonably believe it is already set somewhere and inert. A guard must not share
a name with something documented as doing nothing.

**What this module does not do.** It grants no authority. Passing the production branch means the
URL is consistent with a production migration, not that a production migration is approved —
production migrations remain unauthorized outside a separately approved phase. The guard's whole job
is to stop the *wrong* environment being migrated, never to bless the right one.

**Local and test URLs are untouched.** SQLite and every non-MySQL dialect bypass the guard entirely,
so temporary-file SQLite harnesses keep working with no environment at all.

**Value-free by construction.** Nothing here reads a credential file or ``.env``, opens a connection,
or logs a URL. Failure messages carry the target name, a classification of the parsed user and
schema, and a reason code — never a password, host, port, query parameter, or whole connection
string.
"""

from __future__ import annotations

import os
from typing import Mapping, Optional
from urllib.parse import urlsplit

# --- environment contract -----------------------------------------------------------------

TARGET_ENV = "PEAK_ALEMBIC_TARGET"
LAB_CONFIRM_ENV = "PEAK_LAB_MIGRATION_CONFIRM"
PRODUCTION_CONFIRM_ENV = "PEAK_PRODUCTION_MIGRATION_CONFIRM"

TARGET_LAB = "lab"
TARGET_PRODUCTION = "production"
SUPPORTED_TARGETS = (TARGET_LAB, TARGET_PRODUCTION)

#: The only value either confirmation variable accepts. Anything else — including "true", "yes",
#: and an empty string — reads as unconfirmed, so a half-set variable fails closed.
CONFIRM_VALUE = "1"

# --- the fixed lab identity ---------------------------------------------------------------

#: Phase 83 created exactly these two names, through SQL, and nothing else may pass as the lab.
LAB_SCHEMA = "peak_lab"
LAB_MIGRATION_USER = "peak_lab_migrate"

#: Any identifier starting with this marks a lab object; used to keep lab names out of production.
LAB_MARKER = "peak_lab"

#: The provider's default database on a freshly created managed service. A migration aimed at it
#: means the DSN's schema segment was lost or never written, so it must never pass as the lab.
PROVIDER_DEFAULT_DATABASES = frozenset({"defaultdb", "mysql", "information_schema", "sys",
                                        "performance_schema"})

#: Substrings that mark an identifier as production-ish. Present for a clear reason code; the lab
#: branch's exact-name requirement already excludes them.
PRODUCTION_MARKERS = ("prod", "production")

#: Only these dialects are guarded. SQLite ignores this module entirely so local harnesses, which
#: point at a temporary file and set no environment at all, keep working unchanged.
GUARDED_DIALECTS = frozenset({"mysql", "mariadb"})

# --- outcome and user/schema classes ------------------------------------------------------

OUTCOME_NOT_GUARDED = "not_guarded_dialect"
OUTCOME_LAB_OK = "lab_target_confirmed"
OUTCOME_PRODUCTION_OK = "production_target_confirmed"

USER_CLASS_LAB_MIGRATION = "expected_lab_migration_user"
USER_CLASS_LAB_MARKED = "lab_marked_user"
USER_CLASS_PRODUCTION_MARKED = "production_marked_user"
USER_CLASS_OTHER = "other_user"
USER_CLASS_ABSENT = "absent"

SCHEMA_CLASS_LAB = "expected_lab_schema"
SCHEMA_CLASS_LAB_MARKED = "lab_marked_schema"
SCHEMA_CLASS_PROVIDER_DEFAULT = "provider_default_schema"
SCHEMA_CLASS_PRODUCTION_MARKED = "production_marked_schema"
SCHEMA_CLASS_OTHER = "other_schema"
SCHEMA_CLASS_ABSENT = "absent"


class MigrationTargetError(RuntimeError):
    """Raised before any connection when the URL does not match the declared target.

    ``reason`` is a stable code for tests and audit notes; ``str(exc)`` is the operator message and
    is value-free — it names variables, classes, and expected constants only.
    """

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


def dialect_of(url: str) -> str:
    """Return the bare dialect of a SQLAlchemy URL — ``mysql+pymysql://…`` yields ``mysql``.

    Parsing is deliberately textual: this module must not import SQLAlchemy, because the guard has
    to be callable and testable in a stdlib-only interpreter.
    """
    scheme = urlsplit(url).scheme
    return scheme.split("+", 1)[0].strip().lower()


def parse_identity(url: str) -> dict:
    """Return only the two identifying fields the guard judges: username and database/schema.

    Host, port, password, and query parameters are parsed past and thrown away rather than stored,
    so nothing this function returns can leak into a message or a traceback.
    """
    parts = urlsplit(url)
    try:
        username = parts.username or ""
    except ValueError:
        username = ""
    database = parts.path.lstrip("/").split("/", 1)[0]
    return {
        "dialect": dialect_of(url),
        "username": username.strip(),
        "database": database.strip(),
    }


def _has_marker(value: str, markers) -> bool:
    low = value.lower()
    return any(m in low for m in markers)


def classify_user(username: str) -> str:
    if not username:
        return USER_CLASS_ABSENT
    low = username.lower()
    if low == LAB_MIGRATION_USER:
        return USER_CLASS_LAB_MIGRATION
    if LAB_MARKER in low:
        return USER_CLASS_LAB_MARKED
    if _has_marker(low, PRODUCTION_MARKERS):
        return USER_CLASS_PRODUCTION_MARKED
    return USER_CLASS_OTHER


def classify_schema(database: str) -> str:
    if not database:
        return SCHEMA_CLASS_ABSENT
    low = database.lower()
    if low == LAB_SCHEMA:
        return SCHEMA_CLASS_LAB
    if low in PROVIDER_DEFAULT_DATABASES:
        return SCHEMA_CLASS_PROVIDER_DEFAULT
    if LAB_MARKER in low:
        return SCHEMA_CLASS_LAB_MARKED
    if _has_marker(low, PRODUCTION_MARKERS):
        return SCHEMA_CLASS_PRODUCTION_MARKED
    return SCHEMA_CLASS_OTHER


def _fail(reason: str, detail: str, target: str, user_class: str, schema_class: str) -> None:
    raise MigrationTargetError(
        reason,
        f"Alembic migration target check failed: {detail} "
        f"[target={target or 'unset'} user_class={user_class} schema_class={schema_class} "
        f"reason={reason}]. This message is value-free by design: it names variables, expected "
        f"constants, and classifications only, never a connection value.",
    )


def assert_migration_target(url: str, env: Optional[Mapping[str, str]] = None) -> dict:
    """Require an explicit, matching migration target, or raise :class:`MigrationTargetError`.

    Returns a small value-free summary — outcome, target, and the two classifications — so a caller
    or harness can record what was decided without ever holding a connection value.

    Called before the engine is created, so every failure below happens with no connection open and
    no statement issued.
    """
    env = os.environ if env is None else env
    identity = parse_identity(url)
    user_class = classify_user(identity["username"])
    schema_class = classify_schema(identity["database"])

    if identity["dialect"] not in GUARDED_DIALECTS:
        # SQLite and friends: local, disposable, and never an environment worth confusing.
        return {"outcome": OUTCOME_NOT_GUARDED, "target": None, "dialect": identity["dialect"],
                "user_class": user_class, "schema_class": schema_class}

    target = (env.get(TARGET_ENV) or "").strip().lower()
    if not target:
        _fail("target_not_declared",
              f"a MySQL/MariaDB migration requires {TARGET_ENV} to be set to one of "
              f"{', '.join(SUPPORTED_TARGETS)}",
              target, user_class, schema_class)
    if target not in SUPPORTED_TARGETS:
        _fail("target_not_supported",
              f"{TARGET_ENV} must be one of {', '.join(SUPPORTED_TARGETS)}",
              target, user_class, schema_class)

    if target == TARGET_LAB:
        if (env.get(LAB_CONFIRM_ENV) or "").strip() != CONFIRM_VALUE:
            _fail("lab_not_confirmed",
                  f"a lab migration requires {LAB_CONFIRM_ENV}={CONFIRM_VALUE}",
                  target, user_class, schema_class)
        if schema_class == SCHEMA_CLASS_PROVIDER_DEFAULT:
            _fail("lab_schema_is_provider_default",
                  f"the URL names a provider default database, not the controlled lab schema "
                  f"{LAB_SCHEMA}",
                  target, user_class, schema_class)
        if schema_class == SCHEMA_CLASS_PRODUCTION_MARKED or user_class == USER_CLASS_PRODUCTION_MARKED:
            _fail("production_marker_under_lab_target",
                  "the URL carries a production marker while the declared target is the lab",
                  target, user_class, schema_class)
        if schema_class != SCHEMA_CLASS_LAB:
            _fail("lab_schema_mismatch",
                  f"a lab migration must name the controlled schema {LAB_SCHEMA}",
                  target, user_class, schema_class)
        if user_class != USER_CLASS_LAB_MIGRATION:
            _fail("lab_user_mismatch",
                  f"a lab migration must connect as {LAB_MIGRATION_USER}",
                  target, user_class, schema_class)
        return {"outcome": OUTCOME_LAB_OK, "target": target, "dialect": identity["dialect"],
                "user_class": user_class, "schema_class": schema_class}

    # target == TARGET_PRODUCTION. Passing here means the URL is *consistent with* production, not
    # that a production migration is authorized; that remains a separately approved phase.
    if (env.get(PRODUCTION_CONFIRM_ENV) or "").strip() != CONFIRM_VALUE:
        _fail("production_not_confirmed",
              f"a production migration requires {PRODUCTION_CONFIRM_ENV}={CONFIRM_VALUE}, and "
              f"remains unauthorized outside a separately approved phase",
              target, user_class, schema_class)
    if schema_class in (SCHEMA_CLASS_LAB, SCHEMA_CLASS_LAB_MARKED) or \
            user_class in (USER_CLASS_LAB_MIGRATION, USER_CLASS_LAB_MARKED):
        _fail("lab_marker_under_production_target",
              f"the URL carries a lab marker ({LAB_MARKER}) while the declared target is "
              f"production",
              target, user_class, schema_class)
    if schema_class == SCHEMA_CLASS_PROVIDER_DEFAULT:
        _fail("production_schema_is_provider_default",
              "the URL names a provider default database rather than the controlled schema",
              target, user_class, schema_class)
    if schema_class == SCHEMA_CLASS_ABSENT:
        _fail("production_schema_absent",
              "the URL names no database/schema at all",
              target, user_class, schema_class)
    if user_class == USER_CLASS_ABSENT:
        _fail("production_user_absent",
              "the URL names no user at all",
              target, user_class, schema_class)
    return {"outcome": OUTCOME_PRODUCTION_OK, "target": target, "dialect": identity["dialect"],
            "user_class": user_class, "schema_class": schema_class}
