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
      <PageHeader title="Internal assessment"
                  intro={`${engagement.client.name} · ${engagement.engagement_label ?? "Untitled engagement"}`} />
      <AssessmentView a={assessment} engagementId={engagement.id} />
    </>
  );
}
