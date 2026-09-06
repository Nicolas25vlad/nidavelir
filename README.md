<div align="center">

# Nidavelir

**An MCP-native development forge for isolated, verifiable autonomous coding work.**

Nidavelir turns development tasks into short-lived, sandboxed agent jobs: create a task, dispatch a worker, inspect the result, validate it, and destroy the environment when the work is done.

</div>

---

## What is Nidavelir?

Nidavelir is a self-hosted orchestration system for running coding agents as disposable workers.

Its core idea is intentionally simple: **tasks are durable, agents are not.**

A task lives in Nidavelir's board and moves through a controlled lifecycle. When execution starts, Nidavelir creates an isolated Docker container, checks out the target repository into a task-specific branch, launches a coding agent such as Codex CLI, streams its progress, and keeps the environment alive until the result is independently validated.

The worker does not decide that the job is finished. The orchestrator does.

```text
ChatGPT / MCP client
        │
        ▼
   Nidavelir Core
        │
        ├── task state
        ├── policy + validation
        ├── logs + artifacts
        └── worker lifecycle
                │
                ▼
       ephemeral Docker worker
                │
                ├── repository checkout
                ├── Codex CLI
                ├── tests / lint / build
                └── task branch
```

The result is a small self-hosted software factory that can be operated from any MCP-capable client without giving autonomous workers permanent access to the host.

## Why?

Coding agents are useful, but "give an agent a shell and hope" is not an orchestration model.

Nidavelir adds the missing control plane:

- **persistent tasks** instead of disposable chat context;
- **ephemeral workers** instead of long-lived agent machines;
- **isolated execution** instead of direct host access;
- **observable progress** instead of opaque background work;
- **explicit validation** instead of trusting an agent's final message;
- **branch-per-task Git workflows** instead of letting workers touch `main`;
- **MCP as the control surface** so an external orchestrator can create, inspect, reject, retry, approve and merge work.

## Task lifecycle

Nidavelir keeps internal states deliberately boring and machine-friendly. The Norse branding belongs in the UI, not in the protocol.

```text
BACKLOG
   │
   ▼
QUEUED
   │
   ▼
RUNNING
   │
   ▼
AGENT_DONE
   │
   ▼
VALIDATING
   ├──────────────► NEEDS_CHANGES ─────► QUEUED
   │
   └──────────────► APPROVED ──────────► MERGED ─────► CLOSED
```

A worker reaching `AGENT_DONE` means only that it has submitted a result. Tests, policy checks, diff inspection and external review can still reject the task.

## Architecture

```text
┌──────────────────────────────────────────────────────────────┐
│                       MCP clients                            │
│              ChatGPT · CLI · other agents                   │
└───────────────────────────┬──────────────────────────────────┘
                            │ MCP
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                     Nidavelir Core                           │
│                                                              │
│  API · Task Engine · Scheduler · Policy · Validation · Git  │
└───────────────┬──────────────────────────────┬───────────────┘
                │                              │
                ▼                              ▼
       ┌─────────────────┐            ┌─────────────────────┐
       │   PostgreSQL    │            │   Docker Engine     │
       │ tasks / events  │            │ worker lifecycle    │
       └─────────────────┘            └──────────┬──────────┘
                                                │
                              ┌─────────────────┼─────────────────┐
                              ▼                 ▼                 ▼
                         Worker #42        Worker #43        Worker #44
                         task branch       task branch       task branch
                         Codex CLI         Codex CLI         Codex CLI
```

The Docker control socket belongs to Nidavelir Core. Workers should never receive `/var/run/docker.sock` or privileged host mounts.

See [`docs/architecture.md`](docs/architecture.md) for the current design notes.

## MCP surface

The first version is expected to expose a deliberately small toolset:

```text
create_task
list_tasks
get_task
update_task
start_task
cancel_task

get_agent_status
get_agent_logs
get_task_diff
run_task_tests

approve_task
reject_task
merge_task
```

MCP is a control plane, not the place where implementation state lives. Tasks, logs, attempts and validation results remain durable inside Nidavelir.

## Workers

Every execution attempt gets its own isolated environment.

```text
task 42
└── attempt 3
    ├── container: nidavelir-task-42-attempt-3
    ├── workspace: /workspace/repo
    ├── branch: task/42-fix-refresh-token
    ├── agent: codex
    └── limits: cpu / memory / timeout / network policy
```

A worker should be replaceable at any time. If an attempt crashes or produces a bad result, Nidavelir records the attempt, destroys the container, and can launch a clean one with updated feedback.

## Git model

Workers never push directly to the protected branch.

```text
main
 └── task/42-fix-refresh-token
       ├── agent commits
       ├── validation
       ├── review
       └── merge after approval
```

A task can therefore fail spectacularly without turning the repository into modern art.

## Web interface

The web UI is an operational cockpit, not the source of truth.

The initial product surface is planned around four views:

| View | Purpose |
| --- | --- |
| **Overview** | compact briefing of active work, failures, blocked tasks and recent completions |
| **Board** | kanban view of durable task state |
| **Agents** | active and historical worker attempts, runtime, resource use and status |
| **Task detail** | prompt, acceptance criteria, logs, diff, checks, attempts and validation history |

The interface should favor dense, legible information over decorative dashboard furniture. No fake analytics, giant empty cards, gratuitous gradients or AI-generated control-panel sludge.

## Security model

Nidavelir assumes coding agents are powerful and fallible.

Initial constraints:

- workers run unprivileged;
- no Docker socket inside workers;
- no unrestricted host filesystem mounts;
- per-worker CPU, memory and execution limits;
- task-scoped credentials where possible;
- protected branches remain protected;
- force-push to protected branches is forbidden;
- all task transitions and worker attempts are auditable;
- network access should be restricted by policy rather than assumed safe.

Isolation is part of the product, not an optional deployment hardening step.

## Planned stack

The exact implementation is still intentionally flexible, but the current direction is:

| Layer | Direction |
| --- | --- |
| Orchestrator | Python + FastAPI |
| Task state | PostgreSQL |
| Agent protocol | MCP |
| Worker runtime | Docker Engine |
| Initial coding agent | Codex CLI |
| Web UI | React / TypeScript |
| Repository integration | Git + GitHub |

## Project layout

```text
nidavelir/
├── core/          # orchestrator, task engine, scheduler, validation
├── mcp/           # MCP server and tool definitions
├── worker/        # disposable agent runtime image
├── web/           # operational web interface
├── docs/          # architecture and design notes
└── compose.yaml   # local/self-hosted stack
```

The directories above describe the target layout. The project is currently in the architecture/bootstrap phase.

## Roadmap

### Phase 1 · Single-worker MVP

- persistent task model;
- MCP task creation and inspection;
- create/destroy one Docker worker per task attempt;
- launch Codex CLI with task context;
- stream logs and collect exit state;
- manual approval or rejection.

### Phase 2 · Validation and Git workflow

- branch per task;
- commits and diff inspection;
- configurable test/lint/build checks;
- acceptance criteria;
- reject-and-retry loop;
- controlled merge.

### Phase 3 · Web operations

- overview briefing;
- kanban board;
- worker/agent visibility;
- live task logs;
- diff and validation views;
- attempt history and audit trail.

### Phase 4 · Multi-agent orchestration

- specialized worker profiles;
- dependency-aware tasks;
- parallel execution;
- QA/reviewer agents;
- task decomposition;
- resource-aware scheduling.

## Design principles

1. **Tasks are durable. Agents are disposable.** Execution can die without losing the work model.
2. **Completion is a claim, not a fact.** Agent output must be validated before a task closes.
3. **Isolation by default.** Workers should receive the minimum host access required to perform a task.
4. **Git is the boundary.** Work happens on task branches and becomes permanent only after approval.
5. **MCP controls the system, not its internals.** The protocol stays small while Nidavelir owns state and policy.
6. **Observability before autonomy.** If the operator cannot understand what an agent is doing, the system is not ready for more autonomy.
7. **The UI earns every pixel.** Dense operational information beats decorative dashboard noise.

## Project status

**Pre-alpha.** Nidavelir is currently being designed and bootstrapped.

The first milestone is intentionally narrow: create a task through MCP, execute it inside an isolated Codex worker, inspect the result, approve or reject it, and tear the worker down cleanly.

## Contributing

The project is not yet accepting broad feature work while the task model and worker lifecycle are being stabilized.

Architecture discussions and narrowly scoped issues are welcome once the first executable skeleton lands.

## License

License not selected yet.

<div align="center">
  <strong>Durable tasks. Disposable agents. Verified work.</strong>
</div>
