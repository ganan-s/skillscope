export type UtilityPane = "repositories" | "threads" | "inspector";

export interface PaneLayout {
  widths: Record<UtilityPane, number>;
  collapsed: Record<UtilityPane, boolean>;
}

export const PANE_LAYOUT_KEY = "skillscope:pane-layout:v1";

export const PANE_LIMITS: Record<
  UtilityPane,
  { min: number; max: number }
> = {
  repositories: { min: 184, max: 320 },
  threads: { min: 240, max: 420 },
  inspector: { min: 320, max: 520 },
};

export const DEFAULT_PANE_LAYOUT: PaneLayout = {
  widths: { repositories: 232, threads: 304, inspector: 384 },
  collapsed: { repositories: false, threads: false, inspector: true },
};

type ReadStorage = Pick<Storage, "getItem">;

function clamp(pane: UtilityPane, value: unknown): number {
  const fallback = DEFAULT_PANE_LAYOUT.widths[pane];
  if (typeof value !== "number" || !Number.isFinite(value)) return fallback;
  const { min, max } = PANE_LIMITS[pane];
  return Math.min(max, Math.max(min, value));
}

export function loadPaneLayout(storage?: ReadStorage): PaneLayout {
  try {
    const resolvedStorage =
      storage ??
      (typeof window !== "undefined" ? window.localStorage : undefined);
    if (!resolvedStorage) return DEFAULT_PANE_LAYOUT;
    const parsed = JSON.parse(resolvedStorage.getItem(PANE_LAYOUT_KEY) ?? "");
    return {
      widths: {
        repositories: clamp("repositories", parsed.widths?.repositories),
        threads: clamp("threads", parsed.widths?.threads),
        inspector: clamp("inspector", parsed.widths?.inspector),
      },
      collapsed: {
        repositories: parsed.collapsed?.repositories === true,
        threads: parsed.collapsed?.threads === true,
        inspector: parsed.collapsed?.inspector !== false,
      },
    };
  } catch {
    return DEFAULT_PANE_LAYOUT;
  }
}

export function resizePane(
  layout: PaneLayout,
  pane: UtilityPane,
  width: number,
): PaneLayout {
  return {
    ...layout,
    widths: { ...layout.widths, [pane]: clamp(pane, width) },
  };
}

export function togglePane(
  layout: PaneLayout,
  pane: UtilityPane,
): PaneLayout {
  return {
    ...layout,
    collapsed: {
      ...layout.collapsed,
      [pane]: !layout.collapsed[pane],
    },
  };
}

export function revealPane(
  layout: PaneLayout,
  pane: UtilityPane,
): PaneLayout {
  if (!layout.collapsed[pane]) return layout;
  return {
    ...layout,
    collapsed: { ...layout.collapsed, [pane]: false },
  };
}
