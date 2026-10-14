import Link from "next/link";

import { AssessmentView } from "@/components/assessment-view";
import { PageHeader } from "@/components/page-header";
import { apiGet, requireConsultant, type AssessmentResponse } from "@/lib/api";

/**
 * The engagement's internal assessment. Read-only and derived on every request from persisted
 * records — there is no save action here, and nothing on this page writes.
 */
export default async function AssessmentPage(props: PageProps<"/engagements/[id]/assessment">) {
  await requireConsultant();
  const { id } = await props.params;
  const { engagement, assessment } = await apiGet<AssessmentResponse>(
    `/engagements/${encodeURIComponent(id)}/assessment`,
  );
  return (
    <>
      <Link href={`/engagements/${engagement.id}`}
            className="mb-4 inline-flex min-h-touch items-center text-sm font-medium text-brand">
        ← {engagement.engagement_label ?? "Engagement"}
      </Link>
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <PageHeader title="Internal assessment"
                    intro={`${engagement.client.name} · ${engagement.engagement_label ?? "Untitled engagement"}`} />
        <Link href={`/engagements/${engagement.id}/final-report`} className="peak-button shrink-0">
          Final report
        </Link>
      </div>
      <AssessmentView a={assessment} engagementId={engagement.id} />
    </>
  );
}
