import { updateClient } from "@/app/workspace-actions";
import { ClientForm } from "@/components/client-form";
import { PageHeader } from "@/components/page-header";
import { apiGet, requireConsultant, type Client } from "@/lib/api";

export default async function EditClientPage(props: PageProps<"/clients/[id]/edit">) {
  await requireConsultant();
  const { id } = await props.params;
  const { client } = await apiGet<{ client: Client }>(`/clients/${encodeURIComponent(id)}`);
  return (
    <>
      <PageHeader title={`Edit ${client.organization_label}`} />
      <ClientForm action={updateClient.bind(null, client.id)} client={client}
                  cancelHref={`/clients/${client.id}`} submitLabel="Save changes" />
    </>
  );
}
