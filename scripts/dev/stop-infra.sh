#!/usr/bin/env bash
# Stop the native dev stack started by scripts/dev/start-infra.sh.
set -uo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
local_dir="$root/.local"
pg_bin="${PG_BIN:-/opt/homebrew/opt/postgresql@16/bin}"

[ -d "$local_dir/postgres" ] && "$pg_bin/pg_ctl" -D "$local_dir/postgres" -m fast stop >/dev/null 2>&1
[ -f "$local_dir/redis.pid" ] && kill "$(cat "$local_dir/redis.pid")" 2>/dev/null
[ -f "$local_dir/nats.pid" ] && kill "$(cat "$local_dir/nats.pid")" 2>/dev/null
[ -d "$local_dir/mongodb" ] && mongod --dbpath "$local_dir/mongodb" --shutdown >/dev/null 2>&1
echo "stopped"
