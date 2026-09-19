/** Build the prompt-to-skill spine from a stored conversation detail. */

import type { Conversation, SkillActivation, Task } from "./types";

export interface TimelineEntry {
  task: Task | null;
  activations: SkillActivation[];
}

/**
 * Interleave stored tasks with the skill activations attributed to them.
 *
 * Activations whose `task_id` is missing or does not match a recorded task
 * remain visible as unmatched entries rather than disappearing.
 */
export function buildTimeline(conversation: Conversation): TimelineEntry[] {
  const taskIds = new Set(conversation.tasks.map((task) => task.id));
  const assigned = new Map<string, SkillActivation[]>();
  const unmatched: SkillActivation[] = [];

  for (const activation of conversation.skill_activations) {
    const taskId = activation.task_id;
    if (taskId && taskIds.has(taskId)) {
      const existing = assigned.get(taskId);
      if (existing) {
        existing.push(activation);
      } else {
        assigned.set(taskId, [activation]);
      }
    } else {
      unmatched.push(activation);
    }
  }

  const timeline: TimelineEntry[] = conversation.tasks.map((task) => ({
    task,
    activations: assigned.get(task.id) ?? [],
  }));

  if (unmatched.length > 0) {
    timeline.push({ task: null, activations: unmatched });
  }
  return timeline;
}
