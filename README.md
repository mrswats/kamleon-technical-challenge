# Kamleon Technical Challenge

This repository contains my solution to the Kamleon Technical Challenge.

## Installation

Create a virtual Environment, install dependencies.

```console
virtualenv .venv -p python 3.14
source .venv/bin/activate
pip install -r test-requirements.txt
```

### Running locally

Development server:

```console
./manage.py migrate
./manage.py runserver
```

### Running Docker locally

```console
docker compose build
docker compose up -d
```

Then, the API server is accessible on `http://localhost:8000/`

### Running migrations

Running migrations is very easy. Run the migrations on SQLite, locally:

```console
./manage.py migrate
```

Running migrations with production like settings

```console
./manage.py migrate --settings kamleon.settings.production
```

## Tests

Using pytest for Tests, and getting a coverage report in terminal.

```console
python -m pytest --cov --cov-report term-missing
```

> [!NOTE]: Tests run in a SQLite in memory database for performance reasons. In
> production, the application runs with a PostgreSQL database instead. For
> example, using the docker compose will spin up a PostgreSQL database in a
> container.

## Formatting and Linting

Using pre-commit for linting and formatting

```console
pre-commit install
pre-commit run --all-files
```

## Data model

The data model is as follows:

![Data model](./img/models.png)

The data model follows the specification. We have a `Custumer` table which is
related to the `User` model, which contains the authorization data (`username`
and `password`). The `Customer` model also includes a `kid` field which is a
unique value for each row, and used to lookup customers during an API call in
the database.

Then, the `Device` model is related through a foreign key to the `Custumer`, so
a `Custumer` can have many `Devices`. This model, contains a `status` which
only accepts three values: `Active`, `Inactive` and `Faulted`. This field could
be expanded in the future more stats where needed. The `serial_number` is a
randomly generated on create and it is used as an ID for retriving data from
the API.

Finally, the measurement table, which contains the measurement data: `unit`,
`value`, `type`, `timestamp`. Also, every measurement is associated to a
`Device`. Additionally, a `measurement_hash` field is included so that we have
an easy way to check whether a measurement exists in the database, with an
index. This model also includes a `kid` field in the same way as in the
custumer model.

All the models contain a `created_at` and an `updated_at` fields that are
automatically created and updated when appropriate. The foreign keys are
configured so that no data is deleted when related rows are, so that we do not
lose any data.

Under the GDPR, when a customer is deleted, their personal data should be
erased or anonymized, unless we are legally required to retain some of it (for
example, invoices for tax purposes). Any data that must be retained should be
separated from the operational database, access to it should be restricted, and
it should be deleted once the legal retention period expires.

## API Design

The API Design is very straightforward: Two endpoints for customer: retrieving
and creating, two endpoints for devices: retrieving and creating, and a single
ingest endpoint. The ingestion ingestion endpoint is idempotent. However, the
idempotency is implemented with the `measurement_hash` field. So the hash is
calculated, and checked in the database whether it exists or not. The endpoint
will always return a `201` HTTP Status regardless the measurement already
exists or the device is Inactive.

The API Documentation can be accessed while running the server at
[http://localhost:8000/docs/](http://localhost:8000/docs/). The OpenAPI standard
is used and it includes `curl` examples there.

## Encryption and data communications protocols

In transit, all data should be transmitted through TLS, in the case of HTTP
through HTTPS so that the data in encrypted. If further levels were needed from
the business, it could be added on top og HTTP: Encrypt the body of the
request/response and decrypt it on the server/client.

## Authorization and Authentication

For authentication and authorization, there are a million and one methods to
accomplish that. The most popular one in my opinion would be JWT (Json Web
Tokens). JWT allows for stateless authorization seamlessly, and it is easy to
authenticate a user with it in different services.

This would also allow to identify the user and apply filters to the data, as
well as implement a permission system so that would allow certain users to do
certain actions.

## Performance considerations

Without any more information about the business needs, it is difficult to talk
about performance optimizations. But it would be easy to add database indexes
depending on access patterns, for example. Once deployed, it would be easy to
send some traffic on the service and analyze the hot paths so further studies
could be done in order to inform the optimization process.

In general, an Stateless REST API is easy to scale horizontally, so that more
requests can be handled per second. Furthermore, it would be interesting to
add a cache between the web server and the database, so we do not have to access
the database on every request for often accessed data.

Finally, one of the performance optimizations I have implemented, is the use of
a background job architecture so that the heavy load of looking up the
measurements and performing the insertion can be done outside the
request-response cycle and thus making the API much faster to respond. Any errors
derived from that can be studied and handled separately, if needed. This would
allow for the integtion endpoint to work much faster and not block the web server
freeing as well the client for being able to perform more tasks.

## Monitoring and Observability

There are many observability tools available. My favourite ones are using
sentry for error tracking and prometheus for basic application metrics.
Querying the metrics from grafana would allow us to have an overview of the
application, and setup alarms that would be able to alert us when the
application runs slower than usual, or when the worker queue is getting longer
than we would like, indicating a need for scaling.

## Code quality and maintainability

Linters and formatters are very important so that code is consistent all
throughout the codebase, and it allows us to not have to think about these
details while writing code, so that we can focus on the business logic.
Moreover, it allows us to avoid making mistakes in a way that is consistent.

My preferred stack for code quality tools start by flake8, pyupgrade and black.
All of these tools run in the pre-commit framework which allows us to run and
update versions of the tools seemlessly, and run them easily in CI to check
during pull request review.

## Testing strategy

The testing strategy for web applications is rather straightforward. It does
not make sense to test the internals, but rather to test the public endpoints
that are being called by the clients. In this case, tests were added for all
the endpoints checking both status codes and returned data. Additionally, tests
for some of the side effects and in particular the worker which while it's not
part of the public API, it is an important component of the business logic,
was tested thoroughly as well.

## What would I improve with more time

### Correctness and robustness

Broader tests. Integration tests for the full request cycle, edge cases
(invalid input, duplicate records, deleting an already-deleted customer), and a
coverage report in CI. Stricter validation and consistent errors. A single
error format across all endpoints, with clear status codes. Idempotency and
concurrency handling. Idempotency keys for create operations and transactions
or locking where concurrent updates could conflict.

### Data and GDPR

A proper erasure workflow. A deletion endpoint or job that anonymizes
identifying fields while keeping legally required records (e.g. invoices) in a
separate, access-restricted store with a defined retention period. Automated
retention. A scheduled task that purges retained data when its retention period
expires. Audit logging. A record of who accessed, changed, or deleted personal
data, without storing the personal data itself in the logs. Data export. An
endpoint for subject access and portability requests. Soft delete vs. hard
delete. A clear, documented policy for each model.

### Security

Stronger authentication and permissions. JWT or OAuth2, role-based permissions,
and per-object access checks. Rate limiting and throttling. DRF throttling at
minimum, plus protection at the gateway level. Secrets and configuration.
Environment-based settings, no secrets in the repo, and separate settings per
environment. Dependency scanning. Tools like pip-audit or Dependabot, plus a
security headers check.

### Performance and scalability

Query optimisation. Fix N+1 queries, add database indexes, and use
django-debug-toolbar or query logging to find them. Pagination and filtering.
Cursor-based pagination for large collections. Caching. Redis for frequently
read, rarely changed data. Production database. Move from SQLite to PostgreSQL
with connection pooling. Background jobs. Celery or RQ for slow or scheduled
work such as exports, emails, and retention clean-up. Load testing. Locust or
k6 to find real bottlenecks instead of guessing.

## AI Development

No AI assistence was used during the development of this challenge.

## On the choice of framework

The choice of using Django in this challenge was deliverate not only for
personal preference, but also for technical reasons. Django is a very mature
web framework with a wide community support. It means it is well tested, and a
lot of different libraries are built for and on top of django.

On the technical side of things, Django has been engineered to be loosely
coupled and tightly integrated which means that switching components of the
framework is easy, while the integration with the different components. This
means that the use of the ORM during the requests as well as the testing is
engineered together and it is trivially easy to write code that works
flawlessly without any issues.

In my experience, other frameworks along with ORMs do not have the luxury of
being tightly integrated and and thus the integration falls on the hands of the
developer. This might lead to performance degradation and other nasty surprises
long after which would then not easily to be solved.

It is also worth mentioning the Django Admin. The Django admin is a django app
built with django itself which is easily configured which allow superusers to
view the data in the database with q web interface instead of having to use SQL
to do so. Moreover, being it sucha a good tool, it also benefits of a lot of
customizability and packages with added features.

## Limitations

Django and Django REST Framework come with some known trade-offs:

### **Synchronous by default.**

Django supports async views, but much of the ecosystem,
including parts of the ORM and many third-party packages, still runs
synchronously under the hood. This is mitigated by the stateless design of the
endpoints: each request is independent, so the service can be scaled
horizontally by running multiple instances behind a load balancer.

### **ORM query patterns.**

As with any ORM, it is easy to introduce N+1 queries.
Django offers `select_related` and `prefetch_related` to address this, but queries
on performance-critical paths still need to be reviewed carefully, for example
with query logging or django-debug-toolbar.

### **Serialization speed.**

DRF’s default serializers are slow for large result sets.
If this becomes a bottleneck, there are faster alternatives, such as serpy,
msgspec, or Django Ninja (which uses Pydantic), or serializing read-only
endpoints directly from .values() querysets.
