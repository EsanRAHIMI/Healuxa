#!/usr/bin/env bash
# Start the native (no Docker) local dev stack: PostgreSQL 16, Redis, NATS JetStream, MongoDB.
# All data lives under ./.local (git-ignored). Safe to re-run; running services are left alone.
#   brew install postgresql@16 redis nats-server mongodb-community
# Stop everything with: scripts/dev/stop-infra.sh
set -euo pipefail
# Postgres on macOS aborts ("postmaster became multithreaded") without a valid locale.
export LC_ALL="${LC_ALL:-en_US.UTF-8}"

root="$(cd "$(dirname "$0")/../.." && pwd)"
local_dir="$root/.local"
pg_bin="${PG_BIN:-/opt/homebrew/opt/postgresql@16/bin}"
pg_data="$local_dir/postgres"
mkdir -p "$local_dir"

listening() { nc -z 127.0.0.1 "$1" >/dev/null 2>&1; }

# PostgreSQL — role/password match infrastructure defaults (healuxa/dev).
if ! listening 5432; then
  if [ ! -d "$pg_data" ]; then
    pwfile="$(mktemp)"; echo "dev" > "$pwfile"
    "$pg_bin/initdb" -D "$pg_data" -U healuxa --pwfile="$pwfile" -A scram-sha-256 >/dev/null
    rm -f "$pwfile"
  fi
  "$pg_bin/pg_ctl" -D "$pg_data" -l "$local_dir/postgres.log" -o "-p 5432 -k $local_dir -c listen_addresses=127.0.0.1" -w start >/dev/null
fi
export PGPASSWORD=dev
for db in $(grep -oE 'CREATE DATABASE [a-z_]+' "$root/infrastructure/postgres/init-databases.sql" | awk '{print $3}'); do
  "$pg_bin/psql" -h 127.0.0.1 -U healuxa -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$db'" | grep -q 1 \
    || "$pg_bin/createdb" -h 127.0.0.1 -U healuxa "$db"
done
echo "postgres  postgresql+asyncpg://healuxa:dev@127.0.0.1:5432/<db>"

# Redis
if ! listening 6379; then
  redis-server --port 6379 --bind 127.0.0.1 --dir "$local_dir" --daemonize yes \
    --logfile "$local_dir/redis.log" --pidfile "$local_dir/redis.pid" >/dev/null
fi
echo "redis     redis://127.0.0.1:6379/0"

# NATS with JetStream
if ! listening 4222; then
  mkdir -p "$local_dir/nats"
  nohup nats-server -a 127.0.0.1 -p 4222 -js -sd "$local_dir/nats" \
    -P "$local_dir/nats.pid" > "$local_dir/nats.log" 2>&1 &
  for _ in $(seq 1 20); do listening 4222 && break; sleep 0.25; done
fi
echo "nats      nats://127.0.0.1:4222"

# MongoDB single-node replica set (Atlas-like topology)
if ! listening 27020; then
  MONGO_DATA_DIR="$local_dir/mongodb" "$root/scripts/dev/start-mongodb.sh" >/dev/null
fi
echo "mongodb   mongodb://127.0.0.1:27020/?replicaSet=rs0"
