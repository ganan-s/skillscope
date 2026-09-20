import type { Conversation } from "../api/types";
import { buildTimeline } from "../api/timeline";

interface Props {
  conversation: Conversation | null;
  selectedActivationId: string | null;
  onSelectActivation: (id: string | null) => void;
}

function skillBasename(path: string): string {
  const parts = path.split("/");
  // Return parent directory name if it exists, else the filename
  const idx = parts.lastIndexOf("SKILL.md");
  if (idx > 0) return parts[idx - 1];
  return parts[parts.length - 1] || path;
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

export function ThreadCanvas({
  conversation,
  selectedActivationId,
  onSelectActivation,
}: Props) {
  if (!conversation) {
    return (
      <div className="flex h-full min-w-0 flex-1 items-center justify-center p-8">
        <p className="text-[13px] text-text-secondary">
          Select a conversation to inspect
        </p>
      </div>
    );
  }

  const timeline = buildTimeline(conversation);

  return (
    <div className="flex h-full min-w-0 flex-1 flex-col overflow-hidden">
      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-7">
        <div className="mx-auto max-w-[46rem]">
          <p className="mb-6 text-[11px] tabular-nums text-text-secondary">
            {conversation.task_count} prompts · {conversation.activation_count}{" "}
            activations
          </p>

          {timeline.length === 0 && (
            <p className="text-[13px] text-text-secondary">
              No prompts recorded.
            </p>
          )}

          {timeline.map(({ task, activations }, idx) => (
            <div
              key={task?.id ?? "unmatched-activations"}
              className={idx > 0 ? "mt-7" : ""}
            >
              {task ? (
                <div className="flex items-start gap-3">
                  <span
                    aria-hidden="true"
                    className="mt-2 h-2 w-2 shrink-0 rounded-full bg-text-tertiary"
                  />
                  <div className="min-w-0 flex-1">
                    <p className="text-[15px] leading-[1.6] whitespace-pre-line text-text">
                      {task.text}
                    </p>
                  </div>
                </div>
              ) : (
                <p className="text-[13px] text-text-secondary">
                  {conversation.tasks.length === 0
                    ? "No prompts recorded."
                    : "Skills without a matching prompt"}
                </p>
              )}

              {activations.length > 0 ? (
                <div className="mt-2 ml-[3px] border-l border-spine pl-5">
                  {activations.map((act) => {
                    const isSelected = act.id === selectedActivationId;
                    return (
                      <button
                        key={act.id}
                        type="button"
                        onClick={() =>
                          onSelectActivation(isSelected ? null : act.id)
                        }
                        aria-pressed={isSelected}
                        className={`relative mb-1 flex w-full items-center gap-2 rounded-lg py-1.5 pr-3 pl-3 text-left transition-colors duration-150 ${
                          isSelected ? "bg-accent-soft" : "hover:bg-active-bg"
                        }`}
                      >
                        {isSelected && (
                          <span
                            aria-hidden="true"
                            className="absolute top-1.5 bottom-1.5 left-0.5 w-[3px] rounded-full bg-accent"
                          />
                        )}
                        <span
                          aria-hidden="true"
                          className="h-1.5 w-1.5 shrink-0 rounded-full bg-spine"
                        />
                        <span className="min-w-0 flex-1 truncate">
                          <span
                            className={`text-[13px] text-text ${
                              isSelected ? "font-semibold" : "font-medium"
                            }`}
                          >
                            {act.name ?? skillBasename(act.path)}
                          </span>
                          <span className="ml-2 text-[11px] text-text-secondary">
                            {sourceLabel(act.source)}
                          </span>
                        </span>
                        {act.payload.status === "unavailable" && (
                          <span className="shrink-0 rounded border border-border px-1.5 py-px text-[10px] tracking-wide uppercase text-text-secondary">
                            Unavailable
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              ) : (
                <div className="mt-2 ml-[3px] pl-5">
                  <p className="text-[12px] text-text-secondary">
                    No skills invoked
                  </p>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
