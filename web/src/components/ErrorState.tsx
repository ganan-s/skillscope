interface Props {
  code: string;
  message: string;
  retry: () => void;
}

export function ErrorState({ code, message, retry }: Props) {
  const isStoreMissing = code === "store_missing";

  return (
    <div className="flex h-screen items-center justify-center p-8">
      <div className="w-full max-w-md rounded-2xl border border-border bg-card p-7 text-center shadow-material">
        <h1 className="text-[17px] font-semibold text-text">
          {isStoreMissing ? "Store not found" : "Something went wrong"}
        </h1>
        <p className="mt-2 text-[13px] leading-relaxed text-text-secondary">
          {message}
        </p>
        {isStoreMissing && (
          <pre className="mt-4 overflow-x-auto rounded-lg border border-border-subtle bg-inset px-3 py-2 text-left font-mono text-[12px] text-text">
            skillscope ingest --harness cursor
          </pre>
        )}
        <button
          type="button"
          onClick={retry}
          className="mt-5 inline-flex h-8 items-center justify-center rounded-lg bg-accent px-4 text-[13px] font-medium text-white transition-opacity duration-150 hover:opacity-90"
        >
          Retry
        </button>
      </div>
    </div>
  );
}
