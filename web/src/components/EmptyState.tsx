export function EmptyState() {
  return (
    <div className="flex h-screen flex-col items-center justify-center gap-4 px-8">
      <h1 className="text-lg font-medium text-text">No conversations yet</h1>
      <p className="max-w-md text-center text-sm leading-relaxed text-text-secondary">
        The snapshot store is empty. Run an ingest to populate it with closed
        agent conversations:
      </p>
      <pre className="rounded border border-border bg-white px-4 py-2 font-mono text-sm text-text">
        skillscope ingest --harness cursor
      </pre>
    </div>
  );
}
