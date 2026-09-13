import { HealthStatus, ModelItem, Task, Action, Artifact, TaskScope, TaskEvent } from "../types";

let API_BASE = "http://127.0.0.1:8000";
let SESSION_TOKEN = "";

export function setApiConfig(baseUrl: string, token: string) {
  API_BASE = baseUrl.replace(/\/$/, "");
  SESSION_TOKEN = token;
}

export function getSessionToken(): string {
  return SESSION_TOKEN;
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (SESSION_TOKEN) {
    headers["Authorization"] = `Bearer ${SESSION_TOKEN}`;
  }

  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(errorData.detail || `Error HTTP ${res.status}`);
  }

  return res.json();
}

export const api = {
  getHealth: () => request<HealthStatus>("/v1/health"),
  getModels: () => request<{ models: ModelItem[] }>("/v1/models"),
  listTasks: () => request<Task[]>("/v1/tasks"),
  getTask: (taskId: string) =>
    request<{ task: Task; actions: Action[]; artifacts: Artifact[] }>(`/v1/tasks/${taskId}`),
  createTask: (data: { instruction: string; scope_id: string; input_refs?: string[]; output_name?: string }) =>
    request<{ task_id: string; state: string }>("/v1/tasks", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  pauseTask: (taskId: string) =>
    request<{ status: string }>(`/v1/tasks/${taskId}/pause`, { method: "POST" }),
  resumeTask: (taskId: string) =>
    request<{ status: string }>(`/v1/tasks/${taskId}/resume`, { method: "POST" }),
  cancelTask: (taskId: string) =>
    request<{ status: string }>(`/v1/tasks/${taskId}/cancel`, { method: "POST" }),
  resolveApproval: (taskId: string, approvalId: string, approved: boolean) =>
    request<{ resolved: boolean }>(`/v1/tasks/${taskId}/approvals/${approvalId}`, {
      method: "POST",
      body: JSON.stringify({ approved }),
    }),
  listScopes: () => request<TaskScope[]>("/v1/scopes"),
  createScope: (data: Partial<TaskScope>) =>
    request<TaskScope>("/v1/scopes", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateScopeRoots: (scopeId: string, data: { read_roots: string[]; write_roots: string[] }) =>
    request<TaskScope>(`/v1/scopes/${encodeURIComponent(scopeId)}/roots`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  getPreferences: () => request<Record<string, any>>("/v1/preferences"),
  setPreference: (key: string, value: any) =>
    request("/v1/preferences", {
      method: "POST",
      body: JSON.stringify({ key, value }),
    }),

  connectEvents: (taskId: string, onEvent: (event: TaskEvent) => void, onError?: (err: any) => void) => {
    const url = `${API_BASE}/v1/tasks/${taskId}/events?token=${encodeURIComponent(SESSION_TOKEN)}`;
    const eventSource = new EventSource(url);

    eventSource.onmessage = (e) => {
      try {
        const data: TaskEvent = JSON.parse(e.data);
        onEvent(data);
      } catch (err) {
        console.error("Error al parsear evento SSE:", err);
      }
    };

    // Escuchar eventos tipados específicos
    const eventTypes = [
      "task_state_changed",
      "task_plan_explained",
      "action_proposed",
      "action_started",
      "action_completed",
      "action_failed",
      "approval_requested",
      "approval_resolved",
      "task_completed",
      "task_failed",
      "task_paused",
      "task_resumed",
      "task_cancelled",
    ];

    eventTypes.forEach((type) => {
      eventSource.addEventListener(type, (e: any) => {
        try {
          const data: TaskEvent = JSON.parse(e.data);
          onEvent(data);
        } catch (err) {
          console.error(`Error procesando SSE ${type}:`, err);
        }
      });
    });

    eventSource.onerror = (err) => {
      if (onError) onError(err);
      eventSource.close();
    };

    return () => eventSource.close();
  },
};
