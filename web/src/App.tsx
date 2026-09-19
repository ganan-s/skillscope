import { RepositoryRail } from "./components/RepositoryRail";
import { ThreadList } from "./components/ThreadList";
import { ThreadCanvas } from "./components/ThreadCanvas";
import { EvidenceInspector } from "./components/EvidenceInspector";
import { EmptyState } from "./components/EmptyState";
import { ErrorState } from "./components/ErrorState";
import { useStore } from "./hooks/useStore";

export default function App() {
  const store = useStore();
  const {
    status,
    groups,
    selectedConversation,
    selectedConversationId,
    selectedActivationId,
    selectConversation,
    selectActivation,
  } = store;

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

  const selectedGroup = groups.find((g) =>
    g.conversations.some((c) => c.id === selectedConversationId),
  );

  const selectedActivation = selectedConversation?.skill_activations.find(
    (a) => a.id === selectedActivationId,
  );

  return (
    <div className="flex h-screen overflow-hidden">
      <RepositoryRail
        groups={groups}
        selectedConversationId={selectedConversationId}
        onSelectConversation={selectConversation}
      />
      <ThreadList
        group={selectedGroup ?? groups[0] ?? null}
        selectedConversationId={selectedConversationId}
        onSelectConversation={selectConversation}
      />
      <ThreadCanvas
        conversation={selectedConversation}
        selectedActivationId={selectedActivationId}
        onSelectActivation={selectActivation}
      />
      {selectedActivation && (
        <EvidenceInspector
          activation={selectedActivation}
          onClose={() => selectActivation(null)}
        />
      )}
    </div>
  );
}
