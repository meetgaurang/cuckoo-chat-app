#!/bin/sh
# Entrypoint for AWS Lambda (zip deploy + AWS Lambda Web Adapter).
#
# The LWA layer's /opt/bootstrap (wired in via AWS_LAMBDA_EXEC_WRAPPER) execs
# this script, then proxies each Lambda invocation to the HTTP server we start
# here. We run the exact same uvicorn command used locally, so prod and dev
# share one runtime — and SSE streaming is preserved via response streaming.
# Invoke uvicorn as a module: `pip install -t` lays packages flat next to this
# script, so a bare `uvicorn` would resolve to the package *directory*. `-m`
# avoids that and doesn't rely on the console script being on PATH.
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}"
