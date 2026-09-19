import Link from "next/link";

import { createEngagement } from "@/app/workspace-actions";
import { EngagementForm } from "@/components/engagement-form";
import { PageHeader } from "@/components/page-header";
import { apiGet, requireConsultant, type Client, type ConsultantOption } from "@/lib/api";

export default async function NewEngagementPage(props: PageProps<"/engagements/new">) {
  await requireConsultant();
  const clientId = (await props.searchParams).client;
  if (typeof clientId !== "string" || !clientId) {
    return (
      <>
        <PageHeader title="Add engagement" />
        <div className="peak-card text-ink-muted">
          Engagements are added from a client. <Link href="/clients" className="font-medium text-brand">Choose a client</Link>.
        </div>
      </>
    );
  }
  const [{ client }, { consultants }] = await Promise.all([
    apiGet<{ client: Client }>(`/clients/${encodeURIComponent(clientId)}`),
    apiGet<{ consultants: ConsultantOption[] }>("/consultant-options"),
  ]);
  return (
    <>
      <PageHeader title="Add engagement" />
      <EngagementForm action={createEngagement} consultants={consultants}
                      client={{ id: client.id, name: client.organization_label }}
                      cancelHref={`/clients/${client.id}`} submitLabel="Add engagement" />
    </>
  );
}
