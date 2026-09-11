# Nidavelir Worker

Disposable runtime image used for isolated coding-agent attempts.

The worker contains Codex CLI, Cursor Agent CLI, a small common shell toolset, and a pinned read-only catalog of Agent Skills. Repository-specific language runtimes still belong in dedicated worker images/profiles rather than turning the base image into a kitchen sink.

## Agent profiles

Before invoking a harness, `nidavelir-resolve-profile` classifies the task and exposes only the useful skills for that domain. Supported first-pass profiles are `generic`, `frontend`, `backend`, `fullstack`, `infra`, `testing`, `database`, `android`, and `docs`.

Ponytail is the only universal skill. Specialized skills are selected on demand from task/repository signals. For example, a frontend task does not receive Vitest unless testing is relevant, an infra task does not receive Kubernetes unless Kubernetes/Helm is involved, and a backend task does not receive PostgreSQL guidance merely because it is backend code.

The resolver understands an explicit `profile` field for forward compatibility; persisted Core/MCP/Web profile overrides and attempt snapshots are tracked separately in #60.

All third-party skills are fetched at image build time from exact Git revisions declared in `skills.lock.json`. Their license texts are copied into `/opt/nidavelir/third-party/licenses`.

## Token efficiency

Token use is a runtime resource. Workers therefore default to an economy policy instead of maximum deliberation:

| Setting | Default | Purpose |
| --- | --- | --- |
| `NIDAVELIR_CODEX_REASONING_EFFORT` | `low` | avoid paying reasoning-token cost for routine coding work |
| `NIDAVELIR_CODEX_VERBOSITY` | `low` | minimize prose/output tokens |
| `NIDAVELIR_CODEX_TOOL_OUTPUT_TOKEN_LIMIT` | `4000` | stop large command/file outputs from bloating later turns |
| `NIDAVELIR_CODEX_PROJECT_DOC_MAX_BYTES` | `16384` | bound automatic project-instruction ingestion |

The values can be overridden for harder workloads. Escalating reasoning should be deliberate and measurable, not the default.

The worker prompt keeps stable policy/profile instructions before task-specific text to improve provider prompt-cache reuse across similar attempts. Empty description/context sections are omitted rather than sending placeholder prose.

Codex runs with JSON events and the worker extracts `turn.completed` usage into the structured `NIDAVELIR_RESULT`: input tokens, cached input, cache-write input, output, reasoning output, and total. Core already persists that result JSON, so token usage is auditable without a schema migration. Cursor currently reports `token_usage: null` until equivalent usage metadata is available through the CLI surface Nidavelir uses.

## Worker communication contract

Disposable workers are executors, not chat partners. They spend effort on implementation/tools rather than narration, avoid routine progress chatter, and keep final prose to at most four short lines containing only outcome, checks, and a blocker when one exists.

Nidavelir persists structured result metadata, Git state, diffs, checks, and bounded logs independently of that final prose.

## Build

```bash
docker build -t nidavelir-worker:dev worker/
```

Pin a Codex CLI version when reproducibility matters:

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

The container runs as the unprivileged `nidavelir` user (UID/GID `10001`) and uses `/workspace/repo` as its working directory.

## Security boundary

Workers must not receive `/var/run/docker.sock`, privileged mode, unrestricted host filesystem mounts, or credentials for unrelated harnesses/host services.

Resource limits are applied by Nidavelir Core when it creates a worker. The image itself does not try to control its own CPU or memory budget.

The default `sleep infinity` command only keeps a freshly-created worker alive for the orchestrator. Core overrides the command for actual task execution.
