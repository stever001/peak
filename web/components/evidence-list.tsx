import type { TaskEvidence } from "@/lib/api";
import { EVIDENCE_KIND_LABELS, formatBytes, splitEvidence } from "@/lib/evidence";
import { formatDate } from "@/lib/labels";
import { RECORD_KIND_LABELS } from "@/lib/work-plan";

function Capture({ e, apiUrl, muted, children }: {
  e: TaskEvidence; apiUrl: string; muted?: boolean; children?: React.ReactNode;
}) {
  const src = `${apiUrl}${e.content_path}`;
  return (
    <li className={`rounded-peak border border-line p-3 ${muted ? "bg-canvas opacity-75" : "bg-surface"}`}>
      <div className="flex flex-col gap-3 sm:flex-row">
        <a href={src} target="_blank" rel="noreferrer noopener" className="shrink-0">
          {/* Served by the API from a short-lived signed URL; the original bytes, unchanged. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={src} alt={e.caption ?? EVIDENCE_KIND_LABELS[e.evidence_kind]} loading="lazy"
               referrerPolicy="no-referrer"
               className="h-32 w-full rounded-peak border border-line bg-canvas object-contain sm:w-40" />
        </a>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-ink-muted">
            {EVIDENCE_KIND_LABELS[e.evidence_kind]}{muted && " · replaced"}
          </p>
          {e.caption ? <p className="mt-1 whitespace-pre-line">{e.caption}</p>
            : <p className="mt-1 text-ink-muted">No caption.</p>}
          {e.task_record && (
            <p className="mt-1 text-sm text-ink-muted">
              Related record: {RECORD_KIND_LABELS[e.task_record.record_kind]}
              {e.task_record.created_at && `, ${formatDate(e.task_record.created_at)}`}
            </p>
          )}
          <p className="mt-1 text-sm text-ink-muted">
            {[e.uploaded_by && `Added by ${e.uploaded_by}`, formatDate(e.created_at), formatBytes(e.byte_length)]
              .filter(Boolean).join(" · ")}
          </p>
          <a href={src} target="_blank" rel="noreferrer noopener"
             className="mt-1 inline-flex min-h-touch items-center text-sm font-medium text-brand">
            Open full size
          </a>
          {children}
        </div>
      </div>
    </li>
  );
}

/** Phase 220: captured photos and document photos. Shown as captured; never read or scored. */
export function EvidenceList({ items, apiUrl, replaceForm }: {
  items: TaskEvidence[];
  apiUrl: string;
  /** The replace form for a current capture, when capture is open. */
  replaceForm?: (e: TaskEvidence) => React.ReactNode;
}) {
  const { current, replaced } = splitEvidence(items);
  return (
    <div className="space-y-4">
      <ul className="space-y-3">
        {current.map((e) => (
          <Capture key={e.id} e={e} apiUrl={apiUrl}>
            {replaceForm && (
              <details className="mt-2">
                <summary className="inline-flex min-h-touch cursor-pointer items-center text-sm font-medium text-brand">
                  Replace this {EVIDENCE_KIND_LABELS[e.evidence_kind].toLowerCase()}
                </summary>
                <div className="mt-3">{replaceForm(e)}</div>
              </details>
            )}
          </Capture>
        ))}
      </ul>
      {replaced.length > 0 && (
        <details>
          <summary className="inline-flex min-h-touch cursor-pointer items-center text-sm font-medium text-brand">
            Replaced versions ({replaced.length})
          </summary>
          <ul className="mt-3 space-y-3">
            {replaced.map((e) => <Capture key={e.id} e={e} apiUrl={apiUrl} muted />)}
          </ul>
        </details>
      )}
    </div>
  );
}
