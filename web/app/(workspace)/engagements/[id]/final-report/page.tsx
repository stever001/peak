import Link from "next/link";

import { ArtifactReviewPanel } from "@/components/artifact-review-panel";
import { FinalReportView } from "@/components/final-report-view";
import { PageHeader } from "@/components/page-header";
import {
  apiGet, requireConsultant, type ConsultantOption, type FinalReportResponse, type FinalReportReview,
} from "@/lib/api";

/**
 * The engagement's internal Final Report. The draft is derived on every request from the internal
 * assessment and is never written by viewing it. The internal review panel (Phase 213) prepares a release
 * package only when a consultant asks: an immutable version with its web page and DOCX rendered once and
 * stored. Approvers review those stored files, and the two approvals and the release apply to that package.
 */
export default async function FinalReportPage(props: PageProps<"/engagements/[id]/final-report">) {
  const me = await requireConsultant();
  const { id } = await props.params;
  const path = `/engagements/${encodeURIComponent(id)}/final-report`;
  const [{ engagement, report, markdown }, { review }, { consultants }] = await Promise.all([
    apiGet<FinalReportResponse>(path),
    apiGet<{ review: FinalReportReview }>(`${path}/packages`),
    apiGet<{ consultants: ConsultantOption[] }>("/consultant-options"),
  ]);
  return (
    <>
      <Link href={`/engagements/${engagement.id}`}
            className="mb-4 inline-flex min-h-touch items-center text-sm font-medium text-brand">
        ← {engagement.engagement_label ?? "Engagement"}
      </Link>
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <PageHeader title="Final report (internal draft)"
                    intro={`${engagement.client.name} · ${engagement.engagement_label ?? "Untitled engagement"}`} />
        <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:justify-end">
          {/* A plain link, not <Link>: the route handler answers with a file attachment. */}
          <a href={`/engagements/${engagement.id}/final-report/docx`} download className="peak-button shrink-0">
            Download DOCX
          </a>
          <Link href={`/engagements/${engagement.id}/assessment`}
                className="inline-flex min-h-touch shrink-0 items-center justify-center rounded-peak border border-line bg-surface px-6 font-medium hover:border-brand">
            Internal assessment
          </Link>
        </div>
      </div>
      <ArtifactReviewPanel review={review} engagementId={engagement.id} meId={me.id}
                           lead={engagement.assigned_consultant} options={consultants} />
      <h2 className="mb-3 text-xl font-semibold text-brand">Live draft (working state)</h2>
      <FinalReportView r={report} markdown={markdown} engagementId={engagement.id} />
    </>
  );
}
