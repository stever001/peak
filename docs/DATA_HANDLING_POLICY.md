# Data Handling Policy

**Status: operational first policy — private/internal, pre-legal.** This is Peak's
initial, working policy for handling client-related material. It is written for
founder/consultant use and is intended to be reviewed and strengthened by legal counsel
later. It does **not** claim legal or regulatory compliance is complete.

## 1. Purpose and scope

This policy governs how Peak handles client-related material relative to this
repository. The guiding rule is simple:

> **The repository holds source assets only. Client data is never stored in the repo.**

## 2. Private, internal-only status

- This is a **private, internal Peak project. It is not open source.**
- **No outside developer access is contemplated.** Access is limited to Peak
  personnel.
- The repository is an **internal operating system**: it is not client-facing, and
  nothing in it is operated by or delivered directly to a client.

## 3. Source assets only — no stored data artifacts

The repository contains **source assets only**:

- Peak documentation,
- schemas,
- prompt contracts,
- tools / scripts,
- tests / validation logic,
- architecture / policy materials.

The repository must **not** contain any of the following:

- client data,
- pseudo-client stored records,
- committed generated fixtures,
- sample engagement packets,
- sample outputs,
- redacted notes,
- inventory exports,
- telemetry,
- financial records,
- resolver capsule payloads.

Where representative objects are needed for validation, they are **synthetic and
generated at runtime** in temporary, ignored locations — never committed. See
[`FIXTURE_STRATEGY.md`](FIXTURE_STRATEGY.md).

## 4. Where client data lives

Client data belongs in **controlled engagement database/storage** and, where
appropriate, in **private resolver capsules**. The data layer is that controlled
storage — **not Git**. Collected client data is **private engagement data by default**;
it is not public. The architecture of that data layer is described in
[`CONTROLLED_DATA_ARCHITECTURE.md`](CONTROLLED_DATA_ARCHITECTURE.md),
[`ENGAGEMENT_DATA_MODEL.md`](ENGAGEMENT_DATA_MODEL.md), and
[`RESOLVER_CAPSULE_ARCHITECTURE.md`](RESOLVER_CAPSULE_ARCHITECTURE.md), and its staged
build-out in [`DATABASE_IMPLEMENTATION_PLAN.md`](DATABASE_IMPLEMENTATION_PLAN.md) (all
architecture/planning only — not implemented).

## 5. Client data is for authorized engagements only

- Actual client data is used **only for authorized live client engagement work**.
- Client data **must not** be used for examples, fixtures, demos, training, tests, or
  any non-engagement use.
- Client data **must not be committed** to this repository under any circumstances.

## 6. Real financial impact numbers

Within authorized engagement work (in controlled storage, not the repo), real financial
impact numbers **may be used** when they are:

- **Evidence-linked** — tied to an `evid_` id / source rather than asserted,
- **Source-labeled** — marked *reported* vs. *verified*, and
- **Human-reviewed** — checked before they reach a client.

Do not fabricate or extrapolate financial impact.

## 7. Secrets and system access

The following must **never** be committed to the repository, in any form:

- Secrets, credentials, passwords, API keys, or access tokens.
- Private system exports (ERP/WMS extracts, database dumps) or anything granting access
  to a client system.

If a secret is ever committed by mistake, treat it as compromised: rotate it and raise
it with Peak leadership. (Removing it in a later commit does **not** remove it from
history.)

## 8. Sensitive-data flags in `EvidenceReference`

`EvidenceReference` (a schema — a source asset) carries a `sensitive_data_flag` and a
`summary`, and is populated inside controlled engagement storage, not the repo. The raw
sensitive content stays in controlled storage; `access_notes` / `retention_notes`
record where it lives and how it is handled.

## 9. Retention

- Client data is retained within its **controlled engagement storage** under
  Peak-approved handling, for as long as the engagement requires.
- The repository stores **no** client data and therefore has no client-data retention
  obligation.
- A formal **retention** schedule (durations, secure storage, access controls) is
  future work (§13).

## 10. No external publication, cross-client reuse, or AgentNet publication without governance

Private engagement data must **not** be published externally, reused across clients, or
published to / grounded through AgentNet **without explicit Peak governance approval.**

## 11. Human review before client-facing use

No output derived from this system may be shared with a client without **explicit human
review and approval**. See the readiness ladder in
[`CONSULTANT_WORKFLOW.md`](CONSULTANT_WORKFLOW.md) and the governance state gates in
[`GOVERNANCE_STATES.md`](GOVERNANCE_STATES.md) / [`STATE_TRANSITIONS.md`](STATE_TRANSITIONS.md):
agent output defaults to `draft`/`needs_review`, and only a human sets
`client_facing_approved`.

## 12. AgentNet status

AgentNet is **intended future grounding/resolution architecture only**. It is **not
integrated**. No real client data may be published to, or grounded through, AgentNet
without a separate, explicit Peak governance decision (§10).

## 13. LLM usage caution

The prompt contracts are run by a human against an LLM of their choice. Because that may
be a third-party service:

- **Do not paste real client data into an unapproved third-party LLM/tool.** Approved,
  contractually-covered services may be used with real engagement data under the
  engagement's authorization.
- Treat anything sent to a third-party tool as potentially retained by that vendor.

## 14. Redaction policy removed

Earlier drafts of this policy framed repo safety around **redaction**. That framing has
been **removed**. Because the repository stores no data artifacts at all (§3), there is
nothing in it to redact. Any test or demo material is **synthetic**, generated at
runtime, rather than redacted client data.

## 15. Future work (not yet in place)

This is a first policy. Still to be defined, ideally with legal review:

- A formal **retention** schedule and secure storage/access controls for engagement
  storage and resolver capsules.
- **DPA / vendor review** for any LLM or third-party service used with client material.
- **Client consent** / engagement-authorization language for AI-assisted assessment.
- A defined **governance** process for external publication, cross-client reuse, and any
  future AgentNet grounding of real material.

Nothing in this section is claimed to exist yet.

---

*See also:* [`FIXTURE_STRATEGY.md`](FIXTURE_STRATEGY.md) (synthetic fixtures, no stored
data), [`CONSULTANT_WORKFLOW.md`](CONSULTANT_WORKFLOW.md) (the operating process).
