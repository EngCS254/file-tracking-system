#!/bin/sh
set -eu
: "${DFTS_APP_PASSWORD:?Set DFTS_APP_PASSWORD before starting PostgreSQL}"
: "${DFTS_MIGRATION_PASSWORD:?Set DFTS_MIGRATION_PASSWORD before starting PostgreSQL}"
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=app_password="$DFTS_APP_PASSWORD" \
  --set=migration_password="$DFTS_MIGRATION_PASSWORD" <<'SQL'
CREATE ROLE dfts_owner LOGIN PASSWORD :'migration_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT BYPASSRLS;
CREATE ROLE dfts_app LOGIN PASSWORD :'app_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
GRANT CONNECT ON DATABASE dfts TO dfts_owner, dfts_app;
GRANT USAGE ON SCHEMA public TO dfts_owner, dfts_app;
GRANT CREATE ON SCHEMA public TO dfts_owner;
SQL
