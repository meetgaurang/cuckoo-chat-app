#!/bin/sh
# Local dev entrypoint: runs the backend with autoreload on port 8000.
# Reads config from backend/.env. (Prod uses run.sh under the Lambda Web
# Adapter — no --reload, port 8080.)
cd "$(dirname "$0")"

if [ -x .venv/bin/uvicorn ]; then
  UVICORN=.venv/bin/uvicorn       # prefer the project venv
else
  UVICORN=uvicorn                 # fall back to whatever's on PATH
fi

exec "$UVICORN" app.main:app --reload --host 127.0.0.1 --port "${PORT:-8000}"
