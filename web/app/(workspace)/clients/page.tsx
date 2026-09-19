import Link from "next/link";

import { PageHeader } from "@/components/page-header";
import { apiGet, requireConsultant, type ClientSummary } from "@/lib/api";

export default async function ClientsPage(props: PageProps<"/clients">) {
  await requireConsultant();
  const q = (await props.searchParams).q;
  const query = typeof q === "string" ? q.trim() : "";
  const { clients } = await apiGet<{ clients: ClientSummary[] }>(
    `/clients${query ? `?q=${encodeURIComponent(query)}` : ""}`,
  );

  return (
    <>
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <PageHeader title="Clients" />
        <Link href="/clients/new" className="peak-button shrink-0">Add client</Link>
      </div>
      <form role="search" action="/clients" className="mb-6 flex gap-3">
        <label htmlFor="q" className="sr-only">Search clients</label>
        <input id="q" name="q" type="search" defaultValue={query}
               placeholder="Search by company, city or contact" className="peak-input" />
        <button type="submit"
                className="min-h-touch shrink-0 rounded-peak border border-line bg-surface px-5 font-medium hover:border-brand">
          Search
        </button>
      </form>
      {clients.length === 0 ? (
        <div className="peak-card text-ink-muted">
          {query ? `No clients match “${query}”.` : "No clients yet. Add the first one."}
        </div>
      ) : (
        <ul className="grid gap-3 lg:grid-cols-2">
          {clients.map((c) => (
            <li key={c.id}>
              <Link href={`/clients/${c.id}`}
                    className="flex min-h-20 flex-col justify-center gap-1 rounded-peak border border-line bg-surface px-5 py-4 hover:border-brand">
                <span className="text-lg font-semibold text-brand">{c.organization_label}</span>
                <span className="text-sm text-ink-muted">
                  {[c.city, c.country].filter(Boolean).join(", ") || "No location"}
                  {c.contact_name ? ` · ${c.contact_name}` : ""}
                  {` · ${c.engagement_count} ${c.engagement_count === 1 ? "engagement" : "engagements"}`}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
