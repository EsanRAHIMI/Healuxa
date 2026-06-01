#!/usr/bin/env bash
# E2E smoke: identity-service → transformation-engine via public HTTP APIs only.
# Requires: curl, jq, both services running, dev DBs migrated (identity 0003+).
set -euo pipefail

IDENTITY_URL="${IDENTITY_URL:-http://localhost:8001}"
TRANSFORMATION_URL="${TRANSFORMATION_URL:-http://localhost:8000}"
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
# Sets RESP_BODY, RESP_CODE; writes response headers to header_out.
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
check_health "$TRANSFORMATION_URL" "transformation-engine"

SMOKE_EMAIL="smoke-$(date +%s)-${RANDOM}@example.com"
SMOKE_PASSWORD="password123"

info "Register user ($SMOKE_EMAIL)"
curl_request POST "$IDENTITY_URL/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"identifier\":\"$SMOKE_EMAIL\",\"password\":\"$SMOKE_PASSWORD\",\"locale\":\"en\"}"
assert_http 201
ACCESS_TOKEN="$(echo "$RESP_BODY" | jq -r '.access_token')"
[[ -n "$ACCESS_TOKEN" && "$ACCESS_TOKEN" != "null" ]] || die "register: missing access_token"

info "Introspect token (journey permissions)"
curl_request POST "$IDENTITY_URL/v1/auth/introspect" \
  -H "Content-Type: application/json" \
  -H "X-Service-Client-Id: $SERVICE_AUTH_CLIENT_ID" \
  -H "X-Service-Client-Secret: $SERVICE_AUTH_CLIENT_SECRET" \
  -d "{\"token\":\"$ACCESS_TOKEN\"}"
assert_http 200
assert_jq_true '.active == true' "introspect: token not active"
USER_ID="$(echo "$RESP_BODY" | jq -r '.sub')"
[[ -n "$USER_ID" && "$USER_ID" != "null" ]] || die "introspect: missing sub"

for perm in journeys:create journeys:read journeys:write; do
  if ! echo "$RESP_BODY" | jq -e --arg p "$perm" '.perms | index($p) != null' >/dev/null; then
    die "introspect: missing permission $perm — body: $RESP_BODY"
  fi
done
info "Introspect OK (user_id=$USER_ID, journey permissions present)"

info "Create journey (Bearer token)"
HEADER_FILE="$(mktemp)"
trap 'rm -f "$HEADER_FILE"' EXIT
curl_request_with_headers POST "$TRANSFORMATION_URL/v1/journeys" "$HEADER_FILE" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":\"$USER_ID\",\"primary_goals\":[\"smoke-wellness\"]}"
assert_http 201

JOURNEY_ID="$(echo "$RESP_BODY" | jq -r '.id')"
[[ -n "$JOURNEY_ID" && "$JOURNEY_ID" != "null" ]] || die "create journey: missing id"

LOCATION="$(grep -i '^location:' "$HEADER_FILE" | tail -n1 | tr -d '\r' | cut -d' ' -f2-)"
EXPECTED_LOCATION="/v1/journeys/$JOURNEY_ID"
if [[ "$LOCATION" != "$EXPECTED_LOCATION" ]]; then
  die "create journey: Location header expected '$EXPECTED_LOCATION', got '${LOCATION:-<missing>}'"
fi
info "Create journey OK (journey_id=$JOURNEY_ID)"

info "Get journey by user"
curl_request GET "$TRANSFORMATION_URL/v1/journeys/$USER_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
assert_http 200
FETCHED_ID="$(echo "$RESP_BODY" | jq -r '.id')"
[[ "$FETCHED_ID" == "$JOURNEY_ID" ]] || die "get journey: id mismatch (expected $JOURNEY_ID, got $FETCHED_ID)"

echo ""
echo "SMOKE PASSED: identity → transformation E2E"
echo "  user:    $SMOKE_EMAIL"
echo "  user_id: $USER_ID"
echo "  journey: $JOURNEY_ID"
