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
    try {
      window.localStorage.setItem(PANE_LAYOUT_KEY, JSON.stringify(layout));
    } catch {
      // Persistence is best-effort when storage is blocked or full.
    }
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
