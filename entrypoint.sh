#!/usr/bin/env bash

set -euo pipefail

main() {
    ./manage.py runserver --settings kamleon.settings.production
    gunicorn "kamleon.wsgi:application"
}

main "$@"
