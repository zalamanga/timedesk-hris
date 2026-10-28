#!/bin/sh
set -eu
python -m app.cli init-db
if [ "${APP_SEED_DEMO:-false}" = "true" ]; then
  python -m app.cli seed-demo
fi
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
