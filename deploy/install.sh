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
  postgres_password="$(od -An -N32 -tx1 /dev/urandom | tr -d ' \n')"
  cat > "$INSTALL_DIR/.env" <<EOF
NIDAVELIR_VERSION=$VERSION
NIDAVELIR_BIND_ADDRESS=0.0.0.0
NIDAVELIR_POSTGRES_PASSWORD=$postgres_password
NIDAVELIR_DATABASE_URL=postgresql+psycopg://nidavelir:$postgres_password@postgres:5432/nidavelir
NIDAVELIR_LOG_LEVEL=INFO
NIDAVELIR_MAX_PARALLEL_WORKERS=2
NIDAVELIR_WORKER_CPUS=1.0
NIDAVELIR_WORKER_MEMORY=2g
NIDAVELIR_WORKER_TIMEOUT_SECONDS=1800
NIDAVELIR_WORKER_STOP_TIMEOUT_SECONDS=10
NIDAVELIR_GITHUB_TOKEN=
NIDAVELIR_OPENAI_API_KEY=
NIDAVELIR_CURSOR_API_KEY=
EOF
  printf 'Created %s/.env with a random PostgreSQL password.\n' "$INSTALL_DIR"
else
  printf 'Keeping existing %s/.env unchanged.\n' "$INSTALL_DIR"
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
printf '2. Ensure your operator account can access Docker (Docker group or rootless Docker).\n'
printf '3. Check config: nidavelir doctor\n'
printf '4. Start/update: nidavelir update %s\n' "$VERSION"
printf '\nWeb: http://<server>:8080\nMCP: http://<server>:8001/mcp\nCore: http://<server>:8000\n'
