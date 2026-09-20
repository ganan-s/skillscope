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
      <div className="flex h-full w-full min-w-0 flex-col">
        <div className="flex h-11 shrink-0 items-center px-4">
          <span className="text-[13px] text-text-secondary">
            Select a repository
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full w-full min-w-0 flex-col">
      <div className="flex h-11 shrink-0 items-center gap-2 px-4">
        <h2 className="truncate text-[13px] font-semibold text-text">
          {group.label}
        </h2>
        <span className="ml-auto shrink-0 text-[11px] tabular-nums text-text-secondary">
          {group.conversations.length} threads
        </span>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-1.5">
        {group.conversations.map((conv) => {
          const isActive = conv.id === selectedConversationId;
          return (
            <button
              key={conv.id}
              type="button"
              onClick={() => onSelectConversation(conv.id)}
              aria-current={isActive ? "true" : undefined}
              className={`relative flex w-full flex-col gap-1 rounded-[10px] py-2 pr-3 pl-3.5 text-left transition-colors duration-150 ${
                isActive ? "bg-accent-soft" : "hover:bg-active-bg"
              }`}
            >
              {isActive && (
                <span
                  aria-hidden="true"
                  className="absolute top-2 bottom-2 left-1 w-[3px] rounded-full bg-accent"
                />
              )}
              <span
                className={`line-clamp-2 text-[13px] leading-snug ${
                  isActive ? "font-semibold text-text" : "text-text"
                }`}
              >
                {conv.title ?? "Untitled"}
              </span>
              <span className="flex items-center gap-1.5 text-[11px] text-text-secondary">
                <span className="tabular-nums">
                  {relativeTime(conv.ended_at ?? conv.started_at)}
                </span>
                <span aria-hidden="true" className="text-text-tertiary">
                  ·
                </span>
                {conv.activation_count > 0 ? (
                  <span className="tabular-nums">
                    {conv.activation_count} skill
                    {conv.activation_count !== 1 ? "s" : ""}
                  </span>
                ) : (
                  <span className="text-text-secondary">No skills</span>
                )}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
