import { updateObservation } from "@/app/discovery-actions";
import { ObservationForm } from "@/components/observation-form";
import { PageHeader } from "@/components/page-header";
import { apiGet, requireConsultant, type Observation } from "@/lib/api";

export default async function EditObservationPage(props: PageProps<"/observations/[id]/edit">) {
  await requireConsultant();
  const { id } = await props.params;
  const { observation: o } = await apiGet<{ observation: Observation }>(`/observations/${encodeURIComponent(id)}`);
  return (
    <>
      <PageHeader title="Edit observation" />
      <div className="peak-card">
        <ObservationForm action={updateObservation.bind(null, o.id, o.engagement_id)} observation={o}
                         submitLabel="Save changes" cancelHref={`/engagements/${o.engagement_id}#discovery`} />
      </div>
    </>
  );
}
