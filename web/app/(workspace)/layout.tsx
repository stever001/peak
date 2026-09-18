import { logout } from "@/app/actions";
import { PeakMark } from "@/components/peak-mark";
import { RoleBadge } from "@/components/role-badge";
import { BottomNav, SidebarNav } from "@/components/workspace-nav";
import { requireConsultant } from "@/lib/api";

export default async function WorkspaceLayout({ children }: LayoutProps<"/">) {
  const me = await requireConsultant();
  const isAdmin = me.role === "admin";

  return (
    <div className="min-h-dvh md:pl-sidebar">
      {/* Tablet/desktop: persistent sidebar */}
      <aside className="fixed inset-y-0 left-0 hidden w-sidebar flex-col bg-brand p-4 text-on-brand md:flex">
        <div className="mb-8 flex items-center gap-3 px-2 pt-2">
          <PeakMark inverted />
          <div className="leading-tight">
            <p className="text-lg font-semibold">Peak</p>
            <p className="text-sm text-on-brand/75">Consultant Workspace</p>
          </div>
        </div>
        <SidebarNav isAdmin={isAdmin} />
        <div className="mt-auto border-t border-on-brand/20 px-2 pt-4">
          <p className="truncate font-medium">{me.name}</p>
          <div className="mt-1 mb-3"><RoleBadge role={me.role} /></div>
          <form action={logout}>
            <button type="submit"
                    className="min-h-touch w-full rounded-peak border border-on-brand/40 px-4 text-base font-medium hover:bg-brand-strong">
              Sign out
            </button>
          </form>
        </div>
      </aside>

      {/* Phone: compact top bar */}
      <header className="sticky top-0 z-10 flex items-center justify-between gap-3 bg-brand px-4 py-2 text-on-brand md:hidden">
        <div className="flex min-w-0 items-center gap-3">
          <PeakMark inverted />
          <p className="truncate font-medium">{me.name}</p>
        </div>
        <form action={logout}>
          <button type="submit" className="min-h-touch rounded-peak px-3 text-base font-medium hover:bg-brand-strong">
            Sign out
          </button>
        </form>
      </header>

      <main className="mx-auto w-full max-w-5xl px-4 pt-6 pb-28 md:px-8 md:py-10">{children}</main>

      <BottomNav isAdmin={isAdmin} />
    </div>
  );
}
