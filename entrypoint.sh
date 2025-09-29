#!/bin/sh
set -e

# Copy .env if missing (convenience for dev); do NOT overwrite an existing .env
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
  echo "Creating .env from .env.example"
  cp .env.example .env
fi

# Simple TCP wait-for (host:port) - fallback if DB vars are present
wait_for_db() {
  DB_HOST=${DB_HOST:-${DB_HOST}}
  DB_PORT=${DB_PORT:-3306}
  if [ -z "$DB_HOST" ]; then
    echo "DB_HOST not set, skipping wait-for-db"
    return
  fi

  echo "Waiting for DB $DB_HOST:$DB_PORT to be available..."
  retries=0
  until nc -z "$DB_HOST" "$DB_PORT" >/dev/null 2>&1; do
    retries=$((retries+1))
    if [ $retries -ge 30 ]; then
      echo "Timeout waiting for DB after $retries attempts"
      return 1
    fi
    sleep 2
  done
  echo "DB is responding"
}

# Only attempt migration/stamp when run.py exists (i.e. app present)
if [ -f "run.py" ]; then
  # Wait for DB if DB_HOST provided
  wait_for_db || echo "Continuing even if DB not reachable (check network)"

  # Default behavior: DO NOT auto-apply migrations/stamp to avoid data loss
  # Control behavior with env vars AUTO_MIGRATE and AUTO_STAMP
  AUTO_MIGRATE=${AUTO_MIGRATE:-false}
  AUTO_STAMP=${AUTO_STAMP:-false}

  # Inspect alembic_version presence
  ALEMBIC_EXISTS=false
  if command -v mysql >/dev/null 2>&1; then
    # Use mysql client if available
    if mysql -h "${DB_HOST}" -P "${DB_PORT}" -u"${DB_USER}" -p"${DB_PASSWORD}" -e "SHOW TABLES LIKE 'alembic_version';" 2>/dev/null | grep -q alembic_version; then
      ALEMBIC_EXISTS=true
    fi
  else
    # Fallback: attempt to run `flask db current` and parse output
    if flask db current >/dev/null 2>&1; then
      ALEMBIC_EXISTS=true
    fi
  fi

  echo "alembic_version table exists: $ALEMBIC_EXISTS"

  if [ "$ALEMBIC_EXISTS" = "true" ]; then
    if [ "$AUTO_MIGRATE" = "true" ]; then
      echo "AUTO_MIGRATE=true -> running 'flask db upgrade'"
      flask db upgrade || echo "Warning: 'flask db upgrade' failed"
    else
      echo "AUTO_MIGRATE not enabled; skipping 'flask db upgrade'"
    fi
  else
    if [ "$AUTO_STAMP" = "true" ]; then
      echo "AUTO_STAMP=true -> running 'flask db stamp head' to mark DB as migrated (no schema changes)"
      flask db stamp head || echo "Warning: 'flask db stamp head' failed"
    else
      echo "alembic_version not found and AUTO_STAMP not enabled; skipping migrations to avoid data loss"
    fi
  fi
fi

# Exec the container CMD
exec "$@"
