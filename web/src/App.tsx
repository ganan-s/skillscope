import { useEffect } from "react";
import { RepositoryRail } from "./components/RepositoryRail";
import { ThreadList } from "./components/ThreadList";
import { ThreadCanvas } from "./components/ThreadCanvas";
import { EvidenceInspector } from "./components/EvidenceInspector";
import { EmptyState } from "./components/EmptyState";
import { ErrorState } from "./components/ErrorState";
import {
  PaneIcon,
  WorkspaceToolbar,
} from "./components/WorkspaceToolbar";
import { WorkspacePane } from "./components/WorkspacePane";
import { usePaneLayout } from "./hooks/usePaneLayout";
import { useStore } from "./hooks/useStore";

export default function App() {
  const store = useStore();
  const { layout, setPaneWidth, toggle, reveal } = usePaneLayout();
  const {
    status,
    groups,
    selectedConversation,
    selectedConversationId,
    selectedActivationId,
    selectConversation,
    selectActivation,
  } = store;

  const selectedGroup = groups.find((g) =>
    g.conversations.some((c) => c.id === selectedConversationId),
  );
  const selectedActivation = selectedConversation?.skill_activations.find(
    (a) => a.id === selectedActivationId,
  );

  useEffect(() => {
    if (selectedActivation) reveal("inspector");
  }, [selectedActivation, reveal]);

  if (status.kind === "loading") {
    return (
      <div className="flex h-screen items-center justify-center">
        <p className="text-text-tertiary text-sm tracking-wide">Loading...</p>
      </div>
    );
  }

  if (status.kind === "error") {
    return <ErrorState code={status.code} message={status.message} retry={store.retry} />;
  }

  if (status.kind === "empty") {
    return <EmptyState />;
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <WorkspaceToolbar
        repositoryLabel={selectedGroup?.label ?? null}
        conversationTitle={selectedConversation?.title ?? null}
        collapsed={layout.collapsed}
        onToggle={toggle}
      />
      <div className="flex min-h-0 flex-1 overflow-x-auto overflow-y-hidden">
        <WorkspacePane
          pane="repositories"
          label="repositories"
          glyph={<PaneIcon pane="repositories" />}
          width={layout.widths.repositories}
          collapsed={layout.collapsed.repositories}
          resizeSide="right"
          onToggle={() => toggle("repositories")}
          onResize={(width) => setPaneWidth("repositories", width)}
        >
          <div className="h-full w-full min-w-0 [&>*]:!w-full">
            <RepositoryRail
              groups={groups}
              selectedConversationId={selectedConversationId}
              onSelectConversation={selectConversation}
            />
          </div>
        </WorkspacePane>
        <WorkspacePane
          pane="threads"
          label="threads"
          glyph={<PaneIcon pane="threads" />}
          width={layout.widths.threads}
          collapsed={layout.collapsed.threads}
          resizeSide="right"
          onToggle={() => toggle("threads")}
          onResize={(width) => setPaneWidth("threads", width)}
        >
          <div className="h-full w-full min-w-0 [&>*]:!w-full">
            <ThreadList
              group={selectedGroup ?? groups[0] ?? null}
              selectedConversationId={selectedConversationId}
              onSelectConversation={selectConversation}
            />
          </div>
        </WorkspacePane>
        <main className="flex min-w-[24rem] flex-1">
          <ThreadCanvas
            conversation={selectedConversation}
            selectedActivationId={selectedActivationId}
            onSelectActivation={selectActivation}
          />
        </main>
        <WorkspacePane
          pane="inspector"
          label="inspector"
          glyph={<PaneIcon pane="inspector" />}
          width={layout.widths.inspector}
          collapsed={layout.collapsed.inspector}
          resizeSide="left"
          onToggle={() => toggle("inspector")}
          onResize={(width) => setPaneWidth("inspector", width)}
        >
          <div className="h-full w-full min-w-0 [&>*]:!w-full">
            {selectedActivation ? (
              <EvidenceInspector
                activation={selectedActivation}
                onClose={() => toggle("inspector")}
              />
            ) : (
              <div className="flex h-full items-center justify-center">
                <p className="text-sm text-text-tertiary">
                  Select a skill activation
                </p>
              </div>
            )}
          </div>
        </WorkspacePane>
      </div>
    </div>
  );
}
