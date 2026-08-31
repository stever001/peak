# Phase 89 — The Lab-Only Writer Enablement Decision Gate

Phase 89 adds a deliberate, test-covered **lab-only** writer-enablement decision path, so a future
phase can rehearse the existing create-only Peak writers against the controlled lab schema under
explicit constraints. Repo baseline at entry: `8307793`, Alembic head `014_engagement_classification`,
14 migrations, 18 controlled tables, 12 writers.

**Production writer enablement remains false.** **No writer was invoked**, **no record was created**,
**no lab or scenario database was contacted**, **no production access occurred**, **no live Alembic
migration ran**, and **no migration `015` was created**. Every URL in the new module and its tests
is synthetic and unroutable.

**Lab write rehearsal is still not approved.** A positive decision from this gate says the target
and scope are right. It is not permission to write. That remains a separately approved phase.

---

## 1. The problem this closes

Phase 88 proved the seeded lab scenario can be measured read-only. The natural next step is to turn
those measurements into Peak records *in the lab*. The Phase 51 gate cannot express that: it is
**environment-blind** and hardcodes every authorization to `False`. That is exactly right for
production and useless for a lab rehearsal — it left lab enablement as an undifferentiated source
edit, where the change that enables a lab write and the change that would enable a production write
look the same.

Phase 89 separates the two axes. Lab enablement becomes a decision the repository can express,
check, and test; production enablement stays where it was.

---

## 2. What was added

| file | role |
| --- | --- |
| `tools/lab_writer_enablement_decision_gate.py` | the lab decision, as a pure function plus an offline CLI |
| `tests/validate_phase89_lab_writer_enablement_gate.py` | 123 checks over the gate and the production gate |
| `Makefile` | `validate-phase89` (wired into `make validate`) and `lab-writer-enablement-decision-gate` |
| `tests/validate_phase72_…py` | one line moved inside an existing gate — see §11.6 |

**The production gate was not edited.** `tools/production_writer_enablement_decision_gate.py` is
**byte-identical** to its previous commit, and the harness asserts that as a git-backed check rather
than inferring it from a passing run. The new module does not import, wrap, or extend it.

**The Phase 84 target guard is reused, not reimplemented.** The lab gate loads
`alembic/migration_target_guard.py` by path for its user/schema classification primitives. "What
counts as production-marked, or as the provider's default schema" must have exactly one definition
in this repository; two copies would drift, and the copy that drifted would be the one guarding a
write.

---

## 3. The environment contract

Four variables, none of them reused from another purpose:

| variable | required value | meaning |
| --- | --- | --- |
| `PEAK_WRITER_TARGET` | `lab` | names the target environment |
| `PEAK_LAB_WRITER_ENABLEMENT_CONFIRM` | exactly `1` | confirms lab writer enablement |
| `PEAK_LAB_WRITER_TARGET_URL` | a lab DSN | parsed for **shape only**; never connected to |
| `PEAK_LAB_WRITER_TARGETS` | `table/action,…` | the writer targets being requested |

The confirmation accepts **only** the exact string `1`. `true`, `yes`, `1 ` and the empty string all
read as unconfirmed, so a half-set or accidentally-inherited variable **fails closed**.

**Nine variables are explicitly refused as authorizers**, each because it already means something
else and one confirmation must never grant two authorities:

| refused | why |
| --- | --- |
| `PEAK_LAB_CONFIRM` | Phase 82 published it as a reserved no-op; a gate must not share a name with something documented as doing nothing |
| `PEAK_ALEMBIC_TARGET`, `PEAK_LAB_MIGRATION_CONFIRM`, `PEAK_PRODUCTION_MIGRATION_CONFIRM` | Phase 84 migration authority — migrating the lab and writing rows to it are different powers |
| `PEAK_LAB_SCENARIO_RO_URL`, `PEAK_LAB_SCENARIO_LOADER_URL` | Phase 85 scenario access; neither is a Peak writer credential |
| `PEAK_PRODUCTION_DB_URL`, `PEAK_RUNTIME_DATABASE_URL`, `PEAK_DATABASE_URL` | production-named variables must never authorize a lab write |

Each of the nine is tested individually: setting it to `1` in place of the real confirmation denies
with `lab_confirmation_absent_or_not_exact_value`.

This is a direct response to the standing Phase 82 §3 seam that Phase 88 hit — where a
production-named variable pointed at the lab and the variable name could not say which environment
it meant. **The new variables name their own purpose honestly.**

---

## 4. What a positive lab decision requires

All of the following, in order. Any one failing denies with a stable, value-free reason code:

1. `PEAK_WRITER_TARGET` is exactly `lab` — a `production` target denies immediately, with its own
   reason code, whatever else is set.
2. The lab confirmation is exactly `1`.
3. A target URL is present and its dialect is MySQL/MariaDB.
4. The schema is **not** `peak_lab_scenario` — the scenario schema holds source-system simulation,
   not controlled Peak tables, and is never a writer target.
5. The schema is not the provider's default (`defaultdb` and friends) — a DSN aimed there has lost
   its schema segment.
6. The schema is not production-marked, and is **exactly** `peak_lab`.
7. The user is not production-marked, and is an **approved lab writer role**. Only
   `peak_lab_runtime` qualifies: it holds `SELECT` + `INSERT` and no `DELETE`, which is the right
   shape for create-only writers. The lab **migration** role and the scenario read-only role are
   both refused.
8. At least one writer target is requested, and **every** requested target is inside the enableable
   set.

---

## 5. Writer targets are scoped, not blanket-enabled

Three pairs are lab-enableable:

| table | action |
| --- | --- |
| `source_ingestion_records` | `create_source_ingestion_record` |
| `evidence_references` | `create_draft` |
| `review_records` | `create_review_record` |

Every one is a **create** action; no `update_*` or `mark_superseded` action is enableable, matching
the create-only writer discipline. The set is a **strict subset** of the controlled allowlist —
appearing on `peak/persistence/allowlist.py` means a writer may *plan* an action, which is a weaker
statement than "a lab rehearsal may request it here."

**The engagement authorization anchor pair is excluded on purpose** and named in a separate
never-enableable set, so the exclusion is testable rather than merely implied by absence. It creates
identity/root records through the separate single-pair anchor path; enabling it belongs to its own
approval rather than riding in beside the data-record writers. `clients/create_draft` is listed
there too, since `clients` is never writable.

**A mixed request fails whole.** Asking for one enableable target and one excluded target denies the
entire request rather than granting the acceptable half.

---

## 6. Production cannot be reached from this path

Every production field is `False` on **every** path the module can take — there is no branch,
variable, or argument that makes one true, and the harness asserts the source contains no assignment
that could:

| field | value |
| --- | --- |
| `production_write_authorized` | always `false` |
| `safe_to_write_production_now` | always `false` |
| `production_writer_enablement_authorized` | always `false` |
| `database_contacted`, `sql_issued`, `writer_invoked`, `records_created` | always `false` |
| `credential_file_read`, `secrets_printed` | always `false` |
| `lab_write_requires_separate_phase_approval` | always `true` |

Verified from the other direction too: running the **production** gate with every lab variable set
produces output **byte-identical** to running it with none.

---

## 7. Output is value-free

The DSN is parsed into a username and a schema name, each classified into a fixed label; host, port,
password and query parameters are parsed past and discarded. A decision carries target labels,
booleans, reason codes, user/schema classes and writer-target names — and the harness asserts that a
decision built from a URL containing a password, host, port, certificate path and query parameter
contains **none** of them, nor the scheme, nor even a `://`. That check is guarded against vacuity:
the same case must also authorize.

---

## 8. Testing

**123 checks in `validate_phase89_lab_writer_enablement_gate.py`**, wired into `make validate`, plus
**31 assertions** in the module's own `--self-test`, reachable as
`make lab-writer-enablement-decision-gate`. Both are offline and use synthetic values only.

Coverage: baseline unchanged; production gate byte-identical and still denying, including under lab
variables; no database, credential, or writer code path in the new module; the environment contract
and every refused authorizer; the enableable set against the real allowlist; all fifteen deny
branches; the authorize branch; lab-never-implies-production across four environments; and
value-free output.

---

## 9. What this does not do

- **It invokes no writer and creates no record.** Phase 89 is a decision path only.
- **It does not authorize a lab write.** A positive decision is a statement about target and scope.
- **It does not contact any database** — not production, not the lab, not the scenario schema.
- **It grants production nothing.** Production enablement remains exactly where Phase 51 left it.
- **It does not enable all writers.** Three create pairs; everything else denies.

---

## 10. What a later phase may do, with separate approval

**Nothing below is authorized by Phase 89.**

A future phase may propose a lab writer rehearsal. Before any writer runs it must name, in advance:

- **which writer**, and which table/action pair
- **which records**, and the expected record count
- **which lab source measurements** the records derive from
- **the authorization scope** carried on each record
- **the idempotency keys**, given every writer is create-only with no `UPDATE` path
- **the expected receipts**, and the **post-write verification** that will confirm them
- **the cleanup posture**, decided before the write and not after

Two constraints carry forward unchanged: **writers are create-only**, so a correction means a new
version slug rather than a rewrite; and **production write enablement remains a separate,
unapproved decision** that this gate does not touch.

---

## 11. Warnings and decisions needing review

1. **The engagement authorization anchor is excluded, which may block the rehearsal.** A lab
   rehearsal that needs an engagement anchor to hang records from will find that pair refused. That
   is deliberate — it forces the anchor decision to be made explicitly — but a future phase may need
   to request it, and that request should be its own reviewed change to `LAB_ENABLEABLE_WRITER_TARGETS`.

2. **`peak_lab_runtime` is the only approved lab writer role.** Its `SELECT` + `INSERT` grant matches
   create-only writers exactly and gives no removal path — so, as in production, a lab record written
   by runtime **cannot be removed by runtime**. The cleanup posture must be decided before the first
   lab write, not after.

3. **The gate checks DSN *shape*, not reachability.** It cannot know whether a well-formed
   `peak_lab` URL points at the real lab; it only refuses URLs that are clearly something else.
   The credential boundary remains the enforcing control.

4. **A positive decision is easy to misread as approval.** The field name is
   `lab_write_authorized`, and the CLI prints an explicit line saying it is a decision about target
   and scope rather than approval to write. Future readers should treat the phase approval, not this
   field, as the authority.

5. **One unrelated harness needed a one-line fix, and it was not in this phase's scope.**
   Phase 72's harness carried an authoring-time scope guard — "no prior-phase operator utility was
   modified" — that sat **outside** the gate the comment three lines above it describes. Because it
   diffs from Phase 72's baseline to the working tree, it judged every later phase's `tools/` file
   against Phase 72's allowlist, so **adding any new operator utility failed `make validate`
   permanently**. Phase 89's new module tripped it.

   This is the same defect class Phase 86 swept: an authoring-time guard that should have gone quiet
   once its phase landed. The adjacent guard in the same function had already been gated when Phase
   84 tripped it; this one was missed. The fix **moves the check inside the existing gate** — the
   assertion, its label, and its allowlist are unchanged, and it still runs while Phase 72 is being
   authored, which is the only time it means anything. It was not widened, weakened, or removed.

   Flagged because it is a change to a harness this phase otherwise had no business touching. The
   alternative was to leave `make validate` red.

6. **`PEAK_WRITER_TARGET` is a new general-purpose name.** It currently accepts `lab` and refuses
   everything else including `production`. If a later phase gives it a production meaning, the
   refusal in this module must be revisited deliberately rather than relaxed in passing.

---

## 12. Superseded in part by Phase 90

[`PHASE90_LAB_ENGAGEMENT_ANCHOR_BOOTSTRAP.md`](PHASE90_LAB_ENGAGEMENT_ANCHOR_BOOTSTRAP.md) acted on
§11.1 above — the warning that the anchor exclusion would block the first rehearsal. It did.

**What changed.** The engagement authorization anchor pair moved out of `NEVER_LAB_ENABLEABLE` into
its own **bootstrap branch**, reachable only with a second confirmation
(`PEAK_LAB_ENGAGEMENT_ANCHOR_BOOTSTRAP_CONFIRM=1`), every Phase 89 check still applying, and the
anchor as the **only** requested target.

**What did not change.** The anchor is still **absent** from `LAB_ENABLEABLE_WRITER_TARGETS`, so it
is still not generally lab-enableable — the invariant this document's §5 was really asserting. The
three data-record pairs behave exactly as described here and need no bootstrap confirmation.
`clients/create_draft` remains the sole member of `NEVER_LAB_ENABLEABLE`. No `update_*` or `mark_*`
action is enableable. Every refused authorizer in §3 remains refused. **Production remains denied on
every path and the production gate remains byte-identical.**

The Phase 89 harness assertion that named the anchor in `NEVER_LAB_ENABLEABLE` was updated to the
durable form: **the anchor is not generally lab-enableable**.

