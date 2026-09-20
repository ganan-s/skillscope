# Skillscope Workspace Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing dashboard into a Finder-like, system-themed workspace with accessible collapsible and resizable utility panes.

**Architecture:** Keep the existing data store and four content components. Add one pure pane-layout state module, one React hook that persists that state, and focused workspace chrome components for the toolbar, collapsed rails, and resize handles. Styling remains Tailwind-first with a small CSS token layer for system light/dark materials.

**Tech Stack:** React 19, TypeScript 6, Tailwind CSS 4, Vite 8, Node's built-in test runner.

---

## File structure

- Create `web/src/layout/paneLayout.ts`: pane types, constraints, defaults, persistence normalization, and pure state transitions.
- Create `web/tests/paneLayout.test.ts`: deterministic tests for defaults, persistence, clamping, collapse, and reveal behavior.
- Create `web/src/hooks/usePaneLayout.ts`: React state and local-storage synchronization around the pure layout module.
- Create `web/src/components/WorkspaceToolbar.tsx`: unified title bar and pane toggle controls.
- Create `web/src/components/WorkspacePane.tsx`: expanded pane shell, collapsed icon rail, pointer resizing, and keyboard resizing.
- Modify `web/src/App.tsx`: compose the toolbar and pane shells around existing content components.
- Modify `web/src/components/RepositoryRail.tsx`: remove fixed outer sizing and refine repository navigation states.
- Modify `web/src/components/ThreadList.tsx`: remove fixed outer sizing and refine thread rows.
- Modify `web/src/components/ThreadCanvas.tsx`: remove duplicate top header and polish the timeline.
- Modify `web/src/components/EvidenceInspector.tsx`: remove fixed outer sizing and polish metadata/content surfaces.
- Modify `web/src/components/EmptyState.tsx` and `web/src/components/ErrorState.tsx`: use the shared material treatment.
- Modify `web/src/index.css`: system appearance tokens, materials, scrollbar, focus, reduced motion, and base styles.
- Modify `web/package.json`: add a zero-dependency layout test script.

### Task 1: Pure pane layout state

**Files:**
- Create: `web/src/layout/paneLayout.ts`
- Create: `web/tests/paneLayout.test.ts`
- Modify: `web/package.json`

- [ ] **Step 1: Add the failing layout tests**

Create `web/tests/paneLayout.test.ts`:

```ts
import assert from "node:assert/strict";
import test from "node:test";
import {
  DEFAULT_PANE_LAYOUT,
  loadPaneLayout,
  resizePane,
  revealPane,
  togglePane,
} from "../src/layout/paneLayout.ts";

test("invalid persisted state falls back to defaults", () => {
  const storage = { getItem: () => "{bad json" };
  assert.deepEqual(loadPaneLayout(storage), DEFAULT_PANE_LAYOUT);
});

test("persisted widths are clamped and booleans are retained", () => {
  const storage = {
    getItem: () =>
      JSON.stringify({
        widths: { repositories: 999, threads: 20, inspector: 410 },
        collapsed: { repositories: true, threads: false, inspector: false },
      }),
  };
  assert.deepEqual(loadPaneLayout(storage), {
    widths: { repositories: 320, threads: 240, inspector: 410 },
    collapsed: { repositories: true, threads: false, inspector: false },
  });
});

test("resize, toggle, and reveal preserve unrelated pane state", () => {
  const resized = resizePane(DEFAULT_PANE_LAYOUT, "threads", 500);
  assert.equal(resized.widths.threads, 420);
  assert.equal(resized.widths.repositories, 232);

  const collapsed = togglePane(resized, "repositories");
  assert.equal(collapsed.collapsed.repositories, true);

  const revealed = revealPane(collapsed, "inspector");
  assert.equal(revealed.collapsed.inspector, false);
  assert.equal(revealed.collapsed.repositories, true);
});
```

Add the script to `web/package.json`:

```json
"test": "node --experimental-strip-types --test tests/paneLayout.test.ts"
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
cd web && npm test
```

Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `src/layout/paneLayout.ts`.

- [ ] **Step 3: Implement the pure layout module**

Create `web/src/layout/paneLayout.ts`:

```ts
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

export function loadPaneLayout(
  storage: ReadStorage | undefined =
    typeof window === "undefined" ? undefined : window.localStorage,
): PaneLayout {
  if (!storage) return DEFAULT_PANE_LAYOUT;
  try {
    const parsed = JSON.parse(storage.getItem(PANE_LAYOUT_KEY) ?? "");
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
```

- [ ] **Step 4: Run the test and verify GREEN**

Run:

```bash
cd web && npm test
```

Expected: `3` tests pass.

- [ ] **Step 5: Commit**

```bash
git add web/package.json web/src/layout/paneLayout.ts web/tests/paneLayout.test.ts
git commit -m "Add persisted pane layout state"
```

### Task 2: React pane hook and accessible workspace shell

**Files:**
- Create: `web/src/hooks/usePaneLayout.ts`
- Create: `web/src/components/WorkspacePane.tsx`

- [ ] **Step 1: Implement the React state adapter**

Create `web/src/hooks/usePaneLayout.ts`:

```ts
import { useCallback, useEffect, useState } from "react";
import {
  loadPaneLayout,
  PANE_LAYOUT_KEY,
  resizePane,
  revealPane,
  togglePane,
  type UtilityPane,
} from "../layout/paneLayout";

export function usePaneLayout() {
  const [layout, setLayout] = useState(loadPaneLayout);

  useEffect(() => {
    window.localStorage.setItem(PANE_LAYOUT_KEY, JSON.stringify(layout));
  }, [layout]);

  const setPaneWidth = useCallback((pane: UtilityPane, width: number) => {
    setLayout((current) => resizePane(current, pane, width));
  }, []);

  const toggle = useCallback((pane: UtilityPane) => {
    setLayout((current) => togglePane(current, pane));
  }, []);

  const reveal = useCallback((pane: UtilityPane) => {
    setLayout((current) => revealPane(current, pane));
  }, []);

  return { layout, setPaneWidth, toggle, reveal };
}
```

- [ ] **Step 2: Implement the pane shell and resize handle**

Create `web/src/components/WorkspacePane.tsx` with:

```tsx
import type { PointerEvent, ReactNode } from "react";
import { PANE_LIMITS, type UtilityPane } from "../layout/paneLayout";

interface Props {
  pane: UtilityPane;
  label: string;
  glyph: ReactNode;
  width: number;
  collapsed: boolean;
  resizeSide: "left" | "right";
  onToggle: () => void;
  onResize: (width: number) => void;
  children: ReactNode;
}

export function WorkspacePane({
  pane,
  label,
  glyph,
  width,
  collapsed,
  resizeSide,
  onToggle,
  onResize,
  children,
}: Props) {
  const limits = PANE_LIMITS[pane];
  const direction = resizeSide === "right" ? 1 : -1;

  const startResize = (event: PointerEvent<HTMLDivElement>) => {
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = width;
    const move = (next: globalThis.PointerEvent) => {
      onResize(startWidth + (next.clientX - startX) * direction);
    };
    const stop = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
  };

  if (collapsed) {
    return (
      <aside className="pane-material flex w-10 shrink-0 justify-center border-r border-border/80 py-2">
        <button
          type="button"
          aria-label={`Show ${label}`}
          aria-pressed="false"
          title={`Show ${label}`}
          onClick={onToggle}
          className="toolbar-button"
        >
          {glyph}
        </button>
      </aside>
    );
  }

  return (
    <aside
      className="pane-material relative flex min-w-0 shrink-0"
      style={{ width }}
    >
      <div className="min-w-0 flex-1">{children}</div>
      <div
        role="separator"
        aria-label={`Resize ${label}`}
        aria-orientation="vertical"
        aria-valuemin={limits.min}
        aria-valuemax={limits.max}
        aria-valuenow={width}
        tabIndex={0}
        onPointerDown={startResize}
        onKeyDown={(event) => {
          if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
          event.preventDefault();
          const delta = event.key === "ArrowRight" ? 10 : -10;
          onResize(width + delta * direction);
        }}
        className={`resize-handle ${resizeSide === "left" ? "left-0" : "right-0"}`}
      />
    </aside>
  );
}
```

- [ ] **Step 3: Run type, lint, and layout tests**

Run:

```bash
cd web && npm test && npm run lint && npm run build
```

Expected: all commands exit `0`.

- [ ] **Step 4: Commit**

```bash
git add web/src/hooks/usePaneLayout.ts web/src/components/WorkspacePane.tsx
git commit -m "Add accessible resizable workspace panes"
```

### Task 3: Toolbar and application composition

**Files:**
- Create: `web/src/components/WorkspaceToolbar.tsx`
- Modify: `web/src/App.tsx`

- [ ] **Step 1: Add the unified toolbar**

Create `WorkspaceToolbar.tsx` with a semantic `<header>`, the Skillscope title,
the selected repository/conversation context, and three native `<button>`
controls. Each button uses `aria-pressed={!collapsed}`, a visible `title`, and
the shared `toolbar-button` class. Render 16px inline SVG line icons for
repositories, threads, and inspector using `stroke="currentColor"`.

The public interface is:

```tsx
interface Props {
  repositoryLabel: string | null;
  conversationTitle: string | null;
  collapsed: Record<UtilityPane, boolean>;
  onToggle: (pane: UtilityPane) => void;
}
```

- [ ] **Step 2: Compose panes in `App.tsx`**

Keep all existing loading, error, empty, selection, and API logic. Add
`usePaneLayout`, render `WorkspaceToolbar` above a flex workspace, and wrap
repositories, threads, and inspector in `WorkspacePane`.

Use these fixed semantics:

```tsx
useEffect(() => {
  if (selectedActivation) reveal("inspector");
}, [selectedActivation, reveal]);
```

The repository and thread shells resize from the right. The inspector resizes
from the left. Render the inspector shell whenever an activation is selected
or the inspector is expanded; when no activation is selected, show a centered
“Select a skill activation” utility state. Closing the inspector calls only
`toggle("inspector")`, preserving `selectedActivationId`.

- [ ] **Step 3: Build and inspect the app**

Run:

```bash
cd web && npm run build
```

Expected: TypeScript and Vite build exit `0`.

- [ ] **Step 4: Commit**

```bash
git add web/src/App.tsx web/src/components/WorkspaceToolbar.tsx
git commit -m "Compose Finder-style dashboard workspace"
```

### Task 4: Apply the Finder-like visual system

**Files:**
- Modify: `web/src/index.css`
- Modify: `web/src/components/RepositoryRail.tsx`
- Modify: `web/src/components/ThreadList.tsx`
- Modify: `web/src/components/ThreadCanvas.tsx`
- Modify: `web/src/components/EvidenceInspector.tsx`
- Modify: `web/src/components/EmptyState.tsx`
- Modify: `web/src/components/ErrorState.tsx`

- [ ] **Step 1: Replace the theme tokens and base styles**

Define semantic light variables in `:root`, dark values in
`@media (prefers-color-scheme: dark)`, and map Tailwind theme colors to those
variables. Include:

```css
:root {
  color-scheme: light dark;
  --app-surface: #f5f5f7;
  --app-pane: rgba(250, 250, 252, 0.86);
  --app-card: #ffffff;
  --app-border: rgba(60, 60, 67, 0.18);
  --app-text: #1d1d1f;
  --app-secondary: #6e6e73;
  --app-tertiary: #8e8e93;
  --app-selection: #007aff;
  --app-selection-bg: rgba(0, 122, 255, 0.12);
}

@media (prefers-color-scheme: dark) {
  :root {
    --app-surface: #1c1c1e;
    --app-pane: rgba(44, 44, 46, 0.88);
    --app-card: #2c2c2e;
    --app-border: rgba(235, 235, 245, 0.18);
    --app-text: #f5f5f7;
    --app-secondary: #aeaeb2;
    --app-tertiary: #8e8e93;
    --app-selection: #0a84ff;
    --app-selection-bg: rgba(10, 132, 255, 0.2);
  }
}
```

Add shared `pane-material`, `toolbar-button`, and `resize-handle` component
classes with Tailwind `@apply`, visible `:focus-visible`, a 6px resize hit
target, subtle scrollbar styling, `backdrop-filter` fallback, and a
`prefers-reduced-motion` rule that removes transitions.

- [ ] **Step 2: Refine each existing content component**

Remove outer fixed widths and duplicate pane borders. Preserve all data and
event behavior while applying these exact treatments:

- repository header and rows: 11px uppercase section label, 8px radius,
  selected material with both tint and semibold weight;
- thread header and rows: 44px header, 12px row radius with 6px outer margin,
  two-line title clamp, compact metadata;
- timeline: 44px contextual header moves to the global toolbar, content width
  `max-w-[46rem]`, 16px body type, selected activation gets a blue leading
  accent and material fill;
- inspector: compact definition grid, inset evidence surface, sticky captured
  content heading, independent code scrolling;
- empty/error states: centered material card with semantic button styling.

- [ ] **Step 3: Run all frontend checks**

Run:

```bash
cd web && npm test && npm run lint && npm run build
```

Expected: layout tests pass; Oxlint reports no errors; Vite production build
exits `0`.

- [ ] **Step 4: Commit**

```bash
git add web/src/index.css web/src/components
git commit -m "Polish dashboard with system materials"
```

### Task 5: Browser verification and final corrections

**Files:**
- Modify only files implicated by observed defects.

- [ ] **Step 1: Start the API and Vite development servers**

Run in separate processes:

```bash
uv run skillscope serve
cd web && npm run dev -- --host 127.0.0.1
```

Expected: API responds on `127.0.0.1:8000`; Vite responds on its printed local
URL.

- [ ] **Step 2: Verify the full interaction matrix**

In the browser, verify:

1. repository, thread, and inspector panes collapse to 40px rails and restore;
2. pointer resizing clamps at every minimum and maximum;
3. focused resize handles respond to left/right arrows;
4. widths and collapse state survive refresh;
5. selecting an activation reveals the inspector;
6. closing and reopening the inspector preserves selection;
7. light and dark media emulation both retain contrast and hierarchy;
8. 1024px and 1440px widths remain usable;
9. focus order and focus rings are visible; and
10. long prompts, paths, and captured content scroll without breaking layout.

- [ ] **Step 3: Run final verification**

Run:

```bash
cd web && npm test && npm run lint && npm run build
cd .. && uv run ruff check . && uv run ruff format --check .
git diff --check
```

Expected: every command exits `0`.

- [ ] **Step 4: Commit any browser-driven corrections**

If browser verification required corrections:

```bash
git add web
git commit -m "Fix workspace interaction details"
```

If no correction was required, do not create an empty commit.
