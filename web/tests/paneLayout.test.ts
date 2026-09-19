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
