#!/usr/bin/env bash
# E2E smoke: identity-service → profile-service via public HTTP APIs only.
# Requires: curl, jq, both services running, identity migration 0004+, profile Atlas configured.
set -euo pipefail

IDENTITY_URL="${IDENTITY_URL:-http://localhost:8001}"
PROFILE_URL="${PROFILE_URL:-http://localhost:8002}"
SERVICE_AUTH_CLIENT_ID="${SERVICE_AUTH_CLIENT_ID:-healuxa-internal}"
SERVICE_AUTH_CLIENT_SECRET="${SERVICE_AUTH_CLIENT_SECRET:-dev-service-secret-change-me}"

RESP_BODY=""
RESP_CODE=""

die() {
  echo "ERROR: $*" >&2
  exit 1
}

info() {
  echo "==> $*"
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "'$1' is required but not installed"
}

# curl_request METHOD URL [curl options...]
# Sets RESP_BODY and RESP_CODE from response body and HTTP status.
curl_request() {
  local method=$1
  local url=$2
  shift 2
  local body_file
  body_file="$(mktemp)"
  local code
  code="$(
    curl -sS -X "$method" "$url" \
      -o "$body_file" \
      -w "%{http_code}" \
      "$@"
  )" || {
    rm -f "$body_file"
    die "curl failed: $method $url"
  }
  RESP_BODY="$(cat "$body_file")"
  RESP_CODE="$code"
  rm -f "$body_file"
}

# curl_request_with_headers METHOD URL header_out [curl options...]
curl_request_with_headers() {
  local method=$1
  local url=$2
  local header_out=$3
  shift 3
  local body_file
  body_file="$(mktemp)"
  local code
  code="$(
    curl -sS -X "$method" "$url" \
      -D "$header_out" \
      -o "$body_file" \
      -w "%{http_code}" \
      "$@"
  )" || {
    rm -f "$body_file"
    die "curl failed: $method $url"
  }
  RESP_BODY="$(cat "$body_file")"
  RESP_CODE="$code"
  rm -f "$body_file"
}

assert_http() {
  local expected=$1
  if [[ "$RESP_CODE" != "$expected" ]]; then
    die "expected HTTP $expected, got $RESP_CODE — body: $RESP_BODY"
  fi
}

assert_jq_true() {
  local filter=$1
  local msg=$2
  if ! echo "$RESP_BODY" | jq -e "$filter" >/dev/null 2>&1; then
    die "$msg — body: $RESP_BODY"
  fi
}

check_health() {
  local base=$1
  local name=$2
  curl_request GET "$base/health"
  assert_http 200
  assert_jq_true '.status == "ok"' "$name /health: expected status ok"

  curl_request GET "$base/ready"
  assert_http 200
  assert_jq_true '.status == "ready"' "$name /ready: expected status ready"
}

need_cmd curl
need_cmd jq

info "Checking prerequisites (health / ready)"
check_health "$IDENTITY_URL" "identity-service"
check_health "$PROFILE_URL" "profile-service"

SMOKE_EMAIL="smoke-profile-$(date +%s)-${RANDOM}@example.com"
SMOKE_PASSWORD="password123"

info "Register user ($SMOKE_EMAIL)"
curl_request POST "$IDENTITY_URL/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"identifier\":\"$SMOKE_EMAIL\",\"password\":\"$SMOKE_PASSWORD\",\"locale\":\"en\"}"
assert_http 201
ACCESS_TOKEN="$(echo "$RESP_BODY" | jq -r '.access_token')"
[[ -n "$ACCESS_TOKEN" && "$ACCESS_TOKEN" != "null" ]] || die "register: missing access_token"

info "Introspect token (profile permissions)"
curl_request POST "$IDENTITY_URL/v1/auth/introspect" \
  -H "Content-Type: application/json" \
  -H "X-Service-Client-Id: $SERVICE_AUTH_CLIENT_ID" \
  -H "X-Service-Client-Secret: $SERVICE_AUTH_CLIENT_SECRET" \
  -d "{\"token\":\"$ACCESS_TOKEN\"}"
assert_http 200
assert_jq_true '.active == true' "introspect: token not active"
USER_ID="$(echo "$RESP_BODY" | jq -r '.sub')"
[[ -n "$USER_ID" && "$USER_ID" != "null" ]] || die "introspect: missing sub"

for perm in profiles:read profiles:write; do
  if ! echo "$RESP_BODY" | jq -e --arg p "$perm" '.perms | index($p) != null' >/dev/null; then
    die "introspect: missing permission $perm — body: $RESP_BODY"
  fi
done
info "Introspect OK (user_id=$USER_ID, profile permissions present)"

info "GET profile before create (expect 404)"
curl_request GET "$PROFILE_URL/v1/profiles/$USER_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
assert_http 404

PROFILE_BODY="$(jq -nc \
  --arg uid "$USER_ID" \
  '{
    user_id: $uid,
    lifecycle_stage: "onboarding",
    vip_tier: "none",
    scores: {},
    consent: {terms_accepted: true}
  }')"

HEADER_FILE=""
HEADER_FILE_GET=""

info "PUT profile (Bearer token)"
HEADER_FILE="$(mktemp)"
trap 'rm -f "${HEADER_FILE:-}" "${HEADER_FILE_GET:-}"' EXIT
curl_request_with_headers PUT "$PROFILE_URL/v1/profiles/$USER_ID" "$HEADER_FILE" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$PROFILE_BODY"
assert_http 200

ETAG="$(grep -i '^etag:' "$HEADER_FILE" | tail -n1 | tr -d '\r' | awk '{print $2}')"
[[ -n "$ETAG" ]] || die "put profile: missing ETag header"
[[ "$ETAG" == "v1" ]] || die "put profile: expected ETag v1, got ${ETAG}"

info "GET profile after create"
HEADER_FILE_GET="$(mktemp)"
trap 'rm -f "${HEADER_FILE:-}" "${HEADER_FILE_GET:-}"' EXIT
curl_request_with_headers GET "$PROFILE_URL/v1/profiles/$USER_ID" "$HEADER_FILE_GET" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
assert_http 200
if ! echo "$RESP_BODY" | jq -e --arg USER_ID "$USER_ID" '.user_id == $USER_ID' >/dev/null 2>&1; then
  die "get profile: user_id mismatch — body: $RESP_BODY"
fi
assert_jq_true '.lifecycle_stage == "onboarding"' "get profile: lifecycle_stage mismatch"
GET_ETAG="$(grep -i '^etag:' "$HEADER_FILE_GET" | tail -n1 | tr -d '\r' | awk '{print $2}')"
[[ "$GET_ETAG" == "v1" ]] || die "get profile: expected ETag v1, got ${GET_ETAG:-<missing>}"

echo ""
echo "SMOKE PASSED: identity → profile E2E"
echo "  user:    $SMOKE_EMAIL"
echo "  user_id: $USER_ID"
echo "  etag:    $ETAG"
