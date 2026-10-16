import Link from "next/link";

import { EngagementList } from "@/components/engagement-list";
import { PageHeader } from "@/components/page-header";
import { apiGet, requireConsultant, type Engagement } from "@/lib/api";

export default async function EngagementsPage() {
  await requireConsultant();
  const { engagements } = await apiGet<{ engagements: Engagement[] }>("/engagements");
  return (
    <>
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <PageHeader title="Engagements"
                    intro="Every engagement across all clients. Add a new engagement from its client's page." />
        {/* Phase 215: Internal Test / Training needs no real client; the form offers internal test clients. */}
        <Link href="/engagements/new?type=internal_test"
              className="inline-flex min-h-touch shrink-0 items-center justify-center rounded-peak border border-line bg-surface px-6 font-medium hover:border-brand">
          Add internal test engagement
        </Link>
      </div>
      <EngagementList engagements={engagements}
                      empty="No engagements yet. Open a client to add the first one." />
    </>
  );
}
