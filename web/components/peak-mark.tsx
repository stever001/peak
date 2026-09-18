/** Simple Peak mark: a summit on the brand colour. */
export function PeakMark({ inverted = false }: { inverted?: boolean }) {
  return (
    <svg viewBox="0 0 40 40" className="size-10 shrink-0" aria-hidden="true">
      <rect width="40" height="40" rx="10" className={inverted ? "fill-on-brand" : "fill-brand"} />
      <path d="M8 29 L17 14 L22 21 L25 17 L32 29 Z" className="fill-accent" />
      <path d="M17 14 L20 19 L14.5 19 Z" className={inverted ? "fill-brand" : "fill-on-brand"} />
    </svg>
  );
}
