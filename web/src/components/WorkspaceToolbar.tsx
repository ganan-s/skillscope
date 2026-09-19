import type { UtilityPane } from "../layout/paneLayout";

interface Props {
  repositoryLabel: string | null;
  conversationTitle: string | null;
  collapsed: Record<UtilityPane, boolean>;
  onToggle: (pane: UtilityPane) => void;
}

const paneLabels: Record<UtilityPane, string> = {
  repositories: "repositories",
  threads: "threads",
  inspector: "inspector",
};

export function PaneIcon({ pane }: { pane: UtilityPane }) {
  if (pane === "repositories") {
    return (
      <svg
        aria-hidden="true"
        viewBox="0 0 16 16"
        className="h-4 w-4"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M2.5 3.5h4l1.5 2h5.5v7h-11z" />
      </svg>
    );
  }

  if (pane === "threads") {
    return (
      <svg
        aria-hidden="true"
        viewBox="0 0 16 16"
        className="h-4 w-4"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M3 3.5h10M3 8h10M3 12.5h7" />
      </svg>
    );
  }

  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 16 16"
      className="h-4 w-4"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="8" cy="8" r="5.5" />
      <path d="M8 7.25v3.25M8 5.25h.01" />
    </svg>
  );
}

export function WorkspaceToolbar({
  repositoryLabel,
  conversationTitle,
  collapsed,
  onToggle,
}: Props) {
  return (
    <header className="flex h-12 shrink-0 items-center gap-3 border-b border-border bg-white px-3">
      <h1 className="shrink-0 text-sm font-semibold">Skillscope</h1>
      <div className="min-w-0 flex-1 truncate text-xs text-text-tertiary">
        {repositoryLabel ?? "No repository"}
        {conversationTitle && ` / ${conversationTitle}`}
      </div>
      <div className="flex shrink-0 items-center gap-1">
        {(["repositories", "threads", "inspector"] as const).map((pane) => {
          const action = collapsed[pane] ? "Show" : "Hide";
          const label = paneLabels[pane];
          return (
            <button
              key={pane}
              type="button"
              title={`${action} ${label}`}
              aria-label={`${action} ${label} pane`}
              aria-pressed={!collapsed[pane]}
              onClick={() => onToggle(pane)}
              className="toolbar-button"
            >
              <PaneIcon pane={pane} />
            </button>
          );
        })}
      </div>
    </header>
  );
}
