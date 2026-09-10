#!/usr/bin/env bash
set -euo pipefail

REPO="Nicolas25vlad/nidavelir"
RAW_BASE="https://raw.githubusercontent.com/$REPO/main"
INSTALL_DIR="${NIDAVELIR_HOME:-/opt/nidavelir}"
BIN_PATH="${NIDAVELIR_BIN:-/usr/local/bin/nidavelir}"
VERSION="${NIDAVELIR_VERSION:-latest}"
OPERATOR_GROUP="${NIDAVELIR_OPERATOR_GROUP:-nidavelir}"
OPERATOR_USER="${NIDAVELIR_OPERATOR_USER:-${SUDO_USER:-}}"

fatal() {
  printf 'nidavelir installer: %s\n' "$*" >&2
  exit 1
}

need() {
  command -v "$1" >/dev/null 2>&1 || fatal "$1 is required"
}

random_hex() {
  od -An -N32 -tx1 /dev/urandom | tr -d ' \n'
}

random_installation_id() {
  od -An -N6 -tx1 /dev/urandom | tr -d ' \n'
}

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  fatal "initial installation requires root (for example: curl ... | sudo bash)"
fi

need curl
need docker
need od
docker compose version >/dev/null 2>&1 || fatal "Docker Compose v2 is required"

groupadd --force "$OPERATOR_GROUP"
if [[ -n "$OPERATOR_USER" && "$OPERATOR_USER" != "root" ]]; then
  if id "$OPERATOR_USER" >/dev/null 2>&1; then
    usermod -aG "$OPERATOR_GROUP" "$OPERATOR_USER"
  else
    fatal "operator user '$OPERATOR_USER' does not exist"
  fi
fi

mkdir -p "$INSTALL_DIR"
chown root:"$OPERATOR_GROUP" "$INSTALL_DIR"
chmod 0750 "$INSTALL_DIR"

compose_tmp="$(mktemp)"
cli_tmp="$(mktemp)"
trap 'rm -f "$compose_tmp" "$cli_tmp"' EXIT

curl -fsSL "$RAW_BASE/deploy/compose.prod.yaml" -o "$compose_tmp"
curl -fsSL "$RAW_BASE/deploy/nidavelir" -o "$cli_tmp"

if [[ ! -f "$INSTALL_DIR/.env" ]]; then
  postgres_password="$(random_hex)"
  mcp_auth_token="$(random_hex)"
  installation_id="$(random_installation_id)"
  cat > "$INSTALL_DIR/.env" <<EOF
NIDAVELIR_VERSION=$VERSION
NIDAVELIR_INSTALLATION_ID=$installation_id
NIDAVELIR_COMPOSE_PROJECT_NAME=nidavelir-$installation_id
NIDAVELIR_WEB_BIND_ADDRESS=127.0.0.1
NIDAVELIR_WEB_HOST_PORT=8080
NIDAVELIR_MCP_BIND_ADDRESS=127.0.0.1
NIDAVELIR_MCP_HOST_PORT=8001
NIDAVELIR_POSTGRES_PASSWORD=$postgres_password
NIDAVELIR_DATABASE_URL=postgresql+psycopg://nidavelir:$postgres_password@postgres:5432/nidavelir
NIDAVELIR_LOG_LEVEL=INFO
NIDAVELIR_MAX_PARALLEL_WORKERS=2
NIDAVELIR_WORKER_CPUS=1.0
NIDAVELIR_WORKER_MEMORY=2g
NIDAVELIR_WORKER_TIMEOUT_SECONDS=1800
NIDAVELIR_WORKER_STOP_TIMEOUT_SECONDS=10
NIDAVELIR_POSTGRES_CPUS=0.50
NIDAVELIR_POSTGRES_MEMORY=512m
NIDAVELIR_CORE_CPUS=0.75
NIDAVELIR_CORE_MEMORY=512m
NIDAVELIR_MCP_CPUS=0.25
NIDAVELIR_MCP_MEMORY=256m
NIDAVELIR_WEB_CPUS=0.25
NIDAVELIR_WEB_MEMORY=128m
NIDAVELIR_GITHUB_TOKEN=
NIDAVELIR_OPENAI_API_KEY=
NIDAVELIR_CURSOR_API_KEY=
NIDAVELIR_MCP_AUTH_TOKEN=$mcp_auth_token
NIDAVELIR_MCP_RESOURCE_URL=http://127.0.0.1:8001/mcp
NIDAVELIR_MCP_ISSUER_URL=http://127.0.0.1:8001
EOF
  printf 'Created %s/.env with random PostgreSQL/MCP secrets and installation namespace.\n' "$INSTALL_DIR"
else
  printf 'Keeping existing %s/.env values.\n' "$INSTALL_DIR"
  if ! grep -q '^NIDAVELIR_INSTALLATION_ID=.' "$INSTALL_DIR/.env"; then
    installation_id="$(random_installation_id)"
    printf '\nNIDAVELIR_INSTALLATION_ID=%s\n' "$installation_id" >> "$INSTALL_DIR/.env"
    printf 'Added a per-installation Docker namespace to the existing configuration.\n'
  fi
  if ! grep -q '^NIDAVELIR_COMPOSE_PROJECT_NAME=.' "$INSTALL_DIR/.env"; then
    # Legacy installs used /opt/nidavelir/compose.yaml, whose implicit Compose
    # project name is "nidavelir". Preserve it so the existing database volume
    # remains attached after this upgrade.
    printf 'NIDAVELIR_COMPOSE_PROJECT_NAME=nidavelir\n' >> "$INSTALL_DIR/.env"
    printf 'Preserved the legacy Compose project name for existing Docker data.\n'
  fi
  if ! grep -q '^NIDAVELIR_WEB_HOST_PORT=' "$INSTALL_DIR/.env"; then
    printf 'NIDAVELIR_WEB_HOST_PORT=8080\n' >> "$INSTALL_DIR/.env"
  fi
  if ! grep -q '^NIDAVELIR_MCP_HOST_PORT=' "$INSTALL_DIR/.env"; then
    printf 'NIDAVELIR_MCP_HOST_PORT=8001\n' >> "$INSTALL_DIR/.env"
  fi
  if ! grep -q '^NIDAVELIR_MCP_AUTH_TOKEN=.' "$INSTALL_DIR/.env"; then
    printf '\nNIDAVELIR_MCP_AUTH_TOKEN=%s\n' "$(random_hex)" >> "$INSTALL_DIR/.env"
    printf 'Added a random MCP bearer token to the existing configuration.\n'
  fi
  if ! grep -q '^NIDAVELIR_MCP_RESOURCE_URL=' "$INSTALL_DIR/.env"; then
    printf 'NIDAVELIR_MCP_RESOURCE_URL=http://127.0.0.1:8001/mcp\n' >> "$INSTALL_DIR/.env"
  fi
  if ! grep -q '^NIDAVELIR_MCP_ISSUER_URL=' "$INSTALL_DIR/.env"; then
    printf 'NIDAVELIR_MCP_ISSUER_URL=http://127.0.0.1:8001\n' >> "$INSTALL_DIR/.env"
  fi
fi

chown root:"$OPERATOR_GROUP" "$INSTALL_DIR/.env"
chmod 0660 "$INSTALL_DIR/.env"
install -o root -g "$OPERATOR_GROUP" -m 0664 "$compose_tmp" "$INSTALL_DIR/compose.yaml"
install -m 0755 "$cli_tmp" "$BIN_PATH"

docker compose --env-file "$INSTALL_DIR/.env" -f "$INSTALL_DIR/compose.yaml" config --quiet

printf '\nNidavelir installed.\n'
if [[ -n "$OPERATOR_USER" && "$OPERATOR_USER" != "root" ]]; then
  printf 'Operator: %s (group %s)\n' "$OPERATOR_USER" "$OPERATOR_GROUP"
  printf 'Open a new login session before using the new group membership.\n'
fi
printf '1. Edit configuration: nano %s/.env\n' "$INSTALL_DIR"
printf '2. For remote MCP, set its bind/resource/issuer values to your HTTPS deployment.\n'
printf '3. Ensure your operator account can access Docker (Docker group or rootless Docker).\n'
printf '4. Check config: nidavelir doctor\n'
printf '5. Start/update: nidavelir update %s\n' "$VERSION"
printf '\nWeb: http://127.0.0.1:8080 by default\nMCP: http://127.0.0.1:8001/mcp by default (Bearer auth required)\nCore: internal Docker network only\nDocker: resources are namespaced per Nidavelir installation\n'