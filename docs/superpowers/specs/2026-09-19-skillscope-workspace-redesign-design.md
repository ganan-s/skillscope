# Skillscope workspace redesign

## Scope

Refine the existing read-only dashboard into a modern Finder-like workspace
without changing its API, ingestion behavior, or information architecture.
The redesign supersedes only the visual direction and pane behavior in the
original dashboard specification.

## Visual direction

Use a restrained macOS utility aesthetic:

- system light and dark appearances via `prefers-color-scheme`;
- the system UI font stack, with monospace reserved for paths and evidence;
- a translucent unified toolbar and subtly differentiated navigation surfaces;
- Apple blue for selection and focus, with semantic colors used sparingly;
- hairline separators, soft material shadows, and 8–12px corner radii;
- compact navigation density and a generous central reading canvas; and
- 140–180ms transitions disabled by `prefers-reduced-motion`.

The interface must remain legible without transparency and meet WCAG AA
contrast for text and controls.

## Workspace layout

The workspace contains a unified 44px toolbar above four panes:

1. repository navigator;
2. conversation list;
3. prompt-to-skill timeline; and
4. evidence inspector.

The timeline is the flexible primary pane. The three utility panes can be
resized within explicit minimum and maximum widths. Each utility pane can
collapse to a 40px icon rail and restore with one click. Resize handles use
pointer input and expose keyboard resizing in 10px increments.

Pane widths and collapsed state persist in browser local storage. Invalid or
obsolete persisted values fall back to defaults. Selecting a skill activation
reveals the evidence inspector. Closing the inspector collapses it without
clearing the selected activation.

On narrow windows, utility panes retain their minimum widths and the timeline
remains scroll-safe; the interface does not silently discard navigation state.

## Components and state

`App` owns workspace layout state through one `usePaneLayout` hook. The hook
handles defaults, constraints, persistence, collapse state, and resize input.

A `WorkspaceToolbar` presents the title, current context, and native buttons
for toggling the repository, conversation, and inspector panes. Buttons expose
labels, tooltips, pressed state, visible focus, and at least a 28px desktop hit
area.

Existing repository, thread, timeline, and inspector components continue to
own their content. They receive layout state but do not duplicate persistence
or resizing logic. One shared resize handle provides the behavior Tailwind
does not supply. No component library or runtime dependency is added.

## Content treatment

- Repository rows use sidebar selection material and retain path tooltips.
- Conversation rows show title, recency, and activation count with clearer
  selected and hover states.
- Prompt blocks retain the causal spine but improve rhythm, line length, and
  skill activation affordances.
- Evidence metadata uses compact definition rows. Captured content uses a
  high-contrast inset code surface with independent scrolling.
- Loading, empty, error, unavailable-content, and zero-skill states use the
  same visual system and remain explicit.

## Accessibility

- All pane controls and resize handles are keyboard operable.
- Collapse controls expose `aria-pressed`; resize handles expose separator
  semantics and current/minimum/maximum values.
- Focus indicators use the platform accent and are never removed.
- Color is not the sole indicator of selection or status.
- Motion and transparency respect operating-system accessibility preferences.

## Verification

Automated checks cover pane defaults, persistence, width clamping, collapse
state, and activation-driven inspector reveal. Existing grouping and timeline
behavior must remain unchanged.

Manual browser verification covers:

- light and dark system appearances;
- all pane collapse and restore paths;
- pointer and keyboard resizing at width constraints;
- refresh persistence;
- inspector selection and close behavior;
- long titles, paths, evidence, and empty states;
- focus order and visible focus; and
- representative narrow and wide desktop windows.

The production frontend build and lint checks must pass before handoff.
