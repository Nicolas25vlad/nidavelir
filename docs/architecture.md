# Architecture

Nidavelir is built around one boundary: the orchestration plane is durable; execution environments are disposable.

## Components

### Core

Owns task state, attempts, scheduling, validation, Git operations and worker lifecycle.

### MCP server

Exposes a narrow remote-control surface. It translates tool calls into Core operations and does not own durable state.

### Worker runtime

A disposable Docker image containing the coding agent and the minimum toolchain required for the assigned task.

### Web

A read-heavy operational interface for task state, active workers, logs, diffs and validation history.

### PostgreSQL

Stores durable tasks, attempts, state transitions, validation results and audit events.

## Core invariants

1. A worker cannot close its own task.
2. A worker cannot write directly to a protected branch.
3. Destroying a worker cannot delete the durable task record.
4. Every execution attempt is independently addressable and auditable.
5. Validation results are attached to a specific attempt and revision.
6. The Docker control plane is never exposed inside worker containers.

## Task model

A task should minimally contain:

- stable ID;
- title and description;
- target repository;
- acceptance criteria;
- state;
- priority;
- dependencies;
- selected worker profile;
- current attempt;
- timestamps and audit metadata.

An attempt should minimally contain:

- attempt ID;
- task ID;
- container ID;
- branch/ref;
- agent type;
- started/finished timestamps;
- exit state;
- logs reference;
- produced commit/ref;
- validation result.

## Initial execution sequence

```text
create_task
    ↓
queue task
    ↓
create task branch
    ↓
create isolated container
    ↓
clone / checkout repository
    ↓
launch coding agent
    ↓
stream progress + logs
    ↓
agent submits result
    ↓
run validation
    ↓
approve ─────────────── reject
   │                       │
   ▼                       ▼
 merge                 destroy attempt
   │                   create new attempt
   ▼
close task
```

## Open decisions

- whether the queue remains database-backed for the MVP or gets a dedicated broker later;
- how credentials are injected and revoked per task;
- which network policy mechanism is used for workers;
- whether validation runs inside a second clean container or a dedicated validation worker;
- how repository providers beyond GitHub are abstracted;
- how long logs and task artifacts are retained.
