import Link from "next/link";

import type { EvidenceReference, LinkedEvidence } from "@/lib/api";
import { EVIDENCE_KIND_LABELS } from "@/lib/evidence";
import { formatDate } from "@/lib/labels";

/** Phase 221: a capture's provenance line: kind, originating task and date. */
export function EvidenceProvenance({ e }: { e: EvidenceReference }) {
  return (
    <span className="block text-sm text-ink-muted">
      <span className="block">{[EVIDENCE_KIND_LABELS[e.evidence_kind], e.created_at && formatDate(e.created_at)].filter(Boolean).join(" · ")}</span>
      <Link href={`/phases/${e.task.phase_id}/tasks/${e.task.id}#evidence`} className="inline-flex min-h-touch items-center font-medium text-brand">
        {e.task.title ?? "Task"}
      </Link>
    </span>
  );
}

export function EvidenceThumb({ e, apiUrl }: { e: EvidenceReference; apiUrl: string }) {
  const src = `${apiUrl}${e.content_path}`;
  return (
    <a href={src} target="_blank" rel="noreferrer noopener" className="shrink-0">
      {/* Served by the API from a short-lived signed URL; the original bytes, unchanged. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={src} alt={e.caption ?? EVIDENCE_KIND_LABELS[e.evidence_kind]} loading="lazy"
           referrerPolicy="no-referrer"
           className="h-20 w-24 rounded-peak border border-line bg-canvas object-contain" />
    </a>
  );
}

/**
 * Phase 221: the captures a consultant linked to an observation, as they were chosen. A capture
 * replaced since stays linked and is labelled; the newer capture is never shown in its place.
 */
export function LinkedEvidenceList({ items, apiUrl }: { items: LinkedEvidence[]; apiUrl: string }) {
  if (items.length === 0) return null;
  return (
    <div className="mt-3">
      <p className="text-sm font-medium">Supporting photos and documents ({items.length})</p>
      <ul className="mt-2 space-y-2">
        {items.map((e) => (
          <li key={e.id} className={`flex gap-3 rounded-peak border border-line p-2 ${e.superseded ? "bg-canvas" : "bg-surface"}`}>
            <EvidenceThumb e={e} apiUrl={apiUrl} />
            <div className="min-w-0 flex-1">
              {e.superseded && (
                <p className="text-sm font-semibold text-ink-muted">Replaced on its task since it was linked</p>
              )}
              {e.caption ? <p className="whitespace-pre-line">{e.caption}</p>
                : <p className="text-ink-muted">No caption.</p>}
              <EvidenceProvenance e={e} />
              <a href={`${apiUrl}${e.content_path}`} target="_blank" rel="noreferrer noopener"
                 className="inline-flex min-h-touch items-center text-sm font-medium text-brand">
                Open full size
              </a>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
