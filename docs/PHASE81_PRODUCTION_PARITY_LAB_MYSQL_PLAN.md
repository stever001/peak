# Phase 81 — the Production-Parity Lab MySQL Plan

**Baseline:** `9ee0047` — "Add Phase 80 R8 measurement feasibility review closure". Branch `main`,
clean tree at baseline, Alembic head `014_engagement_classification`, 14 migrations, 18 tables, 12
writers.

**Phase 81 is planning only.** No production access occurred. No database, service, schema, user, or
credential was created. No writer was invoked and no record of any kind was created. No migration was
run. No new infrastructure was added. **No environment file was sourced and no connection was
opened** — the runtime connectivity gate was run in `--self-test` mode only. Head stays
`014_engagement_classification` with 14 migrations, 18 tables, and 12 writers, and **production
remains untouched**.

This phase defines what Phase 82 should build. **Phase 81 does not build it.**

---

## 1. Why a lab environment, and what it is not

**The artifact-only internal_test chain has reached its measurement limit.** Phase 79 registered, and
Phase 80 reviewed and closed, the finding that this scenario cannot produce the two things R8
confirmation requires — **measured quantitative findings** and an **evidence reliability rating** —
because every collected source is description-level and there is no live system to measure. Deriving
quantities from descriptions would be fabrication, not derivation; and a reliability rating rates a
measurement basis, of which none exists.

Local validation currently runs on **SQLite**, which the scaffold has always described as a fast
structural smoke path and **not** the production-readiness proof path. The gap is not theoretical:
`make mysql-collation-audit` reports `MODEL_POLICY_SATISFIED_PRODUCTION_UNVERIFIED` — the model
satisfies the governed-collation policy, and nothing has verified that a **server built from these
migrations** actually delivers it. Phase 46 is the cautionary case: a fresh production bootstrap
failed partway at migration `008` on the `alembic_version` `VARCHAR(32)` issue and needed manual
recovery. That failure mode has never been rehearsed anywhere it is safe to rehearse it.

**What the lab is:** a production-parity MySQL environment for **measured development and
validation** — somewhere migrations can be applied from empty, schema and collation can be verified
against a real server, the three-role credential model can be exercised end to end, and durable
internal measured scenarios can exist.

**What the lab is not.** It is not production, not a client environment, not a public or resolver
environment, and not a publication environment. It carries **no client-facing report authority, no
final-report authority, no capsule publication authority, and no AgentNet resolver publication
authority**. It is not a release-promotion stage — nothing deploys through it.

**It does not reopen the Phase 80 closure.** Measured lab values are **lab-scenario values, not
client evidence**. They cannot make R8 authoritative in the production record, cannot upgrade
`fnd_000`, and there is still no closure or `UPDATE` verb in any writer's vocabulary. Phase 80's
closure was scenario-specific and remains exactly as recorded.

---

## 2. Recommended topology

**A separate managed MySQL service, provisioned independently of production.**

| option | verdict |
| --- | --- |
| **(a) separate managed MySQL service** | **Recommended.** Distinct host, distinct credential namespace, highest parity (same provider defaults, version family, `sql_mode`, TLS, online-DDL and grant behaviour), bounded blast radius. A wrong DSN cannot reach production. Cost: a recurring bill — the only option with one. |
| (b) second database/schema inside the production service | **Rejected.** Same host, same admin plane, same connection endpoint and connection limits. One mistyped DSN or unqualified `alembic upgrade head` reaches production — which holds real internal_test records that runtime cannot delete. The persistence rubric already requires environments to be **distinct managed databases**, and production is never a smoke-test target. |
| (c) local MySQL install | Not recommended as the durable lab. Parity drifts silently on `sql_mode`, default collation, and row format, and durable records would live on a laptop. |
| (d) ephemeral local MySQL 8 container | **Recommended as an optional rehearsal tier only** — see below. Not the durable lab: it holds no durable measured scenario. |

**Optional rehearsal tier.** A throwaway MySQL 8 container is the cheapest way to rehearse the
fresh-bootstrap path that broke in Phase 46, before spending a managed provisioning attempt on it.
This is consistent with existing practice — Phase 80 rehearsed idempotency off-production against
temporary SQLite before writing. **If used, every container artifact lives outside the repository:**
`tests/validate_phase49_runtime_database_url_separation.py` asserts that `docker-compose.yml`,
`Procfile`, `deploy.yaml`, and `runtime.env` **do not exist** at repo root, so committing a compose
file there would fail `make validate`. The rehearsal tier is optional and may be skipped.

The repository stays **provider-agnostic**: it names no cloud vendor today, and this plan adds none.
Provider selection is an operational choice recorded out-of-band, not in the repo.

---

## 3. Naming

**Environment label: `peak_lab`.** Purpose: *production-parity measured-development environment*.

**"staging" is deliberately rejected.** The word is already load-bearing and means the opposite of
what this environment is. `PEAK_MANAGED_MYSQL_STAGING_DSN`, `make mysql-parity-staging`, and
`PEAK_MANAGED_MYSQL_DISPOSABLE` define a staging target as an **empty, disposable, throwaway schema
holding no data ever** — the parity gate *refuses* (exit 2) a configured DSN that is not marked
disposable. The lab is durable and holds measured rows by design. Naming it "staging" would let
someone later point `PEAK_MANAGED_MYSQL_STAGING_DSN` at it and silently break the disposability
contract. ("Staging" is also warehouse-location vocabulary in the R9/R10 chain.)

`peak_lab`, `peak_lab_scenario`, and the `PEAK_LAB_*` env namespace have **zero collisions** in the
repository today.

The lab is **not** the environment named by `--env test` either: `test` collides with the
`internal_test` engagement classification, which is a different axis entirely.

---

## 4. Credentials and secrets

**Three lab credentials, mirroring the production role split, none of them reused from production.**

| role | lab user | privileges | mirrors |
| --- | --- | --- | --- |
| migration | `peak_lab_migrate` | DDL on `peak_lab` only | `PEAK_DATABASE_URL` |
| runtime | `peak_lab_runtime` | **`SELECT` + `INSERT` only** on `peak_lab` | `PEAK_RUNTIME_DATABASE_URL` |
| read-only verifier | `peak_lab_readonly` | `SELECT` only | `PEAK_PRODUCTION_DB_URL` |

**The runtime credential must be provisioned to exactly `SELECT` + `INSERT`** — no `UPDATE`, no
`DELETE`, no DDL, no global privilege, no `GRANT OPTION`. This is not a formality: the connectivity
gate's `REQUIRED_GRANTS` / `FORBIDDEN_GRANTS` are fixed, so a lab runtime user carrying `DELETE` for
convenience **fails the gate**. Provisioning to the same posture keeps the gate reusable unmodified
and preserves its meaning. **Reset and teardown use the migration credential**, separately and
deliberately — never runtime.

**Durable env var names, stored out-of-repo:** `PEAK_LAB_MIGRATION_URL`, `PEAK_LAB_RUNTIME_URL`,
`PEAK_LAB_READONLY_URL`. These are the names the lab env file uses. Because `alembic/env.py` reads
**only** `PEAK_DATABASE_URL` and has no `-x`, no `--name`, and no section switching, each lab value is
exported into its role variable **transiently, one at a time, in a shell that has never held a
production value**. See §12 for the residual risk this leaves.

**Secrets stay outside the repository and are never printed.** `.env` and `.env.*` are gitignored;
only `.env.example` (placeholders) is tracked. Phase 82 may add **documented variable names and an
out-of-repo template**, never a value. Every gate must continue to report `secrets_printed=false`,
and failures continue to be reported by exception **type** only, because driver messages embed the
connection string.

---

## 5. Hard safety boundaries

- **No production credential is reused**, and no lab value is ever written into a production env file.
- **No production data is copied.** No snapshot, dump, or restore into the lab, in either direction.
- **No real client data**, ever — not in the lab, not in examples, fixtures, demos, training, or
  tests. A lab is a training/test use, so this is barred by construction.
- **No pseudo-client data is committed to the repository.** Simulated records may live in the lab
  database; they may not live in Git.
- **No fixtures, examples, or sample packets are committed.** `make validate` already fails if
  forbidden stored-artifact paths reappear.
- **No broad grants.** Three users, three privilege sets, never interchangeable, never pointed at the
  same database user.
- **The runtime credential gets no `UPDATE` and no `DELETE`** unless separately justified and
  approved. Anything the lab runtime writes is therefore **permanent** — scenario data must be
  designed durable from the start, not written and cleaned up.
- **No public resolver or AgentNet publication authority.** The AgentNet resolver gate stays **shut
  rather than relaxed**, precisely because the public resolver is live.
- **No client-facing report authority, no final-report authority, no capsule publication authority.**
- **No lab-scoped scope value may be mixed with live client or engagement scope** — the standing
  `fixture_test` rule applies unchanged.
- **The lab does not reuse the production `internal_test_001` / `99999` / `internal_peak_only`
  anchor.** That anchor is a **production row**. The lab gets its own anchor in its own reserved
  namespace.
- **No `publication_allowed`, `capsule_candidate_ready`, `client_facing_approved`, `authoritative`,
  or `financial_verified` is set true in the lab.** Doing so would establish a precedent for the
  production writer.

---

## 6. Schema and migration posture

- **The lab controlled schema starts at Alembic head `014_engagement_classification`**, reached by
  applying the existing migrations to an **empty** schema.
- **Migration count must match production: 14.** **Table count expected: 18**, plus
  `alembic_version`.
- **No migration `015` in Phase 81**, and none in Phase 82. The lab must never become a route by
  which an untested `015` reaches production.
- **Phase 82 applies existing migrations to the lab. It does not alter production.**
- **Parity is `InnoDB` + `utf8mb4`, with `utf8mb4_bin` pinned on governed columns** — identity,
  scope, idempotency keys, and fingerprints — the determinism the
  `UNIQUE (owner_id, client_id, engagement_id, idempotency_key)` boundary depends on across 11
  tables. MySQL 8's `utf8mb4` default is case-insensitive, so determinism comes from **per-column
  pinning only**, exactly as in production.
- **No MySQL major version is pinned by the repo**, deliberately; `utf8mb4_bin` was chosen partly to
  work across 5.7 and 8.x. The lab should nonetheless match production's version **family**, since
  matching it is the point.
- `alembic/env.py` runs the Phase 47 `alembic_version` widening preflight automatically in online
  mode, so a fresh lab bootstrap does not hit the Phase 46 failure.
- **Lab verification compares head, table count, charset, and collation against known expectations.**
  `tools/production_mysql_collation_verify.py` already pins `EXPECTED_ALEMBIC_HEAD =
  "014_engagement_classification"` and `EXPECTED_TABLE_COUNT = 18`, so it works against the lab
  **unmodified** via the lab read-only credential.
- **Production remains untouched**, and no production verifier run is part of this posture.

---

## 7. Measurement scenarios — and where that data actually lives

**The controlled 18-table schema has no table that holds measured operational data.** It holds
governance records *about* sources and evidence: `source_ingestion_records` registers an export's
**metadata**, never its rows. So a lab at head `014` gives parity and a place to exercise writers,
but does **not** by itself provide a measured R1/R2 dataset.

**The resolution is architectural, and it is the right shape anyway: the measured scenario is a
simulated source system.** R1 and R2 are exports *from* a system of record — they are not Peak
records. So the lab environment holds **two separate schemas**:

| schema | contents | Alembic-managed | in production |
| --- | --- | --- | --- |
| `peak_lab` | the controlled Peak schema — exactly 14 migrations, 18 tables, head `014` | **yes** | mirrors production |
| `peak_lab_scenario` | the simulated source system: measured R1/R2/location rows | **no — never** | **never** |

`peak_lab_scenario` is **lab-only, not referenced by any Alembic revision, and never migrated into
production.** This keeps the controlled schema byte-identical to production at 14 migrations and 18
tables, and puts measured data where it conceptually belongs — behind a source-system boundary that
Peak reads from exactly as it would read a client ERP.

**Minimum measured scenario, to replace the artifact-only limitation:**

*In `peak_lab_scenario` (the simulated source system):*
1. **A measured item master (R2-equivalent)** — item identifier, description, unit of measure, status
   flag, attribute-completeness indicators, owning system reference. R2 is the interpretive key;
   without it, R1-derived evidence would overstate its own reliability.
2. **Measured on-hand inventory at a declared grain (R1-equivalent)** — item identifier, location
   identifier, quantity on hand, unit of measure, `as_of_timestamp`, source system reference.
   **Location must be a real grain key, not a free string.**
3. **A location/bin model with effective dating** — hierarchy levels with present/absent markers, an
   explicit field-to-level mapping for R1's location fields, a declared semantic for
   `location_identifier`, representation of hold/damaged/quarantine/staging/in-transit/virtual
   inventory, and an **effective date** so R1's `as_of_timestamp` has something to align to. This is
   the highest-leverage item: it is what the Phase 71 readiness thresholds were unable to assess.
4. **Dual-system location identifiers** for an ERP-class and a WMS-class source, with deliberate
   alignment *and* deliberate divergence, so "align or diverge, on which levels and by what rule"
   becomes measurable — and so "does a WMS exist in this scenario" is answerable at all.
5. **A shared item-identifier domain across R1 and R2 with deliberate normalization mismatches**, so
   identifier alignment is measured rather than assumed.

*In `peak_lab` (the controlled schema, through unchanged writers):*
6. **One lab engagement anchor** — `engagement_category=internal_test`, `real_client_data=false`,
   `client_accessible=false`, `capsule_publication_authorized=false`, its own reserved lab
   `client_id` namespace, `authorization_scope=internal_peak_only`. Written only through the Phase 54
   anchor writer. **Not** the production `internal_test_001` anchor.
7. **`source_system_references`** — one ERP-class, one WMS-class. This is what makes "system of
   record" a **queryable fact** rather than an artifact assertion, and is the structural prerequisite
   for the precedence direction R8 states.
8. **`source_ingestion_records`, `review_records`, and — for the first time —
   `evidence_references`**, whose `reliability` can now be rated **against a measurement basis** and
   whose `evidence_status` can reach `verified` by checking against data. Those are precisely the two
   things Phase 79 recorded as impossible.

This set supports measured quantitative findings, an evidence reliability rating,
source-of-record / authority-precedence confirmation practice, and location-dimension readiness
assessment practice — as DB-backed measured data rather than artifact-only description.

**Measured lab data must be distinguishable from real client data at the record level**, not by
convention: the classification columns are the mechanism, the reserved `client_id` is only a visible
marker, and `packet_source_type` needs a value that distinguishes **measured lab data** from the
existing description-level `internal_test_export` artifacts — otherwise the measurement gap silently
reopens.

**What not to model yet:**

- **Do not model a full inventory business.** This is a measurement scenario, not an ERP.
- **Do not build a financial transaction system**, and do not populate `financial_impact_estimates`.
- **Do not add production publication or AgentNet resolver flow.**
- **Do not add client-facing report generation** unless separately approved.
- **Do not pull R4 count/variance into default scope.** It widens the work into inventory accuracy
  and quantity correctness, which this chain does not claim and is not authorized to claim.
- **Do not treat a lab `review_bundle_record` as a way to clear `fnd_000`.** That block is a **Phase
  36 planner vocabulary limitation**, not a measurement gap, and a lab does not fix it.

---

## 8. What Phase 82 should build

**Environment creation, migration, and verification only.** Ordered:

1. *(optional)* Rehearse the bootstrap against a throwaway MySQL 8 container, **entirely outside the
   repository** — apply the 14 migrations to an empty schema, confirm head `014` and 18 tables.
2. Provision the managed `peak_lab` MySQL service, separate from production. Record the provider and
   version family out-of-band.
3. Create the `peak_lab` database/schema. **Do not create `peak_lab_scenario` yet.**
4. Create the three lab credentials with the §4 privilege split. Runtime is **exactly**
   `SELECT` + `INSERT`.
5. Write the out-of-repo lab env template — **documented variable names only, no values.** Confirm
   nothing lands in the repo and nothing is printed.
6. Apply the existing 14 migrations to the empty `peak_lab` schema. **No `015`.**
7. Verify: head is `014_engagement_classification`, 18 base tables plus `alembic_version`, charset
   `utf8mb4`, engine `InnoDB`, governed columns `utf8mb4_bin`. Run the read-only verifier via
   `PEAK_LAB_READONLY_URL`, and the runtime connectivity gate via `PEAK_LAB_RUNTIME_URL` — the gate
   should report `required_grants_present=true`, `excess_grants_present=false`.
8. Document the resulting lab environment state in a Phase 82 doc.

**Phase 82 creates no measured data rows, invokes no writer, and creates no Peak record** unless that
is separately and explicitly approved. **Production is not touched at any step.**

## 9. What Phase 83 may build

Separately approved, and not before Phase 82 is verified:

- Create `peak_lab_scenario` and seed the §7 measured scenario. Seeding is a **migration-credential**
  operation (or an approved lab-only seed path) — never runtime, which cannot delete what it writes.
- Create the lab engagement anchor and the durable measured Peak records through **existing,
  unchanged writers**.
- Add lab validation and measurement tests.

Two governance questions belong to Phase 83, not 82: **the writer-enablement decision gate is
environment-blind and hardcodes every authorization to `false`**, so authorizing lab writes is a
deliberate source edit with its own review — it cannot and must not be flipped by an env var. And
**every writer is create-only with no `UPDATE` path**, so correcting a measured scenario means a new
version slug, never a rewrite.

---

## 10. Non-claims and boundaries

- **No production access of any kind.** No env file sourced, no connection opened, no cloud console
  or API contacted, no production verifier run. The runtime connectivity gate was run in
  `--self-test` mode only, reporting `self_test_mode_no_database_contacted`.
- **No database, service, schema, user, or credential was created**, in any environment.
- **No writer was invoked and no record was created** — no production row, no lab row, no
  `review_records`, source ingestion, evidence reference, review bundle, report draft, Client,
  Engagement, intake note, capsule, client-facing output, or AgentNet publication record.
- **No migration was run**, and no `alembic stamp`, `UPDATE`, `DELETE`, manual SQL, or cleanup was
  issued. No application table was scanned, counted, or probed.
- **No new infrastructure** — no migration, model, writer, allowlist pair, schema, table, operator,
  or harness. **Docs only.**
- **No branch, worktree, or commit** was created by this phase's planning work.
- **No artifact body, fixture, example, or sample packet** was read, printed, committed, or stored.
- **No secrets or environment values** printed or committed.
- **No real client data.** `internal_test` only.
- **This plan authorizes nothing.** It is a plan; Phase 82 provisioning requires its own approval.

## 11. Posture after Phase 81

- **Nothing in the database changed.** Head stays `014_engagement_classification`, 14 migrations, 18
  tables, 12 writers.
- **R8 authority precedence remains unconfirmed and R8 remains non-authoritative.** The Phase 80
  closure stands exactly as recorded — scenario-specific, not a refutation, not a state change, and
  **no R8 row was modified**. Real client data could still confirm R8 later; so, in a different way,
  could a measured lab scenario — neither changes what the production record says today.
- **The reviewed Phase 79 source remains source-only, not evidence.**
- **R1 remains provisional**, and the location finding stays **data-readiness and reliability only,
  never inventory accuracy.**
- **The R5 WMS scope clarification remains a reviewed scope-blocker enumeration only**; R5 WMS scope
  itself remains unresolved, and the **Phase 64 R5 receiving/putaway export remains uncollected.**
- **R3–R7 remain deferred**, with the count/variance request **conditionally required /
  scope-dependent.**
- **The Phase 74 outline is unmodified** and `fnd_000` remains `blocked_no_review_support`.
- **Report finalization, client-facing output, capsule publication, and AgentNet resolver publication
  remain unauthorized.**

---

## 12. Warnings and decisions needing review

1. **`alembic/env.py` reads only `PEAK_DATABASE_URL`** — no second target, no `-x`, no section
   switching. Targeting the lab means putting the lab DSN in the **production-named variable**, so
   the variable name no longer tells you which environment it points at. Phase 82's control is
   procedural: a dedicated lab shell that has never held a production value, one role variable
   exported at a time. *Mitigating, but not a control:* production is already at head `014`, so a
   misdirected `alembic upgrade head` is currently a no-op — **which stops being true the moment a
   `015` exists.** A lab-aware target resolver is a candidate for Phase 83+ and needs its own
   approval. **This is the largest residual risk in the plan.**
2. **`make mysql-parity-staging` cannot verify a live lab.** `run_staging()` accepts the DSN and
   disposable marker and then emits `[hold]` and returns 0 **without connecting** — the live parity
   run was never implemented. Phase 82 should therefore verify with
   `tools/production_mysql_collation_verify.py` pointed at the lab read-only credential, which works
   unmodified. Implementing the live parity path is a separate, later decision.
3. **`make mysql-parity-staging` reads `PEAK_MANAGED_MYSQL_TEST_DSN`, not the staging one** — the
   recipe passes no `--env`, and `--env` defaults to `test`. Worth knowing before anyone assumes the
   staging variable is wired.
4. **Tool output labels say "production" when pointed at a lab** (`production_connection_made`,
   `production_connectivity_result`). Cosmetic today; misleading if a lab run's output ever becomes
   an audit artifact. Renaming is a later, separate change — **not** Phase 82.
5. **Documentation currency: governed-column counts.** `GOVERNED_MYSQL_COLLATION_POLICY.md` and
   migration `013` state **211 governed columns of 308**; `make mysql-collation-audit` now reports
   **212 of 309**. The difference is migration `014`'s `engagement_category`, which is correctly
   pinned `utf8mb4_bin` on MySQL. Not a defect — the Phase 42/44 figures simply predate `014` and
   read as current. Worth annotating.
6. **Cost.** A separate managed service is the only recommended option carrying a recurring bill.
   That is a deliberate trade for blast-radius isolation, and it is the user's call.
7. **`docker-compose.yml` at repo root fails `make validate`.** Any container rehearsal must keep
   every artifact outside the repository.
8. **Adding `--env lab` to the managed-MySQL tools** would touch `choices` and `ENV_DSN_VARS` in two
   files. Phase 82 does not need it — the read-only verifier and connectivity gate reach the lab by
   role variable alone. Deferred.
