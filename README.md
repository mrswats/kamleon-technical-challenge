# Kamleon Technical Challenge

A small backend service that manages **customers**, their connected **devices** and the
**measurements** those devices generate.

**Stack:** Python 3.14 · FastAPI · Pydantic v2 · SQLAlchemy 2.0 (async, psycopg 3) ·
PostgreSQL 17 · Alembic · pytest.

- [Running the application](#running-the-application)
- [Running the tests](#running-the-tests)
- [API documentation and curl examples](#api-documentation-and-curl-examples)
- [Data model](#data-model)
- [Main technical decisions and assumptions](#main-technical-decisions-and-assumptions)
- [Known limitations](#known-limitations)
- [What I would improve with more time](#what-i-would-improve-with-more-time)
- [Data protection and security proposals](#data-protection-and-security-proposals)
- [Monitoring and observability](#monitoring-and-observability)
- [Code quality and testing strategy](#code-quality-and-testing-strategy)
- [AI-assisted development](#ai-assisted-development)

## Running the application

### With Docker (recommended)

```console
docker compose up --build
```

This starts PostgreSQL, applies the migrations and serves the API on
`http://localhost:8000`. Interactive API documentation is at
[`http://localhost:8000/docs`](http://localhost:8000/docs) (Swagger UI), with ReDoc at
`/redoc` and the OpenAPI schema at `/openapi.json`.

### Without Docker for the API

You still need a PostgreSQL. The compose file provides one:

```console
docker compose up -d db

python3.14 -m venv .venv
source .venv/bin/activate
pip install -e ".[test,dev]"

alembic upgrade head
uvicorn kamleon.asgi:app --reload
```

The only setting is `DATABASE_URL` (environment variable or a local `.env` file). Its
default, `postgresql+psycopg://postgres:postgres@localhost:5432/postgres`, matches the
compose database.

### Migrations

```console
alembic upgrade head                              # apply
alembic revision --autogenerate -m "describe it"  # after changing a model
alembic downgrade -1                              # revert the last one
```

The container applies pending migrations on start (`MODE=api`). `MODE=migrate` runs them
and exits, which is what you would use as a one-off job when running several replicas.

### Dependency lockfiles

Dependencies are declared in `pyproject.toml`. To pin them with hashes (what the Dockerfile
and CI use automatically when the files exist):

```console
pip install pip-tools
pip-compile --generate-hashes pyproject.toml -o requirements.txt
pip-compile --generate-hashes --extra test pyproject.toml -o test-requirements.txt
```

Dependabot keeps them up to date.

## Running the tests

The tests run against a **real PostgreSQL**: the behaviour that matters here (unique
constraints, `ON CONFLICT`, row locks, concurrent requests) is PostgreSQL behaviour and
cannot be verified on SQLite.

```console
docker compose up -d db
python -m pytest --cov --cov-report term-missing
python -m pytest -n 4          # in parallel
```

- `TEST_DATABASE_URL` (default: the compose database) must point at a server whose user
  can create databases.
- Every pytest-xdist worker creates its **own database**, builds it by running the real
  Alembic migrations, and drops it at the end. Tables are truncated between tests, so tests
  are isolated and `pytest-randomly` can shuffle them.
- `covdefaults` fails the run below 100 % coverage (test code included).
- `tests/test_missing_migrations.py` fails when a model changes without a migration, and
  checks that migrations can be reverted and re-applied.

## API documentation and curl examples

The examples below follow one story. Replace the ids with the ones returned to you.

```console
BASE=http://localhost:8000
```

**Create a customer**: `POST /customers`

```console
curl -s -X POST $BASE/customers \
  -H 'content-type: application/json' \
  -d '{"name": "Ada Lovelace", "email": "ada@example.com"}'
```
```json
{"id": "6f1c0a52-3a0e-4d57-9d6c-0f3b1c1f5a10", "name": "Ada Lovelace",
 "email": "ada@example.com", "created_at": "2026-10-11T10:00:00Z",
 "updated_at": "2026-10-11T10:00:00Z"}
```

```console
CUSTOMER=6f1c0a52-3a0e-4d57-9d6c-0f3b1c1f5a10
```

**Retrieve a customer**: `GET /customers/{id}`

```console
curl -s $BASE/customers/$CUSTOMER
```

**Register a device for the customer**: `POST /customers/{id}/devices`

The serial number is the factory serial, chosen by the caller, and is globally unique. A new
device starts `INACTIVE`.

```console
curl -s -X POST $BASE/customers/$CUSTOMER/devices \
  -H 'content-type: application/json' \
  -d '{"serial_number": "KML-000123"}'
```
```json
{"id": "0b7e...", "serial_number": "KML-000123", "customer_id": "6f1c...",
 "status": "INACTIVE", "created_at": "...", "updated_at": "..."}
```

**List a customer's devices**: `GET /customers/{id}/devices?limit=10&offset=0`

```console
curl -s "$BASE/customers/$CUSTOMER/devices?limit=10&offset=0"
```
```json
{"count": 1, "limit": 10, "offset": 0, "results": [{"serial_number": "KML-000123", "...": "..."}]}
```

**Retrieve a device**: `GET /devices/{serial_number}`

```console
curl -s $BASE/devices/KML-000123
```

**Activate / deactivate a device**: `PATCH /devices/{serial_number}/status`

Statuses are `ACTIVE`, `INACTIVE` and `FAULTY`. Only `status` can be sent.

```console
curl -s -X PATCH $BASE/devices/KML-000123/status \
  -H 'content-type: application/json' \
  -d '{"status": "ACTIVE"}'
```

**Ingest a measurement**: `POST /devices/{serial_number}/measurements`

Idempotent. A measurement is identified by *(device, type, timestamp)*. `timestamp` must
carry a timezone.

```console
curl -s -i -X POST $BASE/devices/KML-000123/measurements \
  -H 'content-type: application/json' \
  -d '{"type": "temperature", "value": 21.5, "unit": "celsius",
       "timestamp": "2026-01-01T12:00:00Z"}'
```
```
HTTP/1.1 201 Created
{"id": 1, "device_id": "0b7e...", "type": "temperature", "value": 21.5,
 "unit": "celsius", "timestamp": "2026-01-01T12:00:00Z", "created_at": "..."}
```

Run the same command again (a network retry) and you get `200 OK` with the same stored
measurement and no duplicate. Send the same *(type, timestamp)* with a different value or
unit and you get `409`.

**List a device's measurements**: `GET /devices/{serial_number}/measurements`

Newest first. Filters: `type`, `timestamp_after`, `timestamp_before` (both inclusive, they
filter on when the measurement was *generated*), plus `limit` (1-100, default 10) and
`offset`.

```console
curl -s "$BASE/devices/KML-000123/measurements?type=temperature&timestamp_after=2026-01-01T00:00:00Z&timestamp_before=2026-01-02T00:00:00Z&limit=50"
```
```json
{"count": 1, "limit": 50, "offset": 0, "results": [{"id": 1, "type": "temperature", "...": "..."}]}
```

**Delete a customer**: `DELETE /customers/{id}`

Erases the customer's personal data and deactivates their devices; devices and measurements
are kept (see [the decision below](#what-happens-when-a-customer-is-deleted)).

```console
curl -s -i -X DELETE $BASE/customers/$CUSTOMER      # 204 No Content
```

**Health checks**

```console
curl -s $BASE/_health         # {"health": "ok"}, liveness: no database access
curl -s $BASE/_health/ready   # {"health": "ok", "database": "ok"}, 503 if the DB is unreachable
```

### Errors

Errors raised by the business rules have the shape `{"detail": "...", "code": "..."}`;
`code` is stable and meant for clients. Request validation errors keep FastAPI's standard
`422` body.

| Status | `code` | When |
| --- | --- | --- |
| 404 | `customer_not_found` | Unknown (or deleted) customer |
| 404 | `device_not_found` | Unknown serial number |
| 409 | `duplicate_email` | Email already used by a customer |
| 409 | `duplicate_serial_number` | Serial number already registered |
| 409 | `customer_deleted` | Re-activating a device whose customer was deleted |
| 409 | `device_not_active` | Ingesting for a device that is not `ACTIVE` |
| 409 | `measurement_conflict` | Same device/type/timestamp already stored with another value or unit |
| 422 | `invalid_time_range` | `timestamp_after` is later than `timestamp_before` |
| 422 | (FastAPI) | Malformed input: missing fields, naive timestamps, NaN, unknown fields... |
| 503 | | `/_health/ready` cannot reach the database |

## Data model

```mermaid
erDiagram
    CUSTOMER ||--o{ DEVICE : owns
    DEVICE ||--o{ MEASUREMENT : generates

    CUSTOMER {
        uuid id PK
        string name
        string email UK
        timestamptz deleted_at "set when erased"
        timestamptz created_at
        timestamptz updated_at
    }
    DEVICE {
        uuid id PK
        string serial_number UK
        uuid customer_id FK
        string status "ACTIVE | INACTIVE | FAULTY"
        timestamptz created_at
        timestamptz updated_at
    }
    MEASUREMENT {
        bigint id PK
        uuid device_id FK
        string type
        double value
        string unit
        timestamptz timestamp "when the device generated it"
        timestamptz created_at "when we stored it"
    }
```

Constraints and indexes (all named deterministically through a SQLAlchemy naming
convention, so migrations are reproducible and the application can tell *which* constraint
was violated):

- `customers.email` unique · `devices.serial_number` unique · `devices.status` CHECK in
  (`ACTIVE`, `INACTIVE`, `FAULTY`).
- Foreign keys `devices.customer_id → customers.id` and `measurements.device_id →
  devices.id`, both **`ON DELETE RESTRICT`**.
- `measurements` **unique on `(device_id, type, timestamp)`**: the natural key that makes
  ingestion idempotent. It also serves the common query "one device, one type, a time
  range".
- `ix_measurements_device_id_timestamp (device_id, timestamp)` for queries without a type
  filter and for newest-first ordering.
- `ix_devices_customer_id` for listing a customer's devices.

## Main technical decisions and assumptions

### Layout

Each domain (`identity`, `devices`, `ingestion`, `health`) has its own `models`, `schemas`,
`service` and `router`. Routers only translate HTTP; **services own the business rules and
the transactions**; models describe the tables. The database engine lives on `app.state`
(created by the `create_app()` factory), not in globals, so tests build an app that points
at their own database.

### Idempotent ingestion

The same measurement can be delivered several times (network retries), possibly at the same
instant. Deduplication is delegated to the database instead of a check-then-insert in Python:

1. The device row is locked `FOR SHARE` and checked to be `ACTIVE`.
2. `INSERT ... ON CONFLICT DO NOTHING` on `(device_id, type, timestamp)`, a single atomic
   statement.
3. If the row already existed: **`200`** with the stored measurement when value and unit
   match (a true retry), **`409`** when they differ. A corrected value is therefore never
   silently dropped, and a replayed old message can never overwrite newer data.

*Assumption:* a device reports at most one value per measurement type per instant. If it
could legitimately send several, the key would become a device-generated measurement id.

### Concurrency and data integrity

- **Ingest vs. deactivate.** Ingestion holds `FOR SHARE` on the device row; changing a status
  takes `FOR UPDATE`. Concurrent ingestions do not block each other, but a deactivation waits
  for in-flight ingestions to commit, and from then on new ones are refused. So no
  measurement is accepted for a device after it became inactive.
- **Unique values** (serial number, email, measurement key) are enforced by `UNIQUE`
  constraints; a lost race becomes a clean `409`, never a `500`.
- **Customer deletion vs. device registration/activation** are serialised through a lock on
  the customer row. Locks are always taken customer first, then device, so they cannot
  deadlock.
- These behaviours are covered by tests that fire concurrent requests (20 identical
  ingestions, 10 identical device registrations, ingestions racing a deactivation).

### What happens when a customer is deleted

A device and its measurements are operational data that may be needed after a customer
leaves, while the customer's *personal* data must be erasable (GDPR). So `DELETE
/customers/{id}`:

- **anonymises** the customer (name and email are overwritten, `deleted_at` is set) and
  frees the email for reuse;
- **deactivates** the customer's devices so they stop ingesting;
- **keeps** the devices and measurements, which no longer point to an identifiable person;
- the foreign keys are `ON DELETE RESTRICT`, so no row can ever be removed by cascade.

A deleted customer behaves as not found (`404`), and their devices cannot be re-activated.

### Other decisions

- **FastAPI async + SQLAlchemy 2.0 + psycopg 3.** Ingestion is I/O-bound; the same
  `postgresql+psycopg://` URL serves the async API and the sync Alembic runs.
- **No Redis/queue for ingestion.** Ingestion is one cheap indexed statement, so it is done
  inside the request. That lets the API tell the device the truth (`404`/`409`) and removes a
  way to lose acknowledged data (a message accepted into a queue that is lost, or rejected
  later by a worker nobody sees). A queue would be the next step only for batch ingestion at
  a volume one Postgres cannot absorb.
- **Identifiers.** Customers and devices use UUIDs (not guessable or enumerable) and devices
  are addressed by their serial number. Measurements use a `bigint` identity (high volume,
  cheap to index). The serial number is supplied by the caller: it is the number printed on
  the product, not something the server should invent.
- **Time.** `timestamptz` everywhere; request timestamps must be timezone-aware (a naive time
  is ambiguous and is rejected). Time-range filters apply to the measurement's own
  `timestamp`, inclusive on both ends, not to when it was stored.
- **`value` is a finite number** (`double precision`). NaN and Infinity are rejected.
- **Statuses:** `ACTIVE`, `INACTIVE` (the default for a new device) and `FAULTY`. Only
  `ACTIVE` devices can ingest.
- **Pagination:** `limit` (max 100) and `offset`, with a `count`. Simple and predictable.
- **Two health endpoints:** `/_health` (liveness, never touches the DB, so a database outage
  does not make an orchestrator restart healthy pods) and `/_health/ready` (readiness).
- **Authentication is deliberately not implemented**, as allowed by the brief. Unknown
  request fields are rejected, so credentials cannot be sent by mistake.

## Known limitations

- No authentication or authorisation, and no rate limiting (see the proposals below).
- One measurement per request. Devices that batch would benefit from a bulk endpoint.
- `offset` pagination gets slow for very deep pages and `count` scans the filtered rows.
- The `measurements` table is not partitioned; for large time-series volumes it should be
  (by time), or moved to TimescaleDB.
- Customers cannot be updated, and devices and measurements cannot be edited or deleted
  through the API.
- Anonymisation is irreversible, and it does not reach database backups, which keep the old
  data until they expire.
- The container runs migrations on start. With several replicas starting at once, run the
  `migrate` mode once as a separate job instead.
- No load test has been run, so throughput numbers are unmeasured.

## What I would improve with more time

**Correctness and API**
- A batch ingestion endpoint (`POST /devices/{sn}/measurements:batch`) returning how many
  were inserted and how many were duplicates, with the same `ON CONFLICT` approach.
- Keyset (cursor) pagination on `(timestamp, id)` for measurements.
- An `Idempotency-Key` header for the create endpoints.
- Rejecting timestamps unreasonably far in the future.

**Data and GDPR**
- A subject-access / portability export endpoint, an audit log of who read or erased
  personal data (without storing the data itself), and a scheduled retention job.
- Pseudonymise instead of overwriting where the business needs to keep statistics per
  (former) customer.

**Scalability**
- Time partitioning of `measurements` and a retention/downsampling policy.
- Read replicas for the query endpoints; PgBouncer in front of Postgres.
- A load test (k6 or Locust) to find the real bottleneck before optimising.

**Operations**
- OpenTelemetry instrumentation and the dashboards and alerts described below.
- Deployment manifests and a CD pipeline (out of scope for this exercise).

## Data protection and security proposals

1. **GDPR: erasure by anonymisation, plus retention.** Implemented for the primary case:
   deleting a customer overwrites their personal data and keeps operational data, so the
   rest of the system keeps working. To complete it: a documented retention period per data
   category with a scheduled purge job; keep any record the law requires us to retain
   (e.g. invoices) in a separate, access-restricted store; make sure analytics and logs never
   contain emails or names (use the customer UUID); and apply the same erasure to backups by
   expiring them within a bounded window.
2. **Encryption in transit and at rest.** TLS 1.2+ (preferably 1.3) terminated at the
   ingress with HSTS, and TLS between the service and PostgreSQL (`sslmode=verify-full`).
   Encrypt volumes and backups at rest (managed Postgres or disk encryption). For the most
   sensitive columns (customer email) add application-level encryption with keys held in a
   KMS and rotated, so a leaked database dump alone is not enough. Encrypting request bodies
   on top of HTTPS is not worth its key-management cost.
3. **API authentication for users and services.** OAuth 2.0 / OpenID Connect with
   short-lived JWT access tokens validated against the identity provider's JWKS, scopes per
   operation (read, write, admin) and an ownership check on every customer, device and
   measurement route (a caller only sees their own customers' data). Rate limiting at the
   gateway and per token.
4. **Device authentication, separate from user authentication.** Devices should not share
   a user token. Give each device its own credential: a client certificate (mutual TLS) or a
   per-device key provisioned at manufacturing and bound to its serial number, revocable
   when a device is deactivated or marked `FAULTY`. The ingestion route then accepts only
   the device whose credential matches the serial number in the URL.

Also worth having in the pipeline: dependency and image scanning (`pip-audit`, Dependabot,
Trivy), secrets kept out of the repository, and secure response headers at the gateway.

## Monitoring and observability

**Stack:** OpenTelemetry instrumentation exporting to Prometheus (metrics), Grafana (dashboards
and alerting) and a trace backend (Tempo or Jaeger), with structured JSON logs carrying a
request id shipped to Loki or the platform's log service, and Sentry for grouped exceptions.
Chosen because it is open standard, vendor-neutral and covers metrics, traces and logs with
the same context.

**What to monitor**

- *API (RED):* request rate, error rate (5xx) and latency percentiles (p50/p95/p99) per
  route; saturation (CPU, memory, workers).
- *PostgreSQL:* connections and pool usage, slow queries, lock waits and deadlocks,
  replication lag, disk growth (the `measurements` table is the one that will grow).
- *Business signals:* measurements ingested per minute; share of `409 device_not_active`
  (misconfigured or decommissioned devices still sending); share of `measurement_conflict`
  (a firmware bug re-sending different values for the same instant); and, most valuable,
  **ACTIVE devices that have gone silent** (no measurement for N times their reporting
  interval).
- *Probes:* `/_health` for liveness and `/_health/ready` for readiness; an external
  synthetic check that creates and reads back a test measurement.

**Detecting and alerting**

- Alert on symptoms users feel, using SLOs with burn-rate alerts (e.g. 99.9 % of ingestions
  succeed; ingest p99 under 500 ms) rather than on every CPU spike.
- Cause-based alerts for things that always precede an incident: database connections near
  the limit, replication lag, disk above 80 %, lock waits, a growing 5xx rate.
- Route by severity through Alertmanager: page the on-call engineer for SLO burn and
  database trouble, Slack for warnings (silent devices, conflict rate). Every alert links to
  a runbook and to the dashboard and traces for the affected route.

## Code quality and testing strategy

- **Tooling (pre-commit and CI):** black, flake8 (+ bugbear, comprehensions), pyupgrade,
  reorder-python-imports, autoflake, strict mypy, plus whitespace/YAML hooks. CI runs
  pre-commit and the test suite against a PostgreSQL service container.
- **Testing:** tests exercise the public HTTP API, status codes and bodies, since that is
  the contract clients rely on; plus a database test module proving that constraints hold
  *even if the application were bypassed*. The riskiest parts (idempotency, locking, unique
  races) have dedicated concurrent tests against real PostgreSQL. A migration-drift test
  keeps models and migrations in sync.

## AI-assisted development

> **TODO before submitting:** this section must be your own account. The notes below state
> what can be said factually from how this solution was produced; complete or correct the
> rest so that it is true.

- **Tools used:** Claude (Anthropic), as a chat/coding assistant.
- **What I used it for:** reviewing my first submission against the brief, and porting the
  service from Django/DRF to FastAPI/SQLAlchemy/Alembic while keeping the project structure,
  tooling and test style.
- **Validation of the generated code:** the SQL behaviour that the design depends on
  (unique-constraint idempotency, 20 parallel identical inserts producing one row, the
  `FOR SHARE` lock delaying a concurrent status update, `ON DELETE RESTRICT`) was checked by
  hand against a real PostgreSQL 16. The Pydantic validation rules were exercised in isolation.
  <!-- TODO: add the commands you ran and their results: pytest, mypy, pre-commit, docker compose up -->
- **An AI-generated suggestion I changed or rejected:**
  <!-- TODO: write one real example from your own review of the code. -->
- **AGENTS.md / skills used:**
  <!-- TODO: state which, if any (own or public) and what they do; otherwise "none". -->
