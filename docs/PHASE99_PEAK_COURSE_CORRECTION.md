# Phase 99 — Peak Course Correction and Practical Delivery Reset

**Baseline.** `baee362` — *Draft Phase 98 bounded report outline*.

**Classification.** Project drift check / proportionality reset / practical delivery planning.
**Docs-only.** No database was contacted. No env file was read. No writer was invoked. No record
was created. No migration `015` was created. No schema, model, enum, writer, allowlist, gate, or
harness changed. `peak_lab` remains at **four application rows by documented state only** — this
phase did not connect to verify that.

---

## 1. Reset statement

Peak is an **inventory and warehouse operations consulting automation platform**. It is **not** a
financial transaction system, and not a medical, legal, or otherwise highly regulated sensitive
system.

**Governance is sized to operational-consulting risk.** The real risks are mishandling a client's
data, writing to production by accident, and publishing an unreviewed claim as if it were
authoritative. Those are worth real controls. An internal lab artifact about a synthetic scenario is
not, and must not be processed as though it were.

## 2. Drift assessment — yes, and it is measurable

**The objective is still right; the ratio is wrong.** Repo shape at this baseline:

| | Lines |
|---|---|
| Product code (`peak/`) | ~23,400 |
| Tests | ~39,900 |
| Docs | ~29,600 |

Roughly **3 lines of test-and-doc for every line of product**. More specifically:

- **70 of 73 test files read `docs/*.md` and assert on its prose.** The suite is substantially a
  documentation-conformance suite. This is the direct cause of Phase 96's *eight ungated harness
  freezes*: a DB-free planner change that touched no writer, model, enum, or gate broke eight
  harnesses, every one on the same doc-text check.
- **12 of 21 `tools/` scripts are single-use record creators** — one bespoke tool per phase, per row.
- **86 Make targets**, and `make validate` now takes about two minutes.
- **The ten consulting workflows are the product, and none has been run end to end.** Prompts exist
  for all seven areas and the agent registry declares all ten agents, but the only two implemented
  workflow modules — managed record writing and internal report review — are both *governance*
  workflows. Intake, discovery, interview structuring, walk-around, reporting, quick-win, and
  proposal remain unexercised.
- **Phases 95–98 produced 694 lines of documentation, zero consulting artifacts, and zero records** —
  four consecutive phases in which the deliverable was a document about the previous document.

**Credit where due: the Phase 91 correction took.** Phase 91 named the per-phase harness habit, and
Phases 92–98 added **no new harness**. That is the model for this phase: name the habit, stop it,
do not build a mechanism to enforce stopping it.

## 3. What remains important — keep these

- **No real client data in the repo.** Non-negotiable; this is the actual risk.
- **No secrets, DSNs, hosts, ports, or env values in the repo.**
- **Production writes stay explicitly gated.** The production writer enablement gate, the lab writer
  gate, the Alembic target guard, and the runtime-connectivity separation encode durable, non-obvious
  invariants that would be expensive to rediscover. They are proportional. Keep them.
- **AgentNet publication stays explicitly gated.**
- **Evidence and claim boundaries stay clear** — the thing the depth-one chain actually demonstrated.
- **Lab records are durable.** Do not casually delete them; cleanup posture is decided before a
  write, not after.

## 4. What to avoid — stop these unless a real defect appears

- **A new harness per phase.** Extend an existing test, or add nothing.
- **Asserting on documentation prose in tests.** Test behavior. A paragraph's existence is not an
  invariant; making it one is what makes DB-free changes break eight suites.
- **Migration `015` without a concrete workflow blocker.** No schema change to enable a planner path.
- **Expanding a gate because a path exists.** Gate what is actually reachable and actually risky.
- **Creating records solely to satisfy planner breadth.** A row added to turn a section green is
  manufactured evidence.
- **Turning every internal document into a compliance artifact.** Not every doc needs a non-actions
  list, a baseline table, and a leak scan.
- **Re-documenting unchanged access posture or unchanged row counts.** If nothing changed, say
  nothing.
- **One-off tools.** A twelfth single-use record creator is a smell, not a deliverable.
- **Treating Peak like a payments, medical, or legal compliance system.**

## 5. Practical delivery bias

- Prefer **human-readable internal memos and consulting outlines** over further infrastructure proofs.
- Prefer **DB-free planner and draft exercises** wherever they are sufficient — they usually are.
- Prefer **one useful consulting artifact** over another proof that the machinery is safe. The
  machinery's safety is by now well established; its usefulness is not.
- **Accept some internal imperfection** where client safety and production safety are unaffected.
- **Fix stale wording opportunistically**, when it reduces confusion — not as its own phase.
- Measure a phase by whether **a Peak consultant could use what it produced**.

## 6. Phase 100 recommendation

**Refine Phase 98 into a human-readable internal memo a Peak consultant could actually use.**

- DB-free and record-free.
- Prose a consultant reads, not a governance artifact: what was measured, what it means, what it
  does not mean, what to do next.
- Carry the one finding and the presence-vs-sufficiency caveat in plain language.
- **Do not add breadth** unless the memo cannot be useful without it.
- No migration `015`. No new harness. No DB write. No new gate.

**After Phase 100,** the highest-value direction is exercising one real consulting workflow —
intake or discovery — through the existing prompts and mock executor to produce a consulting
artifact. That is the product. The governance layer is ready for it and has been for some time.

## 7. Baseline at the end of this phase

| Property | Value |
|---|---|
| Alembic head | `014_engagement_classification` |
| Migrations / migration 015 | 14 / does not exist |
| Controlled Peak tables / writers | 18 / 12 |
| Production write enablement | None standing; gate reports false |
| `peak_lab` application rows | **4** — by documented state only; not verified in this phase |
| `peak_lab_scenario` | Not read, not written |
| New harnesses added | None |
