#!/usr/bin/env bash
#
# Build the production image, start it with a real PostgreSQL through Docker Compose, run
# the curl integration tests against it, and tear everything down again.
#
#   tests/integration/run.sh            # build, test, clean up
#   KEEP=1 tests/integration/run.sh     # leave the stack running afterwards (for debugging)
#
# It uses its own Compose project (own containers, own database volume) and its own port
# (18000), so it can run while your normal `docker compose up` stack is running.
# Needs Docker Compose >= 2.24, curl and jq.

set -euo pipefail

cd "$(dirname "$0")/../.."

PROJECT="kamleon-it"
COMPOSE=(docker compose -p "$PROJECT" -f docker-compose.yml -f docker-compose.integration.yml)
export BASE_URL="${BASE_URL:-http://localhost:18000}"

step() { printf '\n\033[1;34m==> %s\033[0m\n' "$1"; }
die() {
    printf '\033[31mFAIL\033[0m %s\n' "$1" >&2
    exit 1
}

cleanup() {
    local status=$?
    if ((status != 0)); then
        step "Failed (exit $status): last API logs"
        "${COMPOSE[@]}" logs --no-color --tail=80 api || true
    fi
    if [[ "${KEEP:-0}" == "1" ]]; then
        echo "Stack left running at $BASE_URL (stop it with: ${COMPOSE[*]} down -v)"
    else
        step "Tearing the stack down"
        "${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
    fi
    exit "$status"
}
trap cleanup EXIT

http_code() { curl -s -o /dev/null -m 10 -w '%{http_code}' "$BASE_URL$1" || true; }

step "Building the image and starting PostgreSQL + the API"
"${COMPOSE[@]}" up -d --build --wait --wait-timeout 180

step "Production-like checks on the container"
uid="$("${COMPOSE[@]}" exec -T api id -u | tr -d '\r')"
[[ "$uid" != "0" ]] || die "the API container runs as root"
echo "  ok    the API container does not run as root (uid $uid)"

step "Running the API integration tests"
tests/integration/test_api.sh

step "Restart resilience: data survives an API restart and migrations re-run cleanly"
marker_email="restart-$(date +%s)$RANDOM@example.com"
marker="$(curl -sS -m 10 -X POST "$BASE_URL/customers" -H 'Content-Type: application/json' \
    -d "{\"name\": \"Restart marker\", \"email\": \"$marker_email\"}" | jq -r .id)"
[[ ${#marker} -eq 36 ]] || die "could not create the marker customer"
"${COMPOSE[@]}" restart api
"${COMPOSE[@]}" up -d --wait --wait-timeout 120
[[ "$(http_code "/customers/$marker")" == "200" ]] || die "data was lost across an API restart"
echo "  ok    the marker customer is still there after the restart"
tests/integration/test_api.sh

step "Dependency failure: liveness stays up, readiness reports the database is down"
"${COMPOSE[@]}" stop db
[[ "$(http_code /_health)" == "200" ]] || die "liveness should not depend on the database"
echo "  ok    /_health still answers 200 without the database"
[[ "$(http_code /_health/ready)" == "503" ]] || die "readiness should be 503 without the database"
echo "  ok    /_health/ready answers 503 without the database"
"${COMPOSE[@]}" start db
for _ in $(seq 60); do
    [[ "$(http_code /_health/ready)" == "200" ]] && break
    sleep 1
done
[[ "$(http_code /_health/ready)" == "200" ]] || die "the API did not recover after the database came back"
echo "  ok    the API recovered once the database came back"

step "All integration checks passed"
