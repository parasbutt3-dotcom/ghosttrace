#!/usr/bin/env bash
#
# Restore a GHOSTTRACE PostgreSQL backup created by infra/backup.sh.
#
# Usage:
#   ./infra/restore.sh <backup-file>
#
# Environment overrides (defaults match docker-compose.yml):
#   DB_CONTAINER       container name/id (auto-detected from compose if empty)
#   COMPOSE_FILE       path to docker-compose.yml (default: docker-compose.yml)
#   POSTGRES_USER      database user (default: ghosttrace)
#   POSTGRES_DB        database name (default: ghosttrace)

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <backup-file>" >&2
  exit 1
fi

BACKUP_FILE="$1"
DB_CONTAINER="${DB_CONTAINER:-}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
POSTGRES_USER="${POSTGRES_USER:-ghosttrace}"
POSTGRES_DB="${POSTGRES_DB:-ghosttrace}"

if [[ ! -f "$BACKUP_FILE" ]]; then
  echo "Backup file not found: ${BACKUP_FILE}" >&2
  exit 1
fi

if [[ -z "$DB_CONTAINER" ]]; then
  if [[ -f "$COMPOSE_FILE" ]]; then
    DB_CONTAINER="$(docker compose -f "$COMPOSE_FILE" ps -q db 2>/dev/null || true)"
  fi
fi
if [[ -z "$DB_CONTAINER" ]]; then
  echo "Could not find the Postgres container. Set DB_CONTAINER or run from the compose project directory." >&2
  exit 1
fi

echo "Restoring ${BACKUP_FILE} into database '${POSTGRES_DB}' on container '${DB_CONTAINER}'"
if [[ "$BACKUP_FILE" == *.gz ]]; then
  gunzip -c "$BACKUP_FILE" | docker exec -i "$DB_CONTAINER" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1
else
  docker exec -i "$DB_CONTAINER" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 < "$BACKUP_FILE"
fi

echo "Restore complete."
