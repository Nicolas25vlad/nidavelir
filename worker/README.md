# Nidavelir Worker

Disposable runtime image used for isolated coding-agent attempts.

The image intentionally contains only a small common toolset plus Codex CLI. Repository-specific language toolchains should be added through worker profiles later instead of turning the base image into a kitchen sink.

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
- long-lived host credentials.

Resource limits are applied by Nidavelir Core when it creates a worker. The image itself does not try to control its own CPU or memory budget.

The default `sleep infinity` command only keeps a freshly-created worker alive for the orchestrator. Core is expected to override the command for actual task execution.
