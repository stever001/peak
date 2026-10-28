import type { EvidenceKind, TaskEvidence } from "@/lib/api";

/** Phase 220: labels and messages for captured evidence. Shared by the server page and client form. */

export const EVIDENCE_KIND_LABELS: Record<EvidenceKind, string> = {
  photo: "Photo",
  document_photo: "Photo of a document",
};

export const EVIDENCE_KIND_HINTS: Record<EvidenceKind, string> = {
  photo: "Something you saw: a location, a label, a pallet, a screen.",
  document_photo: "A paper or printed item: a packing slip, a count sheet, a receiving log.",
};

export const EVIDENCE_ACCEPT = "image/jpeg,image/png,image/heic,image/heif";

/** The API's refusal codes, in the consultant's words. Unknown codes fall back to a generic line. */
export const EVIDENCE_ERRORS: Record<string, string> = {
  empty_file: "Choose a photo to add.",
  file_too_large: "That file is larger than 20 MB. Take the photo again at a smaller size.",
  unsupported_type: "Add a JPEG, PNG or HEIC photo.",
  invalid_field: "Check the caption and try again.",
  invalid_link: "That record is not part of this task. Choose another.",
  already_replaced: "That photo was already replaced. Replace the newest version instead.",
  upload_expired: "The page was open too long. Try the upload again.",
  invalid_grant: "The upload could not be verified. Reload the page and try again.",
  storage_unavailable: "Photo storage is not available right now. Try again later.",
  phase_not_authorized: "Evidence can be added once the phase is authorized.",
  phase_closed: "This phase is completed, so its evidence is closed.",
  task_resolved: "This task is resolved, so its evidence is closed.",
  task_not_accepted: "Accept this task into the work plan before adding evidence.",
};

export function evidenceError(code: string): string {
  return EVIDENCE_ERRORS[code] ?? "The photo was not added. Try again.";
}

export function formatBytes(n: number): string {
  return n >= 1024 * 1024 ? `${(n / (1024 * 1024)).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`;
}

/** Current captures first in upload order; replaced versions kept separately for history. */
export function splitEvidence(items: TaskEvidence[]) {
  return {
    current: items.filter((e) => !e.superseded_by),
    replaced: items.filter((e) => e.superseded_by),
  };
}
