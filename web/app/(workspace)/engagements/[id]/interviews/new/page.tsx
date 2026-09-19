import { startInterview } from "@/app/discovery-actions";
import { InterviewStartForm } from "@/components/interview-start-form";
import { PageHeader } from "@/components/page-header";
import { apiGet, requireConsultant, type Discovery, type Engagement } from "@/lib/api";

export default async function NewInterviewPage(props: PageProps<"/engagements/[id]/interviews/new">) {
  await requireConsultant();
  const { id } = await props.params;
  const [{ engagement }, { discovery }] = await Promise.all([
    apiGet<{ engagement: Engagement }>(`/engagements/${encodeURIComponent(id)}`),
    apiGet<{ discovery: Discovery }>(`/engagements/${encodeURIComponent(id)}/discovery`),
  ]);
  return (
    <>
      <PageHeader title="Start interview"
                  intro={`${engagement.engagement_label ?? "Engagement"} · ${engagement.client.name ?? ""}`} />
      <InterviewStartForm action={startInterview.bind(null, engagement.id)}
                          keyPersonnel={discovery.key_personnel}
                          cancelHref={`/engagements/${engagement.id}#discovery`} />
    </>
  );
}
