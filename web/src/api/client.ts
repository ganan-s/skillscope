/** Fetch helpers for the Skillscope API. */

import type {
  Conversation,
  ConversationPage,
  ConversationSummary,
  StoreMetadata,
} from "./types";

class ApiClientError extends Error {
  status: number;
  code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.code = code;
  }
}

async function request<T>(url: string): Promise<T> {
  const resp = await fetch(url);
  if (!resp.ok) {
    let code = "unknown";
    let message = resp.statusText;
    try {
      const body = await resp.json();
      code = body.code ?? code;
      message = body.message ?? message;
    } catch {
      /* ignore parse failure */
    }
    throw new ApiClientError(resp.status, code, message);
  }
  return resp.json() as Promise<T>;
}

/** Fetch all conversation summaries by paging through the API. */
export async function fetchAllConversations(
  pageSize = 100,
): Promise<ConversationSummary[]> {
  const all: ConversationSummary[] = [];
  let cursor: string | null = null;

  do {
    const params = new URLSearchParams({ limit: String(pageSize) });
    if (cursor) params.set("cursor", cursor);

    const page = await request<ConversationPage>(
      `/api/v1/conversations?${params}`,
    );
    all.push(...page.items);
    cursor = page.next_cursor;
  } while (cursor);

  return all;
}

/** Fetch one conversation's full detail. */
export async function fetchConversation(id: string): Promise<Conversation> {
  return request<Conversation>(`/api/v1/conversations/${encodeURIComponent(id)}`);
}

/** Fetch store metadata. */
export async function fetchMetadata(): Promise<StoreMetadata> {
  return request<StoreMetadata>("/api/v1/meta");
}

export { ApiClientError };
