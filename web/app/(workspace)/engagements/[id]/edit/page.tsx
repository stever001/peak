import { updateEngagement } from "@/app/workspace-actions";
import { EngagementForm } from "@/components/engagement-form";
import { PageHeader } from "@/components/page-header";
import { apiGet, requireConsultant, type ConsultantOption, type Engagement } from "@/lib/api";

export default async function EditEngagementPage(props: PageProps<"/engagements/[id]/edit">) {
  await requireConsultant();
  const { id } = await props.params;
  const [{ engagement }, { consultants }] = await Promise.all([
    apiGet<{ engagement: Engagement }>(`/engagements/${encodeURIComponent(id)}`),
    apiGet<{ consultants: ConsultantOption[] }>("/consultant-options"),
  ]);
  return (
    <>
      <PageHeader title={`Edit ${engagement.engagement_label ?? "engagement"}`} />
      <EngagementForm action={updateEngagement.bind(null, engagement.id)} engagement={engagement}
                      client={engagement.client} consultants={consultants}
                      cancelHref={`/engagements/${engagement.id}`} submitLabel="Save changes" />
    </>
  );
}
