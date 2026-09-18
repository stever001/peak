import { PageHeader } from "@/components/page-header";
import { requireConsultant } from "@/lib/api";

export default async function EngagementsPage() {
  await requireConsultant();
  return (
    <>
      <PageHeader title="Engagements" />
      <div className="peak-card text-ink-muted">
        Engagements are coming next. Each client will be able to have several engagements.
      </div>
    </>
  );
}
