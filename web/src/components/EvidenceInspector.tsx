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
    <div className="border-border flex h-full w-96 shrink-0 flex-col border-l bg-white shadow-sm">
      {/* Header */}
      <div className="border-border flex h-12 shrink-0 items-center justify-between border-b px-4">
        <span className="truncate text-sm font-medium">
          {activation.name ?? "Unnamed skill"}
        </span>
        <button
          onClick={onClose}
          className="flex h-6 w-6 items-center justify-center rounded text-text-tertiary transition-colors hover:bg-active-bg hover:text-text"
          aria-label="Close inspector"
        >
          <svg viewBox="0 0 12 12" className="h-3 w-3" fill="currentColor">
            <path d="M2.5 1.1L6 4.6l3.5-3.5 1.4 1.4L7.4 6l3.5 3.5-1.4 1.4L6 7.4l-3.5 3.5-1.4-1.4L4.6 6 1.1 2.5z" />
          </svg>
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {/* Metadata */}
        <div className="space-y-3">
          <MetaRow label="Source" value={sourceLabel(activation.source)} />
          <MetaRow label="Path" value={activation.path} mono />
          {activation.description && (
            <MetaRow label="Description" value={activation.description} />
          )}
          <MetaRow
            label="Provenance"
            value={activation.time_provenance}
          />
          {activation.activated_at && (
            <MetaRow
              label="Activated"
              value={new Date(activation.activated_at).toLocaleString()}
            />
          )}
          <MetaRow label="Sequence" value={String(activation.sequence)} />
        </div>

        {/* Payload */}
        <div className="mt-6">
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-widest text-text-tertiary">
            Captured Content
          </h4>
          {activation.payload.status === "captured" &&
          activation.payload.content ? (
            <pre className="bg-surface max-h-80 overflow-auto rounded border border-border p-3 font-mono text-xs leading-relaxed text-text">
              {activation.payload.content}
            </pre>
          ) : (
            <div className="rounded border border-border-subtle bg-surface p-3">
              <p className="text-xs italic text-text-tertiary">
                Content unavailable
                {activation.payload.unavailable_reason &&
                  `: ${activation.payload.unavailable_reason}`}
              </p>
            </div>
          )}
          {activation.payload.sha256 && (
            <p className="mt-1 font-mono text-xs text-text-tertiary">
              sha256: {activation.payload.sha256.slice(0, 16)}...
            </p>
          )}
          {activation.payload.byte_length != null && (
            <p className="font-mono text-xs text-text-tertiary">
              {activation.payload.byte_length} bytes
            </p>
          )}
        </div>

        {/* Resource Reads */}
        {activation.resource_reads.length > 0 && (
          <div className="mt-6">
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-widest text-text-tertiary">
              Resource Reads ({activation.resource_reads.length})
            </h4>
            <div className="space-y-2">
              {activation.resource_reads.map((rr) => (
                <div
                  key={rr.id}
                  className="rounded border border-border-subtle p-3"
                >
                  <p className="truncate font-mono text-xs text-text">
                    {rr.path}
                  </p>
                  <p className="mt-1 text-xs text-text-tertiary">
                    {rr.payload.status === "captured"
                      ? `${rr.payload.byte_length ?? "?"} bytes`
                      : `unavailable: ${rr.payload.unavailable_reason ?? "unknown"}`}
                  </p>
                </div>
              ))}
            </div>
          </div>
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
    <div>
      <dt className="text-xs font-medium uppercase tracking-wider text-text-tertiary">
        {label}
      </dt>
      <dd
        className={`mt-0.5 text-sm text-text ${mono ? "break-all font-mono text-xs" : ""}`}
      >
        {value}
      </dd>
    </div>
  );
}
