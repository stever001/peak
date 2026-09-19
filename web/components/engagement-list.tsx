import Link from "next/link";

import { StatusBadge } from "@/components/status-badge";
import type { Engagement } from "@/lib/api";

/** Large tappable engagement cards: one column on phone/iPad portrait, two on wide screens. */
export function EngagementList({ engagements, showClient = true, empty }: {
  engagements: Engagement[]; showClient?: boolean; empty: string;
}) {
  if (engagements.length === 0) return <div className="peak-card text-ink-muted">{empty}</div>;
  return (
    <ul className="grid gap-3 lg:grid-cols-2">
      {engagements.map((e) => (
        <li key={e.id}>
          <Link href={`/engagements/${e.id}`}
                className="flex min-h-20 flex-col gap-2 rounded-peak border border-line bg-surface px-5 py-4 hover:border-brand">
            <span className="flex items-start justify-between gap-3">
              <span className="text-lg font-semibold text-brand">{e.engagement_label ?? "Untitled engagement"}</span>
              <StatusBadge status={e.status} />
            </span>
            <span className="text-sm text-ink-muted">
              {[showClient ? e.client.name : null,
                e.assigned_consultant?.name ?? "Unassigned",
                e.current_phase ? `Phase: ${e.current_phase}` : null].filter(Boolean).join(" · ")}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
