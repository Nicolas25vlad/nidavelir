const defaultBaseUrl = "http://127.0.0.1:8000";

export type TaskState =
  | "BACKLOG"
  | "QUEUED"
  | "RUNNING"
  | "AGENT_DONE"
  | "VALIDATING"
  | "NEEDS_CHANGES"
  | "APPROVED"
  | "MERGED"
  | "CLOSED"
  | "CANCELLED";

export interface TaskTransition {
  id: number;
  from_state: TaskState;
  to_state: TaskState;
  reason: string | null;
  occurred_at: string;
}

export interface Task {
  id: string;
  title: string;
  description: string;
  repository: string;
  base_branch: string;
  acceptance_criteria: string[];
  state: TaskState;
  created_at: string;
  updated_at: string;
  transitions: TaskTransition[];
}

export type AttemptStatus =
  | "PREPARING"
  | "RUNNING"
  | "SUCCEEDED"
  | "FAILED"
  | "CANCELLED"
  | "TIMED_OUT";

export interface Attempt {
  id: string;
  task_id: string;
  number: number;
  status: AttemptStatus;
  harness: string;
  harness_version: string | null;
  container_name: string;
  volume_name: string;
  branch_name: string;
  commit_sha: string | null;
  result: Record<string, unknown> | null;
  exit_code: number | null;
  failure_reason: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface AttemptLogs {
  attempt_id: string;
  status: AttemptStatus;
  logs: string;
}

export interface CreateTaskInput {
  title: string;
  repository: string;
  description?: string;
  base_branch?: string;
  acceptance_criteria?: string[];
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export class NidavelirApi {
  constructor(private readonly baseUrl = import.meta.env.VITE_NIDAVELIR_API_URL ?? defaultBaseUrl) {}

  private async request<T>(
    method: string,
    path: string,
    options: { body?: unknown; signal?: AbortSignal } = {},
  ): Promise<T> {
    const response = await fetch(new URL(path, this.baseUrl), {
      method,
      headers: {
        Accept: "application/json",
        ...(options.body === undefined ? {} : { "Content-Type": "application/json" }),
      },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: options.signal,
    });

    if (!response.ok) {
      let detail: unknown;
      try {
        const payload = (await response.json()) as { detail?: unknown };
        detail = payload.detail;
      } catch {
        detail = await response.text().catch(() => undefined);
      }
      throw new ApiError(`Nidavelir API request failed: ${response.status}`, response.status, detail);
    }

    if (response.status === 204) {
      return undefined as T;
    }
    return response.json() as Promise<T>;
  }

  get<T>(path: string, signal?: AbortSignal): Promise<T> {
    return this.request<T>("GET", path, { signal });
  }

  createTask(input: CreateTaskInput): Promise<Task> {
    return this.request<Task>("POST", "/tasks", { body: input });
  }

  listTasks(signal?: AbortSignal): Promise<Task[]> {
    return this.get<Task[]>("/tasks", signal);
  }

  getTask(taskId: string, signal?: AbortSignal): Promise<Task> {
    return this.get<Task>(`/tasks/${taskId}`, signal);
  }

  startTask(taskId: string, harness = "codex"): Promise<Attempt> {
    return this.request<Attempt>("POST", `/tasks/${taskId}/start`, {
      body: { harness },
    });
  }

  cancelTask(taskId: string): Promise<void> {
    return this.request<void>("POST", `/tasks/${taskId}/cancel`);
  }

  listAttempts(taskId: string, signal?: AbortSignal): Promise<Attempt[]> {
    return this.get<Attempt[]>(`/tasks/${taskId}/attempts`, signal);
  }

  getAttemptLogs(attemptId: string, signal?: AbortSignal): Promise<AttemptLogs> {
    return this.get<AttemptLogs>(`/attempts/${attemptId}/logs`, signal);
  }
}

export const api = new NidavelirApi();
