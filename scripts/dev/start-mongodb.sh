#!/usr/bin/env bash
# Start a disposable single-node MongoDB replica set without Docker.
# Atlas is a replica set, so tests exercise the same topology discovery path.
#   MONGO_PORT (default 27020)  MONGO_DATA_DIR (default ./.local/mongodb)
set -euo pipefail

port="${MONGO_PORT:-27020}"
data_dir="${MONGO_DATA_DIR:-$(pwd)/.local/mongodb}"
mkdir -p "$data_dir"

mongod --dbpath "$data_dir" --port "$port" --bind_ip 127.0.0.1 --replSet rs0 \
  --fork --logpath "$data_dir/mongod.log"

python3 - "$port" <<'PY'
import socket, sys, time
port = int(sys.argv[1])
for _ in range(60):
    try:
        socket.create_connection(("127.0.0.1", port), 1).close()
        break
    except OSError:
        time.sleep(0.5)
else:
    sys.exit(f"mongod did not listen on {port}")
PY

if command -v mongosh >/dev/null 2>&1; then
  mongosh --quiet --port "$port" --eval \
    "try { rs.status() } catch (e) { rs.initiate({_id: 'rs0', members: [{_id: 0, host: '127.0.0.1:$port'}]}) }" >/dev/null
else
  python3 -c "
import pymongo, sys
c = pymongo.MongoClient('mongodb://127.0.0.1:$port/?directConnection=true')
try:
    c.admin.command('replSetGetStatus')
except pymongo.errors.OperationFailure:
    c.admin.command('replSetInitiate', {'_id': 'rs0', 'members': [{'_id': 0, 'host': '127.0.0.1:$port'}]})
"
fi

for _ in $(seq 1 60); do
  if python3 -c "
import pymongo
c = pymongo.MongoClient('mongodb://127.0.0.1:$port/?replicaSet=rs0', serverSelectionTimeoutMS=1000)
c.admin.command('ping')
" >/dev/null 2>&1; then
    echo "MONGODB_URI=mongodb://127.0.0.1:$port/?replicaSet=rs0"
    exit 0
  fi
  sleep 1
done
echo "replica set did not elect a primary" >&2
exit 1
