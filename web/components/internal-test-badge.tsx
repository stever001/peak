/**
 * Marks an internal_test engagement or client (Phase 215): testing, training and acceptance material,
 * never real-client data. Internal UI chrome only: it never appears in a report rendition.
 */
export function InternalTestBadge({ deleted = false }: { deleted?: boolean }) {
  return (
    <span className="inline-flex shrink-0 rounded-full border border-ink bg-highlight px-3 py-1 text-xs font-semibold text-ink">
      {deleted ? "Internal Test · Deleted" : "Internal Test"}
    </span>
  );
}
