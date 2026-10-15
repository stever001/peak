import {
  designateFinalApprover, finalDecision, leadDecision, prepareReleasePackage, releasePackage,
} from "@/app/artifact-actions";
import { Pill } from "@/components/assessment-view";
import { DecisionForm, DesignateForm, ReleaseForm, SubmitVersionForm } from "@/components/artifact-review-forms";
import {
  getWebRendition, type ApprovalDecision, type ConsultantOption, type FinalReportReview, type PackageState,
  type PersonRef, type ReleasePackage,
} from "@/lib/api";

const STATE: Record<PackageState, { label: string; tone: string }> = {
  prepared: { label: "Awaiting Lead Consultant review", tone: "bg-line" },
  lead_approved: { label: "Lead approved · awaiting Final Approver", tone: "bg-highlight" },
  final_approved: { label: "Final approved · ready to release", tone: "bg-accent" },
  released: { label: "Released", tone: "bg-accent" },
  superseded: { label: "Superseded", tone: "bg-line" },
  rejected: { label: "Rejected", tone: "bg-highlight" },
};

const link =
  "inline-flex min-h-touch items-center justify-center rounded-peak border border-line bg-surface px-5 font-medium hover:border-brand";

function when(at: string | null) {
  return at ? new Date(at).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }) + " UTC" : "";
}

const who = (p: PersonRef | null) => p?.name ?? p?.id ?? "Unknown";

function Decision({ title, d }: { title: string; d: ApprovalDecision | null }) {
  return (
    <div>
      <dt className="text-sm text-ink-muted">{title}</dt>
      <dd className="mt-0.5">
        {d ? (
          <>
            <span className="font-medium">{d.decision === "approved" ? "Approved" : "Rejected"}</span> by {who(d.by)}
            <span className="text-ink-muted"> · {when(d.at)} · reviewed the {d.reviewed_rendition === "docx" ? "DOCX" : "web page"}</span>
            {d.note && <p className="mt-1 whitespace-pre-line text-sm text-ink-muted">“{d.note}”</p>}
          </>
        ) : <span className="text-ink-muted">Not yet decided</span>}
      </dd>
    </div>
  );
}

function PackageRecord({ p }: { p: ReleasePackage }) {
  return (
    <dl className="grid gap-4 sm:grid-cols-2">
      <div>
        <dt className="text-sm text-ink-muted">Prepared</dt>
        <dd className="mt-0.5">
          {who(p.created_by)} <span className="text-ink-muted">· {when(p.created_at)} · report version {p.version_number}</span>
        </dd>
      </div>
      <div>
        <dt className="text-sm text-ink-muted">Package fingerprint</dt>
        <dd className="mt-0.5 font-mono text-sm">{p.package_hash.slice(0, 16)}</dd>
      </div>
      <Decision title="Lead Consultant" d={p.lead_decision} />
      <div>
        <dt className="text-sm text-ink-muted">Final Approver designation</dt>
        <dd className="mt-0.5">
          {p.designations.length === 0 ? <span className="text-ink-muted">None</span> : (
            <ol className="space-y-1 text-sm">
              {p.designations.map((d) => (
                <li key={d.id} className={d.id === p.current_designation?.id ? "font-medium" : "text-ink-muted line-through"}>
                  {who(d.consultant)} — designated by {who(d.by)} · {when(d.at)}
                  {d.id === p.current_designation?.id && " (current)"}
                </li>
              ))}
            </ol>
          )}
        </dd>
      </div>
      <Decision title="Final Approver" d={p.final_decision} />
      <div>
        <dt className="text-sm text-ink-muted">Release</dt>
        <dd className="mt-0.5">
          {p.release ? <>Released by {who(p.release.by)} <span className="text-ink-muted">· {when(p.release.at)}</span></>
            : <span className="text-ink-muted">Not released</span>}
        </dd>
      </div>
    </dl>
  );
}

function RenditionLinks({ p }: { p: ReleasePackage }) {
  const base = `/release-packages/${encodeURIComponent(p.id)}`;
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
      <a href={`${base}/web`} target="_blank" rel="noopener" className={link}>Open web page</a>
      {/* A plain link, not <Link>: the route handler answers with the stored file. */}
      <a href={`${base}/docx`} download className={link}>Download DOCX</a>
    </div>
  );
}

/** What the signed-in consultant can do next on the latest package. The API enforces every rule. */
function Controls({ p, engagementId, meId, leadId, leadName, options }: {
  p: ReleasePackage; engagementId: string; meId: string; leadId: string | null; leadName: string | null;
  options: ConsultantOption[];
}) {
  const leadApprover = p.lead_decision?.by.id ?? null;
  const designee = p.current_designation?.consultant.id ?? null;
  if (!p.hash_verified) return null;
  if (p.client_problems.length > 0 && ["prepared", "lead_approved", "final_approved"].includes(p.state)) {
    return <p className="text-sm text-ink-muted">This package can&apos;t be approved or released until its renditions are client-facing.</p>;
  }
  if (p.state === "prepared") {
    if (!leadId) return <p className="text-sm text-ink-muted">An Admin must assign a consultant to this engagement; they give the Lead Consultant approval.</p>;
    if (meId !== leadId) return <p className="text-sm text-ink-muted">Awaiting the Lead Consultant, {leadName ?? "the assigned consultant"}.</p>;
    return <DecisionForm action={leadDecision.bind(null, p.id, engagementId)} packageHash={p.package_hash} level="Lead Consultant" />;
  }
  if (p.state === "lead_approved") {
    const canDesignate = meId === leadApprover || meId === leadId;
    const choices = options.filter((o) => o.id !== leadApprover && o.id !== designee);
    return (
      <div className="space-y-5">
        {canDesignate && (
          <DesignateForm action={designateFinalApprover.bind(null, p.id, engagementId)} options={choices}
                         reassign={designee !== null} />
        )}
        {designee === null && !canDesignate && <p className="text-sm text-ink-muted">Awaiting Final Approver designation by the Lead Consultant.</p>}
        {designee !== null && (meId === designee
          ? <DecisionForm action={finalDecision.bind(null, p.id, engagementId)} packageHash={p.package_hash} level="Final Approver" />
          : <p className="text-sm text-ink-muted">Awaiting the Final Approver, {who(p.current_designation!.consultant)}.</p>)}
      </div>
    );
  }
  if (p.state === "final_approved") {
    if (meId === leadApprover || meId === p.final_decision?.by.id) {
      return <ReleaseForm action={releasePackage.bind(null, p.id, engagementId)} packageHash={p.package_hash} />;
    }
    return <p className="text-sm text-ink-muted">Ready to release by the Lead approver or the Final Approver.</p>;
  }
  if (p.state === "rejected") {
    return <p className="text-sm text-ink-muted">Rejected packages stay on record. Revise the working material, then prepare a new package.</p>;
  }
  return null;
}

/**
 * Internal review and release of the Final Report (Phase 213). Humans approve a release package: one fixed
 * report version and the exact web page and DOCX file rendered from it when the package was prepared. The web
 * page shown here and the DOCX offered here are those stored files, never a fresh rendering. Package and version
 * numbers, approvers and release records are internal: none of it appears in the report or its renditions.
 */
export async function ArtifactReviewPanel({ review, engagementId, meId, lead, options }: {
  review: FinalReportReview; engagementId: string; meId: string; lead: PersonRef | null;
  options: ConsultantOption[];
}) {
  const [latest, ...earlier] = review.packages;
  const webHtml = latest?.hash_verified ? await getWebRendition(latest.id) : null;
  const prepare = prepareReleasePackage.bind(null, engagementId);
  return (
    <section className="peak-card mb-8 space-y-5" aria-labelledby="review-heading">
      <div className="flex flex-wrap items-center gap-2">
        <h2 id="review-heading" className="text-xl font-semibold text-brand">Review and release</h2>
        <Pill>Internal only</Pill>
      </div>
      <p className="text-sm text-ink-muted">
        Approval applies to a release package: a fixed version of this report with its exact client-facing web page
        and DOCX file, stored when the package is prepared. What you review here is exactly what would be released.
        Review either one; your decision covers both. The Lead Consultant
        approves first, then a different consultant designated as Final Approver.
      </p>
      {!latest ? (
        <div className="space-y-3">
          <p>No release package yet. Prepare one from the live draft below to start review.</p>
          <SubmitVersionForm action={prepare} label="Prepare release package" />
        </div>
      ) : (
        <>
          {review.draft_matches_latest ? (
            <p className="text-sm">The live draft below has the same content as package {latest.package_number}.</p>
          ) : (
            <div className="space-y-3 rounded-peak border-l-4 border-attention bg-canvas px-4 py-3">
              <p className="text-sm">
                The live draft below has changed since package {latest.package_number} was prepared. Package{" "}
                {latest.package_number} is unchanged and can still be reviewed as it is. To release the current content,
                prepare a new package; approvals never carry over.
              </p>
              <SubmitVersionForm action={prepare} label="Prepare new package" />
            </div>
          )}
          <article className="space-y-4 rounded-peak border border-line p-4">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="font-semibold">Package {latest.package_number}</h3>
              <Pill tone={STATE[latest.state].tone}>{STATE[latest.state].label}</Pill>
            </div>
            {!latest.hash_verified ? (
              <p role="alert" className="rounded-peak border-l-4 border-attention bg-canvas px-4 py-3 text-sm">
                This package&apos;s stored files or content no longer match their recorded hashes. It cannot be reviewed,
                approved or released.
              </p>
            ) : (
              <>
                <div className="space-y-2">
                  <h4 className="font-semibold">Web page in this package</h4>
                  {/* The stored HTML itself, sandboxed: no script runs and nothing is re-rendered. */}
                  <iframe title={`Web page in package ${latest.package_number}`} srcDoc={webHtml ?? ""} sandbox=""
                          className="h-[32rem] w-full rounded-peak border border-line bg-white" />
                </div>
                <RenditionLinks p={latest} />
                {latest.client_problems.length > 0 && (
                  <div role="alert" className="rounded-peak border-l-4 border-attention bg-canvas px-4 py-3 text-sm">
                    <p className="font-medium">These renditions are not client-facing, so this package can&apos;t be approved or released:</p>
                    <ul className="mt-1 list-disc pl-5">{latest.client_problems.map((m) => <li key={m}>{m}</li>)}</ul>
                  </div>
                )}
              </>
            )}
            <PackageRecord p={latest} />
            <Controls p={latest} engagementId={engagementId} meId={meId} leadId={lead?.id ?? null}
                      leadName={lead?.name ?? null} options={options} />
          </article>
          {earlier.length > 0 && (
            <details className="rounded-peak border border-line p-4">
              <summary className="cursor-pointer font-medium">Earlier packages ({earlier.length})</summary>
              <div className="mt-4 space-y-6">
                {earlier.map((p) => (
                  <div key={p.id} className="space-y-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-semibold">Package {p.package_number}</h3>
                      <Pill tone={STATE[p.state].tone}>{STATE[p.state].label}</Pill>
                    </div>
                    {p.hash_verified && <RenditionLinks p={p} />}
                    <PackageRecord p={p} />
                  </div>
                ))}
              </div>
            </details>
          )}
        </>
      )}
    </section>
  );
}
