# Nidavelir Worker

Disposable runtime used for isolated coding attempts.

The worker image contains Codex CLI, Cursor Agent CLI, a small common shell toolset, profile resolution, validation helpers, and a pinned read-only Agent Skills catalog. It is deliberately not the supervisor. External Codex/Cursor/Claude/ChatGPT sessions control Nidavelir through MCP; the CLI inside this container is only the execution harness for one attempt.

## Execution model

```text
external supervisor
      │ MCP
      ▼
Nidavelir Core
      │
      ▼
disposable worker container
      │
      ├── Codex CLI
      └── Cursor Agent CLI
```

Supervisor identity and worker harness are independent. A task requested by Codex may execute using Cursor CLI and vice versa.

## Agent profiles

Before invoking a worker harness, `nidavelir-resolve-profile` combines task wording with repository signals and selects a domain briefing.

Current profiles:

| Profile | Primary concern |
| --- | --- |
| `generic` | ordinary repository changes |
| `frontend-web` | browser UI, React/TypeScript, accessibility and state boundaries |
| `backend` | API contracts, services, persistence and failure semantics |
| `fullstack` | coordinated frontend/backend contracts |
| `devops` | Docker, Kubernetes, CI/CD, deployment and operations |
| `qa` | regression, integration, E2E and failure-path testing |
| `database` | PostgreSQL, migrations, locking and query behavior |
| `android-xml` | Android Views/XML, Fragments, resources and lifecycle |
| `android-compose` | Jetpack Compose, state flow and side effects |
| `design` | information hierarchy, interaction states, accessibility and visual consistency |
| `docs` | precise repository documentation |

Android XML and Compose are separate profiles. The resolver uses task text plus repository evidence such as `res/layout`, `Fragment`, `RecyclerView`, `@Composable` and `setContent`.

Legacy explicit names are normalized for compatibility:

```text
frontend -> frontend-web
infra    -> devops
testing  -> qa
android  -> XML or Compose auto-detection
```

A short shared `base_instructions` policy applies to every profile. Domain prompts only add what is specific to that specialty. This keeps the stable prefix compact and improves prompt-cache reuse.

## Skills

Ponytail is the only universal Skill. Everything else is demand-loaded.

Examples:

- frontend work receives React + TypeScript; feature architecture/Vitest appear only when relevant;
- DevOps work receives Docker Compose or Kubernetes only when the task/repository signals require them;
- backend work receives FastAPI/PostgreSQL guidance only when those technologies are involved;
- QA work receives Playwright/Vitest only when they match the test surface;
- Android-specific testing/system Skills are exposed only to Android attempts that need them.

The complete Skill store is baked into the image, but only base + selected skills are linked into harness discovery paths for the current attempt.

All third-party Skills are fetched during image build from exact Git revisions declared in `skills.lock.json`. Their license texts are copied into `/opt/nidavelir/third-party/licenses`.

## Token efficiency

Token use is a runtime resource. Workers therefore default to an economy policy instead of maximum deliberation:

| Setting | Default | Purpose |
| --- | --- | --- |
| `NIDAVELIR_CODEX_REASONING_EFFORT` | `low` | avoid expensive reasoning for routine implementation |
| `NIDAVELIR_CODEX_VERBOSITY` | `low` | minimize prose/output tokens |
| `NIDAVELIR_CODEX_TOOL_OUTPUT_TOKEN_LIMIT` | `4000` | limit command/file output that can inflate later context |
| `NIDAVELIR_CODEX_PROJECT_DOC_MAX_BYTES` | `16384` | bound automatic project-instruction ingestion |

Reasoning can be escalated for harder workloads, but escalation should be explicit and measurable.

The prompt layout keeps shared policy/profile instructions before task-specific text to maximize provider prompt-cache reuse. Empty optional sections are omitted.

Codex runs with JSON events and the worker extracts usage from `turn.completed` into `NIDAVELIR_RESULT`: input, cached input, cache-write input, output, reasoning output and total tokens. Cursor currently reports `token_usage: null` until the CLI path used by Nidavelir exposes equivalent metrics.

## Communication contract

Disposable workers are executors, not chat partners.

They are instructed to:

- inspect existing code before changing it;
- implement rather than narrate;
- avoid progress chatter and reasoning recap;
- touch only what the task requires;
- use repository instructions and relevant Skills when useful;
- keep final prose to outcome, checks and blocker, at most a few short lines.

Durable evidence lives in Git state, structured results, diffs, validation records and bounded logs.

## Validation plan

The worker resolves validation before coding finishes so Nidavelir can persist what should be checked independently of the harness response.

A plan is one of:

- `configured`: explicit task checks;
- `auto`: conservative checks inferred from known project signals;
- `skipped`: no safe deterministic check was found.

`skipped` is explicitly surfaced as unvalidated work rather than silently counting as success.

## Runtime isolation

The container runs as the unprivileged `nidavelir` user (UID/GID `10001`) and uses `/workspace/repo` as its working directory.

Workers must not receive:

- `/var/run/docker.sock`;
- privileged mode;
- unrestricted host filesystem mounts;
- supervisor/MCP credentials;
- credentials for worker harnesses that were not selected.

CPU, memory and timeout limits are applied by the orchestrator when it creates the container.

## Performance direction

Disposable workers should be cheap to create even when many tasks run concurrently.

The runtime design therefore favors:

- prebuilt worker images, never `docker build` in the task hot path;
- runtime-specific images instead of one image containing every language SDK;
- safe npm/pip/Gradle/Cargo cache reuse;
- Git object/mirror reuse while keeping attempt workspaces isolated;
- fewer helper-container transitions when they add no meaningful security boundary;
- no pool of idle coding-agent containers consuming RAM.

The goal is ephemeral workers on top of warm reusable infrastructure.

## Build

```bash
docker build -t nidavelir-worker:dev worker/
```

Pin harness versions when reproducibility matters:

```bash
docker build \
  --build-arg CODEX_VERSION=<version> \
  -t nidavelir-worker:<version> \
  worker/
```

## Smoke test

```bash
docker run --rm \
  --cpus=1 \
  --memory=1g \
  nidavelir-worker:dev \
  codex --version
```
