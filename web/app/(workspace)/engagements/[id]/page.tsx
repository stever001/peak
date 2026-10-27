import Link from "next/link";

import { deleteInternalTestEngagement } from "@/app/workspace-actions";
import { DiscoverySection } from "@/components/discovery-section";
import { Detail } from "@/components/field";
import { InternalTestBadge } from "@/components/internal-test-badge";
import { InternalTestDeleteForm } from "@/components/internal-test-delete-form";
import { PageHeader } from "@/components/page-header";
import { StatusBadge } from "@/components/status-badge";
import { WorkPlanSection } from "@/components/work-plan-section";
import {
  apiGet, requireConsultant, type Discovery, type Engagement, type EngagementPhaseSummary,
} from "@/lib/api";

export default async function EngagementPage(props: PageProps<"/engagements/[id]">) {
  const me = await requireConsultant();
  const { id } = await props.params;
  const [{ engagement: e }, { discovery }, { phases }] = await Promise.all([
    apiGet<{ engagement: Engagement }>(`/engagements/${encodeURIComponent(id)}`),
    apiGet<{ discovery: Discovery }>(`/engagements/${encodeURIComponent(id)}/discovery`),
    apiGet<{ phases: EngagementPhaseSummary[] }>(`/engagements/${encodeURIComponent(id)}/phases`),
  ]);
  return (
    <>
      <Link href="/engagements" className="mb-4 inline-flex min-h-touch items-center text-sm font-medium text-brand">
        ← All engagements
      </Link>
      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <PageHeader title={e.engagement_label ?? "Untitled engagement"} />
          {e.engagement_classification === "internal_test" && <InternalTestBadge deleted={e.source_status === "deleted"} />}
        </div>
        <div className="flex shrink-0 flex-wrap gap-3">
          <Link href={`/engagements/${e.id}/assessment`} className="peak-button">
            Internal assessment
          </Link>
          <Link href={`/engagements/${e.id}/final-report`}
                className="inline-flex min-h-touch shrink-0 items-center justify-center rounded-peak border border-line bg-surface px-6 font-medium hover:border-brand">
            Final report
          </Link>
          <Link href={`/engagements/${e.id}/edit`}
                className="inline-flex min-h-touch shrink-0 items-center justify-center rounded-peak border border-line bg-surface px-6 font-medium hover:border-brand">
            Edit engagement
          </Link>
        </div>
      </div>
      {e.source_status === "deleted" && (
        <p className="peak-card mb-6">
          This internal test engagement was deleted{e.deleted_at ? ` on ${e.deleted_at.slice(0, 10)}` : ""}. Its
          history is kept for audit; it accepts no new work.
        </p>
      )}
      <section className="peak-card">
        <dl className="grid gap-5 sm:grid-cols-2">
          <Detail label="Client" value={
            <Link href={`/clients/${e.client.id}`} className="inline-flex min-h-touch items-center font-medium text-brand">{e.client.name}</Link>
          } />
          <Detail label="Status" value={<StatusBadge status={e.status} />} />
          <Detail label="Assigned consultant" value={e.assigned_consultant?.name ?? "Unassigned"} />
          <Detail label="Current phase" value={e.current_phase} />
          <div className="sm:col-span-2">
            <Detail label="Objective" value={e.objective && <span className="whitespace-pre-line">{e.objective}</span>} />
          </div>
        </dl>
      </section>
      <WorkPlanSection phases={phases} />
      <DiscoverySection engagementId={e.id} d={discovery} />
      {me.role === "admin" && e.engagement_classification === "internal_test" && e.source_status === "active" && (
        <InternalTestDeleteForm action={deleteInternalTestEngagement.bind(null, e.id)}
                                label={e.engagement_label ?? ""} />
      )}
    </>
  );
}
