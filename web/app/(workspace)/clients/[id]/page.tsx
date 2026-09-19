import Link from "next/link";

import { Detail } from "@/components/field";
import { EngagementList } from "@/components/engagement-list";
import { PageHeader } from "@/components/page-header";
import { apiGet, requireConsultant, type Client } from "@/lib/api";

export default async function ClientPage(props: PageProps<"/clients/[id]">) {
  await requireConsultant();
  const { id } = await props.params;
  const { client } = await apiGet<{ client: Client }>(`/clients/${encodeURIComponent(id)}`);
  const address = [
    client.address_line1, client.address_line2,
    [client.city, client.region, client.postal_code].filter(Boolean).join(", "), client.country,
  ].filter(Boolean);

  return (
    <>
      <Link href="/clients" className="mb-4 inline-flex min-h-touch items-center text-sm font-medium text-brand">
        ← All clients
      </Link>
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <PageHeader title={client.organization_label} intro={client.description ?? undefined} />
        <Link href={`/clients/${client.id}/edit`}
              className="inline-flex min-h-touch shrink-0 items-center justify-center rounded-peak border border-line bg-surface px-6 font-medium hover:border-brand">
          Edit client
        </Link>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="peak-card">
          <h2 className="mb-4 text-lg font-semibold">Main contact</h2>
          <dl className="grid gap-4 sm:grid-cols-2">
            <Detail label="Name" value={client.contact_name} />
            <Detail label="Title / role" value={client.contact_title} />
            <Detail label="Email" value={client.contact_email} />
            <Detail label="Phone" value={client.contact_phone} />
          </dl>
        </section>
        <section className="peak-card">
          <h2 className="mb-4 text-lg font-semibold">Address</h2>
          {address.length ? (
            <address className="not-italic">{address.map((line) => <div key={line}>{line}</div>)}</address>
          ) : <p className="text-ink-muted">No address recorded.</p>}
        </section>
      </div>

      <section className="peak-card mt-6">
        <h2 className="mb-4 text-lg font-semibold">Key personnel</h2>
        {client.key_personnel.length ? (
          <ul className="grid gap-3 sm:grid-cols-2">
            {client.key_personnel.map((p, i) => (
              <li key={i} className="rounded-peak border border-line p-4">
                <p className="font-medium">{p.name}</p>
                {p.role && <p className="text-sm text-ink-muted">{p.role}</p>}
                {(p.email || p.phone) && (
                  <p className="mt-1 break-words text-sm">{[p.email, p.phone].filter(Boolean).join(" · ")}</p>
                )}
              </li>
            ))}
          </ul>
        ) : <p className="text-ink-muted">No key personnel recorded.</p>}
      </section>

      <section className="mt-8">
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <h2 className="text-xl font-semibold text-brand">Engagements</h2>
          <Link href={`/engagements/new?client=${encodeURIComponent(client.id)}`} className="peak-button">
            Add engagement
          </Link>
        </div>
        <EngagementList engagements={client.engagements} showClient={false}
                        empty="No engagements for this client yet." />
      </section>
    </>
  );
}
