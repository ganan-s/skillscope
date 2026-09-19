import type { Conversation, SkillActivation, Task } from "../api/types";

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

/** Build an interleaved prompt-to-activation timeline. */
function buildTimeline(
  conversation: Conversation,
): { task: Task; activations: SkillActivation[] }[] {
  const timeline: { task: Task; activations: SkillActivation[] }[] = [];
  const activationsByTask = new Map<string | null, SkillActivation[]>();

  for (const act of conversation.skill_activations) {
    const key = act.task_id;
    const existing = activationsByTask.get(key);
    if (existing) {
      existing.push(act);
    } else {
      activationsByTask.set(key, [act]);
    }
  }

  for (const task of conversation.tasks) {
    timeline.push({
      task,
      activations: activationsByTask.get(task.id) ?? [],
    });
  }

  return timeline;
}

export function ThreadCanvas({
  conversation,
  selectedActivationId,
  onSelectActivation,
}: Props) {
  if (!conversation) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <p className="text-sm text-text-tertiary">
          Select a conversation to inspect
        </p>
      </div>
    );
  }

  const timeline = buildTimeline(conversation);

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      {/* Header */}
      <div className="border-border flex h-12 shrink-0 items-center gap-3 border-b bg-white px-6">
        <h2 className="truncate text-sm font-medium">
          {conversation.title ?? "Untitled"}
        </h2>
        <div className="ml-auto flex items-center gap-3 text-xs text-text-tertiary">
          <span>{conversation.task_count} prompts</span>
          <span>{conversation.activation_count} activations</span>
        </div>
      </div>

      {/* Timeline */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto max-w-2xl">
          {timeline.length === 0 && (
            <p className="text-sm text-text-tertiary italic">
              No prompts recorded.
            </p>
          )}

          {timeline.map(({ task, activations }, idx) => (
            <div key={task.id} className={idx > 0 ? "mt-6" : ""}>
              {/* Prompt */}
              <div className="flex items-start gap-3">
                <div className="bg-active mt-1.5 h-2 w-2 shrink-0 rounded-full" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm leading-relaxed text-text">
                    {task.text}
                  </p>
                </div>
              </div>

              {/* Skill activations (causal spine) */}
              {activations.length > 0 ? (
                <div className="border-spine ml-[3px] mt-2 border-l pl-6">
                  {activations.map((act) => (
                    <button
                      key={act.id}
                      onClick={() =>
                        onSelectActivation(
                          act.id === selectedActivationId ? null : act.id,
                        )
                      }
                      className={`mb-2 flex w-full items-center gap-2 rounded px-3 py-2 text-left transition-colors duration-150 ${
                        act.id === selectedActivationId
                          ? "bg-active-bg ring-border ring-1"
                          : "hover:bg-active-bg/50"
                      }`}
                    >
                      <div className="bg-spine mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full" />
                      <div className="min-w-0 flex-1">
                        <span className="text-sm font-medium text-text">
                          {act.name ?? skillBasename(act.path)}
                        </span>
                        <span className="ml-2 text-xs text-text-tertiary">
                          {sourceLabel(act.source)}
                        </span>
                      </div>
                      {act.payload.status === "unavailable" && (
                        <span className="text-xs italic text-text-tertiary">
                          unavailable
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              ) : (
                <div className="ml-[3px] mt-2 pl-6">
                  <p className="text-xs italic text-text-tertiary">
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
