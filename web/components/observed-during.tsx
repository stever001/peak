import Link from "next/link";

import type { ObservationOrigin } from "@/lib/api";

/** Phase 222: where a work observation was made, linked to its task. Phase 224: or written after. */
export function ObservedDuring({ origin }: { origin: ObservationOrigin }) {
  const task = [origin.task_sequence != null && `Task ${origin.task_sequence}`, origin.task_title]
    .filter(Boolean).join(": ") || "a phase task";
  return (
    <span className="flex flex-wrap items-center gap-x-1">
      {origin.written_after_work ? "Written after the work on:" : "Observed during:"}
      <Link href={`/phases/${origin.phase_id}/tasks/${origin.task_id}`}
            className="inline-flex min-h-touch items-center font-medium text-brand">
        {task}
      </Link>
      {origin.phase_title && <span>· {origin.phase_title}</span>}
    </span>
  );
}
