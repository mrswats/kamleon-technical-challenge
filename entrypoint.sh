#!/usr/bin/env bash

set -exuo pipefail

main() {
    pg_isready -h "$DATABASE_HOST" -p "$DATABASE_PORT" -U postgres

    MODE=${MODE:-api}

    echo $MODE

    if [ "$MODE" -eq "api"]; then
        python -m manage migrate --settings kamleon.settings.production
        gunicorn "kamleon.wsgi:application"
    elif [ "$MODE" -eq "worker" ]; then
        rq worker -u "$REDIS_URL" $DEFAULT_QUEUE"
    fi
}

main "$@"
