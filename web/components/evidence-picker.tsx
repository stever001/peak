import type { EvidenceReference } from "@/lib/api";
import { EvidenceProvenance, EvidenceThumb } from "@/components/linked-evidence";

/**
 * Phase 221: choose captures of this engagement that support the observation. Checkboxes named
 * `evidence_ids`; captures already linked are left out (a link is never removed or repeated).
 */
export function EvidencePicker({ available, linkedIds, apiUrl }: {
  available: EvidenceReference[];
  linkedIds: string[];
  apiUrl: string;
}) {
  const choices = available.filter((e) => !linkedIds.includes(e.id));
  return (
    <fieldset className="rounded-peak border border-line p-4">
      <legend className="px-1 font-medium">Supporting photos and documents (optional)</legend>
      <p className="mb-3 text-sm text-ink-muted">
        Link photos captured on this engagement&apos;s tasks. Your observation stays in your own words. A link
        cannot be removed later.
      </p>
      {choices.length === 0 ? (
        <p className="text-sm text-ink-muted">
          {available.length === 0 ? "No photos or documents have been captured on this engagement's tasks yet."
            : "Every captured photo or document is already linked."}
        </p>
      ) : (
        <ul className="max-h-96 space-y-2 overflow-y-auto">
          {choices.map((e) => (
            <li key={e.id} className="flex items-start gap-3 rounded-peak border border-line bg-surface p-2">
              <input type="checkbox" name="evidence_ids" value={e.id} id={`evidence-${e.id}`}
                     className="mt-2 size-5 shrink-0 accent-brand" />
              <EvidenceThumb e={e} apiUrl={apiUrl} />
              <label htmlFor={`evidence-${e.id}`} className="min-w-0 flex-1 cursor-pointer">
                {e.caption ? <span className="block whitespace-pre-line">{e.caption}</span>
                  : <span className="block text-ink-muted">No caption.</span>}
                <EvidenceProvenance e={e} />
              </label>
            </li>
          ))}
        </ul>
      )}
    </fieldset>
  );
}
