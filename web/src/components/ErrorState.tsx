interface Props {
  code: string;
  message: string;
  retry: () => void;
}

export function ErrorState({ code, message, retry }: Props) {
  const isStoreMissing = code === "store_missing";

  return (
    <div className="flex h-screen flex-col items-center justify-center gap-4 px-8">
      <h1 className="text-lg font-medium text-text">
        {isStoreMissing ? "Store not found" : "Something went wrong"}
      </h1>
      <p className="max-w-md text-center text-sm leading-relaxed text-text-secondary">
        {message}
      </p>
      {isStoreMissing && (
        <pre className="rounded border border-border bg-white px-4 py-2 font-mono text-sm text-text">
          skillscope ingest --harness cursor
        </pre>
      )}
      <button
        onClick={retry}
        className="mt-2 rounded border border-border bg-white px-4 py-2 text-sm font-medium text-text transition-colors hover:bg-active-bg"
      >
        Retry
      </button>
    </div>
  );
}
