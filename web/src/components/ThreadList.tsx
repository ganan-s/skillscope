import type { RepositoryGroup } from "../api/grouping";
import { relativeTime } from "../utils/time";

interface Props {
  group: RepositoryGroup | null;
  selectedConversationId: string | null;
  onSelectConversation: (id: string) => void;
}

export function ThreadList({
  group,
  selectedConversationId,
  onSelectConversation,
}: Props) {
  if (!group) {
    return (
      <div className="border-border flex h-full w-72 shrink-0 flex-col border-r bg-white">
        <div className="border-border flex h-12 items-center border-b px-4">
          <span className="text-xs text-text-tertiary">Select a repository</span>
        </div>
      </div>
    );
  }

  return (
    <div className="border-border flex h-full w-72 shrink-0 flex-col border-r bg-white">
      <div className="border-border flex h-12 shrink-0 items-center border-b px-4">
        <span className="truncate text-sm font-medium">{group.label}</span>
        <span className="ml-auto text-xs text-text-tertiary">
          {group.conversations.length} threads
        </span>
      </div>
      <div className="flex-1 overflow-y-auto">
        {group.conversations.map((conv) => {
          const isActive = conv.id === selectedConversationId;
          return (
            <button
              key={conv.id}
              onClick={() => onSelectConversation(conv.id)}
              className={`flex w-full flex-col gap-1 border-b px-4 py-3 text-left transition-colors duration-150 ${
                isActive
                  ? "border-border bg-active-bg"
                  : "border-border-subtle hover:bg-active-bg/50"
              }`}
            >
              <span
                className={`truncate text-sm ${isActive ? "font-medium text-active" : "text-text"}`}
              >
                {conv.title ?? "Untitled"}
              </span>
              <div className="flex items-center gap-2">
                <span className="text-xs text-text-tertiary">
                  {relativeTime(conv.ended_at ?? conv.started_at)}
                </span>
                {conv.activation_count > 0 ? (
                  <span className="text-xs text-text-secondary">
                    {conv.activation_count} skill
                    {conv.activation_count !== 1 ? "s" : ""}
                  </span>
                ) : (
                  <span className="text-xs text-text-tertiary italic">
                    No skills
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
