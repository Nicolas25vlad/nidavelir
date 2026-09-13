<div align="center">
  <img src="assets/nidavelir-logo.svg" alt="Nidavelir" width="860" />

  <p><strong>An MCP-native development forge for isolated, observable and verifiable autonomous coding work.</strong></p>
  <p>Durable tasks. Disposable workers. Replaceable supervisors. Verified work.</p>

  <p>
    <a href="https://github.com/Nicolas25vlad/nidavelir/stargazers"><img alt="GitHub stars" src="https://img.shields.io/github/stars/Nicolas25vlad/nidavelir?style=flat&logo=github" /></a>
    <a href="https://github.com/Nicolas25vlad/nidavelir/issues"><img alt="Open issues" src="https://img.shields.io/github/issues/Nicolas25vlad/nidavelir?style=flat&logo=github" /></a>
    <img alt="Project status" src="https://img.shields.io/badge/status-pre--alpha-d29922" />
    <img alt="MCP" src="https://img.shields.io/badge/control_plane-MCP-8b949e" />
    <img alt="License" src="https://img.shields.io/github/license/Nicolas25vlad/nidavelir" />
  </p>
</div>

---

## What is Nidavelir?

Nidavelir is a self-hosted orchestration system that lets an external coding assistant act as a **supervisor** over disposable coding workers while tasks, logs, diffs, checks and review history remain durable.

Its core rule is: **tasks are durable, workers are disposable, supervisors are replaceable.**

A normal Codex, Cursor, Claude Code or ChatGPT project/chat can remain your primary interface. Instead of doing every code change itself, that supervisor controls Nidavelir through MCP. Nidavelir then launches isolated worker containers that run CLI coding agents such as Codex CLI or Cursor Agent CLI.

The supervisor and worker harness are independent choices. A Codex supervisor may delegate a task to a Cursor CLI worker, another Codex CLI worker or any future compatible worker harness.

```text
Codex / Cursor / Claude / ChatGPT supervisor
                  │
                  │ MCP
                  ▼
          Nidavelir Control Plane
       tasks · queue · context · review
                  │
                  ▼
       disposable worker container
                  │
                  ├── Codex CLI
                  ├── Cursor Agent CLI
                  └── future worker harnesses
```

A worker harness may claim that its work is complete. Nidavelir does not treat that claim as approval. The resulting branch is captured, validated and reviewed before a controlled merge can make it permanent.

> **Completion is a claim, not a fact.**

## How it works

```text
supervisor creates task through MCP
    │
    ▼
persist durable task + supervisor metadata
    │
    ▼
choose worker harness + resolve agent profile
    │
    ▼
allocate isolated Docker worker
    │
    ▼
checkout task branch
    │
    ▼
worker CLI executes with curated Skills
    │
    ▼
persist logs + commit + complete diff
    │
    ▼
run deterministic test / lint / build checks
    │
    ▼
VALIDATING
    ├── reject + feedback ─► NEEDS_CHANGES ─► fresh attempt
    └── approve ───────────► verify reviewed SHA ─► merge ─► CLOSED
```

The worker never receives authority to merge protected branches. Git publication and merge are separate orchestration boundaries controlled by Nidavelir Core.

## Task lifecycle

```text
BACKLOG → QUEUED → RUNNING → AGENT_DONE → VALIDATING
                                      │
                                      ├──► NEEDS_CHANGES ──► QUEUED
                                      │
                                      └──► APPROVED ──► MERGED ──► CLOSED
```

Task state, attempts, validation checks, review decisions and captured patches survive worker destruction and supervisor disconnects.

## Agent Profiles & Skills

A frontend task should not receive the same execution briefing as a database migration or Docker change. Nidavelir resolves an **Agent Profile** before launching the worker harness and exposes a curated skill bundle for that domain.

Current profiles:

| Profile | Focus | Additional Skills |
| --- | --- | --- |
| `generic` | ordinary repository work | base bundle only |
| `frontend` | React / TypeScript / UI | React, TypeScript, feature architecture, Vitest |
| `backend` | APIs and services | FastAPI, PostgreSQL practices |
| `fullstack` | cross-stack changes | frontend + backend bundle |
| `infra` | Docker / Kubernetes / operations | Docker Compose, Kubernetes |
| `testing` | verification and E2E | Playwright, Vitest |
| `database` | PostgreSQL / SQL / migrations | PostgreSQL best practices |
| `android` | Android application work | selected official Android skills |
| `docs` | documentation | base bundle only |

**Ponytail is part of the base bundle for every coding task.** Domain skills are additive. The full skill store is baked into the worker image, but only base + resolved-profile skills are placed in the harness discovery paths for a given attempt.

The first profile layer resolves automatically from task wording and lightweight repository signals. If frontend and backend signals are both strong, the task resolves to `fullstack`. Persisted explicit profile overrides and immutable per-attempt profile/skill snapshots are tracked in #60.

Skills are fetched during image build from exact Git commit SHAs declared in [`worker/skills.lock.json`](worker/skills.lock.json). They are not downloaded from a floating `latest` branch at task runtime. Source license texts are retained under `/opt/nidavelir/third-party/licenses` inside the worker image.

### Worker communication contract

Workers are executors, not chat partners. Their system briefing explicitly tells them to:

- spend tokens on implementation and tools rather than narration;
- avoid routine progress chatter and explanations of private reasoning;
- ask questions only when execution is genuinely blocked by missing information;
- keep the final response short, containing outcome, checks and any blocker.

Nidavelir reads durable Git state, structured results, logs and validation records. A beautiful essay from a worker has approximately zero operational value.

### Third-party Skill credits

Nidavelir does not claim ownership of bundled third-party Agent Skills. They remain governed by their upstream licenses and are pinned for reproducibility.

| Source | Used for | Credit | License | Pinned revision |
| --- | --- | --- | --- | --- |
| [Ponytail](https://github.com/DietrichGebert/ponytail) | base skill for all workers | Dietrich Gebert | MIT | `356918e` |
| [React Frontend Skills](https://github.com/PyModel/react-frontend-skills) | React, TypeScript, frontend architecture, Vitest | Mohamed Elkholy / PyModel | MIT | `aec25a4` |
| [FastAPI](https://github.com/fastapi/fastapi) | official FastAPI agent guidance | FastAPI / Sebastián Ramírez | MIT | `50113da` |
| [Agent Skills](https://github.com/magnus919/agent-skills) | Docker Compose, Kubernetes, Playwright | Magnus Hedemark | MIT | `d0edebb` |
| [Supabase Agent Skills](https://github.com/supabase/agent-skills) | PostgreSQL best practices | Supabase | MIT | `8331f91` |
| [Android Skills](https://github.com/android/skills) | official Android guidance | Google / Android | Apache-2.0 | `bac232f` |

See the lockfile for exact source paths and full revisions. Third-party licenses are copied into the distributed worker image during build.

## Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                    External supervisors                     │
│            Codex · Cursor · Claude · ChatGPT               │
└────────────────────────────┬────────────────────────────────┘
                             │ authenticated MCP
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                       Nidavelir Core                        │
│                                                             │
│ Task Engine · Queue · Docker · Git · Validation · Review   │
└──────────────┬─────────────────────────────┬────────────────┘
               │                             │
               ▼                             ▼
      ┌──────────────────┐          ┌────────────────────┐
      │    PostgreSQL    │          │   Docker Engine    │
      │ tasks / attempts │          │ worker lifecycle   │
      │ checks / reviews │          └─────────┬──────────┘
      └──────────────────┘                    │
                                  ┌───────────┴───────────┐
                                  ▼                       ▼
                           Codex CLI worker         Cursor CLI worker
```

Core owns Docker lifecycle. Workers never receive the Docker socket. Git helpers receive the credentials needed for clone/push; coding harnesses do not receive unrelated infrastructure secrets.

On shared Docker hosts, every Nidavelir installation gets its own installation namespace. Disposable containers and volumes are labeled with that namespace, and destructive cleanup is scoped to resources created by that installation. Nidavelir does not use global Docker prune operations.

For stronger isolation, production can point Nidavelir at a dedicated or rootless Docker daemon using `NIDAVELIR_DOCKER_SOCKET`.

See [`docs/architecture.md`](docs/architecture.md) for design notes.

## MCP control plane

The MCP server is an adapter over Core, not a second source of truth. Current tools cover task creation and updates, execution, logs, diffs, validation results, review decisions and controlled merge.

Typical surface:

```text
list_harnesses
create_task
list_tasks
get_task
update_task
start_task
cancel_task
get_agent_status
get_agent_logs
get_task_diff
get_validation_checks
get_reviews
approve_task
reject_task
merge_task
```

Streamable HTTP MCP is protected by bearer authentication. Production binds Web and MCP to loopback by default; expose them remotely only behind the network controls appropriate for the server.

## Web interface

The Web UI is an operational cockpit over the same durable state:

| View | Purpose |
| --- | --- |
| **Overview** | active work and recent state |
| **Board** | durable task lifecycle |
| **Agents** | worker attempts and runtime status |
| **Task detail** | worker harness, logs, diff, checks, review feedback, approve/reject and merge |

The visual rule is simple: if a pixel does not help answer an operational question, it probably owes rent.

No fake analytics. No giant empty cards. No decorative dashboard sludge.

## Self-hosting

The production deployment is designed to behave like an appliance. A normal server does not need to keep a Git clone around.

Initial installation is the privileged step:

```bash
curl -fsSL https://raw.githubusercontent.com/Nicolas25vlad/nidavelir/main/deploy/install.sh | sudo bash
```

After installation, routine operation is intentionally unprivileged:

```bash
nidavelir doctor
nidavelir update
nidavelir status
nidavelir logs core
nidavelir restart core
```

The installer creates a per-installation Docker namespace, persistent PostgreSQL storage, random MCP authentication material and an operator group. Updates pull published GHCR images while preserving `.env` and database state.

Production defaults are loopback-first:

```text
Web  127.0.0.1:8080
MCP  127.0.0.1:8001/mcp
Core internal Docker network only
```

Ports, worker concurrency, CPU and memory budgets are configurable for servers that already run other workloads. See [`deploy/README.md`](deploy/README.md).

## Security model

Nidavelir assumes coding agents are powerful, useful and entirely capable of doing something spectacularly dumb.

Important boundaries:

- workers run unprivileged;
- workers do not receive `/var/run/docker.sock`;
- workers do not receive unrestricted host filesystem mounts;
- task workers have CPU, memory and execution-time limits;
- persistent Nidavelir services have configurable resource ceilings;
- task branches are separate from protected branches;
- merge requires explicit approval and verification that the reviewed SHA did not move;
- MCP HTTP access requires authentication;
- worker cleanup is scoped to the current Nidavelir installation;
- agent completion never bypasses independent validation.

Isolation is product behavior, not a deployment footnote.

## Repository layout

```text
nidavelir/
├── core/          # orchestrator, task state, Docker, Git, validation, review
├── mcp/           # authenticated supervisor control-plane adapter
├── worker/        # disposable Codex/Cursor worker CLI runtime + Agent Skills
├── web/           # operational cockpit
├── deploy/        # appliance-style self-hosted deployment
├── docs/          # architecture notes
├── assets/        # project identity
└── compose.yaml   # development stack
```

## Roadmap

The project is moving from a single-worker MVP toward reliable self-dogfooding.

**Current focus:** stable durable execution, supervisor/worker separation, persistent worker-harness login, curated Agent Profiles/Skills, MCP bundle management, project context/wiki, and enough recovery behavior for Nidavelir to safely implement its own issues.

Later phases add richer dependency-aware scheduling, multiple concurrent specialist agents and automated reviewer/QA roles. The rule remains the same: autonomy only increases after observability and validation can keep up with it.

## Design principles

1. **Tasks are durable. Workers are disposable. Supervisors are replaceable.**
2. **Completion is a claim, not a fact.**
3. **Isolation by default.**
4. **Git is the permanence boundary.**
5. **MCP controls the system, not its internals.**
6. **Observability before autonomy.**
7. **Give each worker the minimum useful context and tools.**
8. **Agent prose is disposable; artifacts and evidence are durable.**
9. **Supervisor identity and worker harness are independent.**
10. **The UI earns every pixel.**

## Project status

> [!IMPORTANT]
> **Pre-alpha.** The main end-to-end task lifecycle is implemented, but Nidavelir is still being hardened before relying on it as its own primary development environment.

The milestone is no longer “can a worker modify a repository?” The milestone is **can Nidavelir repeatedly develop Nidavelir while external supervisors coordinate it without babysitting containers, credentials or broken state?**

## License

Nidavelir itself is released under the [MIT License](LICENSE). Bundled third-party skills retain their own upstream licenses as documented above and inside the worker image.

---

<div align="center">
  <sub><strong>Nidavelir</strong> · Durable tasks. Disposable workers. Replaceable supervisors.</sub>
</div>
