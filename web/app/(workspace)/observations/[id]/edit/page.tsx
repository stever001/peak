import { updateObservation } from "@/app/discovery-actions";
import { LinkedEvidenceList } from "@/components/linked-evidence";
import { ObservationForm } from "@/components/observation-form";
import { ObservedDuring } from "@/components/observed-during";
import { PageHeader } from "@/components/page-header";
import {
  apiGet, apiPublicUrl, getEngagementEvidence, requireConsultant, type Observation, type Question,
} from "@/lib/api";

export default async function EditObservationPage(props: PageProps<"/observations/[id]/edit">) {
  await requireConsultant();
  const { id } = await props.params;
  const { observation: o } = await apiGet<{ observation: Observation }>(`/observations/${encodeURIComponent(id)}`);
  const { questions } = await apiGet<{ questions: Question[] }>(
    `/questions?engagement_id=${encodeURIComponent(o.engagement_id)}`);
  const ev = await getEngagementEvidence(o.engagement_id);
  const linked = ev?.links[o.id] ?? [];
  const apiUrl = apiPublicUrl();
  const options = questions.filter((q) => q.active).map(({ id: qid, prompt, category }) => ({ id: qid, prompt, category }));
  return (
    <>
      <PageHeader title="Edit observation" />
      {o.origin && (
        <div className="mb-6 text-sm text-ink-muted">
          <p className="font-medium text-ink">Work observation</p>
          <ObservedDuring origin={o.origin} />
        </div>
      )}
      {linked.length > 0 && (
        <div className="peak-card mb-6">
          <LinkedEvidenceList items={linked} apiUrl={apiUrl} />
        </div>
      )}
      <div className="peak-card">
        <ObservationForm action={updateObservation.bind(null, o.id, o.engagement_id)} observation={o}
                         questions={options} submitLabel="Save changes"
                         evidence={ev ? { available: ev.available, linkedIds: linked.map((e) => e.id), apiUrl } : undefined} cancelHref={`/engagements/${o.engagement_id}#discovery`} />
      </div>
    </>
  );
}
