# Peak Project Contract

**The highest-level normative authority in the Peak repository.** Adopted in Phase 210 (baseline
`1a8477c`).

This Contract states Peak's settled product and architectural rules. Each rule gives the rule, the
principle behind it, and the authority where its implementation detail belongs. It is deliberately
short: it does **not** list fields, describe migrations, retell phase history, or restate test
invariants. Where detail is needed, it points to a specialized authority instead of growing.

---

## 1. Authority hierarchy

| Level | Authority | Role |
|---|---|---|
| 1 | **`docs/PEAK_PROJECT_CONTRACT.md`** (this document) | Highest-level normative authority: the settled rules |
| 2 | **Specialized normative authorities** — e.g. [`GOVERNANCE_STATES.md`](GOVERNANCE_STATES.md), [`STATE_TRANSITIONS.md`](STATE_TRANSITIONS.md), [`CONTROLLED_WRITE_ALLOWLIST.md`](CONTROLLED_WRITE_ALLOWLIST.md) with `peak/persistence/allowlist.py`, [`DATA_HANDLING_POLICY.md`](DATA_HANDLING_POLICY.md), [`PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md`](PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md), and the schema/migration authorities; the artifact-lifecycle and capsule-publication authorities once created (§4) | The detailed rules for one domain, consistent with this Contract |
| 3 | **Phase documents** — `docs/PHASE###_*.md`, indexed in [`PHASE_INDEX.md`](PHASE_INDEX.md) | Historical record of when and why a capability was introduced |
| 4 | **[`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md)** | Sequencing and planned work |
| 5 | **Code and tests** | Enforcement and implementation |

**Conflict rule.** If a lower-level authority conflicts with this Contract, **the Contract governs
until the conflict is deliberately resolved**, either by correcting the lower authority or by
amending the Contract (§5). Nobody resolves a conflict by quietly following the lower authority.

**Phase documents as interim detail.** Where no specialized authority exists yet, the phase
document that introduced a rule (for example Phase 117/118 for recommendation eligibility) holds its
detail until a specialized authority takes it over. It holds that detail under this Contract, not
beside it.

---

## 2. Settled rules

### C1 — Product purpose

Peak is a **consultant-facing inventory improvement platform**. It helps Peak consultants run
engagements that improve how clients count, control, value and manage inventory. It is not a
financial-transaction system.

- **Principle:** the product serves the consultant's engagement work; everything else is in support of it.
- **Authority:** [`OPERATING_MODEL.md`](OPERATING_MODEL.md).

### C2 — Canonical truth

**The operational database is canonical truth for persisted business state.** Derived documents
(assessments, reports, renderings) are computed from it and are not a second source of truth.
Neither the repository nor a generated file is a store of business state.

- **Principle:** one place holds the facts; everything else is derived from it and can be rebuilt from it.
- **Authority:** [`CONTROLLED_DATA_ARCHITECTURE.md`](CONTROLLED_DATA_ARCHITECTURE.md), [`DATABASE_SCAFFOLD.md`](DATABASE_SCAFFOLD.md); schema in `peak/db/models.py` and `alembic/versions/`.

### C3 — Least-autonomous mechanism

**Use the least autonomous mechanism that can reliably create the required business outcome.**
Prefer deterministic composition to model synthesis, and a human decision to an automated one,
wherever the simpler mechanism achieves the outcome. Add autonomy only where it is needed to get the
outcome, and keep a human gate on anything client-facing.

- **Principle:** proportionality. Autonomy is a cost to be justified, not a default.
- **Authority:** [`OPERATING_MODEL.md`](OPERATING_MODEL.md) (human-in-the-loop by default).

### C4 — Discovery is not evidence

**Consultant discovery material is distinct from governed evidence.** Discovery (interviews,
answers, observations, the North Star) is consultant working material. It never becomes reviewed
evidence or recommendation eligibility on its own; only the governed evidence and review path can
create those.

- **Principle:** a reader must always be able to tell a consultant's notes from reviewed evidence.
- **Authority:** [`GOVERNANCE_STATES.md`](GOVERNANCE_STATES.md); interim detail in Phases 204 and 206.

### C5 — Recommendation governance

**Formal recommendations stay subject to the established evidence, review and reliability rules.**
No composition, rendering, export or model output may create, widen or reword a formal
recommendation outside those rules.

- **Principle:** a recommendation is only as strong as the reviewed evidence behind it.
- **Authority:** [`GOVERNANCE_STATES.md`](GOVERNANCE_STATES.md), [`STATE_TRANSITIONS.md`](STATE_TRANSITIONS.md); interim detail in Phase 117 (eligibility) and Phase 118 (bounded internal recommendation).

### C6 — Client and engagement authority

**Real consultant-workspace engagements carry `owner_id = peak_consultants` and
`authorization_scope = engagement_authorized`.** The owner is the organizational authority over the
engagement. **Consultant assignment is workflow metadata, not authorization.** Internal test
engagements are classified and isolated separately (interim detail in Phases 55–57).

- **Principle:** authorization comes from stamped ownership and scope, never from who is assigned.
- **Authority:** [`GOVERNANCE_STATES.md`](GOVERNANCE_STATES.md) (`engagement_authorized`), [`CLIENT_ISOLATION_MODEL.md`](CLIENT_ISOLATION_MODEL.md), [`DATABASE_ACCESS_AND_AUDIT.md`](DATABASE_ACCESS_AND_AUDIT.md).

### C7 — One canonical report composition

**There is one canonical FinalReport composition.** The web report and the DOCX are renderings of
that same report content, and no rendering composes report content of its own.

- **Principle:** compose once, render many; renderings cannot drift because they share one source.
- **Authority:** enforced by `peak/reports/final_report.py`, the one composer; artifact detail in the planned artifact-lifecycle authority (§4).

### C8 — Client-facing presentation

**Internal version metadata is not shown to clients.** A client-facing artifact does not display
version labels (v1/v2/v3), internal artifact IDs, capsule IDs, superseded-version history, or the
label "final" merely because the artifact has been released.

- **Principle:** clients see the content Peak stands behind; Peak's internal bookkeeping stays internal.
- **Authority:** planned artifact-lifecycle authority (§4).

### C9 — Versioning

**Important engagement artifacts support internal, immutable version identity.** The conceptual
hierarchy is **Client → Engagement → Phase → Artifact → Version**. Here *Phase* means a stage of the
engagement's consulting work, not a repository delivery phase. Working records may change; **an
issued milestone artifact keeps its historical versions immutable.**

- **Principle:** what was issued stays exactly what was issued.
- **Authority:** planned artifact-lifecycle authority (§4).

### C10 — Capsules bind to immutable versions

**A capsule maps to a specific immutable source or artifact version, never to mutable "current"
state.** A later version supersedes an earlier one; it does not overwrite it.

- **Principle:** a capsule must keep meaning the same thing after the records behind it move on.
- **Authority:** planned capsule-publication authority (§4); current architecture in [`RESOLVER_CAPSULE_ARCHITECTURE.md`](RESOLVER_CAPSULE_ARCHITECTURE.md).

### C11 — Two renderings of a released report

**For a released report, Peak supports a web rendering and a DOCX rendering.** Both derive from the same canonical
artifact version and carry **identical business content**. Presentation and layout may differ by
medium.

- **Principle:** the medium changes the layout, never the substance.
- **Authority:** C7; planned artifact-lifecycle authority (§4).

### C12 — Sequential approval

**Client-facing report release requires two approvals, in order: first the Lead Consultant, then the
Final Approver.** Both approvals apply to **the exact same immutable artifact version**. **Any
content change after an approval invalidates the prior approval chain for release purposes** and
requires re-approval of the new version.

- **Principle:** an approval is for specific content; new content needs new approval.
- **Authority:** planned artifact-lifecycle authority (§4). The general rule that only humans grant client-facing approval is in [`GOVERNANCE_STATES.md`](GOVERNANCE_STATES.md) and [`STATE_TRANSITIONS.md`](STATE_TRANSITIONS.md).

### C13 — Release rule

**Only an artifact version holding both required approvals may be released to the client.**

- **Principle:** release is the result of the approval chain, never a substitute for it.
- **Authority:** planned artifact-lifecycle authority (§4).

### C14 — Internal metadata stays internal

**Approval chain, version identity, provenance, capsule identity and supersession metadata are
internal** unless a specific external requirement says otherwise.

- **Principle:** governance records serve Peak's accountability; they are not part of the client deliverable.
- **Authority:** C8; planned artifact-lifecycle and capsule-publication authorities (§4).

### C15 — No client or sample data in the repository

**The repository holds source assets only.** No live or pseudo-client data, generated client
fixtures, database dumps, credentials, generated reports, or sample engagement records are committed.
Test data is synthetic, generated at runtime, and not committed.

- **Principle:** the repository is code and policy, never a place where client data can leak.
- **Authority:** [`DATA_HANDLING_POLICY.md`](DATA_HANDLING_POLICY.md), [`FIXTURE_STRATEGY.md`](FIXTURE_STRATEGY.md); enforced in part by `tests/validate_phase7_policy.py`.

### C16 — Production safety

**Production schema, data and grant changes stay explicitly gated.** No destructive production
operation happens without explicit approval.

- **Principle:** production changes are deliberate, reviewed and reversible wherever possible.
- **Authority:** [`CONTROLLED_DB_WRITER_BOUNDARY.md`](CONTROLLED_DB_WRITER_BOUNDARY.md), [`CONTROLLED_WRITE_ALLOWLIST.md`](CONTROLLED_WRITE_ALLOWLIST.md), [`DATABASE_SCAFFOLD.md`](DATABASE_SCAFFOLD.md) (migrations and the Alembic target guard).

### C17 — AgentNet publication is explicit

**AgentNet publication is controlled and explicit.** Client-facing approval does **not** imply
AgentNet publication approval; publication needs its own decision.

- **Principle:** sharing with a client and publishing to a network are different acts with different audiences.
- **Authority:** [`PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md`](PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md), [`AGENTNET_MCP_BOUNDARY.md`](AGENTNET_MCP_BOUNDARY.md); planned capsule-publication authority (§4).

### C18 — Auditability and provenance

**Important business outputs keep enough provenance to answer four questions:** what source state
produced this artifact; who approved it; what exact version was released; and which capsule
represents it.

- **Principle:** every issued output can be explained after the fact.
- **Authority:** [`DATABASE_ACCESS_AND_AUDIT.md`](DATABASE_ACCESS_AND_AUDIT.md); planned artifact-lifecycle and capsule-publication authorities (§4).

### C19 — Working state versus issued artifacts

**Working state may change. Issued artifacts must be reconstructible and historically stable.**

- **Principle:** consultants can keep working without rewriting what has already gone out.
- **Authority:** C9; planned artifact-lifecycle authority (§4).

### C20 — Specialized authority pattern

**Any rule that needs implementation detail points to a specialized authority rather than expanding
this Contract.** If no such authority exists, the rule names it as a planned specialized authority
until one is written.

- **Principle:** the Contract stays short enough to be read in full and obeyed.
- **Authority:** this section and §4.

---

## 3. How lower authorities relate to this Contract

- Specialized authorities give detail for rules stated here. They may be stricter, but they may not
  contradict a rule here.
- Phase documents record history. When a phase introduces or changes a settled rule, the Contract
  or the relevant specialized authority is updated in that same phase.
- The implementation plan sequences work toward these rules. Planned work that would break a rule
  needs a Contract amendment first.
- Code and tests enforce the rules. A test that passes does not make a conflicting behaviour
  permitted.

---

## 4. Specialized authorities

**Existing**, by subject:

| Subject | Authority |
|---|---|
| Governance state families, client-facing approval states | [`GOVERNANCE_STATES.md`](GOVERNANCE_STATES.md), [`STATE_TRANSITIONS.md`](STATE_TRANSITIONS.md), `schemas/*.schema.json` |
| Controlled writes | [`CONTROLLED_WRITE_ALLOWLIST.md`](CONTROLLED_WRITE_ALLOWLIST.md), `peak/persistence/allowlist.py`, [`CONTROLLED_DB_WRITER_BOUNDARY.md`](CONTROLLED_DB_WRITER_BOUNDARY.md) |
| Schema and migrations | [`DATABASE_SCAFFOLD.md`](DATABASE_SCAFFOLD.md), `peak/db/models.py`, `alembic/versions/` |
| Tenant isolation, access and audit | [`CLIENT_ISOLATION_MODEL.md`](CLIENT_ISOLATION_MODEL.md), [`DATABASE_ACCESS_AND_AUDIT.md`](DATABASE_ACCESS_AND_AUDIT.md) |
| Data handling and fixtures | [`DATA_HANDLING_POLICY.md`](DATA_HANDLING_POLICY.md), [`FIXTURE_STRATEGY.md`](FIXTURE_STRATEGY.md) |
| Data architecture | [`CONTROLLED_DATA_ARCHITECTURE.md`](CONTROLLED_DATA_ARCHITECTURE.md) |
| AgentNet and capsules (current) | [`PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md`](PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md), [`AGENTNET_MCP_BOUNDARY.md`](AGENTNET_MCP_BOUNDARY.md), [`RESOLVER_CAPSULE_ARCHITECTURE.md`](RESOLVER_CAPSULE_ARCHITECTURE.md) |
| Operating model | [`OPERATING_MODEL.md`](OPERATING_MODEL.md) |

**Planned specialized authorities.** These do not exist yet. Until they do, the Contract rules that
point to them govern directly.

| Planned authority | Will govern | Contract rules |
|---|---|---|
| `ARTIFACT_LIFECYCLE.md` | artifact and version identity, working vs issued state, renderings of a version, the Lead Consultant → Final Approver chain, approval invalidation, release, client-facing presentation | C7–C9, C11–C14, C18, C19 |
| `CAPSULE_PUBLICATION.md` | capsule-to-version binding, supersession, AgentNet publication decisions | C10, C14, C17, C18 |

---

## 5. Amending the Contract

The Contract changes only deliberately: in a phase whose stated purpose includes the amendment,
recorded in that phase's entry in [`PHASE_INDEX.md`](PHASE_INDEX.md). An amendment states the rule
being added, changed or retired, and any lower authority it requires to change.
