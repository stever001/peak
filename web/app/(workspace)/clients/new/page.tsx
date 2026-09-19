import { createClient } from "@/app/workspace-actions";
import { ClientForm } from "@/components/client-form";
import { PageHeader } from "@/components/page-header";
import { requireConsultant } from "@/lib/api";

export default async function NewClientPage() {
  await requireConsultant();
  return (
    <>
      <PageHeader title="Add client" />
      <ClientForm action={createClient} cancelHref="/clients" submitLabel="Add client" />
    </>
  );
}
