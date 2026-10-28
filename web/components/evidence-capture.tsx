"use client";

import { useState } from "react";

import type { EvidenceKind } from "@/lib/api";
import { EVIDENCE_ACCEPT, EVIDENCE_KIND_HINTS, EVIDENCE_KIND_LABELS, formatBytes } from "@/lib/evidence";

const KINDS: EvidenceKind[] = ["photo", "document_photo"];
const CAPTION_LIMIT = 500;

/**
 * Phase 220: add a photo or a photo of a document to a task. A plain form posted straight to the
 * API with a short-lived signed grant (photos are too large for the web tier); the API sends the
 * browser back to this task. No interpretation: the consultant's caption says what it shows.
 */
export function EvidenceForm({ action, grant, maxBytes, records, replacing }: {
  /** Absolute API upload URL. */
  action: string;
  grant: string;
  maxBytes: number;
  /** Current records of this task the capture may be linked to. */
  records: { id: string; label: string }[];
  /** Replacing an earlier capture: its id and kind. The earlier one is kept, marked as replaced. */
  replacing?: { id: string; kind: EvidenceKind };
}) {
  const [kind, setKind] = useState<EvidenceKind>(replacing?.kind ?? "photo");
  const [problem, setProblem] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const suffix = replacing ? `-${replacing.id}` : "";

  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    const file = (e.currentTarget.elements.namedItem("file") as HTMLInputElement).files?.[0];
    const issue = !file ? "Choose a photo to add."
      : file.size > maxBytes ? `That file is ${formatBytes(file.size)}. The limit is ${formatBytes(maxBytes)}.`
      : null;
    if (issue) {
      e.preventDefault();
      setProblem(issue);
      return;
    }
    setProblem(null);
    setPending(true);
  }

  return (
    <form action={action} method="post" encType="multipart/form-data" onSubmit={onSubmit} className="space-y-4">
      <input type="hidden" name="grant" value={grant} />
      <input type="hidden" name="respond" value="redirect" />
      {replacing && <input type="hidden" name="supersedes_evidence_id" value={replacing.id} />}
      {replacing ? (
        <>
          <input type="hidden" name="evidence_kind" value={kind} />
          <p className="rounded-peak bg-canvas px-4 py-3 text-sm">
            The earlier {EVIDENCE_KIND_LABELS[kind].toLowerCase()} stays in the history, marked as replaced.
          </p>
        </>
      ) : (
        <fieldset>
          <legend className="peak-label">What is it?</legend>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {KINDS.map((k) => (
              <label key={k}
                     className={`flex min-h-touch cursor-pointer flex-col justify-center rounded-peak border px-3 py-2 ${k === kind ? "border-brand bg-canvas" : "border-line bg-surface"}`}>
                <span className="flex items-center gap-2 font-medium">
                  <input type="radio" name="evidence_kind" value={k} checked={k === kind}
                         onChange={() => setKind(k)} className="size-5 accent-brand" />
                  {EVIDENCE_KIND_LABELS[k]}
                </span>
                <span className="mt-1 text-sm text-ink-muted">{EVIDENCE_KIND_HINTS[k]}</span>
              </label>
            ))}
          </div>
        </fieldset>
      )}
      <div>
        <label htmlFor={`evidence-file${suffix}`} className="peak-label">Photo</label>
        <input id={`evidence-file${suffix}`} name="file" type="file" accept={EVIDENCE_ACCEPT} required
               className="block min-h-touch w-full rounded-peak border border-line bg-surface px-3 py-2 text-base file:mr-3 file:min-h-10 file:rounded-peak file:border-0 file:bg-canvas file:px-3 file:font-medium file:text-brand" />
        <p className="mt-1 text-sm text-ink-muted">
          Take a photo or choose one. JPEG, PNG or HEIC, up to {formatBytes(maxBytes)}. The original is kept as taken.
        </p>
      </div>
      <div>
        <label htmlFor={`evidence-caption${suffix}`} className="peak-label">What it shows (optional)</label>
        <textarea id={`evidence-caption${suffix}`} name="caption" rows={2} maxLength={CAPTION_LIMIT}
                  className="peak-input" placeholder="For example: dock 3 receiving log, 14 Oct" />
      </div>
      {records.length > 0 && (
        <div>
          <label htmlFor={`evidence-record${suffix}`} className="peak-label">Related record (optional)</label>
          <select id={`evidence-record${suffix}`} name="task_record_id" defaultValue="" className="peak-input">
            <option value="">None</option>
            {records.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
          </select>
        </div>
      )}
      {problem && (
        <p role="alert" className="rounded-peak border-l-4 border-attention bg-canvas px-4 py-3 text-sm">{problem}</p>
      )}
      <button type="submit" disabled={pending}
              className="min-h-touch rounded-peak bg-brand px-5 font-semibold text-white disabled:opacity-60">
        {pending ? "Uploading…" : replacing ? "Replace" : "Add to this task"}
      </button>
    </form>
  );
}
