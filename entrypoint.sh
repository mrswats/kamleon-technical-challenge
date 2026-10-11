#!/usr/bin/env bash

set -euo pipefail

main() {
    case "${MODE:-api}" in
        api)
            # Apply pending migrations, then serve. With several replicas, run the
            # `migrate` mode once as a separate job instead.
            alembic upgrade head
            exec uvicorn --host 0.0.0.0 --port 8000 "kamleon.asgi:app"
            ;;
        migrate)
            exec alembic upgrade head
            ;;
        *)
            echo "Unknown MODE: ${MODE}. Expected 'api' or 'migrate'." >&2
            exit 64
            ;;
    esac
}

main "$@"
