#!/usr/bin/env bash
# GET a Sleeper API path. Usage: sleeper.sh /league/12345
set -euo pipefail
BASE="https://api.sleeper.app/v1"
[ $# -eq 1 ] || { echo "usage: sleeper.sh /path" >&2; exit 2; }
curl -sf --max-time 20 "${BASE}${1}"
