# Self-hosted Nidavelir

The production deployment is designed to behave like an appliance. The server does not need a Git clone for normal operation.

## Requirements

- Linux host
- Docker Engine
- Docker Compose v2
- `curl`

## Install

Initial installation is the privileged step:

```bash
curl -fsSL https://raw.githubusercontent.com/Nicolas25vlad/nidavelir/main/deploy/install.sh | sudo bash
```

The installer creates `/opt/nidavelir`, installs the operator CLI at `/usr/local/bin/nidavelir`, creates the `nidavelir` operator group, generates random PostgreSQL and MCP secrets, creates a random per-installation Docker namespace, and preserves existing configuration on repeat runs. When invoked through `sudo`, the calling user is added to the `nidavelir` group.

Open a new login session after installation so the group membership is refreshed.

The installer does **not** silently add the user to Docker's privileged group. Configure either rootless Docker or explicit Docker access for the operator account according to your host policy. Membership in the traditional `docker` group is effectively high privilege on the host and should be treated accordingly.

Configure runtime credentials once:

```bash
nano /opt/nidavelir/.env
```

`/opt/nidavelir/.env` is owned by `root:nidavelir` and is not world-readable.

Set `NIDAVELIR_GITHUB_TOKEN`, then configure at least one coding harness. API keys remain supported while persistent browser-login auth is implemented separately:

```dotenv
NIDAVELIR_OPENAI_API_KEY=   # optional Codex API-key auth
NIDAVELIR_CURSOR_API_KEY=   # optional Cursor API-key auth
```

Then validate and start without sudo:

```bash
nidavelir doctor
nidavelir update
```

## Shared Docker hosts

Nidavelir is designed to coexist with unrelated Docker workloads on the same server.

Each new installation gets a stable `NIDAVELIR_INSTALLATION_ID` and a matching `NIDAVELIR_COMPOSE_PROJECT_NAME`. Existing installations keep their historical Compose project name during upgrade so their PostgreSQL volume remains attached. Disposable task containers and work volumes include the installation namespace in their names and carry these Docker labels:

```text
io.nidavelir.managed=true
io.nidavelir.installation=<installation-id>
io.nidavelir.attempt_id=<attempt-id>
```

Cancellation and orphan cleanup require the Nidavelir managed label **and** the current installation label. Attempt-specific cleanup additionally requires the attempt ID. The Core does not use global Docker prune operations, so unrelated containers, volumes, images, and networks are outside its cleanup scope.

PostgreSQL is attached only to an internal data network. Core bridges the internal data network and the control network. Web and MCP use only the control network. Disposable coding workers are created separately by Core and are not attached to either appliance network.

Long-running services and task workers have configurable CPU and memory ceilings. Core, MCP, Web, and PostgreSQL also have process-count ceilings. Defaults are intentionally conservative for a shared server:

```dotenv
NIDAVELIR_POSTGRES_CPUS=0.50
NIDAVELIR_POSTGRES_MEMORY=512m
NIDAVELIR_CORE_CPUS=0.75
NIDAVELIR_CORE_MEMORY=512m
NIDAVELIR_CORE_PIDS_LIMIT=256
NIDAVELIR_MCP_CPUS=0.25
NIDAVELIR_MCP_MEMORY=256m
NIDAVELIR_MCP_PIDS_LIMIT=128
NIDAVELIR_WEB_CPUS=0.25
NIDAVELIR_WEB_MEMORY=128m
NIDAVELIR_WEB_PIDS_LIMIT=64
NIDAVELIR_WORKER_CPUS=1.0
NIDAVELIR_WORKER_MEMORY=2g
NIDAVELIR_MAX_PARALLEL_WORKERS=2
```

Tune those values for the host. The worker ceiling applies per active worker, so `NIDAVELIR_MAX_PARALLEL_WORKERS` is also part of the server-wide resource budget.

### Docker daemon boundary

By default, Core mounts `/var/run/docker.sock`. The installation namespace prevents Nidavelir's normal cleanup paths from selecting unrelated resources, but possession of the primary Docker socket is still daemon-level authority. Treat this as operational isolation, not a hard security boundary.

For stronger isolation, run a dedicated or rootless Docker daemon for Nidavelir workers and point the appliance at its Unix socket:

```dotenv
NIDAVELIR_DOCKER_SOCKET=/run/user/1000/docker.sock
```

Only the selected socket is mounted into Core as `/var/run/docker.sock`. With a dedicated daemon, dynamically created worker containers and volumes no longer share the server's primary Docker object namespace at all.

## Network exposure

Production is loopback-first by default:

- Web: `127.0.0.1:8080`
- MCP: `127.0.0.1:8001/mcp`
- Core API: Docker network only, with no host port

Host ports are configurable, so Nidavelir does not require globally reserved `8080` or `8001` ports on a shared server:

```dotenv
NIDAVELIR_WEB_HOST_PORT=18080
NIDAVELIR_MCP_HOST_PORT=18001
```

For remote MCP access, put Nidavelir behind HTTPS and configure the public resource/issuer URLs. Bind the MCP port externally only when the host firewall or reverse proxy is ready:

```dotenv
NIDAVELIR_MCP_BIND_ADDRESS=0.0.0.0
NIDAVELIR_MCP_RESOURCE_URL=https://nidavelir.example/mcp
NIDAVELIR_MCP_ISSUER_URL=https://nidavelir.example
```

The Streamable HTTP MCP endpoint requires `Authorization: Bearer <token>`. The installer generates a high-entropy token on first install. Retrieve it intentionally when configuring a client:

```bash
nidavelir mcp-token
```

Do not put that token in repository files, task descriptions, worker prompts, logs, or browser URLs. The MCP SDK handles unauthorized HTTP requests before they reach tool handlers.

Web and MCP have independent bind settings. This allows the MCP endpoint to be published while the Web control plane remains local or VPN-only.

## Routine operation

Normal operation is intentionally unprivileged:

```bash
nidavelir status
nidavelir logs core
nidavelir restart core
nidavelir update
```

If those commands cannot reach Docker, `nidavelir` stops with an explicit permission error instead of retrying under sudo.

`nidavelir update` pulls published GHCR images and recreates services without deleting the PostgreSQL volume or replacing `/opt/nidavelir/.env`.

## Pin or roll back

Every published build gets a `sha-<12 chars>` tag. Release tags such as `v0.1.0` are published too.

```bash
nidavelir update v0.1.0
nidavelir update sha-0123456789ab
```

If an update cannot pull or start, the CLI restores the previously configured image tag and attempts to bring that version back up.

## Persistent state

Configuration lives in `/opt/nidavelir/.env`. PostgreSQL data lives in the Compose project-scoped `nidavelir-postgres` volume. New installations get a unique Compose project name; upgraded legacy installations intentionally retain the old `nidavelir` project name so the existing database volume remains the same. `nidavelir stop`, `restart`, and `update` do not delete either one.

Do not use `docker compose down -v` unless you intentionally want to delete that installation's database.
