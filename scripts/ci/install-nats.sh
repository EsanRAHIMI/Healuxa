#!/usr/bin/env bash
# Install and start nats-server with JetStream natively on a Linux GitHub runner (checksum-verified).
# Prints NATS_URL=... on stdout (for $GITHUB_ENV); progress goes to stderr.
set -euo pipefail

version="${NATS_VERSION:-v2.15.1}"
arch="linux-amd64"
work="$(mktemp -d)"
base="https://github.com/nats-io/nats-server/releases/download/${version}"
tarball="nats-server-${version}-${arch}.tar.gz"

curl -fsSL -o "$work/$tarball" "$base/$tarball"
curl -fsSL -o "$work/SHA256SUMS" "$base/SHA256SUMS"
(cd "$work" && grep " ${tarball}\$" SHA256SUMS | sha256sum -c - >&2)
tar -xzf "$work/$tarball" -C "$work"
sudo install -m 0755 "$work/nats-server-${version}-${arch}/nats-server" /usr/local/bin/nats-server
nats-server --version >&2

data_dir="${NATS_DATA_DIR:-$work/jetstream}"
nohup nats-server -a 127.0.0.1 -p 4222 -js -sd "$data_dir" > "$work/nats.log" 2>&1 &
for _ in $(seq 1 40); do
  if nc -z 127.0.0.1 4222; then
    echo "NATS_URL=nats://127.0.0.1:4222"
    exit 0
  fi
  sleep 0.25
done
cat "$work/nats.log" >&2
exit 1
