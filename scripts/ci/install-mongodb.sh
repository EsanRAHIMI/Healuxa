#!/usr/bin/env bash
# Install MongoDB server natively on an Ubuntu GitHub runner (no Docker).
set -euo pipefail

version="${MONGODB_VERSION:-8.0}"
codename="$(. /etc/os-release && echo "$VERSION_CODENAME")"

curl -fsSL "https://pgp.mongodb.com/server-${version}.asc" \
  | sudo gpg --dearmor -o "/usr/share/keyrings/mongodb-server-${version}.gpg"
echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-${version}.gpg ] https://repo.mongodb.org/apt/ubuntu ${codename}/mongodb-org/${version} multiverse" \
  | sudo tee "/etc/apt/sources.list.d/mongodb-org-${version}.list" >/dev/null
sudo apt-get update -qq
sudo apt-get install -y -qq mongodb-org-server >/dev/null
mongod --version | head -1
