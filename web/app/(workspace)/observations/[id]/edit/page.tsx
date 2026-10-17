import { updateObservation } from "@/app/discovery-actions";
import { ObservationForm } from "@/components/observation-form";
import { PageHeader } from "@/components/page-header";
import { apiGet, requireConsultant, type Observation, type Question } from "@/lib/api";

export default async function EditObservationPage(props: PageProps<"/observations/[id]/edit">) {
  await requireConsultant();
  const { id } = await props.params;
  const { observation: o } = await apiGet<{ observation: Observation }>(`/observations/${encodeURIComponent(id)}`);
  const { questions } = await apiGet<{ questions: Question[] }>(
    `/questions?engagement_id=${encodeURIComponent(o.engagement_id)}`);
  const options = questions.filter((q) => q.active).map(({ id: qid, prompt, category }) => ({ id: qid, prompt, category }));
  return (
    <>
      <PageHeader title="Edit observation" />
      <div className="peak-card">
        <ObservationForm action={updateObservation.bind(null, o.id, o.engagement_id)} observation={o}
                         questions={options} submitLabel="Save changes" cancelHref={`/engagements/${o.engagement_id}#discovery`} />
      </div>
    </>
  );
}
