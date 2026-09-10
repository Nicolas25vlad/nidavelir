# Nidavelir Worker

Disposable runtime image used for isolated coding-agent attempts.

The worker contains Codex CLI, Cursor Agent CLI, a small common shell toolset, and a pinned read-only catalog of Agent Skills. Repository-specific language runtimes still belong in dedicated worker images/profiles rather than turning the base image into a kitchen sink.

## Agent profiles

Before invoking a harness, `nidavelir-resolve-profile` classifies the task and exposes only the skills for that domain. Supported first-pass profiles are:

- `generic`
- `frontend`
- `backend`
- `fullstack`
- `infra`
- `testing`
- `database`
- `android`
- `docs`

The resolver uses task text plus lightweight repository signals. A task payload may set `profile` explicitly; otherwise `auto` resolution is used.

Ponytail is part of the base bundle and is available to every coding profile. Profile-specific skills are linked into both `~/.agents/skills` and `~/.codex/skills`, while the complete skill store remains outside the discovery path.

All third-party skills are fetched at image build time from exact Git revisions declared in `skills.lock.json`. Their license texts are copied into `/opt/nidavelir/third-party/licenses`.

## Worker communication contract

Disposable workers are executors, not chat partners. Their prompt instructs them to spend effort on implementation and tools rather than narration, avoid routine progress chatter, and keep the final response to at most six short lines containing only outcome, checks, and a blocker when one exists.

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

Workers must not receive:

- `/var/run/docker.sock`;
- privileged mode;
- unrestricted host filesystem mounts;
- credentials for unrelated harnesses or host services.

Resource limits are applied by Nidavelir Core when it creates a worker. The image itself does not try to control its own CPU or memory budget.

The default `sleep infinity` command only keeps a freshly-created worker alive for the orchestrator. Core overrides the command for actual task execution.
