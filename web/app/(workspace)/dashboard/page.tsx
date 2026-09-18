import Link from "next/link";

import { PageHeader } from "@/components/page-header";
import { RoleBadge } from "@/components/role-badge";
import { requireConsultant } from "@/lib/api";

export default async function DashboardPage() {
  const me = await requireConsultant();
  const firstName = me.name.split(" ")[0];

  return (
    <>
      <PageHeader title="Peak Consultant Workspace" />
      <section className="peak-card mb-6 flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm text-ink-muted">Signed in as</p>
          <p className="text-xl font-semibold">{me.name}</p>
          <p className="break-all text-sm text-ink-muted">{me.email}</p>
        </div>
        <RoleBadge role={me.role} />
      </section>

      <section className="peak-card">
        <h2 className="mb-3 text-lg font-semibold">Welcome, {firstName}</h2>
        <p className="mb-5 max-w-prose text-ink-muted">
          This is the workspace for Peak client engagements. Every consultant can work on every
          client and engagement.
        </p>
        <ul className="grid gap-3 sm:grid-cols-2">
          <li>
            <Link href="/clients" className="flex min-h-touch items-center rounded-peak border border-line px-4 py-3 hover:border-brand">
              <span><strong className="block text-brand">Clients</strong>
                <span className="text-sm text-ink-muted">The organizations Peak works with</span></span>
            </Link>
          </li>
          <li>
            <Link href="/engagements" className="flex min-h-touch items-center rounded-peak border border-line px-4 py-3 hover:border-brand">
              <span><strong className="block text-brand">Engagements</strong>
                <span className="text-sm text-ink-muted">Work for a client; a client can have several</span></span>
            </Link>
          </li>
          {me.role === "admin" && (
            <li>
              <Link href="/consultants" className="flex min-h-touch items-center rounded-peak border border-line px-4 py-3 hover:border-brand">
                <span><strong className="block text-brand">Consultants</strong>
                  <span className="text-sm text-ink-muted">Add consultant accounts (Admin)</span></span>
              </Link>
            </li>
          )}
        </ul>
      </section>
    </>
  );
}
