export function EmptyState() {
  return (
    <div className="flex h-screen items-center justify-center p-8">
      <div className="w-full max-w-md rounded-2xl border border-border bg-card p-7 text-center shadow-material">
        <h1 className="text-[17px] font-semibold text-text">
          No conversations yet
        </h1>
        <p className="mt-2 text-[13px] leading-relaxed text-text-secondary">
          The snapshot store is empty. Run an ingest to populate it with closed
          agent conversations:
        </p>
        <pre className="mt-4 overflow-x-auto rounded-lg border border-border-subtle bg-inset px-3 py-2 text-left font-mono text-[12px] text-text">
          skillscope ingest --harness cursor
        </pre>
      </div>
    </div>
  );
}
