import Link from "next/link";

import { FinalReportView } from "@/components/final-report-view";
import { PageHeader } from "@/components/page-header";
import { apiGet, requireConsultant, type FinalReportResponse } from "@/lib/api";

/**
 * The engagement's internal Final Report foundation. Read-only and derived on every request from the
 * internal assessment — there is no save, approve, or export action here, and nothing on this page writes.
 */
export default async function FinalReportPage(props: PageProps<"/engagements/[id]/final-report">) {
  await requireConsultant();
  const { id } = await props.params;
  const { engagement, report, markdown } = await apiGet<FinalReportResponse>(
    `/engagements/${encodeURIComponent(id)}/final-report`,
  );
  return (
    <>
      <Link href={`/engagements/${engagement.id}`}
            className="mb-4 inline-flex min-h-touch items-center text-sm font-medium text-brand">
        ← {engagement.engagement_label ?? "Engagement"}
      </Link>
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <PageHeader title="Final report (internal draft)"
                    intro={`${engagement.client.name} · ${engagement.engagement_label ?? "Untitled engagement"}`} />
        <Link href={`/engagements/${engagement.id}/assessment`}
              className="inline-flex min-h-touch shrink-0 items-center justify-center rounded-peak border border-line bg-surface px-6 font-medium hover:border-brand">
          Internal assessment
        </Link>
      </div>
      <FinalReportView r={report} markdown={markdown} engagementId={engagement.id} />
    </>
  );
}
