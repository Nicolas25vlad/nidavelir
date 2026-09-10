import { FormEvent, useEffect, useState } from "react";
import { Link, NavLink, Route, Routes, useParams } from "react-router-dom";

import { AsyncState } from "./components/AsyncState";
import {
  ApiError,
  api,
  type Attempt,
  type AttemptDiff,
  type AttemptLogs,
  type Harness,
  type ReviewDecision,
  type Task,
  type TaskState,
  type ValidationCheck,
} from "./lib/api";

const navigation = [
  { to: "/", label: "Overview", end: true },
  { to: "/board", label: "Board" },
  { to: "/agents", label: "Agents" },
];

const boardStates: TaskState[] = [
  "BACKLOG",
  "QUEUED",
  "RUNNING",
  "AGENT_DONE",
  "VALIDATING",
  "NEEDS_CHANGES",
  "APPROVED",
];

function PageHeader({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  return (
    <header className="page-header">
      <span className="eyebrow">{eyebrow}</span>
      <h1>{title}</h1>
      <p>{description}</p>
    </header>
  );
}

function errorText(error: unknown): string {
  if (error instanceof ApiError) {
    if (typeof error.detail === "string") return error.detail;
    if (error.detail !== undefined) return `${error.message}: ${JSON.stringify(error.detail)}`;
    return error.message;
  }
  return error instanceof Error ? error.message : "Unknown error";
}

function formatTime(value: string | null | undefined): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function StateBadge({ state }: { state: string }) {
  return <span className={`badge badge--${state.toLowerCase()}`}>{state.replaceAll("_", " ")}</span>;
}

function useTasks(pollMs = 5000) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const data = await api.listTasks();
        if (!active) return;
        setTasks(data);
        setError(null);
      } catch (caught) {
        if (active) setError(errorText(caught));
      } finally {
        if (active) setLoading(false);
      }
    };

    void load();
    const timer = window.setInterval(() => void load(), pollMs);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [pollMs, revision]);

  return { tasks, loading, error, refresh: () => setRevision((value) => value + 1) };
}

function TaskRow({ task }: { task: Task }) {
  return (
    <Link className="task-row" to={`/tasks/${task.id}`}>
      <div>
        <strong>{task.title}</strong>
        <span>{task.repository} · {task.base_branch}</span>
      </div>
      <div className="task-row__meta">
        <StateBadge state={task.state} />
        <span>{formatTime(task.updated_at)}</span>
      </div>
    </Link>
  );
}

function Overview() {
  const { tasks, loading, error } = useTasks();
  const active = tasks.filter((task) => ["QUEUED", "RUNNING", "VALIDATING"].includes(task.state));
  const attention = tasks.filter((task) => ["VALIDATING", "NEEDS_CHANGES", "APPROVED"].includes(task.state));
  const completed = tasks.filter((task) => task.state === "CLOSED");

  if (loading) return <AsyncState kind="loading" title="Loading control plane" detail="Reading durable task state from Core." />;
  if (error) return <AsyncState kind="error" title="Core unavailable" detail={error} />;

  return (
    <section>
      <PageHeader eyebrow="System briefing" title="Overview" description="Live durable task and worker state." />
      <div className="metric-row">
        <div><span>Active</span><strong>{active.length}</strong></div>
        <div><span>Needs decision</span><strong>{attention.length}</strong></div>
        <div><span>Closed</span><strong>{completed.length}</strong></div>
        <div><span>Total</span><strong>{tasks.length}</strong></div>
      </div>
      <div className="section-block">
        <div className="section-heading"><h2>Needs attention</h2><Link to="/board">Open board</Link></div>
        {attention.length === 0 ? (
          <AsyncState kind="empty" title="Nothing waiting on you" detail="Validated, rejected and approved tasks surface here." />
        ) : (
          <div className="task-list">{attention.map((task) => <TaskRow key={task.id} task={task} />)}</div>
        )}
      </div>
      <div className="section-block">
        <div className="section-heading"><h2>Recent tasks</h2></div>
        {tasks.length === 0 ? (
          <AsyncState kind="empty" title="No tasks yet" detail="Create the first durable task from the Board." />
        ) : (
          <div className="task-list">{tasks.slice(0, 6).map((task) => <TaskRow key={task.id} task={task} />)}</div>
        )}
      </div>
    </section>
  );
}

function CreateTaskForm({ onCreated }: { onCreated: () => void }) {
  const [title, setTitle] = useState("");
  const [repository, setRepository] = useState("Nicolas25vlad/nidavelir");
  const [description, setDescription] = useState("");
  const [criteria, setCriteria] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.createTask({
        title,
        repository,
        description,
        acceptance_criteria: criteria.split("\n").map((line) => line.trim()).filter(Boolean),
      });
      setTitle("");
      setDescription("");
      setCriteria("");
      onCreated();
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="task-form" onSubmit={submit}>
      <div className="section-heading"><h2>Create task</h2><span>Durable before execution</span></div>
      <label>Title<input required maxLength={200} value={title} onChange={(event) => setTitle(event.target.value)} /></label>
      <label>Repository<input required value={repository} onChange={(event) => setRepository(event.target.value)} placeholder="owner/repo" /></label>
      <label>Description<textarea rows={3} value={description} onChange={(event) => setDescription(event.target.value)} /></label>
      <label>Acceptance criteria<textarea rows={3} value={criteria} onChange={(event) => setCriteria(event.target.value)} placeholder="One criterion per line" /></label>
      {error && <span className="form-error">{error}</span>}
      <button className="button" disabled={busy || !title.trim() || !repository.trim()} type="submit">{busy ? "Creating…" : "Create task"}</button>
    </form>
  );
}

function Board() {
  const { tasks, loading, error, refresh } = useTasks();
  if (loading) return <AsyncState kind="loading" title="Loading board" detail="Reading persisted task states." />;
  if (error) return <AsyncState kind="error" title="Board unavailable" detail={error} />;

  return (
    <section>
      <PageHeader eyebrow="Durable state" title="Board" description="Every column maps directly to persisted Core state." />
      <CreateTaskForm onCreated={refresh} />
      <div className="kanban" aria-label="Task board">
        {boardStates.map((state) => {
          const columnTasks = tasks.filter((task) => task.state === state);
          return (
            <section className="kanban-column" key={state}>
              <header><StateBadge state={state} /><span>{columnTasks.length}</span></header>
              <div className="kanban-column__body">
                {columnTasks.map((task) => (
                  <Link className="task-card" to={`/tasks/${task.id}`} key={task.id}>
                    <strong>{task.title}</strong><span>{task.repository}</span><small>{formatTime(task.updated_at)}</small>
                  </Link>
                ))}
                {columnTasks.length === 0 && <span className="column-empty">Empty</span>}
              </div>
            </section>
          );
        })}
      </div>
    </section>
  );
}

interface AgentRow extends Attempt { taskTitle: string }

function Agents() {
  const [attempts, setAttempts] = useState<AgentRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const tasks = await api.listTasks();
        const byTask = await Promise.all(tasks.map(async (task) => {
          const taskAttempts = await api.listAttempts(task.id);
          return taskAttempts.map((attempt) => ({ ...attempt, taskTitle: task.title }));
        }));
        if (!active) return;
        setAttempts(byTask.flat().sort((a, b) => b.created_at.localeCompare(a.created_at)));
        setError(null);
      } catch (caught) {
        if (active) setError(errorText(caught));
      } finally {
        if (active) setLoading(false);
      }
    };
    void load();
    const timer = window.setInterval(() => void load(), 5000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);

  if (loading) return <AsyncState kind="loading" title="Loading attempts" detail="Reading execution history." />;
  if (error) return <AsyncState kind="error" title="Attempt feed unavailable" detail={error} />;

  return (
    <section>
      <PageHeader eyebrow="Execution" title="Agents" description="Disposable runtime attempts remain inspectable after cleanup." />
      {attempts.length === 0 ? (
        <AsyncState kind="empty" title="No worker attempts" detail="Start a task from Task Detail." />
      ) : (
        <div className="attempt-table">
          {attempts.map((attempt) => (
            <Link className="attempt-row" to={`/tasks/${attempt.task_id}`} key={attempt.id}>
              <div><strong>{attempt.taskTitle}</strong><span>attempt {attempt.number} · {attempt.harness}{attempt.harness_version ? ` · ${attempt.harness_version}` : ""}</span></div>
              <div><StateBadge state={attempt.status} /><span>{attempt.commit_sha ? attempt.commit_sha.slice(0, 8) : attempt.branch_name}</span></div>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}

function TaskDetail() {
  const { taskId } = useParams();
  const [task, setTask] = useState<Task | null>(null);
  const [attempts, setAttempts] = useState<Attempt[]>([]);
  const [logs, setLogs] = useState<AttemptLogs | null>(null);
  const [diff, setDiff] = useState<AttemptDiff | null>(null);
  const [checks, setChecks] = useState<ValidationCheck[]>([]);
  const [reviews, setReviews] = useState<ReviewDecision[]>([]);
  const [harnesses, setHarnesses] = useState<Harness[]>([]);
  const [selectedHarness, setSelectedHarness] = useState("codex");
  const [feedback, setFeedback] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState(false);

  useEffect(() => {
    if (!taskId) return;
    let active = true;
    const load = async () => {
      try {
        const [nextTask, nextAttempts, nextHarnesses, nextReviews] = await Promise.all([
          api.getTask(taskId),
          api.listAttempts(taskId),
          api.listHarnesses(),
          api.getReviews(taskId),
        ]);
        const latest = nextAttempts[0];
        const [nextLogs, nextDiff, nextChecks] = latest
          ? await Promise.all([
              api.getAttemptLogs(latest.id),
              api.getAttemptDiff(latest.id),
              api.getAttemptChecks(latest.id),
            ])
          : [null, null, [] as ValidationCheck[]];
        if (!active) return;
        setTask(nextTask);
        setAttempts(nextAttempts);
        setHarnesses(nextHarnesses);
        setReviews(nextReviews);
        setLogs(nextLogs);
        setDiff(nextDiff);
        setChecks(nextChecks);
        setError(null);
      } catch (caught) {
        if (active) setError(errorText(caught));
      } finally {
        if (active) setLoading(false);
      }
    };
    void load();
    const timer = window.setInterval(() => void load(), 2000);
    return () => { active = false; window.clearInterval(timer); };
  }, [taskId]);

  const latest = attempts[0];
  const selected = harnesses.find((harness) => harness.id === selectedHarness);
  const canStart = Boolean(task && ["BACKLOG", "QUEUED", "NEEDS_CHANGES"].includes(task.state));
  const canReview = task?.state === "VALIDATING";
  const canMerge = task?.state === "APPROVED";
  const canCancel = Boolean(task && !["CLOSED", "CANCELLED", "MERGED"].includes(task.state));

  const runAction = async (action: () => Promise<unknown>) => {
    setActionBusy(true);
    setError(null);
    try {
      await action();
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      setActionBusy(false);
    }
  };

  if (loading) return <AsyncState kind="loading" title="Loading task" detail="Reading durable task and attempts." />;
  if (!task || !taskId) return <AsyncState kind="error" title="Task unavailable" detail={error ?? "Task not found."} />;

  return (
    <section>
      <PageHeader eyebrow={`Task ${task.id.slice(0, 8)}`} title={task.title} description={`${task.repository} · base ${task.base_branch}`} />
      {error && <AsyncState kind="error" title="Action failed" detail={error} />}

      <div className="task-toolbar">
        <StateBadge state={task.state} />
        <div>
          <select value={selectedHarness} onChange={(event) => setSelectedHarness(event.target.value)} disabled={!canStart || actionBusy}>
            {harnesses.map((harness) => <option value={harness.id} key={harness.id}>{harness.display_name}{harness.configured ? "" : " (not configured)"}</option>)}
          </select>
          <button className="button" disabled={!canStart || !selected?.configured || actionBusy} onClick={() => void runAction(() => api.startTask(taskId, selectedHarness))}>Start {selectedHarness}</button>
          <button className="button button--secondary" disabled={!canCancel || actionBusy} onClick={() => void runAction(() => api.cancelTask(taskId))}>Cancel</button>
        </div>
      </div>

      {selected && !selected.configured && canStart && (
        <AsyncState kind="error" title={`${selected.display_name} is not configured`} detail={`Set ${selected.credential_env} on the server before starting this harness.`} />
      )}

      <div className="detail-grid">
        <article className="detail-panel">
          <h2>Task context</h2>
          <p>{task.description || "No description."}</p>
          <h3>Acceptance criteria</h3>
          {task.acceptance_criteria.length === 0 ? <span className="muted">None defined.</span> : <ul>{task.acceptance_criteria.map((criterion) => <li key={criterion}>{criterion}</li>)}</ul>}
          <h3>Validation commands</h3>
          {task.validation_commands.length === 0 ? <span className="muted">No deterministic checks configured.</span> : <ul>{task.validation_commands.map((command) => <li key={`${command.type}:${command.name}`}><strong>{command.type}</strong> · {command.command}</li>)}</ul>}
        </article>

        <article className="detail-panel">
          <h2>Latest attempt</h2>
          {!latest ? <span className="muted">No attempt yet.</span> : (
            <dl className="kv-list">
              <div><dt>Status</dt><dd><StateBadge state={latest.status} /></dd></div>
              <div><dt>Harness</dt><dd>{latest.harness_version ?? latest.harness}</dd></div>
              <div><dt>Branch</dt><dd>{latest.branch_name}</dd></div>
              <div><dt>Commit</dt><dd>{latest.commit_sha ?? "—"}</dd></div>
              <div><dt>Started</dt><dd>{formatTime(latest.started_at)}</dd></div>
              <div><dt>Exit</dt><dd>{latest.exit_code ?? "—"}</dd></div>
            </dl>
          )}
        </article>
      </div>

      <article className="detail-panel section-block">
        <div className="section-heading"><h2>Validation</h2><span>{checks.length} checks</span></div>
        {checks.length === 0 ? <span className="muted">No persisted validation results.</span> : (
          <div className="timeline">{checks.map((check) => (
            <div key={check.id}>
              <span>{check.check_type}</span><strong>{check.name} · {check.status}</strong><small>{check.command}{check.exit_code === null ? "" : ` · exit ${check.exit_code}`}</small>
            </div>
          ))}</div>
        )}
      </article>

      <article className="log-panel">
        <div className="section-heading"><h2>Diff</h2><span>{diff?.commit_sha?.slice(0, 8) ?? "—"}</span></div>
        <pre>{diff?.stat ? `${diff.stat}\n\n${diff.patch}` : "No persisted diff yet."}</pre>
      </article>

      <article className="detail-panel section-block">
        <div className="section-heading"><h2>Review</h2><span>{reviews.length} decisions</span></div>
        {canReview && (
          <div className="task-form">
            <label>Review feedback<textarea rows={3} value={feedback} onChange={(event) => setFeedback(event.target.value)} placeholder="Required for rejection, optional for approval" /></label>
            <div>
              <button className="button" disabled={actionBusy} onClick={() => void runAction(() => api.approveTask(taskId, feedback))}>Approve</button>
              <button className="button button--secondary" disabled={actionBusy || !feedback.trim()} onClick={() => void runAction(async () => { await api.rejectTask(taskId, feedback); setFeedback(""); })}>Reject + retry</button>
            </div>
          </div>
        )}
        {canMerge && <button className="button" disabled={actionBusy} onClick={() => void runAction(() => api.mergeTask(taskId))}>Merge reviewed commit</button>}
        {task.merge_commit_sha && <p>Merge commit: <code>{task.merge_commit_sha}</code></p>}
        {reviews.length === 0 ? <span className="muted">No review decisions yet.</span> : (
          <div className="timeline">{reviews.map((review) => (
            <div key={review.id}>
              <span>{formatTime(review.created_at)}</span><strong>{review.decision} by {review.actor}</strong><small>{review.feedback || "No feedback"}</small>
            </div>
          ))}</div>
        )}
      </article>

      <article className="log-panel">
        <div className="section-heading"><h2>Worker logs</h2><span>{logs?.status ?? "IDLE"}</span></div>
        <pre>{logs?.logs || "No logs yet."}</pre>
      </article>

      <article className="detail-panel section-block">
        <h2>Transition history</h2>
        {task.transitions.length === 0 ? <span className="muted">No transitions yet.</span> : (
          <div className="timeline">{task.transitions.map((transition) => (
            <div key={transition.id}>
              <span>{formatTime(transition.occurred_at)}</span><strong>{transition.from_state} → {transition.to_state}</strong><small>{transition.reason ?? "No reason recorded"}</small>
            </div>
          ))}</div>
        )}
      </article>
    </section>
  );
}

function NotFound() {
  return (
    <section>
      <PageHeader eyebrow="404" title="Route not found" description="This part of the forge does not exist." />
      <AsyncState kind="error" title="Unknown route" detail="Use the navigation to return to an operational view." />
    </section>
  );
}

export function App() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block"><div className="brand-mark" aria-hidden="true">✦</div><div><strong>Nidavelir</strong><span>control plane</span></div></div>
        <nav aria-label="Primary navigation">
          {navigation.map((item) => <NavLink key={item.to} to={item.to} end={item.end} className={({ isActive }) => (isActive ? "nav-link nav-link--active" : "nav-link")}>{item.label}</NavLink>)}
        </nav>
        <div className="sidebar-status"><span className="status-dot" /><span>pre-alpha</span></div>
      </aside>
      <main className="content">
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/board" element={<Board />} />
          <Route path="/agents" element={<Agents />} />
          <Route path="/tasks/:taskId" element={<TaskDetail />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
    </div>
  );
}
