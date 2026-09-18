export function PageHeader({ title, intro }: { title: string; intro?: string }) {
  return (
    <header className="mb-8">
      <h1 className="text-2xl font-semibold text-brand md:text-3xl">{title}</h1>
      {intro && <p className="mt-2 max-w-prose text-base text-ink-muted">{intro}</p>}
    </header>
  );
}
