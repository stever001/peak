#!/usr/bin/env python3
"""Managed MySQL production-parity checker (Phase 41).

Turns the Phase 38 defect class into a repeatable, automated check.

**The motivating defect.** MySQL enforces a **64-character limit on identifiers** (index and
constraint names). SQLite does not. Phase 38's convention-derived index name
``ix_internal_report_review_packets_internal_assessment_report_draft_id`` is **69** characters: it
passed every local SQLite check and would have failed on ``alembic upgrade head`` against managed
MySQL. Phase 39's convention-derived names would have reached **78**. A green SQLite run is
necessary but **not sufficient** — this tool checks the MySQL-specific assumptions SQLite cannot.

Two modes:

* ``--mode static`` (default) — **fully offline**. No credentials, no network, no DNS, no TLS, no
  ``.env`` read, no DSN, no database of any kind. Safe to run in ``make validate`` on a laptop with
  no managed DB access. Identifiers that migrations build at runtime (f-strings over module
  constants) cannot be read from source text, so when SQLAlchemy/Alembic are importable this mode
  *simulates* each migration's ``upgrade()``/``downgrade()`` against a **recording stand-in for
  ``op``** that executes no SQL and touches no database — yielding the exact identifiers MySQL would
  receive. Without those libraries it falls back to source-text checks and says so.

* ``--mode staging`` — **opt-in, fail-closed**. Refuses to do anything unless the caller has
  explicitly marked the target as disposable test/staging *and* supplied a DSN out-of-band. With no
  such configuration it prints a sanitized skip and exits 0, attempting no network and importing no
  database driver. Production is never selectable.

**Secret hygiene.** This tool never reads ``.env``, never prints an environment variable's value,
never prints a DSN/username/password/host/port/token/certificate, and never prints a raw exception
string (which can embed a DSN). Every outbound line passes through :func:`sanitize` first.

**It changes nothing.** No schema is proposed, no migration is written, no row is read or written,
and no cleanup/delete path exists. It only reports.

See docs/MANAGED_MYSQL_PRODUCTION_PARITY_VALIDATION.md.

Exit status:
  0  -> all parity checks passed, or the mode skipped safely (no configuration)
  1  -> a parity check failed
  2  -> misuse (e.g. production requested, or a staging run without a disposable marker)
"""

from __future__ import annotations

import argparse
import io
import os
import re
import sys
import tokenize

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSIONS_DIR = os.path.join(REPO_ROOT, "alembic", "versions")
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

#: MySQL's hard limit on table / index / constraint / column identifiers.
MYSQL_IDENTIFIER_LIMIT = 64

#: The pinned Alembic head for this baseline. A new migration must update this deliberately.
EXPECTED_HEAD = "012_internal_report_review_packet_decisions"
EXPECTED_MIGRATION_COUNT = 12

#: Required MySQL table options on every created table.
REQUIRED_TABLE_ARGS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}

#: Alembic operations a schema-only migration may use. Anything else is reported.
ALLOWED_MIGRATION_OPS = frozenset({
    "create_table", "create_index", "drop_index", "drop_table", "add_column", "drop_column",
})
#: Operations that would insert data or run arbitrary SQL. None may ever appear.
FORBIDDEN_MIGRATION_OPS = frozenset({
    "bulk_insert", "execute", "run_async",
})
#: Destructive operations, permitted **only** inside a downgrade and only on objects the same
#: migration created.
DESTRUCTIVE_OPS = frozenset({"drop_table", "drop_index", "drop_column"})

#: Identifier names known to exceed the MySQL limit. These must never reappear (Phase 38/39).
KNOWN_OVERLONG_IDENTIFIERS = (
    "ix_internal_report_review_packets_internal_assessment_report_draft_id",          # 69
    "ix_internal_report_review_packet_decisions_internal_report_review_packet_id",    # 74
    "ix_internal_report_review_packet_decisions_internal_assessment_report_draft_id",  # 78
)

#: Columns whose comparison semantics are security- or identity-relevant. If the managed server's
#: default collation is case-insensitive, two values differing only in case collapse into one —
#: which would merge distinct idempotency keys and weaken identity/scope matching.
COMPARISON_SENSITIVE_COLUMNS = (
    "id", "owner_id", "client_id", "engagement_id", "authorization_scope",
    "idempotency_key", "payload_fingerprint", "plan_fingerprint",
    "report_draft_payload_fingerprint", "packet_payload_fingerprint", "packet_hash",
)

#: Environment variables that may carry a DSN. Their *values* are never read into output.
ENV_DSN_VARS = {
    "test": "PEAK_MANAGED_MYSQL_TEST_DSN",
    "staging": "PEAK_MANAGED_MYSQL_STAGING_DSN",
}
PROD_DSN_VAR = "PEAK_MANAGED_MYSQL_PROD_DSN"
#: The caller must set this to explicitly affirm the target is disposable and non-production.
DISPOSABLE_MARKER_VAR = "PEAK_MANAGED_MYSQL_DISPOSABLE"

# --------------------------------------------------------------------------- output sanitation

_SECRET_PATTERNS = (
    # scheme://user:pass@host:port/db  — the whole thing goes, never a partial echo
    re.compile(r"\b[a-zA-Z][a-zA-Z0-9+.\-]*://\S+"),
    re.compile(r"(?i)\b(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key)\b\s*[:=]\s*\S+"),
    re.compile(r"(?i)-----BEGIN [A-Z ]*(?:PRIVATE KEY|CERTIFICATE)-----[\s\S]*?-----END [A-Z ]*(?:PRIVATE KEY|CERTIFICATE)-----"),
    re.compile(r"\b[\w.\-]+:[^\s@/]+@[\w.\-]+"),        # bare user:pass@host
)
_WITHHELD = "[secret withheld]"


def sanitize(text) -> str:
    """Scrub anything DSN- or credential-shaped from a line before it is printed.

    Defense in depth: this tool never *intends* to place a secret in output, but an exception
    message or a caller-supplied label can carry one, so every outbound line is scrubbed.
    """
    out = str(text)
    for pattern in _SECRET_PATTERNS:
        out = pattern.sub(_WITHHELD, out)
    return out


def emit(line: str = "") -> None:
    print(sanitize(line))


def safe_error(exc: BaseException) -> str:
    """Describe a failure by exception *type* only — never its message, which may embed a DSN."""
    return f"{type(exc).__name__} (detail withheld)"


# --------------------------------------------------------------------------- result bookkeeping


class Report:
    """Collects pass / fail / warn / skip findings and renders them."""

    def __init__(self) -> None:
        self.failures: list = []
        self.warnings: list = []
        self.skips: list = []
        self.passes = 0

    def ok(self, label: str) -> None:
        self.passes += 1
        emit(f"  [PASS] {label}")

    def fail(self, label: str, detail: str = "") -> None:
        self.failures.append(label)
        emit(f"  [FAIL] {label}" + (f" — {detail}" if detail else ""))

    def warn(self, label: str, detail: str = "") -> None:
        self.warnings.append(label)
        emit(f"  [WARN] {label}" + (f" — {detail}" if detail else ""))

    def skip(self, label: str) -> None:
        self.skips.append(label)
        emit(f"  [skip] {label}")

    def check(self, label: str, condition: bool, detail: str = "") -> bool:
        if condition:
            self.ok(label)
        else:
            self.fail(label, detail)
        return bool(condition)


# --------------------------------------------------------------------------- migration sources


def migration_files() -> list:
    return sorted(f for f in os.listdir(VERSIONS_DIR) if f.endswith(".py"))


def read_migration(filename: str) -> str:
    with open(os.path.join(VERSIONS_DIR, filename), "r", encoding="utf-8") as fh:
        return fh.read()


def _split_upgrade_downgrade(source: str):
    """Return ``(upgrade_body, downgrade_body)`` as source text."""
    parts = source.split("def downgrade")
    upgrade = parts[0].split("def upgrade")[-1] if "def upgrade" in parts[0] else ""
    downgrade = parts[1] if len(parts) > 1 else ""
    return upgrade, downgrade


def _op_calls(body: str) -> list:
    return re.findall(r"\bop\.([a-z_]+)\s*\(", body)


def code_only(source: str) -> str:
    """Return executable tokens with comments and docstrings removed.

    Boundary claims must be about the code that runs. A comment explaining *why* an overlong
    identifier was rejected is documentation worth keeping — it must not be mistaken for the
    identifier being used.
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


def string_literals(source: str) -> list:
    """Return the string-literal values in a module (docstrings included, comments excluded)."""
    values = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.STRING:
                values.append(tok.string)
    except tokenize.TokenError:  # pragma: no cover
        return re.findall(r'["\']([^"\'\n]+)["\']', source)
    return values


def _is_literal(token: str) -> bool:
    """True when a captured call argument is a quoted literal rather than a runtime name."""
    return bool(token) and token[0] in "\"'"


# --------------------------------------------------------------------------- static: sources


def check_migration_chain(report: Report) -> None:
    emit("\n2. Migration chain: linear, single head, pinned, no unplanned migration")
    files = migration_files()
    report.check(f"exactly {EXPECTED_MIGRATION_COUNT} migrations present",
                 len(files) == EXPECTED_MIGRATION_COUNT,
                 f"found {len(files)}")
    report.check("no migration 013 or later added",
                 not any(re.match(r"^0*(?:1[3-9]|[2-9]\d)_", f) for f in files))

    revisions, downs = {}, {}
    for name in files:
        src = read_migration(name)
        rev = re.search(r'^revision\s*=\s*["\']([^"\']+)["\']', src, re.M)
        down = re.search(r'^down_revision\s*=\s*(?:["\']([^"\']+)["\']|None)', src, re.M)
        if rev:
            revisions[name] = rev.group(1)
        downs[name] = down.group(1) if (down and down.group(1)) else None

    report.check("every migration declares a revision id", len(revisions) == len(files))
    parents = [d for d in downs.values() if d is not None]
    report.check("migration chain is linear (no duplicate down_revision)",
                 len(parents) == len(set(parents)))
    report.check("exactly one base migration (down_revision = None)",
                 sum(1 for d in downs.values() if d is None) == 1)
    children = set(parents)
    heads = [r for r in revisions.values() if r not in children]
    report.check("exactly one head", len(heads) == 1, f"found {len(heads)}")
    report.check(f"head is pinned at {EXPECTED_HEAD}", heads == [EXPECTED_HEAD],
                 "head moved; update EXPECTED_HEAD deliberately if a migration was added")
    unknown = [d for d in parents if d not in set(revisions.values())]
    report.check("every down_revision names a known revision", not unknown)


def check_migration_sources(report: Report) -> None:
    emit("\n3. Migration source policy: schema-only, bounded downgrade, MySQL table options")
    for name in migration_files():
        src = read_migration(name)
        upgrade, downgrade = _split_upgrade_downgrade(src)

        used = set(_op_calls(src))
        forbidden = sorted(used & FORBIDDEN_MIGRATION_OPS)
        report.check(f"{name}: no data/arbitrary-SQL op ({', '.join(sorted(FORBIDDEN_MIGRATION_OPS))})",
                     not forbidden, f"uses {forbidden}")
        unexpected = sorted(used - ALLOWED_MIGRATION_OPS)
        report.check(f"{name}: only schema operations used", not unexpected,
                     f"unexpected {unexpected}")

        low = src.lower()
        report.check(f"{name}: no INSERT / seed data",
                     not any(t in low for t in ("insert into", "bulk_insert", ".insert(",
                                                "op.execute(", "session.add")))

        destructive_up = sorted(set(_op_calls(upgrade)) & DESTRUCTIVE_OPS)
        report.check(f"{name}: no destructive operation in upgrade()", not destructive_up,
                     f"upgrade uses {destructive_up}")

        # Downgrade must only drop what this migration created. Migrations legitimately build
        # identifiers at runtime (loop variables, f-strings over module constants), which source
        # text cannot resolve — those cases are proven exactly by the simulation tier in step 5.
        # Here we compare only literal-vs-literal, so this tier never guesses.
        created_tables = {t for t in re.findall(
            r"op\.create_table\(\s*([A-Za-z_][\w]*|['\"][^'\"]+['\"])", upgrade)}
        dropped_tables = {t for t in re.findall(
            r"op\.drop_table\(\s*([A-Za-z_][\w]*|['\"][^'\"]+['\"])", downgrade)}
        literal_created = {t.strip("\"'") for t in created_tables if _is_literal(t)}
        literal_dropped = {t.strip("\"'") for t in dropped_tables if _is_literal(t)}
        deferred = len(dropped_tables) - len(literal_dropped)
        report.check(f"{name}: downgrade drops only tables this migration created "
                     f"(literal names)",
                     literal_dropped <= literal_created,
                     f"drops {sorted(literal_dropped - literal_created)}")
        if deferred:
            report.skip(f"{name}: {deferred} drop_table target(s) are resolved at runtime; "
                        "exact scope is proven by the simulation in step 5")

        if "op.create_table(" in upgrade:
            for key, value in REQUIRED_TABLE_ARGS.items():
                report.check(f"{name}: declares {key}={value}",
                             re.search(rf'["\']?{key}["\']?\s*[:=]\s*["\']{value}["\']', src)
                             is not None)


def check_source_literal_identifiers(report: Report) -> None:
    emit("\n4. Identifier literals in migration + model source fit the MySQL 64-char limit")
    offenders = []
    scanned = 0
    sources = [(f"alembic/versions/{n}", read_migration(n)) for n in migration_files()]
    with open(os.path.join(REPO_ROOT, "peak", "db", "models.py"), encoding="utf-8") as fh:
        sources.append(("peak/db/models.py", fh.read()))
    for rel, src in sources:
        for literal in re.findall(r'["\']((?:ix_|uq_|fk_|ck_|pk_)[A-Za-z0-9_]+)["\']', src):
            scanned += 1
            if len(literal) > MYSQL_IDENTIFIER_LIMIT:
                offenders.append(f"{rel}: {literal} ({len(literal)})")
    report.check(f"every identifier literal fits {MYSQL_IDENTIFIER_LIMIT} chars "
                 f"({scanned} scanned)", not offenders, "; ".join(offenders))

    # The known-overlong names are deliberately *quoted in comments and docstrings* to explain why
    # the short names exist. That documentation must survive; what must never come back is the
    # name used as an actual identifier. So scan executable code and identifier-shaped string
    # literals — not prose.
    reappeared = []
    for rel, src in sources:
        code = code_only(src)
        literals = [v.strip("\"'") for v in string_literals(src)]
        identifier_literals = [v for v in literals
                               if re.fullmatch(r"(?:ix_|uq_|fk_|ck_|pk_)[A-Za-z0-9_]+", v)]
        for known in KNOWN_OVERLONG_IDENTIFIERS:
            if known in code or known in identifier_literals:
                reappeared.append(f"{rel}: {known}")
    report.check("no known overlong Phase 38/39 identifier is used as a real identifier",
                 not reappeared, "; ".join(reappeared))

    documented = sum(1 for _, src in sources for known in KNOWN_OVERLONG_IDENTIFIERS
                     if known in src)
    if documented:
        report.ok(f"the overlong names remain documented in prose as cautionary examples "
                  f"({documented} mention(s)) without being used")


# --------------------------------------------------------------------------- static: simulated


class _RecordingOp:
    """A stand-in for ``alembic.op`` that records calls and executes nothing.

    No database is opened, no SQL is emitted, no connection exists. This exists purely so a
    migration's *runtime-built* identifiers (f-strings over module constants) become inspectable
    offline — which plain source scanning cannot do.
    """

    def __init__(self) -> None:
        self.tables: list = []        # (name, table_kwargs)
        self.indexes: list = []       # (name, table, unique)
        self.constraints: list = []   # (name, table)
        self.columns: list = []       # (table, column_name)
        self.dropped: list = []       # (op_name, identifier)
        self.unexpected: list = []

    # --- creation ---
    def create_table(self, name, *args, **kwargs):
        self.tables.append((str(name), dict(kwargs)))
        for arg in args:
            cname = getattr(arg, "name", None)
            kind = type(arg).__name__
            if kind in ("UniqueConstraint", "CheckConstraint", "ForeignKeyConstraint",
                        "PrimaryKeyConstraint", "Index") and cname:
                self.constraints.append((str(cname), str(name)))
            elif kind == "Column" and cname:
                self.columns.append((str(name), str(cname)))

    def create_index(self, name, table_name=None, columns=None, unique=False, **kwargs):
        self.indexes.append((str(name), str(table_name), bool(unique)))

    def create_unique_constraint(self, name, table_name=None, *a, **kw):
        self.constraints.append((str(name), str(table_name)))

    def create_foreign_key(self, name, source_table=None, *a, **kw):
        self.constraints.append((str(name), str(source_table)))

    def create_check_constraint(self, name, table_name=None, *a, **kw):
        self.constraints.append((str(name), str(table_name)))

    def add_column(self, table_name, column=None, **kw):
        self.columns.append((str(table_name), str(getattr(column, "name", column))))

    # --- removal (recorded so downgrade scope can be verified) ---
    def drop_index(self, name, table_name=None, **kw):
        self.dropped.append(("drop_index", str(name)))

    def drop_table(self, name, **kw):
        self.dropped.append(("drop_table", str(name)))

    def drop_column(self, table_name, column_name=None, **kw):
        self.dropped.append(("drop_column", f"{table_name}.{column_name}"))

    def drop_constraint(self, name, table_name=None, **kw):
        self.dropped.append(("drop_constraint", str(name)))

    def __getattr__(self, item):
        def _recorder(*args, **kwargs):
            self.unexpected.append(item)
        return _recorder


def _load_migration_module(filename: str):
    import importlib.util

    path = os.path.join(VERSIONS_DIR, filename)
    spec = importlib.util.spec_from_file_location(f"_peak_parity_{filename[:-3]}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_simulated_migrations(report: Report) -> None:
    """Determine the exact identifiers each migration would send to MySQL — with no database."""
    emit("\n5. Simulated migration identifiers (no DB, no SQL, no connection)")
    try:
        import sqlalchemy  # noqa: F401
        import alembic  # noqa: F401
    except ImportError:
        report.skip("SQLAlchemy/Alembic not installed — runtime-built identifiers not simulated "
                    "(source-literal checks above still applied; "
                    "run with PYTHON=.venv/bin/python for the full check)")
        return

    total_ids = 0
    offenders, bad_args, leftovers, unexpected_ops = [], [], [], []
    for name in migration_files():
        try:
            module = _load_migration_module(name)
        except Exception as exc:  # noqa: BLE001 - type only; never leak a message
            report.fail(f"{name}: could not be loaded for simulation", safe_error(exc))
            continue

        recorder = _RecordingOp()
        original = getattr(module, "op", None)
        module.op = recorder
        try:
            module.upgrade()
            created = {
                "tables": [t for t, _ in recorder.tables],
                "indexes": [i for i, _, _ in recorder.indexes],
                "constraints": [c for c, _ in recorder.constraints],
                "columns": [f"{t}.{c}" for t, c in recorder.columns],
            }
            table_kwargs = dict(recorder.tables)
            up_unexpected = list(recorder.unexpected)

            recorder_down = _RecordingOp()
            module.op = recorder_down
            module.downgrade()
            dropped = list(recorder_down.dropped)
            down_unexpected = list(recorder_down.unexpected)
        except Exception as exc:  # noqa: BLE001
            report.fail(f"{name}: simulation raised", safe_error(exc))
            continue
        finally:
            if original is not None:
                module.op = original

        # 5a. Every identifier MySQL would receive fits the limit.
        for kind in ("tables", "indexes", "constraints"):
            for identifier in created[kind]:
                total_ids += 1
                if len(identifier) > MYSQL_IDENTIFIER_LIMIT:
                    offenders.append(f"{name}: {kind[:-1]} '{identifier}' "
                                     f"({len(identifier)} chars)")
        for qualified in created["columns"]:
            column = qualified.split(".", 1)[1]
            total_ids += 1
            if len(column) > MYSQL_IDENTIFIER_LIMIT:
                offenders.append(f"{name}: column '{qualified}' ({len(column)} chars)")

        # 5b. Required MySQL table options on every created table.
        for table, kwargs in table_kwargs.items():
            for key, value in REQUIRED_TABLE_ARGS.items():
                if kwargs.get(key) != value:
                    bad_args.append(f"{name}: {table} missing {key}={value}")

        # 5c. Downgrade removes exactly what upgrade created — nothing wider, nothing left behind.
        created_all = set(created["tables"]) | set(created["indexes"]) \
            | set(created["constraints"]) | set(created["columns"])
        dropped_names = {ident for _, ident in dropped}
        out_of_scope = sorted(dropped_names - created_all)
        if out_of_scope:
            leftovers.append(f"{name}: downgrade touches non-created object(s) {out_of_scope}")
        if up_unexpected or down_unexpected:
            unexpected_ops.append(f"{name}: {sorted(set(up_unexpected + down_unexpected))}")

    report.check(f"every simulated identifier fits {MYSQL_IDENTIFIER_LIMIT} chars "
                 f"({total_ids} identifiers across {len(migration_files())} migrations)",
                 not offenders, "; ".join(offenders))
    report.check("every created table declares InnoDB + utf8mb4", not bad_args,
                 "; ".join(bad_args))
    report.check("every downgrade is scoped to objects its own upgrade created", not leftovers,
                 "; ".join(leftovers))
    report.check("no unexpected Alembic operation is invoked", not unexpected_ops,
                 "; ".join(unexpected_ops))


# --------------------------------------------------------------------------- static: models


def check_model_identifiers(report: Report) -> None:
    emit("\n6. ORM model identifiers fit the MySQL 64-char limit")
    try:
        from peak.db.models import ALL_MODELS
    except ImportError:
        report.skip("SQLAlchemy not installed — model identifiers not introspected "
                    "(run with PYTHON=.venv/bin/python for the full check)")
        return

    offenders, long_tables = [], []
    counted = 0
    for model in ALL_MODELS:
        table = model.__table__
        counted += 1
        if len(table.name) > MYSQL_IDENTIFIER_LIMIT:
            offenders.append(f"table '{table.name}' ({len(table.name)})")
        for column in table.columns:
            if len(column.name) > MYSQL_IDENTIFIER_LIMIT:
                offenders.append(f"column '{table.name}.{column.name}' ({len(column.name)})")
        names = [i.name for i in table.indexes] + [c.name for c in table.constraints if c.name]
        for name in names:
            if len(name) > MYSQL_IDENTIFIER_LIMIT:
                offenders.append(f"index/constraint '{name}' ({len(name)})")
        # The Phase 38 trap: a convention-derived name on a long table silently overflows.
        for column in table.columns:
            derived = f"ix_{table.name}_{column.name}"
            if len(derived) > MYSQL_IDENTIFIER_LIMIT and column.index:
                long_tables.append(f"{table.name}.{column.name} would derive "
                                   f"'{derived}' ({len(derived)})")

    report.check(f"every model identifier fits {MYSQL_IDENTIFIER_LIMIT} chars "
                 f"({counted} tables)", not offenders, "; ".join(offenders))
    report.check("no indexed column relies on a convention-derived name that would overflow",
                 not long_tables, "; ".join(long_tables))

    for model in ALL_MODELS:
        args = getattr(model, "__table_args__", None)
        opts = args if isinstance(args, dict) else next(
            (a for a in (args or ()) if isinstance(a, dict)), {})
        for key, value in REQUIRED_TABLE_ARGS.items():
            if opts.get(key) != value:
                report.fail(f"model {model.__tablename__} declares {key}={value}")
                break
    else:
        report.ok(f"every model declares {REQUIRED_TABLE_ARGS}")


# --------------------------------------------------------------------------- collation policy


def check_collation_policy(report: Report) -> None:
    """Report the charset/collation posture the repo actually pins — and the gap it leaves.

    This deliberately does **not** invent a collation or propose a migration. It states what is
    pinned, what is therefore left to the managed server's default, and which columns that
    ambiguity would affect. Confirming or clearing the gap needs a managed MySQL runtime check
    (``--mode staging``), not a source scan.
    """
    emit("\n7. Charset / collation policy")
    sources = {f"alembic/versions/{n}": read_migration(n) for n in migration_files()}
    with open(os.path.join(REPO_ROOT, "peak", "db", "base.py"), encoding="utf-8") as fh:
        sources["peak/db/base.py"] = fh.read()
    with open(os.path.join(REPO_ROOT, "peak", "db", "models.py"), encoding="utf-8") as fh:
        sources["peak/db/models.py"] = fh.read()
    blob = "\n".join(sources.values())

    report.check("utf8mb4 is pinned as the charset", "utf8mb4" in blob)
    report.check("InnoDB is pinned as the engine", "InnoDB" in blob)
    report.check("no legacy 3-byte utf8 charset is pinned",
                 not re.search(r'["\']utf8["\']|mysql_charset\s*[:=]\s*["\']utf8["\']', blob))

    pinned = re.findall(r"mysql_collate\s*[:=]\s*[\"']([^\"']+)[\"']", blob)
    pinned += re.findall(r"(?i)\bCOLLATE\s+([A-Za-z0-9_]+)", blob)
    if pinned:
        report.ok(f"an explicit collation is pinned ({sorted(set(pinned))})")
        binary_like = [c for c in set(pinned) if c.endswith(("_bin", "_as_cs", "_cs"))]
        report.check("a deterministic (case-sensitive) collation is pinned for governed "
                     "identifiers", bool(binary_like),
                     f"pinned collations are case-insensitive: {sorted(set(pinned))}")
        return

    # Nothing pinned: the managed server's default collation decides comparison semantics.
    report.warn(
        "no explicit collation is pinned anywhere; the managed server default decides comparisons",
        "MySQL 8's default for utf8mb4 is utf8mb4_0900_ai_ci (case- and accent-INSENSITIVE), "
        "while the local SQLite smoke path compares case-SENSITIVELY. This is a genuine "
        "SQLite-vs-MySQL parity gap of the Phase 38 class and cannot be resolved by reading "
        "source: it must be confirmed against the managed server "
        "(`--mode staging`). Affected comparison-sensitive columns: "
        + ", ".join(COMPARISON_SENSITIVE_COLUMNS)
        + ". Consequence if the default is case-insensitive: the UNIQUE "
        "(owner_id, client_id, engagement_id, idempotency_key) idempotency boundary would treat "
        "keys differing only in case as the SAME key. No migration is proposed here — see "
        "docs/MANAGED_MYSQL_PRODUCTION_PARITY_VALIDATION.md.")


# --------------------------------------------------------------------------- modes


def run_static(report: Report) -> int:
    emit("Peak managed MySQL production-parity check — static mode")
    emit("=" * 62)
    emit("Offline: no credentials, no network, no .env, no DSN, no database.")

    emit("\n1. Scope")
    emit(f"  repo migrations : alembic/versions ({len(migration_files())} files)")
    emit(f"  identifier limit: {MYSQL_IDENTIFIER_LIMIT} characters (MySQL)")

    check_migration_chain(report)
    check_migration_sources(report)
    check_source_literal_identifiers(report)
    check_simulated_migrations(report)
    check_model_identifiers(report)
    check_collation_policy(report)
    return 1 if report.failures else 0


def run_staging(report: Report, args) -> int:
    """Opt-in managed-MySQL parity run. Fails closed; skips safely with no configuration."""
    emit("Peak managed MySQL production-parity check — staging mode")
    emit("=" * 62)

    if args.env == "prod":
        emit("REFUSED: production is never a parity/smoke target and is not selectable.")
        emit(f"({PROD_DSN_VAR} exists for operations only; this tool serves test/staging.)")
        return 2

    disposable = args.staging_target_is_disposable or \
        os.environ.get(DISPOSABLE_MARKER_VAR, "").strip().lower() in ("1", "true", "yes")
    dsn_var = ENV_DSN_VARS[args.env]
    dsn_present = bool(os.environ.get(dsn_var))

    if not disposable and not dsn_present:
        emit(f"[skip] no explicit disposable staging target configured "
             f"(mode=staging, env={args.env}).")
        emit("       This is the expected result on a laptop or in CI: managed MySQL parity")
        emit("       validation is opt-in and requires no credentials in Git. Nothing was")
        emit("       connected to, no driver was imported, and no .env was read.")
        emit("       To run it later against a DISPOSABLE test/staging schema:")
        emit(f"         1. export {dsn_var}=... # out-of-band; never committed, never printed")
        emit(f"         2. export {DISPOSABLE_MARKER_VAR}=1  "
             f"# or pass --staging-target-is-disposable")
        emit("       See docs/MANAGED_MYSQL_PRODUCTION_PARITY_VALIDATION.md.")
        return 0

    if not disposable:
        emit("REFUSED: a DSN is configured but the target is not marked disposable.")
        emit(f"         Set {DISPOSABLE_MARKER_VAR}=1 or pass --staging-target-is-disposable")
        emit("         to affirm this schema is throwaway test/staging, never production and")
        emit("         never client data. Refusing to connect.")
        return 2

    if not dsn_present:
        emit(f"[skip] target marked disposable but {dsn_var} is not configured; nothing to do.")
        emit("       No connection attempted, no driver imported, no .env read.")
        return 0

    # Both markers present. Phase 41 ships the gate, not the live run: a live run requires
    # separate, explicit human approval of a specific disposable target.
    emit(f"[ok] {dsn_var} is configured (value hidden) and the target is marked disposable.")
    emit(f"     Environment: {args.env}.")
    emit("[hold] A live managed-MySQL parity run is NOT executed by this phase. It requires")
    emit("       separate explicit approval of a specific disposable staging target. When")
    emit("       approved, the run applies migrations to head on an EMPTY disposable schema,")
    emit("       reads back applied identifier lengths, charset, and collation, and asserts no")
    emit("       client or seed data exists. It performs no production write and no cleanup or")
    emit("       delete path. Run the offline checks now with: --mode static")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Managed MySQL production-parity checker (offline by default).")
    parser.add_argument("--mode", choices=("static", "staging"), default="static",
                        help="static (default) is fully offline; staging is opt-in and "
                             "fails closed without a disposable-target marker.")
    parser.add_argument("--env", choices=("test", "staging", "prod"), default="test",
                        help="Managed environment for --mode staging (prod is refused).")
    parser.add_argument("--staging-target-is-disposable", action="store_true",
                        help="Affirm the staging target is a throwaway schema (never production, "
                             "never client data).")
    args = parser.parse_args(argv)

    report = Report()
    if args.mode == "static":
        code = run_static(report)
    else:
        code = run_staging(report, args)

    if args.mode == "static":
        emit("\n" + "=" * 62)
        emit("Summary")
        emit(f"  passed   : {report.passes}")
        emit(f"  failures : {len(report.failures)}")
        emit(f"  warnings : {len(report.warnings)}")
        emit(f"  skipped  : {len(report.skips)}")
        for label in report.failures:
            emit(f"    FAIL - {label}")
        for label in report.warnings:
            emit(f"    WARN - {label}")
        emit("\nRESULT: " + ("FAIL" if report.failures else "PASS"))
    return code


if __name__ == "__main__":
    sys.exit(main())
