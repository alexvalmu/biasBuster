#!/bin/sh
set -e
# Migrations run from a single place (the api in dev, a one-off job in prod) to avoid races.
if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
  alembic upgrade head
fi
exec "$@"
