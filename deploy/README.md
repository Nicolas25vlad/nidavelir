# Self-hosted Nidavelir

The production deployment is designed to behave like an appliance. The server does not need a Git clone for normal operation.

## Requirements

- Linux host
- Docker Engine
- Docker Compose v2
- `curl`

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/Nicolas25vlad/nidavelir/main/deploy/install.sh | sudo bash
```

The installer creates `/opt/nidavelir`, installs the operator CLI at `/usr/local/bin/nidavelir`, generates a PostgreSQL password, and preserves an existing `.env` on repeat runs.

Configure runtime credentials once:

```bash
sudo nano /opt/nidavelir/.env
```

Set `NIDAVELIR_GITHUB_TOKEN`, then configure at least one coding harness:

```dotenv
NIDAVELIR_OPENAI_API_KEY=   # Codex CLI
NIDAVELIR_CURSOR_API_KEY=   # Cursor Agent CLI
```

You can configure either harness or both. `nidavelir doctor` reports which ones are ready.

Then validate and start:

```bash
sudo nidavelir doctor
sudo nidavelir update
```

The default endpoints are:

- Web: `http://SERVER:8080`
- MCP: `http://SERVER:8001/mcp`
- Core API: `http://SERVER:8000`

## Routine operation

```bash
sudo nidavelir status
sudo nidavelir logs core
sudo nidavelir restart core
sudo nidavelir update
```

`nidavelir update` pulls published GHCR images and recreates services without deleting the PostgreSQL volume or replacing `/opt/nidavelir/.env`.

## Pin or roll back

Every published build gets a `sha-<12 chars>` tag. Release tags such as `v0.1.0` are published too.

```bash
sudo nidavelir update v0.1.0
sudo nidavelir update sha-0123456789ab
```

If an update cannot pull or start, the CLI restores the previously configured image tag and attempts to bring that version back up.

## Persistent state

Configuration lives in `/opt/nidavelir/.env`. PostgreSQL data lives in the Docker named volume `nidavelir-postgres`. `nidavelir stop`, `restart`, and `update` do not delete either one.

Do not use `docker compose down -v` unless you intentionally want to delete the database.
