import { createEngagement } from "@/app/workspace-actions";
import { EngagementForm } from "@/components/engagement-form";
import { PageHeader } from "@/components/page-header";
import {
  apiGet, requireConsultant, type Client, type ClientSummary, type ConsultantOption,
} from "@/lib/api";

/**
 * New engagement. Opened from a client (`?client=`), or for Internal Test / Training without one. The type
 * choice, the internal-test-client chooser and the confirmation are in the form; the server enforces the
 * classification and the Phase 55 client namespace rule either way (Phase 215).
 */
export default async function NewEngagementPage(props: PageProps<"/engagements/new">) {
  const me = await requireConsultant();
  const params = await props.searchParams;
  const clientId = typeof params.client === "string" && params.client ? params.client : null;
  const [opened, { clients: testClients }, { consultants }] = await Promise.all([
    clientId ? apiGet<{ client: Client }>(`/clients/${encodeURIComponent(clientId)}`).then((r) => r.client)
      : Promise.resolve(null),
    apiGet<{ clients: ClientSummary[] }>("/clients?internal_test=true"),
    apiGet<{ consultants: ConsultantOption[] }>("/consultant-options"),
  ]);
  const openedTest = opened?.internal_test === true;
  const initialKind = openedTest || params.type === "internal_test" ? "internal_test" : "real_client";
  const cancelHref = opened ? `/clients/${opened.id}` : "/engagements";
  return (
    <>
      <PageHeader title="Add engagement" />
      <EngagementForm action={createEngagement} consultants={consultants}
                      creation={{
                        realClient: opened && !openedTest ? { id: opened.id, name: opened.organization_label } : null,
                        testClients, initialKind,
                        // Only a client the chooser offers; a retired internal test client is not one.
                        initialTestClientId: openedTest && testClients.some((c) => c.id === opened.id) ? opened.id : "",
                      }}
                      canAssign={me.role === "admin"}
                      cancelHref={cancelHref} submitLabel="Add engagement" />
    </>
  );
}
