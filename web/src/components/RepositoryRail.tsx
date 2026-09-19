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
    <nav className="border-border flex h-full w-56 shrink-0 flex-col border-r bg-white">
      <div className="border-border flex h-12 shrink-0 items-center border-b px-4">
        <span className="text-xs font-semibold tracking-widest uppercase text-text-tertiary">
          Repositories
        </span>
      </div>
      <div className="flex-1 overflow-y-auto py-1">
        {groups.map((group) => {
          const isCollapsed = collapsed.has(group.path);
          const isActive = group.conversations.some(
            (c) => c.id === selectedConversationId,
          );

          return (
            <div key={group.path}>
              <button
                onClick={() => {
                  toggle(group.path);
                  if (isCollapsed && group.conversations.length > 0) {
                    onSelectConversation(group.conversations[0].id);
                  }
                }}
                className={`flex w-full items-center gap-2 px-4 py-2 text-left text-sm transition-colors duration-150 ${
                  isActive
                    ? "bg-active-bg font-medium text-active"
                    : "text-text-secondary hover:bg-active-bg/50"
                }`}
                title={group.path}
              >
                <svg
                  className={`h-3 w-3 shrink-0 transition-transform duration-150 ${
                    isCollapsed ? "" : "rotate-90"
                  }`}
                  viewBox="0 0 12 12"
                  fill="currentColor"
                >
                  <path d="M4 2l4 4-4 4z" />
                </svg>
                <span className="truncate">{group.label}</span>
                <span className="ml-auto text-xs text-text-tertiary">
                  {group.conversations.length}
                </span>
              </button>
            </div>
          );
        })}
      </div>
    </nav>
  );
}
