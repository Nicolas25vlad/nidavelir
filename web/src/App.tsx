import { NavLink, Route, Routes, useParams } from "react-router-dom";

const navigation = [
  { to: "/", label: "Overview", end: true },
  { to: "/board", label: "Board" },
  { to: "/agents", label: "Agents" },
];

type StatePanelProps = {
  title: string;
  detail: string;
  tone?: "muted" | "warning" | "danger";
};

function StatePanel({ title, detail, tone = "muted" }: StatePanelProps) {
  return (
    <div className={`state-panel state-panel--${tone}`}>
      <strong>{title}</strong>
      <span>{detail}</span>
    </div>
  );
}

function PageHeader({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  return (
    <header className="page-header">
      <span className="eyebrow">{eyebrow}</span>
      <h1>{title}</h1>
      <p>{description}</p>
    </header>
  );
}

function Overview() {
  return (
    <section>
      <PageHeader
        eyebrow="System briefing"
        title="Overview"
        description="A compact operational briefing will live here once Core exposes durable task state."
      />
      <div className="panel-grid">
        <StatePanel title="No task data yet" detail="Waiting for the task API from Core." />
        <StatePanel title="No active workers" detail="Worker runtime data lands with the attempt API." />
      </div>
    </section>
  );
}

function Board() {
  return (
    <section>
      <PageHeader
        eyebrow="Durable state"
        title="Board"
        description="Kanban columns will map directly to persisted task states, never local UI state."
      />
      <StatePanel title="Board not connected" detail="The board becomes live in issue #14." />
    </section>
  );
}

function Agents() {
  return (
    <section>
      <PageHeader
        eyebrow="Execution"
        title="Agents"
        description="Active and historical worker attempts will be visible here without opening raw Docker tooling."
      />
      <StatePanel title="No attempt stream" detail="Agent runtime visibility arrives with issue #15." />
    </section>
  );
}

function TaskDetail() {
  const { taskId } = useParams();

  return (
    <section>
      <PageHeader
        eyebrow={`Task ${taskId ?? "unknown"}`}
        title="Task detail"
        description="Prompt, acceptance criteria, attempts, logs, diff and validation will converge on this view."
      />
      <StatePanel title="Task unavailable" detail="Task detail is intentionally a shell until the Core API exists." />
    </section>
  );
}

function NotFound() {
  return (
    <section>
      <PageHeader eyebrow="404" title="Route not found" description="This part of the forge does not exist." />
      <StatePanel title="Unknown route" detail="Use the navigation to return to an operational view." tone="warning" />
    </section>
  );
}

export function App() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-mark" aria-hidden="true">✦</div>
          <div>
            <strong>Nidavelir</strong>
            <span>control plane</span>
          </div>
        </div>

        <nav aria-label="Primary navigation">
          {navigation.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => (isActive ? "nav-link nav-link--active" : "nav-link")}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-status">
          <span className="status-dot" />
          <span>pre-alpha</span>
        </div>
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
