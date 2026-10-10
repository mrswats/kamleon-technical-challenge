#!/usr/bin/env bash

set -exuo pipefail

main() {
    pg_isready -h $DATABASE_HOST -p 5432 -U postgres
    python -m manage migrate --settings kamleon.settings.production
    gunicorn "kamleon.wsgi:application"
}

main "$@"
