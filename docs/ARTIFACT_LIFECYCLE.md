# Artifact Lifecycle

**The specialized normative authority for artifact versioning, approval, release, supersession and
capsule binding.** Adopted in Phase 211 (baseline `c506b77`).

This document sits at level 2 of the authority hierarchy, directly under
[`PEAK_PROJECT_CONTRACT.md`](PEAK_PROJECT_CONTRACT.md). It gives the detail for Contract rules
**C7–C9, C11–C14, C18 and C19**, and the artifact side of **C10 and C17**. It implements those rules
and does not reinterpret them. If anything here conflicts with the Contract, the Contract governs.

**Status: normative, partly implemented.** Phase 212 implemented artifact versions, and Phase 213
release packages, two-stage approval and release, for the Final Report. Everything else here is not
yet built. This document says what the lifecycle *must* mean. It does not define tables, columns, field
schemas, endpoints or migrations. The gaps between this document and the current system are tracked
in [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) (Phase 211 reconciliation items).

Rules are numbered **AL1–AL54** so later phases can cite them. AL41–AL51 (§9A, release packages)
were added in Phase 213. AL52–AL54 (§9B, internal test engagements) were added in Phase 215, along
with a narrow exception in AL17.

---

## 1. Relation to other authorities

| Authority | Relation |
|---|---|
| [`PEAK_PROJECT_CONTRACT.md`](PEAK_PROJECT_CONTRACT.md) | Governs this document. |
| [`GOVERNANCE_STATES.md`](GOVERNANCE_STATES.md) | Defines `ClientFacingApprovalStatus` and the rule that only humans set `approved_for_client`. That rule still holds. For artifact versions, this document is more specific: a human approval is necessary but not sufficient, and client release needs the two-stage chain in §6. |
| [`STATE_TRANSITIONS.md`](STATE_TRANSITIONS.md) | Defines a single human gate, `approved_internal → client_facing_candidate → approved_for_client`, and general supersede rules. For artifact versions, the approval and release semantics here govern. Its supersede rule ("the old record remains referenceable") is consistent with §8. |
| [`CONTROLLED_DATA_ARCHITECTURE.md`](CONTROLLED_DATA_ARCHITECTURE.md) | Describes the controlled-write and data architecture that artifact persistence will have to fit when it is built. It governs *how* artifact records may be written. This document governs *what* an artifact record means. |
| [`PHASE208_FINAL_REPORT_FOUNDATION.md`](PHASE208_FINAL_REPORT_FOUNDATION.md) | Records the one canonical report composer (C7). Its report is an **internal draft derived from working state**. It is not an artifact version. |
| [`PHASE209_FINAL_REPORT_DOCX_EXPORT.md`](PHASE209_FINAL_REPORT_DOCX_EXPORT.md) | Records the DOCX rendering of that same composed report. The rendering rules in §9 apply to it once reports become artifact versions. |
| `CAPSULE_PUBLICATION.md` (**planned, not yet written**) | Will govern capsule mechanics, publication actions and AgentNet publication decisions. Until it exists, §11 here and Contract C10, C14, C17 and C18 govern directly. |

Where those documents are less specific than the Contract or this document about artifact versions,
approval, release, supersession or client presentation, **this document governs artifact lifecycle
semantics**. Their other content is unaffected.

---

## 2. Artifact model

```
Client
  → Engagement
    → Engagement Phase
      → Artifact
        → Artifact Version
```

- **AL1 — Engagement Phase means a consulting stage.** It is a stage of the engagement's consulting
  work, such as intake, discovery, assessment or a later delivery stage. It is **not** a repository
  delivery phase (Phase 208, Phase 211 and so on). It is the same "Phase" as in Contract C9.
- **AL2 — Artifact.** A named milestone output of one engagement phase, such as "the assessment
  report for this engagement's assessment stage". An artifact has a type (§13) and an ordered set of
  versions. It belongs to exactly one engagement, so it inherits that engagement's client, owner
  and authorization scope (Contract C6). An artifact never crosses engagements or clients.
- **AL3 — Artifact Version.** One immutable snapshot of an artifact's content. It has a stable
  internal identity that is never reused or reassigned. Every review, approval, release and capsule
  binding refers to a version, never to the artifact in general and never to working state.

---

## 3. Working state and artifact versions

- **AL4 — Working state is mutable.** Interviews, answers, observations, the North Star,
  evidence records and every other current assessment input are working state. Consultants may keep
  editing them. Working state lives in the operational database, which is canonical truth for
  persisted business state (Contract C2).
- **AL5 — An artifact version is immutable from the moment it exists.** It preserves exactly the
  content that was reviewed, approved or released. Nothing may edit it in place: no consultant, admin,
  migration, rendering or later working-state change.
- **AL6 — Not every edit creates a version.** Edits to working state, and changes to an internal
  draft composed from working state, create no version. A version is created deliberately, when a
  milestone output is fixed for review. A typical trigger is submitting it for Lead Consultant
  approval.
- **AL7 — A version is a snapshot, not a pointer.** A version does not change when the working state
  it came from changes afterwards. Changes to working state after a version exists do not alter that
  version and do not invalidate its approvals. Those changes are simply not in it. Including them
  needs a new version (§4).
- **AL8 — Reconstructible.** A version's business content must be reproducible exactly, in every
  supported rendering, without consulting current working state (Contract C19).
- **AL9 — Drafts are not issued.** A report composed live from working state, such as the Phase
  208/209 internal draft, is working output. It cannot be approved or released as it stands. To
  become releasable, its content must first be fixed as an artifact version.

---

## 4. Lifecycle states

These are the conceptual states. Implementation names may differ, but the meanings below are
normative.

| State | Applies to | Meaning |
|---|---|---|
| `working` | the artifact's working state, not a version | Mutable inputs and live drafts. No approval attaches here. |
| `versioned` | a version | Immutable snapshot created. Awaiting Lead Consultant review. |
| `lead_approved` | a version | The Lead Consultant approved this exact version. Awaiting Final Approver review. |
| `final_approved` | a version | The Final Approver approved this same version after the Lead Consultant did. Eligible for release. |
| `released` | a version | Released to the client. Recorded as a dated event (§7). |
| `superseded` | a version | A newer version of the same artifact has taken its place (§8). |
| `rejected` | a version | An approver declined this version at either stage. The version is kept. |

```
working ──(fix content)──▶ versioned ──▶ lead_approved ──▶ final_approved ──▶ released ──▶ superseded
                               │               │
                               └──▶ rejected ◀─┘
```

- **AL10 — Forward only.** A version never moves backwards. `lead_approved` never returns to
  `versioned`, and `released` never returns to `final_approved`. Status changes record facts about
  an unchanged version. They never change its content.
- **AL11 — Rejection does not destroy.** A rejected version stays retrievable with its rejection
  recorded. Who rejected it, at which stage, when and why are internal provenance (§12).
- **AL12 — Revision means a new version.** If an artifact has entered approval (at least one version
  is `versioned` or later), any content change is made in working state and fixed as a **new**
  version. That new version starts the approval chain from the beginning. An approved or released
  version is never silently changed.
- **AL13 — Superseding an unreleased version.** If a newer version replaces a version that was never
  released, the older version becomes `superseded` too. It keeps its record and any approvals it
  received. Those approvals stay attached to it and do not carry over.
- **AL14 — Release history survives supersession.** Once a released version is superseded, it
  stays marked as having been released, with its release date (§7).

---

## 5. Roles

- **AL15 — Lead Consultant.** Owns the substantive engagement review of the artifact. Gives the
  first approval: that the content is correct, supported and fit to go forward.
- **AL16 — Final Approver.** The second-level release authority. Reviews only versions the Lead
  Consultant has already approved, and decides whether that version may be released to the client.
- **AL17 — Independent decisions.** The Final Approver's approval is a separate decision, recorded
  separately. It is never implied by, derived from or bundled with the Lead Consultant's approval.
  For any one artifact version, the Lead Consultant approval and the Final Approver approval
  must come from **different humans**. The same person may not satisfy both approval levels for the
  same version. This applies per version's approval chain. It does not stop a person from holding
  different roles on different engagements, artifacts or versions. How these roles map onto
  accounts remains an implementation question (AL18). **Exception:** on an `internal_test`
  engagement, one human may give both approvals (AL52). Both decisions are still separate and
  recorded separately.
- **AL18 — Roles are business roles, not account roles.** This document does not map Lead Consultant
  or Final Approver onto the existing `admin` and `consultant` account roles. That mapping, and how
  role holders are assigned per artifact, is an implementation reconciliation item. Role assignment
  is workflow metadata. It never replaces the engagement authorization rules in Contract C6.
- **AL19 — Humans only.** Both approvals are human decisions. Agents, models and automated jobs may
  prepare or propose a version, but they may not approve, release or supersede one (Contract C3;
  [`GOVERNANCE_STATES.md`](GOVERNANCE_STATES.md)).

---

## 6. Approval

- **AL20 — Sequential.** Lead Consultant approval comes first. Final Approver review happens only
  after it (Contract C12).
- **AL21 — Same version.** Both approvals refer to the **exact same immutable artifact version**,
  identified by its internal identity and content hash (§12). An approval of one version says nothing
  about any other version. For release, the approvals are given to one release package that binds
  that version to its exact renditions (§9A, AL43).
- **AL22 — Content change resets the chain.** Any change to business content after either approval
  produces a new version (AL12). Approvals given to earlier versions do not carry forward. The new
  version needs a Lead Consultant approval and then a Final Approver approval of its own.
- **AL23 — Approval records are internal.** Who approved, at which level, when, and any notes are
  internal provenance. They never appear in client-facing content (Contract C14).
- **AL24 — Client approval is not publication approval.** Neither approval, nor release, authorizes
  AgentNet publication or capsule publication. Publication is a separate, explicit decision
  (Contract C17; planned `CAPSULE_PUBLICATION.md`).

---

## 7. Release

- **AL25 — Eligibility.** A version may be released to the client only if all of these are true:
  1. the Lead Consultant approved it;
  2. the Final Approver approved **the same version** after that;
  3. its content has not changed since those approvals. Immutability (AL5) guarantees this, and
     release must still verify it against the recorded content hash;
  4. both approvals were given to the **same release package**, and its renditions still match their
     recorded hashes (§9A).
- **AL26 — Release is an event on a version.** "Released" is a recorded act on one specific version:
  who released it and when. It is never "whatever the report currently says". There is no released
  state for working state or live drafts.
- **AL27 — Released versions stay stable.** A released version stays exactly as released, forever.
  Later work produces a new version, which needs its own approvals before it can be released.
- **AL28 — Earlier releases stay retrievable.** Every released version stays retrievable internally,
  in every supported rendering, after a later version supersedes it.

---

## 8. Supersession and the current version

- **AL29 — Supersession never overwrites.** A newer version may supersede an older one. The older
  version stays immutable, and its content, approvals, release record and capsule binding are kept
  unchanged.
- **AL30 — One current version.** For each artifact there is normally **one** version that is
  current for client delivery: the most recently released version that has not been superseded.
  Superseding a released version with a later released version makes the later one current.
- **AL31 — History is internal.** Superseded versions remain available internally for audit and
  provenance. They are never shown to the client as history (§10).

---

## 9. Renderings: web and DOCX

- **AL32 — Two renderings of one version.** For report artifacts, the web view and the DOCX are two
  renderings of **the same canonical artifact version** (Contract C7, C11).
- **AL33 — Identical business content.** Both renderings carry identical business content: the
  same sections, findings, recommendations, statements and wording. Only layout and presentation may
  differ by medium, such as page breaks, footers, table styling or interactive navigation.
- **AL34 — Renderers do not compose.** Neither renderer may add, remove, reorder for emphasis,
  filter or reinterpret business content. Neither may fetch working state to fill in anything. A
  renderer reads only the version's canonical content. Composition happens once, in the one canonical
  composer, before the version is fixed.
- **AL35 — Content hash covers content, not bytes.** A version's content hash is taken over its
  canonical business content, not over any rendered file. Both renderings therefore correspond to the
  one hash. Each rendering proposed for release also has its own hash over its exact bytes (AL44).

---

## 9A. Release packages

The artifact version is the provenance and source layer. Human approval applies one layer above it,
to what the client will actually receive:

```
artifact version (canonical business content)
  → release package
    → web rendition
    → DOCX rendition
      → Lead Consultant approval → Final Approver approval → release
```

- **AL41 — The version is the source.** An artifact version holds the immutable canonical business
  content and its provenance (§3, §12). It is the source that client-facing renditions are rendered
  from. It is not itself what the client receives.
- **AL42 — A release package binds one version to its renditions.** A client release package binds
  **one** artifact version to the exact client-facing renditions proposed for release: for a report,
  its web rendition and its DOCX rendition. A package is immutable once created. One version may
  have more than one package over time, for example after a presentation change. Each package is a
  separate subject of approval.
- **AL43 — Humans approve the package.** The Lead Consultant and the Final Approver each review and
  approve, or reject, **the same exact release package**. Approving a package approves that
  version's content *as presented in those renditions*. It never approves another package. Final
  Approver designation and rejection apply to the package under review. AL17 (different humans) and
  AL20 (sequential) apply unchanged.
- **AL44 — Renditions derive from one version and carry their own identity.** Both renditions in a
  package are rendered from that package's version alone (AL32, AL34). Each rendition has a stable
  identity and a hash over its exact bytes. The package's identity covers the version's content hash
  and every rendition hash. Together these prove that what was approved is what was released.
- **AL45 — Any change needs a new approval cycle.** A change to business content, or to either
  client-visible rendition, after an approval means a new package, and a new version as well if the
  content changed. That package needs its own Lead Consultant and Final Approver approvals.
  Approvals never carry over from one package to another (AL22). A rejected package is terminal:
  preparing the identical package again never reopens it for another approval cycle.
- **AL46 — Release releases the approved package.** Only a package holding both approvals can be
  released (AL25). What is released, and what is delivered, are that package's stored renditions.
- **AL47 — A released web artifact stays as released.** The released web rendition is the stored
  approved artifact. It must not change when application rendering code later changes. A client web
  view resolves to that stored rendition, never to a fresh rendering of the version.
- **AL48 — A delivered DOCX is the approved file.** A DOCX that is emailed, downloaded or printed for
  the client is the exact approved DOCX artifact, never a later regeneration, even one expected to
  match.
- **AL49 — Internal identifiers stay internal.** Package, version and rendition identities, hashes
  and numbers are internal provenance. No client-facing rendition shows internal version numbers
  (AL36).
- **AL50 — Package renditions are client-facing.** The renditions in a release package are the
  artifacts humans approve and Peak may release, so they follow §10 (AL36, AL37):
  - no internal-draft or approval-status wording;
  - no internal record, version, capsule or approval identifiers;
  - a business title rather than "Final report";
  - no version history.

  They present the same canonical business content, with every section in order, through a
  presentation layer. That layer may leave out or relabel internal status wording and identifiers,
  but it never composes, adds or reinterprets business content (AL34). The internal working views
  of a report are not release renditions and are not bound by this rule. **A package whose stored
  renditions are not client-facing can't be approved or released.** That check concerns only
  Peak-owned presentation material and Peak-generated identifiers. Business content is never
  rejected or reworded for containing ordinary words such as "final report" or "internal".
- **AL51 — The reviewed rendition is recorded.** Each Lead Consultant and Final Approver decision
  records which of the package's renditions that human reviewed: the web rendition or the DOCX.
  - A reviewer may review either one and need not review both.
  - The two reviewers may review different renditions.
  - The reviewed rendition must belong to the package and still match its stored hash.
  - The decision still applies to the whole package and its package hash (AL43).

---

## 9B. Internal test engagements

An `internal_test` engagement is used for testing, training and acceptance. It holds no real client
data (`real_client_data = false`) and is never client-accessible (`client_accessible = false`). Any
consultant may create one; that classification is always forced by the server, never chosen
column by column. Only an Admin may delete one (AL53). These rules were added in Phase 215
([`PHASE215_INTERNAL_TEST_ENGAGEMENTS.md`](PHASE215_INTERNAL_TEST_ENGAGEMENTS.md)).

- **AL52 — One human may give both approvals on internal_test.** On an `internal_test` engagement,
  the Lead Consultant may designate themselves as Final Approver and give both approvals.
  - Everything else in §5–§7 and §9A still applies: Lead approval first, an explicit Final Approver
    designation, the final approval, the binding to the same package and package hash, the
    reviewed-rendition record, and the release gate.
  - Neither stage may be skipped.
  - On a `real_client` engagement AL17 is unchanged: two different humans.
- **AL53 — Deleting an internal_test engagement retires the source; it never destroys history.** An
  Admin's deletion of an `internal_test` engagement is logical:
  - The engagement is marked deleted, leaves the active lists, and accepts no new discovery, report,
    artifact, package, approval or release activity.
  - Its artifact versions, release packages, renditions, approvals, designations, releases, hashes
    and provenance are kept, immutable and auditable (AL5).
  - A `real_client` engagement cannot be deleted.
- **AL54 — Capsules from internal_test data say so, and outlive deletion.** For the future
  capsule-publication authority:
  - Every capsule derived from `internal_test` data must carry its source classification
    machine-readably, for example `engagement_classification: internal_test`. Presentation text
    alone is not enough.
  - Its source status must also be machine-readable, for example `source_status: deleted` once the
    engagement is deleted.
  - Test material must never be presented as real-client operational data.
  - Deleting an `internal_test` engagement must not silently delete, rewrite or hide an
    already-published capsule. Published history stays auditable, and the source's retirement is
    represented explicitly by the publication-management mechanism.
  - Publication itself remains separately authorized (Contract C17).

---

## 10. Client presentation

- **AL36 — The client sees only released content.** A client-facing rendering shows only the content
  of the current released version (AL30). It does not show:
  - version labels such as v1, v2 or v3;
  - internal version, artifact, approval or capsule identifiers, or internal record IDs of any kind;
  - the approval workflow, approver names in their approval role, or approval dates;
  - superseded versions or any revision history;
  - capsule metadata;
  - internal status banners, such as "internal draft" or "requires consultant review".
- **AL37 — No "Final" by default.** Release does not make an artifact "final". A client-facing title
  is the artifact's business title, such as "Inventory Assessment". It never carries "Final" just
  because the version was released. Client-facing file names follow the same rule and contain no
  internal identifiers.

These exclusions apply unless a specific external requirement says otherwise (Contract C14). Any
such exception is recorded in the Contract or in this document before it is built.

---

## 11. Capsule binding

- **AL38 — Exact-version binding.** A capsule that represents an artifact binds to **one exact
  immutable artifact version**. No capsule may silently "follow latest" or point at an artifact in
  general, at working state, or at a live draft (Contract C10).
- **AL39 — New version, new linkage.** Publishing a newer version creates linkage for that new
  version, or changes which binding is current. It never changes the historical binding of the prior
  version. A version-to-capsule relationship, once recorded, is permanent history.
- **AL40 — "Update" never rebinds history.** Whatever a capsule "update" action means in
  [`PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md`](PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md), it
  must not overwrite an existing version-to-capsule identity relationship. A change of artifact
  content is always a new version and a new binding, never an edit to an old one.

Capsule mechanics are **out of scope here**: identity format, publish, update, supersede and revoke
actions, resolver behaviour, and AgentNet publication decisions. They belong to the planned
`CAPSULE_PUBLICATION.md`. That document must comply with AL38–AL40.

---

## 12. Provenance

Every artifact version must eventually be able to answer:

| Question | |
|---|---|
| Which client? | via its engagement |
| Which engagement? | |
| Which engagement phase? | the consulting stage (AL1) |
| What artifact type? | §13 |
| What internal version? | its stable internal identity and its order within the artifact |
| Who created it, and when? | |
| What source state produced it? | a reference to the working state it was composed from, and the composer that produced it |
| What content hash? | over canonical business content (AL35) |
| Who approved it at each level, and when? | Lead Consultant, then Final Approver, plus any rejection |
| Whether, when and by whom it was released? | AL26 |
| What version does it supersede, and what superseded it? | AL29 |
| What capsule is bound to it? | AL38, once capsule publication exists |

This answers Contract C18's four questions: source state, approval, released version and capsule.
How each answer is stored is an implementation decision for a later phase, under
[`CONTROLLED_DATA_ARCHITECTURE.md`](CONTROLLED_DATA_ARCHITECTURE.md) and
[`DATABASE_ACCESS_AND_AUDIT.md`](DATABASE_ACCESS_AND_AUDIT.md). This document defines no columns.
Provenance is internal (AL23, Contract C14).

---

## 13. Artifact types

The framework applies to every milestone output. It is not specific to reports. Types it must
support include:

- **intake snapshot**: the engagement's intake as fixed at a milestone;
- **discovery snapshot**: discovery working material fixed at a milestone. It is still consultant
  working material, not evidence, inside the version (Contract C4);
- **assessment / report**: the composed report (Contract C7), rendered as web and DOCX (§9);
- **proposal for next phase**: Peak's proposal for a following engagement phase;
- **accepted proposal**: the exact proposal version the client accepted, recorded against that
  version. Acceptance is a client act. It is distinct from Peak's internal approval and release;
- **later milestone deliverables**: any further output that needs issued, stable content.

All types follow §§3–12. Field-level content schemas per type are out of scope. They are defined
when each type is implemented. Not every type needs both renderings: §9 applies to report-like
artifacts.

---

## 14. Not defined here

This document deliberately leaves the following to later, separately approved work:

- persistence: tables, columns, migrations, writers and allowlist actions;
- how Lead Consultant and Final Approver are assigned and mapped onto accounts (AL18);
- withdrawing a released version without a replacement;
- how client acceptance of a proposal is captured;
- capsule identity and publication mechanics (planned `CAPSULE_PUBLICATION.md`);
- retention periods for superseded and rejected versions. Until a retention policy says otherwise,
  versions are not deleted.

Each of these must remain consistent with AL1–AL54 and the Contract.
