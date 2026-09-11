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
