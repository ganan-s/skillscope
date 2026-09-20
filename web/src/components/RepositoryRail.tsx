import { useState } from "react";
import type { RepositoryGroup } from "../api/grouping";

interface Props {
  groups: RepositoryGroup[];
  selectedConversationId: string | null;
  onSelectConversation: (id: string) => void;
}

export function RepositoryRail({
  groups,
  selectedConversationId,
  onSelectConversation,
}: Props) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  const toggle = (path: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  return (
    <nav className="flex h-full w-full min-w-0 flex-col">
      <div className="flex h-11 shrink-0 items-center px-4">
        <h2 className="text-[11px] font-semibold tracking-[0.08em] uppercase text-text-secondary">
          Repositories
        </h2>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-2">
        {groups.map((group) => {
          const isCollapsed = collapsed.has(group.path);
          const isActive = group.conversations.some(
            (c) => c.id === selectedConversationId,
          );

          return (
            <button
              key={group.path}
              type="button"
              onClick={() => {
                toggle(group.path);
                if (isCollapsed && group.conversations.length > 0) {
                  onSelectConversation(group.conversations[0].id);
                }
              }}
              aria-expanded={!isCollapsed}
              aria-current={isActive ? "true" : undefined}
              className={`flex w-full items-center gap-1.5 rounded-lg px-2 py-1.5 text-left text-[13px] transition-colors duration-150 ${
                isActive
                  ? "bg-accent-soft font-semibold text-text"
                  : "text-text-secondary hover:bg-active-bg"
              }`}
              title={group.path}
            >
              <svg
                aria-hidden="true"
                className={`h-2.5 w-2.5 shrink-0 text-text-tertiary transition-transform duration-150 ${
                  isCollapsed ? "" : "rotate-90"
                }`}
                viewBox="0 0 12 12"
                fill="currentColor"
              >
                <path d="M4 2l4 4-4 4z" />
              </svg>
              <span className="truncate">{group.label}</span>
              <span className="ml-auto shrink-0 pl-2 text-[11px] tabular-nums text-text-secondary">
                {group.conversations.length}
              </span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
