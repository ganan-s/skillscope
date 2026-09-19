/** Central data store hook for the dashboard. */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiClientError,
  fetchAllConversations,
  fetchConversation,
  fetchMetadata,
} from "../api/client";
import { groupByRepository, type RepositoryGroup } from "../api/grouping";
import type { Conversation, ConversationSummary, StoreMetadata } from "../api/types";

export type StoreStatus =
  | { kind: "loading" }
  | { kind: "ready" }
  | { kind: "empty" }
  | { kind: "error"; code: string; message: string };

export interface Store {
  status: StoreStatus;
  metadata: StoreMetadata | null;
  conversations: ConversationSummary[];
  groups: RepositoryGroup[];
  selectedConversation: Conversation | null;
  selectedConversationId: string | null;
  selectedActivationId: string | null;
  selectConversation: (id: string | null) => void;
  selectActivation: (id: string | null) => void;
  retry: () => void;
}

export function useStore(): Store {
  const [status, setStatus] = useState<StoreStatus>({ kind: "loading" });
  const [metadata, setMetadata] = useState<StoreMetadata | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [groups, setGroups] = useState<RepositoryGroup[]>([]);
  const [selectedConversation, setSelectedConversation] =
    useState<Conversation | null>(null);
  const [selectedConversationId, setSelectedConversationId] = useState<
    string | null
  >(null);
  const [selectedActivationId, setSelectedActivationId] = useState<
    string | null
  >(null);

  const loadingRef = useRef(false);

  const load = useCallback(async () => {
    if (loadingRef.current) return;
    loadingRef.current = true;
    setStatus({ kind: "loading" });

    try {
      const meta = await fetchMetadata();
      setMetadata(meta);

      const convs = await fetchAllConversations();
      setConversations(convs);
      setGroups(groupByRepository(convs));

      if (convs.length === 0) {
        setStatus({ kind: "empty" });
      } else {
        setStatus({ kind: "ready" });
      }
    } catch (err) {
      if (err instanceof ApiClientError) {
        setStatus({ kind: "error", code: err.code, message: err.message });
      } else {
        setStatus({
          kind: "error",
          code: "unknown",
          message: String(err),
        });
      }
    } finally {
      loadingRef.current = false;
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const selectConversation = useCallback(
    async (id: string | null) => {
      setSelectedConversationId(id);
      setSelectedActivationId(null);
      if (!id) {
        setSelectedConversation(null);
        return;
      }
      try {
        const detail = await fetchConversation(id);
        setSelectedConversation(detail);
      } catch {
        setSelectedConversation(null);
      }
    },
    [],
  );

  const selectActivation = useCallback((id: string | null) => {
    setSelectedActivationId(id);
  }, []);

  const retry = useCallback(() => {
    load();
  }, [load]);

  return {
    status,
    metadata,
    conversations,
    groups,
    selectedConversation,
    selectedConversationId,
    selectedActivationId,
    selectConversation,
    selectActivation,
    retry,
  };
}
