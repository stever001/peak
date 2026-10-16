import { createClient } from "@/app/workspace-actions";
import { ClientForm } from "@/components/client-form";
import { PageHeader } from "@/components/page-header";
import { requireConsultant } from "@/lib/api";

export default async function NewClientPage(props: PageProps<"/clients/new">) {
  await requireConsultant();
  // Phase 215: `?internal_test=1` comes from the engagement form's "Create internal test client".
  const internalTest = (await props.searchParams).internal_test === "1";
  return (
    <>
      <PageHeader title={internalTest ? "Add internal test client" : "Add client"} />
      <ClientForm action={createClient} cancelHref={internalTest ? "/engagements/new?type=internal_test" : "/clients"}
                  submitLabel="Add client" internalTestDefault={internalTest} />
    </>
  );
}
