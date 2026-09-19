/** Derive repository groups from stored workspace paths. */

import type { ConversationSummary } from "./types";

export interface RepositoryGroup {
  /** Display label (basename of the workspace path). */
  label: string;
  /** Full workspace path string. */
  path: string;
  /** Conversations belonging to this repository, newest first. */
  conversations: ConversationSummary[];
}

/** Extract the basename from a workspace path string. */
function basename(path: string): string {
  const parts = path.replace(/\/+$/, "").split("/");
  return parts[parts.length - 1] || path;
}

/**
 * Group conversations by workspace path.
 *
 * A conversation with multiple workspace_paths appears under each.
 * A conversation with no workspace_paths appears under "Unknown".
 * Within each group, conversations are ordered newest-first (by ended_at,
 * then started_at, with nulls last).
 */
export function groupByRepository(
  conversations: ConversationSummary[],
): RepositoryGroup[] {
  const groups = new Map<string, ConversationSummary[]>();

  for (const conv of conversations) {
    const paths = conv.workspace_paths.length > 0 ? conv.workspace_paths : [""];
    for (const p of paths) {
      const existing = groups.get(p);
      if (existing) {
        existing.push(conv);
      } else {
        groups.set(p, [conv]);
      }
    }
  }

  const result: RepositoryGroup[] = [];
  for (const [path, convs] of groups) {
    convs.sort((a, b) => {
      const ea = a.ended_at ?? "";
      const eb = b.ended_at ?? "";
      if (ea !== eb) {
        if (!a.ended_at) return 1;
        if (!b.ended_at) return -1;
        return eb.localeCompare(ea);
      }
      const sa = a.started_at ?? "";
      const sb = b.started_at ?? "";
      if (sa !== sb) {
        if (!a.started_at) return 1;
        if (!b.started_at) return -1;
        return sb.localeCompare(sa);
      }
      return 0;
    });

    result.push({
      label: path ? basename(path) : "Unknown",
      path: path || "(no workspace)",
      conversations: convs,
    });
  }

  // Sort groups alphabetically by label
  result.sort((a, b) => a.label.localeCompare(b.label));
  return result;
}
