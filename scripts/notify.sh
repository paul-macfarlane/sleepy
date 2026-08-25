#!/usr/bin/env bash
# Post a message to the user's Discord webhook. Usage: notify.sh "message"
set -euo pipefail
CONFIG="${SLEEPY_HOME:-$HOME/sleepy}/config.json"
[ -f "$CONFIG" ] || { echo "notify.sh: $CONFIG not found — run onboarding" >&2; exit 1; }
WEBHOOK=$(jq -r '.discord_webhook // empty' "$CONFIG")
[ -n "$WEBHOOK" ] || { echo "notify.sh: discord_webhook missing in config" >&2; exit 1; }
[ $# -ge 1 ] || { echo "usage: notify.sh \"message\"" >&2; exit 2; }
jq -n --arg c "$1" '{content:$c}' | curl -sf -X POST -H "Content-Type: application/json" -d @- "$WEBHOOK" > /dev/null
echo "sent"
