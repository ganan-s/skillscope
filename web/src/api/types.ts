/** Narrow API types matching the OpenAPI v1 contract. */

export interface SkillSummary {
  name: string | null;
  path: string;
  source: string;
  activation_count: number;
}

export interface ConversationSummary {
  id: string;
  title: string | null;
  harness: string;
  workspace_paths: string[];
  started_at: string | null;
  ended_at: string | null;
  skills: SkillSummary[];
  task_count: number;
  activation_count: number;
  load_failure_count: number;
}

export interface ConversationPage {
  items: ConversationSummary[];
  next_cursor: string | null;
  limit: number;
}

export interface Payload {
  status: "captured" | "unavailable";
  content: string | null;
  sha256: string | null;
  byte_length: number | null;
  unavailable_reason: string | null;
}

export interface SkillResourceRead {
  id: string;
  path: string;
  sequence: number;
  read_at: string | null;
  time_provenance: string;
  payload: Payload;
}

export interface EffectivenessObservations {
  resource_follow_through: boolean;
  repeated_in_conversation: boolean;
  followed_by_user_task: boolean;
  containing_turn_status: "success" | "error" | "unknown";
}

export interface SkillLoadFailure {
  id: string;
  path: string;
  source: string;
  reason: "failed" | "denied" | "timeout" | "interrupted" | "unknown";
  turn_index: number | null;
  sequence: number;
  failed_at: string | null;
  time_provenance: string;
}

export interface SkillActivation {
  id: string;
  task_id: string | null;
  turn_index: number | null;
  sequence: number;
  activated_at: string | null;
  time_provenance: string;
  path: string;
  source: string;
  name: string | null;
  description: string | null;
  payload: Payload;
  resource_reads: SkillResourceRead[];
  observations: EffectivenessObservations;
}

export interface Task {
  id: string;
  turn_index: number;
  text: string;
  submitted_at: string | null;
  time_provenance: string;
}

export interface Conversation extends ConversationSummary {
  tasks: Task[];
  skill_activations: SkillActivation[];
  skill_load_failures: SkillLoadFailure[];
}

export interface IngestSummary {
  inserted: number;
  updated: number;
  unchanged: number;
  skipped: number;
  failed: number;
}

export interface StoreMetadata {
  api_version: string;
  schema_version: number;
  supported_schema_version: number;
  last_successful_ingest_at: string | null;
  last_ingest_summary: IngestSummary | null;
  harnesses: string[];
}

export interface ApiError {
  code: string;
  message: string;
  details: Record<string, unknown> | null;
}
