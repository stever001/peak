import Link from "next/link";

import { DiscoverySection } from "@/components/discovery-section";
import { Detail } from "@/components/field";
import { PageHeader } from "@/components/page-header";
import { StatusBadge } from "@/components/status-badge";
import { apiGet, requireConsultant, type Discovery, type Engagement } from "@/lib/api";

export default async function EngagementPage(props: PageProps<"/engagements/[id]">) {
  await requireConsultant();
  const { id } = await props.params;
  const [{ engagement: e }, { discovery }] = await Promise.all([
    apiGet<{ engagement: Engagement }>(`/engagements/${encodeURIComponent(id)}`),
    apiGet<{ discovery: Discovery }>(`/engagements/${encodeURIComponent(id)}/discovery`),
  ]);
  return (
    <>
      <Link href="/engagements" className="mb-4 inline-flex min-h-touch items-center text-sm font-medium text-brand">
        ← All engagements
      </Link>
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <PageHeader title={e.engagement_label ?? "Untitled engagement"} />
        <Link href={`/engagements/${e.id}/edit`}
              className="inline-flex min-h-touch shrink-0 items-center justify-center rounded-peak border border-line bg-surface px-6 font-medium hover:border-brand">
          Edit engagement
        </Link>
      </div>
      <section className="peak-card">
        <dl className="grid gap-5 sm:grid-cols-2">
          <Detail label="Client" value={
            <Link href={`/clients/${e.client.id}`} className="font-medium text-brand">{e.client.name}</Link>
          } />
          <Detail label="Status" value={<StatusBadge status={e.status} />} />
          <Detail label="Assigned consultant" value={e.assigned_consultant?.name ?? "Unassigned"} />
          <Detail label="Current phase" value={e.current_phase} />
          <div className="sm:col-span-2">
            <Detail label="Objective" value={e.objective && <span className="whitespace-pre-line">{e.objective}</span>} />
          </div>
        </dl>
      </section>
      <DiscoverySection engagementId={e.id} d={discovery} />
    </>
  );
}
