export type TaskState =
  | "queued"
  | "running"
  | "awaiting_approval"
  | "awaiting_input"
  | "paused"
  | "cancelling"
  | "completed"
  | "failed"
  | "cancelled"
  | "interrupted";

export interface Task {
  task_id: string;
  instruction: string;
  state: TaskState;
  scope_id: string;
  input_refs: string[];
  output_name?: string;
  plan_explanation?: string;
  error_message?: string;
  steps_count: number;
  active_duration_seconds: number;
  created_at: string;
  updated_at: string;
  completed_at?: string;
}

export interface Action {
  action_id: string;
  task_id: string;
  tool: string;
  arguments: Record<string, any>;
  canonical_arguments: Record<string, any>;
  brief_reason: string;
  expected_result: string;
  state: "proposed" | "pending_approval" | "approved" | "rejected" | "executing" | "completed" | "failed" | "cancelled";
  result?: Record<string, any>;
  error?: string;
  created_at: string;
  executed_at?: string;
}

export interface Artifact {
  artifact_id: string;
  task_id: string;
  file_path: string;
  file_name: string;
  size_bytes: number;
  sha256: string;
  created_at: string;
}

export interface TaskScope {
  scope_id: string;
  name: string;
  read_roots: string[];
  write_roots: string[];
  allowed_apps: string[];
  allowed_domains: string[];
  version: number;
}

export interface ModelItem {
  name: string;
  supports_tools: boolean;
  supports_vision: boolean;
  context_length: number;
  quantization?: string;
  tested: boolean;
  is_simulation: boolean;
}

export interface HealthStatus {
  status: string;
  version: string;
  os_platform: string;
  inference_available: boolean;
  model_id?: string;
  desktop_adapter: string;
  active_tasks_count: number;
}

export interface TaskEvent {
  event_id: string;
  task_id: string;
  sequence: number;
  event_type: string;
  payload: Record<string, any>;
  created_at: string;
}
