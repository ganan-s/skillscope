/** Build the prompt-to-skill spine from a stored conversation detail. */

import type {
  Conversation,
  SkillActivation,
  SkillLoadFailure,
  Task,
} from "./types";

export interface TimelineEntry {
  task: Task | null;
  activations: SkillActivation[];
  loadFailures: SkillLoadFailure[];
}

/**
 * Interleave stored tasks with the skill activations attributed to them.
 *
 * Activations whose `task_id` is missing or does not match a recorded task
 * remain visible as unmatched entries rather than disappearing. Failed
 * SKILL.md reads join by turn index the same way.
 */
export function buildTimeline(conversation: Conversation): TimelineEntry[] {
  const taskIds = new Set(conversation.tasks.map((task) => task.id));
  const assigned = new Map<string, SkillActivation[]>();
  const unmatched: SkillActivation[] = [];
  const failuresByTask = new Map<string, SkillLoadFailure[]>();
  const unmatchedFailures: SkillLoadFailure[] = [];

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

  const turnToTaskId = new Map(
    conversation.tasks.map((task) => [task.turn_index, task.id]),
  );
  for (const failure of conversation.skill_load_failures) {
    const taskId =
      failure.turn_index == null
        ? undefined
        : turnToTaskId.get(failure.turn_index);
    if (taskId && taskIds.has(taskId)) {
      const existing = failuresByTask.get(taskId);
      if (existing) {
        existing.push(failure);
      } else {
        failuresByTask.set(taskId, [failure]);
      }
    } else {
      unmatchedFailures.push(failure);
    }
  }

  const timeline: TimelineEntry[] = conversation.tasks.map((task) => ({
    task,
    activations: assigned.get(task.id) ?? [],
    loadFailures: failuresByTask.get(task.id) ?? [],
  }));

  if (unmatched.length > 0 || unmatchedFailures.length > 0) {
    timeline.push({
      task: null,
      activations: unmatched,
      loadFailures: unmatchedFailures,
    });
  }
  return timeline;
}
