#!/usr/bin/env bash
# E2E smoke: identity-service → assessment-service via public HTTP APIs only.
# Requires: curl, jq, both services running, identity migration 0005+, assessment Atlas configured.
set -euo pipefail

IDENTITY_URL="${IDENTITY_URL:-http://localhost:8001}"
ASSESSMENT_URL="${ASSESSMENT_URL:-http://localhost:8003}"
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
check_health "$ASSESSMENT_URL" "assessment-service"

SMOKE_EMAIL="smoke-assessment-$(date +%s)-${RANDOM}@example.com"
SMOKE_PASSWORD="password123"

info "Register user ($SMOKE_EMAIL)"
curl_request POST "$IDENTITY_URL/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"identifier\":\"$SMOKE_EMAIL\",\"password\":\"$SMOKE_PASSWORD\",\"locale\":\"en\"}"
assert_http 201
ACCESS_TOKEN="$(echo "$RESP_BODY" | jq -r '.access_token')"
[[ -n "$ACCESS_TOKEN" && "$ACCESS_TOKEN" != "null" ]] || die "register: missing access_token"

info "Introspect token (assessment permissions)"
curl_request POST "$IDENTITY_URL/v1/auth/introspect" \
  -H "Content-Type: application/json" \
  -H "X-Service-Client-Id: $SERVICE_AUTH_CLIENT_ID" \
  -H "X-Service-Client-Secret: $SERVICE_AUTH_CLIENT_SECRET" \
  -d "{\"token\":\"$ACCESS_TOKEN\"}"
assert_http 200
assert_jq_true '.active == true' "introspect: token not active"
USER_ID="$(echo "$RESP_BODY" | jq -r '.sub')"
[[ -n "$USER_ID" && "$USER_ID" != "null" ]] || die "introspect: missing sub"

for perm in assessments:create assessments:read assessments:write; do
  if ! echo "$RESP_BODY" | jq -e --arg p "$perm" '.perms | index($p) != null' >/dev/null; then
    die "introspect: missing permission $perm — body: $RESP_BODY"
  fi
done
info "Introspect OK (user_id=$USER_ID, assessment permissions present)"

info "Create assessment (Bearer token)"
curl_request POST "$ASSESSMENT_URL/v1/assessments" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":\"$USER_ID\",\"kind\":\"beauty\"}"
assert_http 201

ASSESSMENT_ID="$(echo "$RESP_BODY" | jq -r '.id')"
[[ -n "$ASSESSMENT_ID" && "$ASSESSMENT_ID" != "null" ]] || die "create assessment: missing id"
assert_jq_true '.status == "in_progress"' "create assessment: expected status in_progress"
if ! echo "$RESP_BODY" | jq -e --arg USER_ID "$USER_ID" '.user_id == $USER_ID' >/dev/null 2>&1; then
  die "create assessment: user_id mismatch — body: $RESP_BODY"
fi
info "Create assessment OK (assessment_id=$ASSESSMENT_ID)"

info "Get assessment (Bearer token)"
curl_request GET "$ASSESSMENT_URL/v1/assessments/$ASSESSMENT_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
assert_http 200
if ! echo "$RESP_BODY" | jq -e --arg ASSESSMENT_ID "$ASSESSMENT_ID" '.id == $ASSESSMENT_ID' >/dev/null 2>&1; then
  die "get assessment: id mismatch — body: $RESP_BODY"
fi
assert_jq_true '.status == "in_progress"' "get assessment: expected status in_progress"

SUBMIT_BODY='{"responses":[{"question_id":"smoke-q1","value":"smoke-answer"}]}'

info "Submit assessment (Bearer token)"
curl_request POST "$ASSESSMENT_URL/v1/assessments/$ASSESSMENT_ID/submit" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$SUBMIT_BODY"
assert_http 200
assert_jq_true '.status == "completed"' "submit assessment: expected status completed"
assert_jq_true '.recommended_goals == []' "submit assessment: expected recommended_goals []"
assert_jq_true '.scores == {}' "submit assessment: expected scores {}"

echo ""
echo "SMOKE PASSED: identity → assessment E2E"
echo "  user:         $SMOKE_EMAIL"
echo "  user_id:      $USER_ID"
echo "  assessment_id: $ASSESSMENT_ID"
