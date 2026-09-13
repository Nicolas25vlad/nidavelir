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

Nidavelir is a self-hosted orchestration system that lets a normal coding assistant act as a **supervisor** over isolated coding workers while tasks, attempts, logs, diffs, validation and review history remain durable.

Its core rule is:

> **Tasks are durable. Workers are disposable. Supervisors are replaceable.**

A Codex, Cursor, Claude Code or ChatGPT project/chat remains your primary interface. Instead of replacing that harness, Nidavelir changes its role: the external agent coordinates work through MCP while disposable containers run CLI coding agents that actually modify repositories.

The product used as supervisor and the CLI used as worker are independent choices. A Codex supervisor may delegate to a Cursor Agent CLI worker; a Cursor supervisor may delegate to Codex CLI; multiple supervisors can control different projects through the same Nidavelir installation.

```text
Codex / Cursor / Claude / ChatGPT
        external supervisor
                │
                │ authenticated MCP
                ▼
        Nidavelir Control Plane
 tasks · attempts · context · validation · review
                │
                ▼
       disposable worker container
                │
          worker harness CLI
        ┌───────┴────────┐
        ▼                ▼
    Codex CLI      Cursor Agent CLI
```

Supervisor metadata is persisted separately from worker execution metadata. Closing a supervisor chat does not kill the task, and changing the worker harness does not change who requested the work.

A worker may claim that its work is complete. Nidavelir does not treat that claim as approval.

> **Completion is a claim, not a fact.**

## How it works

```text
supervisor creates task through MCP
    │
    ▼
persist durable task + optional supervisor/project metadata
    │
    ▼
choose worker harness + resolve domain profile
    │
    ▼
allocate isolated Docker workspace
    │
    ▼
worker CLI executes with curated Skills + compact system briefing
    │
    ▼
persist logs + structured result + commit + complete diff
    │
    ▼
run configured or safely auto-resolved validation checks
    │
    ▼
VALIDATING
    ├── reject + structured feedback ─► NEEDS_CHANGES ─► fresh attempt
    └── approve ──────────────────────► verify reviewed SHA ─► merge ─► CLOSED
```

The worker never receives authority to merge protected branches. Git publication, validation, review and merge are separate orchestration boundaries controlled by Nidavelir.

## Task lifecycle

```text
BACKLOG → QUEUED → RUNNING → AGENT_DONE → VALIDATING
                                      │
                                      ├──► NEEDS_CHANGES ──► QUEUED
                                      │
                                      └──► APPROVED ──► MERGED ──► CLOSED
```

Task state, attempts, validation plans, validation checks, review decisions, token usage and captured patches survive worker destruction and supervisor disconnects.

## Supervisors vs worker harnesses

These concepts intentionally do not mean the same thing.

| Concept | Examples | Responsibility |
| --- | --- | --- |
| **Supervisor** | Codex app/chat, Cursor, Claude Code, ChatGPT | decomposes work, creates tasks, inspects evidence, coordinates multiple tasks |
| **Nidavelir** | Core + MCP + PostgreSQL + Web | durable orchestration, isolation, validation, review and merge boundaries |
| **Worker harness** | Codex CLI, Cursor Agent CLI | runs inside a disposable container and edits the repository |

A task may persist `supervisor_client`, `supervisor_session_id` and `project_id`, but those fields never select worker credentials or determine the task lifecycle.

This is deliberately supported:

```text
Codex supervisor  ──► Cursor CLI worker
Cursor supervisor ──► Codex CLI worker
```

Architecture regression tests keep that independence from accidentally collapsing back into one overloaded `harness` concept.

## Agent Profiles & Skills

Workers should be specialists, not one generic prompt wearing seven hats.

Nidavelir resolves a compact **Agent Profile** from task wording and repository signals, then combines a short shared worker policy with domain-specific instructions and demand-loaded Agent Skills.

Current profiles:

| Profile | Focus | Typical additional Skills |
| --- | --- | --- |
| `generic` | ordinary repository work | base bundle only |
| `frontend-web` | React / TypeScript / browser UI | React, TypeScript; architecture/Vitest when relevant |
| `backend` | APIs, services, contracts, persistence | FastAPI and PostgreSQL guidance when relevant |
| `fullstack` | coordinated frontend + backend changes | frontend bundle + backend/database guidance as needed |
| `devops` | Docker, Kubernetes, CI/CD, operations | Docker Compose or Kubernetes when relevant |
| `qa` | regression, integration, E2E and failure-path testing | Playwright or Vitest when relevant |
| `database` | PostgreSQL, SQL, migrations, locking | PostgreSQL best practices |
| `android-xml` | Android Views/XML apps | official Android testing/system guidance when relevant |
| `android-compose` | Jetpack Compose apps | official Android testing/system guidance when relevant |
| `design` | product/UI hierarchy and interaction design | base bundle only |
| `docs` | documentation | base bundle only |

Android XML and Jetpack Compose are separate profiles. The resolver looks at both task text and repository signals such as `res/layout`, `Fragment`, `RecyclerView`, `@Composable` and `setContent`.

`design` is also independent from frontend implementation. A visual/product task should reason about hierarchy, information architecture, states, accessibility, spacing and consistency before code mechanics.

Legacy profile names such as `frontend`, `infra`, `testing` and `android` are normalized by the worker resolver for compatibility.

**Ponytail is part of the base bundle for every coding task.** Domain skills are additive and demand-loaded. The full skill store is baked into the worker image, but only the skills relevant to the resolved profile are exposed in harness discovery paths for an attempt.

Skills are fetched at image build time from exact Git revisions declared in [`worker/skills.lock.json`](worker/skills.lock.json). Workers never install floating `latest` skills at task runtime.

### Worker communication contract

Workers are executors, not chat partners. Their briefing tells them to spend tokens on implementation and tools rather than narration.

The default contract is intentionally terse:

- no routine progress narration;
- no reasoning recap;
- change only what the task requires;
- use repository instructions and relevant Skills rather than rereading everything;
- keep the final response to outcome, checks and blocker, at most a few short lines.

Nidavelir cares about durable artifacts and evidence, not worker eloquence.

## Token efficiency

Parallel coding agents can turn token consumption into a black hole surprisingly quickly, so token efficiency is treated as an infrastructure concern alongside CPU and RAM.

Current worker defaults favor economy:

- Codex reasoning effort defaults to `low`;
- model verbosity defaults to `low`;
- reasoning summaries are disabled;
- tool output added back to model context is bounded;
- automatic project-document context has a size ceiling;
- stable policy/profile text appears before task-specific text to improve prompt-cache reuse;
- Skills are demand-loaded rather than exposing the entire skill store;
- worker prose is deliberately minimal;
- retry feedback is structured instead of repeatedly appending prose to the task description;
- Codex token usage is captured into attempt results and normalized fields when available.

The next cost-control layer is explicit per-task/project budgets, complexity-aware model/reasoning routing, retry escalation and scheduler admission based on token pressure instead of only container count.

## Validation

Validation is independent from the coding agent's claim of success.

Tasks may provide explicit validation commands. When they do not, the worker can safely resolve conservative checks from known repository signals. The resolved plan is persisted on the attempt as one of:

- `configured` - supplied by the task;
- `auto` - safely inferred from known project signals;
- `skipped` - no safe deterministic check could be inferred.

Unknown projects remain reviewable, but they are explicitly marked **UNVALIDATED** instead of silently looking green.

## Third-party Skill credits

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
┌───────────────────────────────────────────────────────────────┐
│                     External supervisors                      │
│             Codex · Cursor · Claude · ChatGPT                │
└──────────────────────────────┬────────────────────────────────┘
                               │ authenticated MCP
                               ▼
┌───────────────────────────────────────────────────────────────┐
│                         Nidavelir Core                         │
│ Task Engine · Execution · Git · Validation · Review · Merge  │
└──────────────┬───────────────────────────────┬────────────────┘
               │                               │
               ▼                               ▼
      ┌──────────────────┐            ┌────────────────────┐
      │    PostgreSQL    │            │   Docker Engine    │
      │ tasks / attempts │            │ isolated workers   │
      │ checks / reviews │            └─────────┬──────────┘
      │ token metadata   │                      │
      └──────────────────┘          ┌───────────┴───────────┐
                                    ▼                       ▼
                             Codex CLI worker         Cursor CLI worker
```

Workers never receive the Docker socket. Git helper stages receive the credentials needed for clone/push; coding harnesses do not receive unrelated infrastructure secrets.

A durable executor service that moves long-running Docker work fully out of the FastAPI process is being hardened separately. Until that lands, the current main branch still starts execution from Core. The target design uses PostgreSQL-backed leases and heartbeats so API restarts do not own agent lifetimes.

See [`docs/architecture.md`](docs/architecture.md) for design notes.

## Performance model

Disposable isolation should not mean repeatedly paying every expensive setup cost.

Nidavelir's performance direction is:

- build and publish worker images ahead of task execution, never build on the task hot path;
- keep worker concurrency bounded by CPU/RAM capacity;
- use smaller runtime-specific worker images where practical;
- reuse package-manager caches without sharing mutable workspaces;
- maintain local Git mirrors/object caches so repeated attempts do not reclone full repository history;
- reduce helper-container churn where isolation between phases does not add security value;
- avoid pools of idle agent containers consuming RAM for no work;
- schedule with task weight, token pressure and cache locality in mind.

The target is **ephemeral execution with warm infrastructure**: throw away the worker, not every useful cache underneath it.

## Shared Docker hosts

Nidavelir is designed to coexist with unrelated containers on the same server.

Every installation receives an installation namespace. Nidavelir-managed containers and volumes are labeled with that namespace, and destructive cleanup is restricted to matching resources. Nidavelir does not use host-wide Docker prune operations.

Persistent services and task workers have configurable CPU/RAM limits. Web and MCP ports are configurable, so Nidavelir does not require ownership of generic host ports.

For stronger isolation, production can point Nidavelir at a dedicated or rootless Docker daemon through `NIDAVELIR_DOCKER_SOCKET`. That moves Nidavelir workers into a separate Docker object namespace from the server's primary daemon.

## MCP control plane

The MCP server is an adapter over Core, not a second source of truth. It supports normal coding harnesses acting as supervisors while durable state stays in Nidavelir.

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

Task creation/listing can carry or filter supervisor metadata such as `supervisor_client`, `supervisor_session_id` and `project_id`. This allows multiple chats/projects to share one installation without coupling task durability to the lifetime of any one MCP client.

Streamable HTTP MCP is protected by bearer authentication. A future session-context layer will derive supervisor identity per MCP session rather than using one process-global identity, which is necessary when many supervisors share the same HTTP server.

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
- cleanup is scoped to the current Nidavelir installation;
- agent completion never bypasses independent validation;
- supervisor credentials and worker credentials are separate concerns.

Isolation is product behavior, not a deployment footnote.

## Repository layout

```text
nidavelir/
├── core/          # orchestration, durable task state, Docker, Git, validation, review
├── mcp/           # authenticated supervisor control-plane adapter
├── worker/        # disposable Codex/Cursor CLI runtime + profile resolver + Skills
├── web/           # operational cockpit
├── deploy/        # appliance-style self-hosted deployment
├── docs/          # architecture and repository notes
├── assets/        # project identity
└── compose.yaml   # development stack
```

## Roadmap

The project is moving from a working isolated-agent MVP toward reliable self-dogfooding.

**Current focus:**

- durable executor + crash/restart recovery;
- persistent worker-harness login without requiring API keys for normal account-based CLI usage;
- explicit durable profile overrides and immutable per-attempt profile/skill snapshots;
- token budgets and complexity-aware routing;
- project context/wiki packs that load only relevant context;
- Skills/MCP bundle registry and per-task allowlists;
- Web/Core authentication and stronger multi-supervisor session identity;
- Git/package caches and lighter worker runtime paths;
- enough E2E coverage for Nidavelir to safely implement its own backlog.

Later phases add dependency-aware scheduling, multiple concurrent specialist workers, automated reviewer/QA roles and more SCM providers. Autonomy only increases after observability and validation can keep up with it.

## Design principles

1. **Tasks are durable. Workers are disposable. Supervisors are replaceable.**
2. **Completion is a claim, not a fact.**
3. **Supervisor identity and worker harness are independent.**
4. **Isolation by default.**
5. **Git is the permanence boundary.**
6. **MCP controls the system, not its internals.**
7. **Observability before autonomy.**
8. **Give each worker the minimum useful context, Skills and credentials.**
9. **Token, CPU and RAM budgets are orchestration concerns.**
10. **Ephemeral execution should reuse safe warm infrastructure.**
11. **Agent prose is disposable; artifacts and evidence are durable.**
12. **The UI earns every pixel.**

## Project status

> [!IMPORTANT]
> **Pre-alpha.** The main end-to-end lifecycle works, but Nidavelir is still being hardened before relying on it as its own primary development environment.

The milestone is no longer “can a worker modify a repository?” The milestone is:

> **Can Nidavelir repeatedly develop Nidavelir while external supervisors coordinate it without babysitting containers, credentials, token spend or broken state?**

## License

Nidavelir itself is released under the [MIT License](LICENSE). Bundled third-party skills retain their own upstream licenses as documented above and inside the worker image.

---

<div align="center">
  <sub><strong>Nidavelir</strong> · Durable tasks. Disposable workers. Replaceable supervisors.</sub>
</div>
