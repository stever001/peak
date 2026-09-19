"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

type Item = { href: string; label: string; icon: string };

const ICONS: Record<string, string> = {
  dashboard: "M4 13h6V4H4v9Zm0 7h6v-5H4v5Zm10 0h6v-9h-6v9Zm0-16v5h6V4h-6Z",
  clients: "M4 21V5l8-2v18M12 7h8v14M7 8h2M7 12h2M7 16h2M15 11h2M15 15h2",
  engagements: "M4 7h16v12H4zM9 7V4h6v3M4 12h16",
  questions: "M9 9a3 3 0 1 1 4 2.8c-.6.3-1 .9-1 1.6V14M12 17.5v.01M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20Z",
  consultants:
    "M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM2 21v-1a6 6 0 0 1 12 0v1M17 11a3 3 0 1 0 0-6M22 21v-1a5 5 0 0 0-4-4.9",
};

function Icon({ name }: { name: string }) {
  return (
    <svg viewBox="0 0 24 24" className="size-6 shrink-0" fill="none" stroke="currentColor"
         strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={ICONS[name]} />
    </svg>
  );
}

export function navItems(isAdmin: boolean): Item[] {
  const items: Item[] = [
    { href: "/dashboard", label: "Dashboard", icon: "dashboard" },
    { href: "/clients", label: "Clients", icon: "clients" },
    { href: "/engagements", label: "Engagements", icon: "engagements" },
    { href: "/questions", label: "Questions", icon: "questions" },
  ];
  if (isAdmin) items.push({ href: "/consultants", label: "Consultants", icon: "consultants" });
  return items;
}

/** Tablet/desktop: persistent vertical sidebar navigation. */
export function SidebarNav({ isAdmin }: { isAdmin: boolean }) {
  const pathname = usePathname();
  return (
    <nav aria-label="Main" className="flex flex-col gap-1">
      {navItems(isAdmin).map((item) => {
        const active = pathname.startsWith(item.href);
        return (
          <Link key={item.href} href={item.href} aria-current={active ? "page" : undefined}
                className={`flex min-h-touch items-center gap-3 rounded-peak border-l-4 px-4 text-base font-medium ${
                  active
                    ? "border-accent bg-brand-strong text-on-brand"
                    : "border-transparent text-on-brand/85 hover:bg-brand-strong/60"
                }`}>
            <Icon name={item.icon} />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}

/** Phone: fixed bottom tab bar. */
export function BottomNav({ isAdmin }: { isAdmin: boolean }) {
  const pathname = usePathname();
  const items = navItems(isAdmin);
  return (
    <nav aria-label="Main"
         className="fixed inset-x-0 bottom-0 z-10 grid border-t border-line bg-surface pb-[env(safe-area-inset-bottom)] md:hidden"
         style={{ gridTemplateColumns: `repeat(${items.length}, minmax(0, 1fr))` }}>
      {items.map((item) => {
        const active = pathname.startsWith(item.href);
        return (
          <Link key={item.href} href={item.href} aria-current={active ? "page" : undefined}
                className={`flex min-h-16 flex-col items-center justify-center gap-1 border-t-4 text-xs font-medium ${
                  active ? "border-accent text-brand" : "border-transparent text-ink-muted"
                }`}>
            <Icon name={item.icon} />
            <span className="max-w-full truncate px-1">{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
