#!/usr/bin/env bash
#
# Black-box integration tests for the Kamleon API, using only curl and jq.
#
# They talk HTTP to an API that is already running (typically the Docker image, see
# `run.sh`), so they exercise what the unit tests cannot: the real container, gunicorn
# workers, the real PostgreSQL and real concurrent connections.
#
#   BASE_URL=http://localhost:8000 tests/integration/test_api.sh
#
# Every run uses unique emails and serial numbers, so it can be repeated against the same
# database without cleaning it. Exit status is 0 when everything passed, 1 otherwise.

set -uo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
BASE_URL="${BASE_URL%/}"
WAIT_SECONDS="${WAIT_SECONDS:-60}"
RUN_ID="$(date +%s)${RANDOM}"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

STATUS=""
BODY=""
PASSED=0
FAILED=0
FAILURES=()

# --------------------------------------------------------------------------- helpers

for tool in curl jq xargs; do
    command -v "$tool" >/dev/null 2>&1 || {
        echo "error: '$tool' is required but not installed" >&2
        exit 2
    }
done

section() { printf '\n\033[1m%s\033[0m\n' "$1"; }

pass() {
    PASSED=$((PASSED + 1))
    printf '  \033[32mok\033[0m    %s\n' "$1"
}

fail() {
    FAILED=$((FAILED + 1))
    FAILURES+=("$1")
    printf '  \033[31mFAIL\033[0m  %s\n' "$1"
    [[ -n "${2-}" ]] && printf '        %s\n' "$2"
    return 0
}

# request METHOD PATH [JSON_BODY]  ->  sets $STATUS and $BODY
request() {
    local method=$1 path=$2 data=${3-}
    local args=(-sS -m 20 -X "$method" -o "$TMP/body" -w '%{http_code}' -H 'Accept: application/json')
    if [[ -n "$data" ]]; then
        args+=(-H 'Content-Type: application/json' --data-binary "$data")
    fi
    STATUS="$(curl "${args[@]}" "$BASE_URL$path")" || STATUS="000"
    BODY="$(cat "$TMP/body" 2>/dev/null || true)"
}

# json JQ_FILTER -> prints a value from the last response body
json() { jq -r "$1" <<<"$BODY"; }

# expect DESCRIPTION EXPECTED_STATUS [JQ_FILTER_THAT_MUST_BE_TRUE]
expect() {
    local description=$1 want=$2 filter=${3-}
    if [[ "$STATUS" != "$want" ]]; then
        fail "$description" "expected HTTP $want, got $STATUS: $(printf '%s' "$BODY" | head -c 300)"
        return 0
    fi
    if [[ -n "$filter" ]] && ! jq -e "$filter" >/dev/null 2>&1 <<<"$BODY"; then
        fail "$description" "HTTP $STATUS but jq '$filter' is not true for: $(printf '%s' "$BODY" | head -c 300)"
        return 0
    fi
    pass "$description"
}

# check DESCRIPTION ACTUAL EXPECTED  (plain value comparison)
check() {
    if [[ "$2" == "$3" ]]; then
        pass "$1"
    else
        fail "$1" "expected '$3', got '$2'"
    fi
}

# fanout METHOD PATH
# Reads NUL-separated JSON bodies on stdin, sends them all at once (up to 20 in parallel)
# and prints one HTTP status code per line.
fanout() {
    xargs -0 -P 20 -I{} \
        curl -s -o /dev/null -m 60 -w '%{http_code}\n' -X "$1" \
        -H 'Content-Type: application/json' --data-binary {} "$BASE_URL$2"
}

count_of() { grep -c -x "$1" || true; }

# ts HOUR [DAY]  ->  2026-01-DAYTHH:00:00Z
ts() { printf '2026-01-%02dT%02d:00:00Z' "${2:-1}" "$1"; }

measurement() { # TYPE VALUE UNIT TIMESTAMP
    printf '{"type": "%s", "value": %s, "unit": "%s", "timestamp": "%s"}' "$1" "$2" "$3" "$4"
}

new_customer() { # NAME EMAIL -> sets CUSTOMER_ID
    request POST /customers "{\"name\": \"$1\", \"email\": \"$2\"}"
    CUSTOMER_ID="$(json .id)"
}

new_device() { # CUSTOMER_ID SERIAL [STATUS]
    request POST "/customers/$1/devices" "{\"serial_number\": \"$2\", \"status\": \"${3:-INACTIVE}\"}"
}

wait_until_ready() {
    local code i
    for ((i = 0; i < WAIT_SECONDS; i++)); do
        code="$(curl -s -o /dev/null -m 3 -w '%{http_code}' "$BASE_URL/_health/ready" || true)"
        [[ "$code" == "200" ]] && return 0
        sleep 1
    done
    echo "error: $BASE_URL/_health/ready did not return 200 within ${WAIT_SECONDS}s" >&2
    return 1
}

# --------------------------------------------------------------------------- scenarios

test_health_and_docs() {
    section "Health checks and documentation"
    request GET /_health
    expect "liveness answers 200" 200 '.health == "ok"'
    request GET /_health/ready
    expect "readiness answers 200 and reaches the database" 200 '.database == "ok"'
    request GET /openapi.json
    expect "OpenAPI schema is served" 200 '.info.title == "Kamleon API"'
    request GET /docs
    expect "Swagger UI is served" 200
    request GET /no-such-route
    expect "unknown route is 404" 404
}

test_customers() {
    section "Customers"
    EMAIL="ada-$RUN_ID@example.com"

    new_customer "Ada Lovelace" "$EMAIL"
    expect "create a customer" 201 ".name == \"Ada Lovelace\" and .email == \"$EMAIL\" and (.id | length) == 36"

    request POST /customers "{\"name\": \"Other Ada\", \"email\": \"$EMAIL\"}"
    expect "duplicate email is a 409" 409 '.code == "duplicate_email"'

    request POST /customers "{\"name\": \"Shouty Ada\", \"email\": \"ADA-$RUN_ID@EXAMPLE.COM\"}"
    expect "email uniqueness is case-insensitive" 409 '.code == "duplicate_email"'

    request GET "/customers/$CUSTOMER_ID"
    expect "retrieve a customer" 200 ".id == \"$CUSTOMER_ID\""

    request GET "/customers/00000000-0000-4000-8000-000000000000"
    expect "unknown customer is a 404" 404 '.code == "customer_not_found"'

    request GET /customers/not-a-uuid
    expect "malformed customer id is a 422" 422 '.detail | type == "array"'

    request POST /customers '{"name": "No Email"}'
    expect "missing email is a 422" 422
    request POST /customers '{"name": "Bad Email", "email": "not-an-email"}'
    expect "invalid email is a 422" 422
    request POST /customers "{\"name\": \"Evil\", \"email\": \"evil-$RUN_ID@example.com\", \"is_admin\": true}"
    expect "unknown fields are rejected" 422
    request POST /customers 'this is not json'
    expect "a non-JSON body is a 422" 422
}

test_devices() {
    section "Devices"
    new_customer "Device Owner" "owner-$RUN_ID@example.com"
    OWNER_ID="$CUSTOMER_ID"
    SERIAL_A="IT${RUN_ID}A"
    SERIAL_B="IT${RUN_ID}B"

    new_device "$OWNER_ID" "$SERIAL_A"
    expect "register a device (starts INACTIVE)" 201 \
        ".serial_number == \"$SERIAL_A\" and .status == \"INACTIVE\" and .customer_id == \"$OWNER_ID\""

    new_device "$OWNER_ID" "$SERIAL_A"
    expect "duplicate serial number is a 409" 409 '.code == "duplicate_serial_number"'

    new_customer "Someone Else" "else-$RUN_ID@example.com"
    new_device "$CUSTOMER_ID" "$SERIAL_A"
    expect "a serial number is unique across customers" 409 '.code == "duplicate_serial_number"'

    new_device "00000000-0000-4000-8000-000000000000" "IT${RUN_ID}X"
    expect "registering for an unknown customer is a 404" 404 '.code == "customer_not_found"'

    request POST "/customers/$OWNER_ID/devices" '{"serial_number": "bad serial!"}'
    expect "a serial number with illegal characters is a 422" 422

    new_device "$OWNER_ID" "$SERIAL_B"
    expect "register a second device" 201

    request GET "/customers/$OWNER_ID/devices"
    expect "list a customer's devices" 200 '.count == 2 and (.results | length) == 2'
    request GET "/customers/$OWNER_ID/devices?limit=1&offset=1"
    expect "device list is paginated" 200 '.count == 2 and .limit == 1 and .offset == 1 and (.results | length) == 1'

    request GET "/devices/$SERIAL_A"
    expect "retrieve a device by serial number" 200 ".customer_id == \"$OWNER_ID\""
    request GET "/devices/IT${RUN_ID}NOPE"
    expect "unknown device is a 404" 404 '.code == "device_not_found"'

    request PATCH "/devices/$SERIAL_A/status" '{"status": "BROKEN"}'
    expect "an invalid status is a 422" 422
    request PATCH "/devices/$SERIAL_A/status" "{\"status\": \"ACTIVE\", \"customer_id\": \"$CUSTOMER_ID\"}"
    expect "a device cannot be moved to another customer through the status endpoint" 422
    request PATCH "/devices/IT${RUN_ID}NOPE/status" '{"status": "ACTIVE"}'
    expect "changing the status of an unknown device is a 404" 404
}

test_ingestion() {
    section "Measurement ingestion (idempotency)"
    local url="/devices/$SERIAL_A/measurements"

    request POST "$url" "$(measurement temperature 21.5 celsius "$(ts 12)")"
    expect "an INACTIVE device refuses measurements" 409 '.code == "device_not_active"'

    request POST "/devices/IT${RUN_ID}NOPE/measurements" "$(measurement temperature 1 celsius "$(ts 12)")"
    expect "an unknown device is a 404, not a silent 201" 404 '.code == "device_not_found"'

    request PATCH "/devices/$SERIAL_A/status" '{"status": "ACTIVE"}'
    expect "activate the device" 200 '.status == "ACTIVE"'

    request POST "$url" "$(measurement temperature 21.5 celsius "$(ts 12)")"
    expect "first delivery is a 201" 201 '.value == 21.5 and .unit == "celsius" and .timestamp == "2026-01-01T12:00:00Z"'
    FIRST_ID="$(json .id)"

    request POST "$url" "$(measurement temperature 21.5 celsius "$(ts 12)")"
    expect "an identical retry is a 200 with the stored measurement" 200 ".id == $FIRST_ID"

    request POST "$url" "$(measurement temperature 21.5 celsius 2026-01-01T14:00:00+02:00)"
    expect "the same instant in another time zone is the same measurement" 200 ".id == $FIRST_ID"

    request POST "$url" "$(measurement temperature 99.9 celsius "$(ts 12)")"
    expect "same instant, different value is a 409" 409 '.code == "measurement_conflict"'
    request POST "$url" "$(measurement temperature 21.5 fahrenheit "$(ts 12)")"
    expect "same instant, different unit is a 409" 409 '.code == "measurement_conflict"'

    request POST "$url" "$(measurement humidity 40 percent "$(ts 12)")"
    expect "another type at the same instant is a new measurement" 201 '.id != '"$FIRST_ID"
    request POST "$url" "$(measurement temperature 22 celsius 2026-01-01T12:00:01Z)"
    expect "another timestamp is a new measurement" 201

    request GET "$url"
    expect "exactly 3 measurements were stored" 200 '.count == 3'

    section "Measurement ingestion (validation)"
    request POST "$url" "$(measurement temperature 1 celsius 2026-01-02T12:00:00)"
    expect "a timestamp without a time zone is a 422" 422
    request POST "$url" '{"type": "temperature", "value": "warm", "unit": "celsius", "timestamp": "2026-01-02T12:00:00Z"}'
    expect "a non-numeric value is a 422" 422
    request POST "$url" '{"type": "", "value": 1, "unit": "celsius", "timestamp": "2026-01-02T12:00:00Z"}'
    expect "an empty type is a 422" 422
    request POST "$url" '{"type": "temperature", "value": 1, "timestamp": "2026-01-02T12:00:00Z"}'
    expect "a missing field is a 422" 422
    request POST "$url" '{"type": "temperature", "value": 1, "unit": "c", "timestamp": "2026-01-02T12:00:00Z", "serial_number": "x"}'
    expect "unknown fields are rejected" 422

    local bad
    for bad in NaN Infinity -Infinity; do
        request POST "$url" "{\"type\": \"temperature\", \"value\": $bad, \"unit\": \"celsius\", \"timestamp\": \"2026-01-02T12:00:00Z\"}"
        expect "$bad is a clean 422 (not a 500) and the input is not echoed" 422 \
            '(.detail | type == "array") and ([.detail[] | has("input")] | any | not)'
    done

    section "Measurement ingestion (device state)"
    new_device "$OWNER_ID" "IT${RUN_ID}F" FAULTY
    request POST "/devices/IT${RUN_ID}F/measurements" "$(measurement temperature 1 celsius "$(ts 12)")"
    expect "a FAULTY device refuses measurements" 409 '.code == "device_not_active"'

    request PATCH "/devices/$SERIAL_B/status" '{"status": "ACTIVE"}'
    request POST "/devices/$SERIAL_B/measurements" "$(measurement temperature 5 celsius "$(ts 1)")"
    expect "a second device accepts the same instant independently" 201
    request PATCH "/devices/$SERIAL_B/status" '{"status": "INACTIVE"}'
    expect "deactivate the device" 200 '.status == "INACTIVE"'
    request POST "/devices/$SERIAL_B/measurements" "$(measurement temperature 6 celsius "$(ts 2)")"
    expect "a deactivated device refuses measurements" 409 '.code == "device_not_active"'
}

test_queries() {
    section "Measurement queries"
    new_customer "Query Owner" "query-$RUN_ID@example.com"
    local serial="IT${RUN_ID}Q" url h
    new_device "$CUSTOMER_ID" "$serial" ACTIVE
    url="/devices/$serial/measurements"

    for h in 0 1 2 3 4 5; do
        request POST "$url" "$(measurement temperature "$h" celsius "$(ts "$h")")"
    done
    for h in 0 1 2; do
        request POST "$url" "$(measurement humidity "$((40 + h))" percent "$(ts "$h")")"
    done

    request GET "$url"
    expect "list all measurements with default paging" 200 '.count == 9 and .limit == 10 and .offset == 0 and (.results | length) == 9'
    expect "results are newest first" 200 '[.results[].timestamp] == ([.results[].timestamp] | sort | reverse)'

    request GET "$url?type=humidity"
    expect "filter by type" 200 '.count == 3 and ([.results[].type] | unique) == ["humidity"]'
    request GET "$url?type=pressure"
    expect "a type without data gives an empty page" 200 '.count == 0 and .results == []'

    request GET "$url?type=temperature&timestamp_after=$(ts 4)"
    expect "timestamp_after is inclusive" 200 '.count == 2'
    request GET "$url?type=temperature&timestamp_before=$(ts 1)"
    expect "timestamp_before is inclusive" 200 '.count == 2'
    request GET "$url?type=temperature&timestamp_after=$(ts 1)&timestamp_before=$(ts 3)"
    expect "a closed time range" 200 '.count == 3'
    request GET "$url?timestamp_after=$(ts 2)&timestamp_before=$(ts 2)"
    expect "a single-instant range matches every type at that instant" 200 '.count == 2'
    request GET "$url?type=temperature&timestamp_after=2026-01-01T07:00:00%2B02:00"
    expect "time filters accept UTC offsets (07:00+02:00 is 05:00Z)" 200 '.count == 1'
    request GET "$url?timestamp_after=2026-06-01T00:00:00Z"
    expect "the filter uses the measurement time, not the ingestion time" 200 '.count == 0'

    local ids="" page offset
    for offset in 0 4 8; do
        request GET "$url?limit=4&offset=$offset"
        expect "page at offset $offset" 200 '.count == 9'
        ids+="$(jq -r '.results[].id' <<<"$BODY")"$'\n'
    done
    check "pages have no overlaps and no gaps (9 distinct ids)" "$(printf '%s' "$ids" | sort -u | grep -c .)" "9"

    request GET "$url?timestamp_after=$(ts 3)&timestamp_before=$(ts 1)"
    expect "an inverted time range is a 422" 422 '.code == "invalid_time_range"'
    request GET "$url?limit=0"
    expect "limit=0 is a 422" 422
    request GET "$url?limit=101"
    expect "limit above 100 is a 422" 422
    request GET "$url?offset=-1"
    expect "a negative offset is a 422" 422
    request GET "$url?timestamp_after=2026-01-01T00:00:00"
    expect "a naive timestamp filter is a 422" 422
    request GET "$url?timestamp_after=yesterday"
    expect "an unparsable timestamp filter is a 422" 422
    request GET "/devices/IT${RUN_ID}NOPE/measurements"
    expect "measurements of an unknown device is a 404" 404

    request GET "/devices/$SERIAL_A/measurements"
    expect "other devices' measurements are not mixed in" 200 '.count == 3'
}

test_concurrency() {
    section "Concurrency (real parallel connections)"
    new_customer "Concurrent Owner" "concurrent-$RUN_ID@example.com"
    local serial="IT${RUN_ID}C" url codes i
    new_device "$CUSTOMER_ID" "$serial" ACTIVE
    url="/devices/$serial/measurements"

    # 1. Twenty identical deliveries at the same instant: one 201, nineteen 200, one row.
    codes="$(for _ in $(seq 20); do
        printf '%s\0' "$(measurement temperature 21.5 celsius "$(ts 12 5)")"
    done | fanout POST "$url")"
    check "20 identical simultaneous deliveries: exactly one 201" "$(count_of 201 <<<"$codes")" "1"
    check "20 identical simultaneous deliveries: nineteen 200" "$(count_of 200 <<<"$codes")" "19"
    request GET "$url?type=temperature"
    expect "...and exactly one row was stored" 200 '.count == 1'

    # 2. Twenty distinct measurements at once are all stored.
    codes="$(for i in $(seq 0 19); do
        printf '%s\0' "$(measurement pressure "$i" hpa "$(printf '2026-01-06T00:00:%02dZ' "$i")")"
    done | fanout POST "$url")"
    check "20 distinct simultaneous measurements: all 201" "$(count_of 201 <<<"$codes")" "20"
    request GET "$url?type=pressure"
    expect "...and all were stored" 200 '.count == 20'

    # 3. Twenty simultaneous registrations of the same serial: one 201, the rest 409.
    codes="$(for _ in $(seq 20); do
        printf '%s\0' "{\"serial_number\": \"IT${RUN_ID}DUP\"}"
    done | fanout POST "/customers/$CUSTOMER_ID/devices")"
    check "20 simultaneous registrations of one serial: exactly one 201" "$(count_of 201 <<<"$codes")" "1"
    check "...the others are 409 (never a 500)" "$(count_of 409 <<<"$codes")" "19"

    # 4. Ingestion racing with a deactivation: every answer is 201 or 409, nothing else,
    #    and the number of stored measurements equals the number of 201s.
    new_device "$CUSTOMER_ID" "IT${RUN_ID}R" ACTIVE
    local race="/devices/IT${RUN_ID}R/measurements"
    for i in $(seq 0 29); do
        printf '%s\0' "$(measurement temperature "$i" celsius "$(printf '2026-01-07T00:00:%02dZ' "$i")")"
    done | fanout POST "$race" >"$TMP/race_codes" &
    local ingest_pid=$!
    sleep 0.05 # let the first ingestions get going, so the deactivation lands in the middle
    request PATCH "/devices/IT${RUN_ID}R/status" '{"status": "INACTIVE"}'
    expect "deactivation succeeds while ingestions are in flight" 200 '.status == "INACTIVE"'
    wait "$ingest_pid"

    local created conflicts others
    created="$(count_of 201 <"$TMP/race_codes")"
    conflicts="$(count_of 409 <"$TMP/race_codes")"
    others="$(grep -c -v -x -E '201|409' "$TMP/race_codes" || true)"
    printf '        (%s ingestions won the race, %s were refused)\n' "$created" "$conflicts"
    check "every racing ingestion is a 201 or a 409 (no 5xx)" "$others" "0"
    check "all 30 racing ingestions were answered" "$((created + conflicts))" "30"
    request GET "$race"
    expect "stored measurements equal acknowledged ones ($created)" 200 ".count == $created"
    request POST "$race" "$(measurement temperature 1 celsius 2026-01-08T00:00:00Z)"
    expect "after the deactivation no measurement is accepted" 409 '.code == "device_not_active"'
}

test_customer_deletion() {
    section "Customer deletion (GDPR erasure)"
    local email="gdpr-$RUN_ID@example.com" serial="IT${RUN_ID}G" customer
    new_customer "Erase Me" "$email"
    customer="$CUSTOMER_ID"
    new_device "$customer" "$serial" ACTIVE
    request POST "/devices/$serial/measurements" "$(measurement temperature 20 celsius "$(ts 12)")"
    expect "the customer's device ingests before deletion" 201

    request DELETE "/customers/$customer"
    expect "delete the customer" 204
    check "a 204 has an empty body" "$BODY" ""

    request GET "/customers/$customer"
    expect "a deleted customer behaves as not found" 404 '.code == "customer_not_found"'
    request DELETE "/customers/$customer"
    expect "deleting twice is a 404" 404
    request GET "/customers/$customer/devices"
    expect "a deleted customer has no device list" 404
    new_device "$customer" "IT${RUN_ID}G2"
    expect "no device can be registered for a deleted customer" 404

    request GET "/devices/$serial"
    expect "the device is kept but deactivated" 200 '.status == "INACTIVE"'
    request POST "/devices/$serial/measurements" "$(measurement temperature 21 celsius "$(ts 13)")"
    expect "the deactivated device refuses new measurements" 409 '.code == "device_not_active"'
    request PATCH "/devices/$serial/status" '{"status": "ACTIVE"}'
    expect "the device cannot be re-activated" 409 '.code == "customer_deleted"'
    request GET "/devices/$serial/measurements"
    expect "historical measurements are retained" 200 '.count == 1'

    new_customer "New Owner" "$email"
    expect "the erased email can be registered again" 201
}

# --------------------------------------------------------------------------- main

printf 'API integration tests against %s (run %s)\n' "$BASE_URL" "$RUN_ID"
wait_until_ready || exit 1

test_health_and_docs
test_customers
test_devices
test_ingestion
test_queries
test_concurrency
test_customer_deletion

printf '\n\033[1m%d passed, %d failed\033[0m\n' "$PASSED" "$FAILED"
if ((FAILED > 0)); then
    printf 'Failed:\n'
    printf '  - %s\n' "${FAILURES[@]}"
    exit 1
fi
