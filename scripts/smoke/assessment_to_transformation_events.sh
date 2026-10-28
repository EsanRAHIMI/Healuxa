#!/usr/bin/env bash
# E2E smoke: assessment.completed travels assessment-service → outbox → JetStream → transformation-engine.
# Requires running identity (8001), transformation (8000) and assessment (8003) with NATS_ENABLED=true,
# plus psql access to the transformation database to confirm the consumer's link record.
set -euo pipefail

IDENTITY_URL="${IDENTITY_URL:-http://localhost:8001}"
TRANSFORMATION_URL="${TRANSFORMATION_URL:-http://localhost:8000}"
ASSESSMENT_URL="${ASSESSMENT_URL:-http://localhost:8003}"
TRANSFORMATION_PG="${TRANSFORMATION_PG:-postgresql://healuxa:dev@127.0.0.1:5432/transformation}"
PSQL="${PSQL:-psql}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-20}"

die() { echo "ERROR: $*" >&2; exit 1; }
info() { echo "==> $*"; }
for cmd in curl jq "$PSQL"; do command -v "$cmd" >/dev/null || die "'$cmd' is required"; done

post() { # post URL TOKEN JSON → prints "<code> <body>"
  local out code
  out="$(mktemp)"
  code="$(curl -sS -o "$out" -w '%{http_code}' -X POST "$1" -H 'Content-Type: application/json' \
    ${2:+-H "Authorization: Bearer $2"} -d "$3")"
  echo "$code $(cat "$out")"; rm -f "$out"
}

for url in "$IDENTITY_URL" "$TRANSFORMATION_URL" "$ASSESSMENT_URL"; do
  [[ "$(curl -s -o /dev/null -w '%{http_code}' "$url/ready")" == 200 ]] || die "$url/ready is not 200"
done

info "Register customer"
read -r code body <<<"$(post "$IDENTITY_URL/v1/auth/register" "" \
  "{\"identifier\":\"smoke-$(date +%s)-$RANDOM@example.com\",\"password\":\"Smoke-pass-1234\",\"locale\":\"en\"}")"
[[ "$code" == 201 ]] || die "register: $code $body"
TOKEN="$(jq -r .access_token <<<"$body")"
USER_ID="$(jq -r '.access_token | split(".")[1] | @base64d | fromjson | .sub' <<<"$body" 2>/dev/null \
  || python3 -c "import base64,json,sys;p=sys.argv[1].split('.')[1];print(json.loads(base64.urlsafe_b64decode(p+'='*(-len(p)%4)))['sub'])" "$TOKEN")"

info "Create journey for $USER_ID"
read -r code body <<<"$(post "$TRANSFORMATION_URL/v1/journeys" "$TOKEN" \
  "{\"user_id\":\"$USER_ID\",\"primary_goals\":[\"smoke-wellness\"]}")"
[[ "$code" == 201 ]] || die "create journey: $code $body"

info "Start and submit assessment"
read -r code body <<<"$(post "$ASSESSMENT_URL/v1/assessments" "$TOKEN" "{\"user_id\":\"$USER_ID\",\"kind\":\"beauty\"}")"
[[ "$code" == 201 ]] || die "start assessment: $code $body"
ASSESSMENT_ID="$(jq -r .id <<<"$body")"
read -r code body <<<"$(post "$ASSESSMENT_URL/v1/assessments/$ASSESSMENT_ID/submit" "$TOKEN" '{"responses":[{"q1":"a"}]}')"
[[ "$code" == 200 ]] || die "submit assessment: $code $body"

info "Wait for transformation-engine to link assessment $ASSESSMENT_ID"
for _ in $(seq 1 "$TIMEOUT_SECONDS"); do
  status="$("$PSQL" "$TRANSFORMATION_PG" -tAc \
    "SELECT link_status FROM journey_assessment_links WHERE assessment_id = '$ASSESSMENT_ID'")"
  if [[ -n "$status" ]]; then
    info "PASS: linked via JetStream (link_status=$status)"
    exit 0
  fi
  sleep 1
done
die "assessment $ASSESSMENT_ID was not consumed within ${TIMEOUT_SECONDS}s"
