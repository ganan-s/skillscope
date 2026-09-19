import type { SkillActivation } from "../api/types";

interface Props {
  activation: SkillActivation;
  onClose: () => void;
}

function sourceLabel(source: string): string {
  switch (source) {
    case "user":
      return "User";
    case "cursor-builtin":
      return "Built-in";
    case "agents":
      return "Agents";
    case "project":
      return "Project";
    default:
      return "Unknown";
  }
}

export function EvidenceInspector({ activation, onClose }: Props) {
  return (
    <div className="flex h-full w-full min-w-0 flex-col">
      {/* Header */}
      <div className="flex h-11 shrink-0 items-center gap-2 px-3 pl-4">
        <h2 className="truncate text-[13px] font-semibold text-text">
          {activation.name ?? "Unnamed skill"}
        </h2>
        <button
          type="button"
          onClick={onClose}
          className="toolbar-button ml-auto shrink-0"
          aria-label="Close inspector"
          title="Close inspector"
        >
          <svg
            aria-hidden="true"
            viewBox="0 0 12 12"
            className="h-3 w-3"
            fill="currentColor"
          >
            <path d="M2.5 1.1L6 4.6l3.5-3.5 1.4 1.4L7.4 6l3.5 3.5-1.4 1.4L6 7.4l-3.5 3.5-1.4-1.4L4.6 6 1.1 2.5z" />
          </svg>
        </button>
      </div>

      {/* Content */}
      <div className="min-h-0 flex-1 overflow-y-auto px-4 pt-2 pb-4">
        {/* Metadata */}
        <dl className="grid grid-cols-[5.25rem_minmax(0,1fr)] items-baseline gap-x-3 gap-y-2">
          <MetaRow label="Source" value={sourceLabel(activation.source)} />
          <MetaRow label="Path" value={activation.path} mono />
          {activation.description && (
            <MetaRow label="Description" value={activation.description} />
          )}
          <MetaRow label="Provenance" value={activation.time_provenance} />
          {activation.activated_at && (
            <MetaRow
              label="Activated"
              value={new Date(activation.activated_at).toLocaleString()}
            />
          )}
          <MetaRow label="Sequence" value={String(activation.sequence)} />
        </dl>

        {/* Payload */}
        <section className="mt-5">
          <h3 className="sticky top-0 z-10 -mx-4 bg-pane px-4 pt-2 pb-2 text-[11px] font-semibold tracking-[0.08em] uppercase text-text-secondary">
            Captured Content
          </h3>
          {activation.payload.status === "captured" &&
          activation.payload.content ? (
            <pre className="max-h-96 overflow-auto rounded-lg border border-border bg-inset p-3 font-mono text-[11.5px] leading-relaxed text-text">
              {activation.payload.content}
            </pre>
          ) : (
            <div className="rounded-lg border border-border-subtle bg-inset p-3">
              <p className="text-[12px] text-text-secondary">
                Content unavailable
                {activation.payload.unavailable_reason &&
                  `: ${activation.payload.unavailable_reason}`}
              </p>
            </div>
          )}
          {activation.payload.sha256 && (
            <p className="mt-2 font-mono text-[11px] break-all text-text-secondary">
              sha256: {activation.payload.sha256.slice(0, 16)}...
            </p>
          )}
          {activation.payload.byte_length != null && (
            <p className="font-mono text-[11px] tabular-nums text-text-secondary">
              {activation.payload.byte_length} bytes
            </p>
          )}
        </section>

        {/* Resource Reads */}
        {activation.resource_reads.length > 0 && (
          <section className="mt-5">
            <h3 className="sticky top-0 z-10 -mx-4 bg-pane px-4 pt-2 pb-2 text-[11px] font-semibold tracking-[0.08em] uppercase text-text-secondary">
              Resource Reads ({activation.resource_reads.length})
            </h3>
            <ul className="space-y-1.5">
              {activation.resource_reads.map((rr) => (
                <li
                  key={rr.id}
                  className="rounded-lg border border-border-subtle px-3 py-2"
                >
                  <p className="truncate font-mono text-[11.5px] text-text">
                    {rr.path}
                  </p>
                  <p className="mt-0.5 text-[11px] text-text-secondary">
                    {rr.payload.status === "captured"
                      ? `${rr.payload.byte_length ?? "?"} bytes`
                      : `unavailable: ${rr.payload.unavailable_reason ?? "unknown"}`}
                  </p>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </div>
  );
}

function MetaRow({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <>
      <dt className="text-[10px] font-semibold tracking-[0.06em] uppercase text-text-secondary">
        {label}
      </dt>
      <dd
        className={`min-w-0 text-text ${
          mono ? "font-mono text-[11.5px] break-all" : "text-[12.5px]"
        }`}
      >
        {value}
      </dd>
    </>
  );
}
