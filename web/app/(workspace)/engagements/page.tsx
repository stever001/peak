import { EngagementList } from "@/components/engagement-list";
import { PageHeader } from "@/components/page-header";
import { apiGet, requireConsultant, type Engagement } from "@/lib/api";

export default async function EngagementsPage() {
  await requireConsultant();
  const { engagements } = await apiGet<{ engagements: Engagement[] }>("/engagements");
  return (
    <>
      <PageHeader title="Engagements"
                  intro="Every engagement across all clients. Add a new engagement from its client's page." />
      <EngagementList engagements={engagements}
                      empty="No engagements yet. Open a client to add the first one." />
    </>
  );
}
