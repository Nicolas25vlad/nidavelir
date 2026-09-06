<div align="center">
  <img src="assets/nidavelir-logo.svg" alt="Nidavelir" width="860" />

  <p><strong>An MCP-native development forge for isolated, observable and verifiable autonomous coding work.</strong></p>
  <p>Turn durable tasks into disposable coding-agent workers, review what they actually changed, and only then let the work become permanent.</p>

  <p>
    <a href="https://github.com/Nicolas25vlad/nidavelir/stargazers"><img alt="GitHub stars" src="https://img.shields.io/github/stars/Nicolas25vlad/nidavelir?style=flat&logo=github" /></a>
    <a href="https://github.com/Nicolas25vlad/nidavelir/network/members"><img alt="GitHub forks" src="https://img.shields.io/github/forks/Nicolas25vlad/nidavelir?style=flat&logo=github" /></a>
    <a href="https://github.com/Nicolas25vlad/nidavelir/issues"><img alt="Open issues" src="https://img.shields.io/github/issues/Nicolas25vlad/nidavelir?style=flat&logo=github" /></a>
    <img alt="Last commit" src="https://img.shields.io/github/last-commit/Nicolas25vlad/nidavelir?style=flat&logo=git" />
    <img alt="Project status" src="https://img.shields.io/badge/status-pre--alpha-d29922" />
    <img alt="MCP" src="https://img.shields.io/badge/control_plane-MCP-8b949e" />
    <img alt="License" src="https://img.shields.io/github/license/Nicolas25vlad/nidavelir" />
  </p>

  <p>
    <a href="#what-is-nidavelir">Overview</a> ·
    <a href="#architecture">Architecture</a> ·
    <a href="#quick-start">Quick start</a> ·
    <a href="#web-interface">Web UI</a> ·
    <a href="#roadmap">Roadmap</a>
  </p>
</div>

---

## What is Nidavelir?

Nidavelir is a self-hosted orchestration system for running coding agents as disposable workers.

Its core idea is intentionally simple: **tasks are durable, agents are not.**

A task lives in Nidavelir's board and moves through a controlled lifecycle. When execution starts, Nidavelir creates an isolated Docker container, checks out the target repository into a task-specific branch, launches a coding agent such as Codex CLI, streams its progress, and keeps the environment alive until the result is independently validated.

The worker can report that it is finished. It cannot decide that the task is finished.

<table>
<tr>
<td width="33%"><strong>Durable control plane</strong><br/><sub>Tasks, attempts, logs and validation history survive worker failure.</sub></td>
<td width="33%"><strong>Disposable execution</strong><br/><sub>Every attempt runs in an isolated environment that can be destroyed and recreated.</sub></td>
<td width="33%"><strong>Independent validation</strong><br/><sub>Agent completion is treated as a claim until checks and review accept the result.</sub></td>
</tr>
</table>

> **Completion is a claim, not a fact.** Nidavelir separates the agent that performs work from the system that decides whether that work is acceptable.

## Why?

Coding agents are useful, but giving an agent a shell and hoping for the best is not an orchestration model.

Nidavelir adds the missing control plane:

- **persistent tasks** instead of disposable chat context;
- **ephemeral workers** instead of long-lived agent machines;
- **isolated execution** instead of direct host access;
- **observable progress** instead of opaque background work;
- **explicit validation** instead of trusting an agent's final message;
- **branch-per-task Git workflows** instead of letting workers touch `main`;
- **MCP as the control surface** so an external orchestrator can create, inspect, reject, retry, approve and merge work.

## How it works

```text
create task
    │
    ▼
 persist task + acceptance criteria
    │
    ▼
 allocate isolated worker
    │
    ▼
 checkout task branch + launch coding agent
    │
    ▼
 stream logs / collect commits / capture result
    │
    ▼
 validate tests + policy + diff + acceptance criteria
    │
    ├── reject ──► destroy worker ──► retry with feedback
    │
    └── approve ─► merge ──► close task ──► destroy worker
```

The environment is temporary. The task history is not.

## Architecture

```text
┌───────────────────────────────────────────────────────────────────────┐
│                            MCP clients                                │
│                   ChatGPT · CLI · other agents                       │
└───────────────────────────────┬───────────────────────────────────────┘
                                │ MCP
                                ▼
┌───────────────────────────────────────────────────────────────────────┐
│                           Nidavelir Core                              │
│                                                                       │
│  API · Task Engine · Scheduler · Policy · Validation · Git · Events  │
└──────────────┬───────────────────────────┬────────────────────────────┘
               │                           │
               ▼                           ▼
      ┌──────────────────┐        ┌────────────────────────┐
      │    PostgreSQL    │        │      Docker Engine     │
      │ tasks / attempts │        │   worker lifecycle     │
      │ events / checks  │        └───────────┬────────────┘
      └──────────────────┘                    │
                                  ┌───────────┼───────────┐
                                  ▼           ▼           ▼
                              Worker #42  Worker #43  Worker #44
                              task branch task branch task branch
                              Codex CLI   Codex CLI   Codex CLI
```

The Docker control socket belongs to Nidavelir Core. Workers should never receive `/var/run/docker.sock` or privileged host mounts.

See [`docs/architecture.md`](docs/architecture.md) for the current design notes.

## Task lifecycle

Nidavelir keeps protocol and persistence states deliberately boring and machine-friendly. The Norse identity belongs in the product surface, not in state-machine cosplay.

```text
BACKLOG → QUEUED → RUNNING → AGENT_DONE → VALIDATING
                                      │
                                      ├──► NEEDS_CHANGES ──► QUEUED
                                      │
                                      └──► APPROVED ──► MERGED ──► CLOSED
```

`AGENT_DONE` means only that the worker submitted a result. Tests, policy checks, diff inspection or external review can still reject it.

## Quick start

Nidavelir is currently pre-alpha, so the bootstrap stack is not yet a complete runnable product. The intended local workflow is:

```bash
git clone https://github.com/Nicolas25vlad/nidavelir.git
cd nidavelir
cp .env.example .env
docker compose up --build
```

The first executable milestone will support this path end to end:

```text
MCP create_task
      ↓
PostgreSQL task
      ↓
Docker worker
      ↓
Codex CLI
      ↓
logs + diff + checks
      ↓
MCP approve_task / reject_task
```

<details>
<summary><strong>Planned MCP surface</strong></summary>

<br/>

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

MCP is the control surface, not the persistence layer. Tasks, logs, attempts and validation results remain durable inside Nidavelir.

</details>

<details>
<summary><strong>Worker execution model</strong></summary>

<br/>

Every execution attempt gets its own isolated environment:

```text
task 42
└── attempt 3
    ├── container: nidavelir-task-42-attempt-3
    ├── workspace: /workspace/repo
    ├── branch: task/42-fix-refresh-token
    ├── agent: codex
    └── limits: cpu / memory / timeout / network policy
```

A worker should be replaceable at any time. If an attempt crashes or produces a bad result, Nidavelir records the attempt, destroys the container and can launch a clean one with updated feedback.

</details>

<details>
<summary><strong>Git model</strong></summary>

<br/>

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

</details>

## Web interface

The web UI is an operational cockpit, not the source of truth.

The visual direction is intentionally restrained: dense information, strong hierarchy, excellent typography, fast scanning and almost no ornamental dashboard furniture.

| View | Purpose |
| --- | --- |
| **Overview** | briefing of active work, blocked tasks, failed attempts and recent completions |
| **Board** | kanban view of durable task state |
| **Agents** | active and historical worker attempts, runtime, resources and status |
| **Task detail** | prompt, acceptance criteria, logs, diff, checks, attempts and validation history |

The UI should answer operational questions quickly:

```text
What is running?
What is blocked?
What failed?
What changed?
What needs my decision?
What can safely disappear?
```

No fake analytics. No giant empty cards. No decorative gradients pretending to be information. No AI-dashboard sludge.

<details>
<summary><strong>Security model</strong></summary>

<br/>

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

</details>

<details>
<summary><strong>Planned stack</strong></summary>

<br/>

| Layer | Direction |
| --- | --- |
| Orchestrator | Python + FastAPI |
| Task state | PostgreSQL |
| Agent protocol | MCP |
| Worker runtime | Docker Engine |
| Initial coding agent | Codex CLI |
| Web UI | React + TypeScript |
| Repository integration | Git + GitHub |

The implementation is still intentionally flexible while the task model and worker lifecycle are being stabilized.

</details>

<details>
<summary><strong>Repository layout</strong></summary>

<br/>

```text
nidavelir/
├── assets/        # project identity and README assets
├── core/          # orchestrator, task engine, scheduler, validation
├── mcp/           # MCP server and tool definitions
├── worker/        # disposable agent runtime image
├── web/           # operational web interface
├── docs/          # architecture and design notes
└── compose.yaml   # local/self-hosted stack
```

These directories currently describe the target architecture. The project is still in its bootstrap phase.

</details>

## Roadmap

<table>
<tr>
<td width="25%" valign="top"><strong>01 · Execute</strong><br/><sub>Persistent tasks, MCP control, one isolated Codex worker, logs and manual approval.</sub></td>
<td width="25%" valign="top"><strong>02 · Verify</strong><br/><sub>Task branches, diffs, test gates, acceptance criteria, retry loops and controlled merge.</sub></td>
<td width="25%" valign="top"><strong>03 · Observe</strong><br/><sub>Board, task briefing, agent runtime, live logs, checks and audit history.</sub></td>
<td width="25%" valign="top"><strong>04 · Orchestrate</strong><br/><sub>Specialized agents, dependencies, parallel execution, QA and task decomposition.</sub></td>
</tr>
</table>

<details>
<summary><strong>Detailed roadmap</strong></summary>

<br/>

### Phase 1 · Single-worker MVP

- [ ] persistent task model;
- [ ] MCP task creation and inspection;
- [ ] create/destroy one Docker worker per task attempt;
- [ ] launch Codex CLI with task context;
- [ ] stream logs and collect exit state;
- [ ] manual approval or rejection.

### Phase 2 · Validation and Git workflow

- [ ] branch per task;
- [ ] commits and diff inspection;
- [ ] configurable test/lint/build checks;
- [ ] acceptance criteria;
- [ ] reject-and-retry loop;
- [ ] controlled merge.

### Phase 3 · Web operations

- [ ] overview briefing;
- [ ] kanban board;
- [ ] worker/agent visibility;
- [ ] live task logs;
- [ ] diff and validation views;
- [ ] attempt history and audit trail.

### Phase 4 · Multi-agent orchestration

- [ ] specialized worker profiles;
- [ ] dependency-aware tasks;
- [ ] parallel execution;
- [ ] QA/reviewer agents;
- [ ] task decomposition;
- [ ] resource-aware scheduling.

</details>

## Design principles

1. **Tasks are durable. Agents are disposable.** Execution can die without losing the work model.
2. **Completion is a claim, not a fact.** Agent output must be validated before a task closes.
3. **Isolation by default.** Workers receive the minimum host access required to perform a task.
4. **Git is the boundary.** Work happens on task branches and becomes permanent only after approval.
5. **MCP controls the system, not its internals.** The protocol stays small while Nidavelir owns state and policy.
6. **Observability before autonomy.** If the operator cannot understand what an agent is doing, the system is not ready for more autonomy.
7. **The UI earns every pixel.** Dense operational information beats decorative dashboard noise.

## Project status

> [!IMPORTANT]
> **Pre-alpha.** Nidavelir is currently being designed and bootstrapped. The architecture is public, but the end-to-end worker lifecycle is not implemented yet.

The first milestone is intentionally narrow: create a task through MCP, execute it inside an isolated Codex worker, inspect the result, approve or reject it, and tear the worker down cleanly.

## Contributing

The project is not yet accepting broad feature work while the task model and worker lifecycle are being stabilized.

Architecture discussions and narrowly scoped issues are welcome once the first executable skeleton lands.

## License

Nidavelir is released under the [MIT License](LICENSE).

---

<div align="center">
  <sub><strong>Nidavelir</strong> · Durable tasks. Disposable agents. Verified work.</sub>
</div>
