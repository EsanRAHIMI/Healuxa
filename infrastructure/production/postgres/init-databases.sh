#!/bin/sh
set -eu
for database in identity transformation provider appointment concierge notification payment subscription; do
  variable="$(printf '%s' "$database" | tr '[:lower:]' '[:upper:]')_DB_PASSWORD"
  password="$(printenv "$variable")"
  psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set=ON_ERROR_STOP=1 \
    --set=role="hx_$database" --set=database="$database" --set=password="$password" <<'SQL'
CREATE ROLE :"role" LOGIN PASSWORD :'password';
CREATE DATABASE :"database" OWNER :"role";
REVOKE ALL ON DATABASE :"database" FROM PUBLIC;
SQL
done
