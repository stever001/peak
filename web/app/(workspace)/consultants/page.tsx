import { redirect } from "next/navigation";

import { PageHeader } from "@/components/page-header";
import { RoleBadge } from "@/components/role-badge";
import { apiFetch, requireConsultant, type Consultant } from "@/lib/api";
import { AddConsultantForm } from "./add-consultant-form";

export default async function ConsultantsPage() {
  await requireConsultant();
  // The Python API decides: 403 for anyone who is not an Admin.
  const res = await apiFetch("/consultants");
  if (res.status === 401) redirect("/login");
  if (res.status === 403) redirect("/dashboard");
  if (!res.ok) throw new Error(`Peak API /consultants failed (${res.status})`);
  const { consultants } = (await res.json()) as { consultants: Consultant[] };

  return (
    <>
      <PageHeader title="Consultants"
                  intro="Admins create consultant accounts. New consultants sign in with the email and initial password you set." />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem] lg:items-start">
        <section className="peak-card">
          <h2 className="mb-4 text-lg font-semibold">
            {consultants.length} {consultants.length === 1 ? "account" : "accounts"}
          </h2>
          <ul className="divide-y divide-line">
            {consultants.map((c) => (
              <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 py-4">
                <div className="min-w-0">
                  <p className="font-medium">{c.name}</p>
                  <p className="break-all text-sm text-ink-muted">{c.email}</p>
                </div>
                <RoleBadge role={c.role} />
              </li>
            ))}
          </ul>
        </section>
        <section className="peak-card">
          <h2 className="mb-4 text-lg font-semibold">Add consultant</h2>
          <AddConsultantForm />
        </section>
      </div>
    </>
  );
}
