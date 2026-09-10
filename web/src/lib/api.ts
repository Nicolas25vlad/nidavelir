const defaultBaseUrl = "/api";

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

export interface ValidationCommand {
  name: string;
  type: "test" | "lint" | "build";
  command: string;
  timeout_seconds: number;
}

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
  validation_commands: ValidationCommand[];
  merge_commit_sha: string | null;
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
  base_commit_sha?: string | null;
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

export interface AttemptDiff {
  attempt_id: string;
  branch_name: string;
  base_commit_sha: string | null;
  commit_sha: string | null;
  stat: string;
  patch: string;
}

export interface ValidationCheck {
  id: string;
  task_id: string;
  attempt_id: string;
  position: number;
  name: string;
  check_type: string;
  command: string;
  status: "PENDING" | "RUNNING" | "PASSED" | "FAILED" | "TIMED_OUT";
  exit_code: number | null;
  output: string;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface ReviewDecision {
  id: string;
  task_id: string;
  attempt_id: string;
  decision: "APPROVED" | "REJECTED";
  actor: string;
  feedback: string;
  created_at: string;
}

export interface MergeResult {
  task_id: string;
  state: TaskState;
  merge_commit_sha: string;
}

export interface CreateTaskInput {
  title: string;
  repository: string;
  description?: string;
  base_branch?: string;
  acceptance_criteria?: string[];
  validation_commands?: ValidationCommand[];
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

  private resolveUrl(path: string): string {
    const base = this.baseUrl.replace(/\/+$/, "");
    const normalizedPath = path.startsWith("/") ? path : `/${path}`;
    if (/^https?:\/\//.test(base)) return `${base}${normalizedPath}`;
    const normalizedBase = base.startsWith("/") ? base : `/${base}`;
    return `${window.location.origin}${normalizedBase}${normalizedPath}`;
  }

  private async request<T>(
    method: string,
    path: string,
    options: { body?: unknown; signal?: AbortSignal } = {},
  ): Promise<T> {
    const response = await fetch(this.resolveUrl(path), {
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

    if (response.status === 204) return undefined as T;
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
    return this.request<Attempt>("POST", `/tasks/${taskId}/start`, { body: { harness } });
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

  getAttemptDiff(attemptId: string, signal?: AbortSignal): Promise<AttemptDiff> {
    return this.get<AttemptDiff>(`/attempts/${attemptId}/diff`, signal);
  }

  getAttemptChecks(attemptId: string, signal?: AbortSignal): Promise<ValidationCheck[]> {
    return this.get<ValidationCheck[]>(`/attempts/${attemptId}/checks`, signal);
  }

  getReviews(taskId: string, signal?: AbortSignal): Promise<ReviewDecision[]> {
    return this.get<ReviewDecision[]>(`/tasks/${taskId}/reviews`, signal);
  }

  approveTask(taskId: string, feedback = "", actor = "web"): Promise<ReviewDecision> {
    return this.request<ReviewDecision>("POST", `/tasks/${taskId}/approve`, {
      body: { actor, feedback },
    });
  }

  rejectTask(taskId: string, feedback: string, actor = "web"): Promise<ReviewDecision> {
    return this.request<ReviewDecision>("POST", `/tasks/${taskId}/reject`, {
      body: { actor, feedback },
    });
  }

  mergeTask(taskId: string): Promise<MergeResult> {
    return this.request<MergeResult>("POST", `/tasks/${taskId}/merge`);
  }
}

export const api = new NidavelirApi();
