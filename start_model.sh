#!/bin/sh
set -eu
cd "$(dirname "$0")"
exec python3 model/model_api.py
