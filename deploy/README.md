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

The installer creates `/opt/nidavelir`, installs the operator CLI at `/usr/local/bin/nidavelir`, creates the `nidavelir` operator group, generates random PostgreSQL and MCP secrets, and preserves existing configuration on repeat runs. When invoked through `sudo`, the calling user is added to the `nidavelir` group.

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

## Network exposure

Production is loopback-first by default:

- Web: `127.0.0.1:8080`
- MCP: `127.0.0.1:8001/mcp`
- Core API: Docker network only, with no host port

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

Configuration lives in `/opt/nidavelir/.env`. PostgreSQL data lives in the Docker named volume `nidavelir-postgres`. `nidavelir stop`, `restart`, and `update` do not delete either one.

Do not use `docker compose down -v` unless you intentionally want to delete the database.
