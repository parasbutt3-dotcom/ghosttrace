#!/usr/bin/env bash
#
# Nightly PostgreSQL backup for GHOSTTRACE.
#
# Dumps the configured database from the Postgres container via `docker exec`,
# writes a timestamped, gzipped SQL file, and prunes backups older than
# RETENTION_DAYS days (default: 7).
#
# Usage:
#   ./infra/backup.sh
#
# Environment overrides (defaults match docker-compose.yml):
#   DB_CONTAINER       container name/id (auto-detected from compose if empty)
#   COMPOSE_FILE       path to docker-compose.yml (default: docker-compose.yml)
#   POSTGRES_USER      database user (default: ghosttrace)
#   POSTGRES_DB        database name (default: ghosttrace)
#   BACKUP_DIR         output directory (default: ./backups)
#   RETENTION_DAYS     keep backups this many days (default: 7)

set -euo pipefail

DB_CONTAINER="${DB_CONTAINER:-}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
POSTGRES_USER="${POSTGRES_USER:-ghosttrace}"
POSTGRES_DB="${POSTGRES_DB:-ghosttrace}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILE="${BACKUP_DIR}/ghosttrace_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

# Resolve the running Postgres container if not given explicitly.
if [[ -z "$DB_CONTAINER" ]]; then
  if [[ -f "$COMPOSE_FILE" ]]; then
    DB_CONTAINER="$(docker compose -f "$COMPOSE_FILE" ps -q db 2>/dev/null || true)"
  fi
fi
if [[ -z "$DB_CONTAINER" ]]; then
  echo "Could not find the Postgres container. Set DB_CONTAINER or run from the compose project directory." >&2
  exit 1
fi

echo "Backing up database '${POSTGRES_DB}' from container '${DB_CONTAINER}' -> ${BACKUP_FILE}"
docker exec "$DB_CONTAINER" pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists | gzip > "$BACKUP_FILE"

# Retention: remove backups older than RETENTION_DAYS days.
find "$BACKUP_DIR" -type f -name 'ghosttrace_*.sql.gz' -mtime +"${RETENTION_DAYS}" -delete

echo "Backup complete: ${BACKUP_FILE}"
