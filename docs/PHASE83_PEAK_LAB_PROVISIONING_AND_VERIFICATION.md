# Phase 83 — Provisioning and Verifying the peak_lab Managed MySQL Lab

**Baseline:** `509d637` — "Add Phase 82 lab MySQL provisioning readiness". Branch `main`, clean tree
at baseline, repo Alembic head `014_engagement_classification`, 14 migrations, 18 tables, 12 writers,
no standing production write enablement.

**Phase 83 executed the Phase 82 runbook under explicit user approval.** It provisioned a separate
managed MySQL lab service, created the controlled schema and three lab credentials, applied the
existing 14 migrations to the lab, and verified the result. **It is environment creation, migration,
and verification only.**

**Production was not touched at any point.** No production environment file was sourced, no
production connection was opened, no production service, network, or configuration was changed, and
no production verifier was run against production. **No writer was invoked and no record was created
through any Peak writer**, in the lab or anywhere else. **No `peak_lab_scenario` was created and no
measured row exists.** **No migration `015`** was authored and **no repository infrastructure was
added** — docs only.

**The provider is not named in this repository**, and no hostname, service URI, DSN, password, token,
certificate, or price appears in any tracked file. That is a standing rule, not a Phase 83 choice.

---

## 1. What was created

| resource | name | notes |
| --- | --- | --- |
| managed service label | **`peak-lab`** | **hyphen** — see §2 |
| controlled schema/database | **`peak_lab`** | underscore; Alembic-managed |
| scenario schema | **`peak_lab_scenario`** | **NOT created** — reserved only |
| migration credential | **`peak_lab_migrate`** | DDL on `peak_lab` only |
| runtime credential | **`peak_lab_runtime`** | **`SELECT` + `INSERT` only** |
| read-only verifier credential | **`peak_lab_verify_ro`** | **`SELECT` only** |

Plan: the **minimal single-node** tier adequate for lab validation. **No high availability, no
replicas, no standby node, no paid extras.** Cost figures are deliberately not recorded here.

**The service is separate from production** — its own host, port, admin plane, and credential
namespace. It is not a database inside the production service, and it is not named `staging`.

---

## 2. Naming correction — the service label could not be `peak_lab`

**Phase 82 specified a managed service label of `peak_lab`. That name is not accepted by the
provider**, whose service names disallow underscores. The service label is therefore **`peak-lab`**,
with a hyphen.

**Only the service label changed.** The MySQL objects keep their underscored names, because they are
created through SQL, where MySQL's identifier rules apply rather than the provider's:

- controlled schema: **`peak_lab`**
- credentials: **`peak_lab_migrate`**, **`peak_lab_runtime`**, **`peak_lab_verify_ro`**

The schema was created with `CREATE DATABASE peak_lab CHARACTER SET utf8mb4` from an admin SQL
session, **not** through the provider console, precisely so the provider's naming rule could not
produce a hyphenated schema name and silently break parity with every downstream document.

The isolation posture is unaffected: `peak-lab` is plainly neither production nor staging.

---

## 3. Grant posture, as verified on the server

Each credential was reduced with `REVOKE ALL PRIVILEGES, GRANT OPTION` and then granted exactly what
its role requires, scoped to `peak_lab.*`. `SHOW GRANTS` confirms the end state:

| credential | global | on `peak_lab.*` | `GRANT OPTION` |
| --- | --- | --- | --- |
| `peak_lab_migrate` | `USAGE` only | `SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, REFERENCES, INDEX, ALTER` | **none** |
| `peak_lab_runtime` | `USAGE` only | **`SELECT, INSERT`** | **none** |
| `peak_lab_verify_ro` | `USAGE` only | **`SELECT`** | **none** |

**No credential holds any privilege on `*.*` beyond `USAGE`**, which the Phase 50 gate classifies as
`HARMLESS_GLOBAL`. **No credential holds `GRANT OPTION`.** No production credential was reused, and
no production data was copied in either direction.

The migration credential's `UPDATE`/`DELETE` are required for `alembic_version` bookkeeping and are
confined to the one schema. **The runtime credential has no `UPDATE` and no `DELETE`**, so anything
it writes in a later phase is permanent by construction — lab scenario data must be designed durable,
not written and cleaned up. Reset and teardown are migration-credential operations, never runtime.

**No credential was created for AgentNet publication, capsule publication, final report, or
client-facing output.** The lab carries no publication authority of any kind.

---

## 4. Migration result

The existing **14** migrations were applied to the empty `peak_lab` schema, and **only** to it:

- **Lab head: `014_engagement_classification`** — matches the repository head.
- **19 base tables** — the **18** controlled tables plus `alembic_version`.
- **All tables `InnoDB`**; database charset `utf8mb4`, database collation `utf8mb4_0900_ai_ci`
  (server default; determinism comes from per-column pinning, not the database default).
- **No migration `015`** was authored or applied.
- **Production was not migrated, stamped, altered, or contacted.**

**The Phase 46 failure mode did not recur.** That bootstrap broke partway at migration `008` on the
`alembic_version` `VARCHAR(32)` limit and needed manual recovery. Here the Phase 47 preflight in
`alembic/env.py` widened the version column automatically before Alembic wrote a revision, and all 14
migrations applied in one clean pass. **This is the first time a fresh bootstrap of this schema has
been rehearsed anywhere it was safe to rehearse it.**

**Server family: MySQL 8.4.** See §7 for the open parity question this raises.

---

## 5. Verification result

### 5.1 Read-only schema and collation verification

Run with `tools/production_mysql_collation_verify.py` under the lab read-only credential, unmodified:

- outcome **`verified_safe_no_remediation_required`**, reason `all_governed_columns_deterministic`
- **alembic head matches: true**
- **19 base tables** (18 expected + `alembic_version`)
- **212 governed columns checked, 212 deterministic, 0 at risk**
- **11 idempotency boundaries checked, 0 at risk**
- `readonly_queries_only=true`, `schema_mutation_made=false`, `data_write_made=false`,
  `migration_executed=false`, `cleanup_delete_made=false`, `secrets_printed=false`

**This is the first server-verified evidence that the governed-collation policy actually holds on a
MySQL server built from these migrations.** `make mysql-collation-audit` has always reported
`MODEL_POLICY_SATISFIED_PRODUCTION_UNVERIFIED` — the model satisfies the policy, with nothing
confirming a real server delivers it. A parity server now confirms it. **The audit's status string is
unchanged and remains accurate**: this run verified the **lab**, not production.

**Wording caption — required.** The tool prints `production_connection_attempted=True`,
`production_connection_made=True`, `production_connectivity_result=succeeded`, and a line reading
"all 212 governed column(s) already use a deterministic collation in production". **Every one of
those statements refers to the lab.** The run used the lab read-only credential against the
`peak-lab` service; **no production connection was attempted or made.** This is the Phase 82 §7.3
tooling gap behaving exactly as predicted, and it is why this caption exists rather than a silent
reliance on the output.

### 5.2 Runtime connectivity and grant gate

Run with `tools/production_runtime_connectivity_gate.py` under the lab runtime credential, live:

`connectivity_succeeded=true` · `required_grants_present=true` · **`excess_grants_present=false`** ·
**`global_privileges_present=false`** · **`grant_option_present=false`** · `schema_mutation_made=false`
· `data_write_made=false` · **`app_table_read_made=false`** · **`writer_invoked=false`** ·
`secrets_printed=false` · `statements_issued=2`

The gate resolved the URL through `create_runtime_engine`, the same path the application uses, and
issued only `SELECT 1` and `SHOW GRANTS FOR CURRENT_USER`.

**Two captions apply.** The gate reports `production_connectivity_result=succeeded` — again, that was
the **lab**. And it reports `ready_for_later_writer_enablement=true`, which is **prerequisite
evidence about the lab credential, not write permission and not a production statement.** The Phase 51
decision gate remains the authority, still reports `safe_to_write_production_now=false`, and is
environment-blind by design: authorizing any lab write is a deliberate source edit with its own
review, and it did not happen here.

### 5.3 Schema inventory and emptiness

Confirmed under the lab read-only credential:

- **`peak_lab` exists**; **`peak_lab_scenario` does not exist**
- **19 base tables**, all `InnoDB`
- **`alembic_version`: 1 row** (the head revision)
- **application rows: 0** — every one of the 18 controlled tables is empty
- **no non-empty application table**

**No measured row, no scenario row, and no Peak record of any kind exists in the lab.**

---

## 6. Lab-only shell guard — applied, and it earned its place

Every lab command ran in a **fresh shell with exactly one lab env file sourced**, asserting before
each connection, by value-free boolean checks only, that the DSN named the expected lab credential and
the `peak_lab` schema, carried TLS settings, and contained no production or staging marker. Each run
additionally asserted that **no other database variable was present in the shell**, so the three role
variables were never simultaneously live. **No environment was printed**: no `env`, no `printenv`, no
bare `set`, no `set -x`, and no `cat`/`grep` of an env file at any point.

Before Alembic, the guard confirmed the target was the lab; the empty `alembic current` output then
independently confirmed an empty schema, which production could not have produced.

**The target was also proven at the SQL layer before any DDL.** The admin session was verified as an
empty, non-production service by three independent signals — the managed admin account name, a
non-default high port, and `SHOW DATABASES` returning only the provider's default database plus the
system schemas, with **no Peak schema and no 18-table set present.** Production would have shown them.

**One incident, recorded rather than hidden.** During env-file authoring, a DSN written **unquoted**
into an env file caused the shell to fail glob expansion on the `?` in the query string and **echo the
whole line, including the migration credential's password**, before any guard could run. **The
`peak_lab_migrate` credential was rotated in response**, and the exposed value was never used
afterwards. Two durable mitigations followed: **every value in every lab env file is single-quoted**,
and the files are now produced by an **out-of-repo generator** that reads passwords with hidden input,
URL-encodes them, and writes correct files directly — removing hand-editing, which had produced five
distinct DSN defects across three attempts (missing `KEY=` prefix, missing `@`, hyphenated schema
name, relative certificate path, unquoted value). **The generator lives outside the repository and is
not tracked.**

**The temporary admin env file contemplated during planning was never created.** The administrative
SQL was run in an interactive session by the operator, so the fourth file — a deviation from the
Phase 82 three-file plan — did not happen.

---

## 7. Warnings and decisions needing review

1. **Server version parity is unconfirmed.** The lab runs **MySQL 8.4**. Phase 81 asked the lab to
   match production's version *family*, and **production's version was not read** — doing so would
   require a production connection, which this phase is barred from and did not make. If production
   runs 8.0, **the lab is a version ahead**, and 8.4 changes several defaults. This is an **open
   parity question**, not a verified match, and it should be settled from out-of-band knowledge before
   the lab is treated as authoritative for production behaviour.
2. **Verifier and gate output say "production" when pointed at the lab.** Captions are supplied in
   §5.1 and §5.2. **Any future lab run whose output becomes an audit artifact must be captioned the
   same way**, because the output does not identify its own environment. Renaming remains a separate,
   later, source-only decision.
3. **`ready_for_later_writer_enablement=true` is about the lab credential**, not production, and is
   not permission. The Phase 51 gate remains the authority and still says no.
4. **The service label is `peak-lab`, the schema is `peak_lab`.** Two similar names now exist. Anyone
   creating further objects must not let the provider's hyphenated label become a schema name.
5. **The credential-exposure incident in §6** is closed by rotation, but the underlying cause —
   hand-written DSNs — is only mitigated by convention plus the generator. Nothing in the repository
   enforces quoting in an out-of-repo file.
6. **`make mysql-parity-staging` remains inert** — `run_staging()` emits `[hold]` and returns 0
   without connecting, and it reads the test DSN variable rather than the staging one. Phase 83 did
   not use or fix it, exactly as Phase 82 specified.
7. **`alembic/env.py` still has no lab target** and reads only `PEAK_DATABASE_URL`. The seam is
   unchanged and remains the largest residual risk. **It is now materially more dangerous than it was
   at Phase 82**: the mitigation that a misdirected `upgrade head` is a harmless no-op held only while
   production and the repository were both at head `014` with nothing further to apply. That is still
   true today, and **it stops being true the moment a `015` exists.**
8. **`GOVERNED_MYSQL_COLLATION_POLICY.md` still states 211 governed columns of 308** while both the
   offline audit and this lab verification report **212**. Stale text, not a defect; still uncorrected.

---

## 8. Non-claims and boundaries

- **No production access.** No production env file sourced, no production connection opened, no
  production verifier run, no production service, network, or configuration changed.
- **No production write, migration, `stamp`, `UPDATE`, `DELETE`, manual SQL, or cleanup.**
- **No `peak_lab_scenario`**, no scenario table, and **no measured row** — verified as 0 application
  rows across all 18 controlled tables.
- **No writer was invoked** and **no record was created through any Peak writer** — no Client,
  Engagement, intake note, source ingestion, evidence reference, review record, review bundle, report
  draft, capsule, client-facing output, or AgentNet publication record.
- **No migration `015`**, and no change to the application schema in the repository.
- **No repository infrastructure added** — no operator, harness, schema, writer, model, migration, or
  allowlist. **Docs only.**
- **No publication authority** — no client-facing report, final-report, capsule, or AgentNet resolver
  publication authority was created or granted. The AgentNet resolver gate stays shut.
- **No real client data and no pseudo-client data.** No fixture, example, or sample packet was created
  or committed.
- **No provider name, hostname, service URI, DSN, username beyond the three approved generic
  credential names, password, token, certificate, price, or env file content** appears in any tracked
  file.

---

## 9. Posture after Phase 83

- **The repository is unchanged apart from documentation.** Repo head stays
  `014_engagement_classification`, 14 migrations, 18 tables, 12 writers.
- **The lab exists, is at parity, and is empty.** Head `014_engagement_classification`, 18 controlled
  tables plus `alembic_version`, `InnoDB`/`utf8mb4`, 212 governed columns deterministic, 11
  idempotency boundaries safe, 0 application rows.
- **No standing production write enablement.** The Phase 51 gate still reports
  `safe_to_write_production_now=false`.
- **R8 authority precedence remains unconfirmed and R8 remains non-authoritative.** The Phase 80
  closure stands exactly as recorded. **A lab does not reopen it**, and measured lab values, when they
  exist, will be **lab-scenario values, not client evidence.**
- **The reviewed Phase 79 source remains source-only, not evidence.**
- **R1 remains provisional**, and the location finding stays **data-readiness and reliability only,
  never inventory accuracy.**
- **The R5 WMS scope clarification remains a reviewed scope-blocker enumeration only**; R5 WMS scope
  is unresolved and the **Phase 64 R5 export remains uncollected.**
- **R3–R7 remain deferred**, count/variance **conditionally required / scope-dependent.**
- **The Phase 74 outline is unmodified** and `fnd_000` remains `blocked_no_review_support`.
- **Report finalization, client-facing output, capsule publication, and AgentNet resolver publication
  remain unauthorized.**

## 10. What Phase 84 may do, with separate approval

**Nothing below is authorized by Phase 83.**

- Create `peak_lab_scenario` and seed the simulated source-system measurement data described in
  Phase 81 §7. Seeding is a **migration-credential** operation — never runtime, which cannot delete
  what it writes.
- Create a lab engagement anchor and durable measured Peak records through **existing, unchanged
  writers**, in the lab only.
- Add lab validation and measurement tests.

Two constraints carry forward unchanged. **The writer-enablement decision gate is environment-blind
and hardcodes every authorization to `false`**, so authorizing lab writes is a deliberate source edit
with its own review — it cannot be flipped by an environment variable. And **every writer is
create-only with no `UPDATE` path**, so correcting a measured scenario means a new version slug, never
a rewrite.
