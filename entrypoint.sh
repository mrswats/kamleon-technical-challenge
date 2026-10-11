#!/usr/bin/env bash

set -exuo pipefail

main() {
    pg_isready -h "$DATABASE_HOST" -p "$DATABASE_PORT" -U postgres

    MODE=${MODE:-api}

    if [ "$MODE" = "api"]; then
        python -m manage migrate --settings kamleon.settings.production
        gunicorn "kamleon.wsgi:application"
    elif [ "$MODE" = "worker" ]; then
        python -m worker "$REDIS_URL" "$QUEUE"
    fi
}

main "$@"
