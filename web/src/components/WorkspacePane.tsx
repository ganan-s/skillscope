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
