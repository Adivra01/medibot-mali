#!/bin/sh
set -eu
cd "$(dirname "$0")"

python3 model/model_api.py &
MODEL_PID=$!
cleanup() {
  kill "$APP_PID" "$MODEL_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

python3 site/server.py &
APP_PID=$!
wait "$APP_PID"
