import { PageHeader } from "@/components/page-header";
import { requireConsultant } from "@/lib/api";

export default async function ClientsPage() {
  await requireConsultant();
  return (
    <>
      <PageHeader title="Clients" />
      <div className="peak-card text-ink-muted">
        Client records are coming next. You&apos;ll be able to add and edit clients here.
      </div>
    </>
  );
}
