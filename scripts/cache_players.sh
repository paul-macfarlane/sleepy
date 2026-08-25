#!/usr/bin/env bash
# Fetch/refresh the NFL player dump (~5MB) into ~/sleepy/cache/players.json.
# Skips download if cache is under 7 days old (pass --force to override).
set -euo pipefail
HOME_DIR="${SLEEPY_HOME:-$HOME/sleepy}"
CACHE="$HOME_DIR/cache/players.json"
mkdir -p "$HOME_DIR/cache"
if [ -f "$CACHE" ] && [ "${1:-}" != "--force" ]; then
  mtime=$(stat -c %Y "$CACHE" 2>/dev/null || stat -f %m "$CACHE")
  age_days=$(( ( $(date +%s) - mtime ) / 86400 ))
  if [ "$age_days" -lt 7 ]; then echo "cache fresh (${age_days}d old): $CACHE"; exit 0; fi
fi
curl -sf --max-time 120 "https://api.sleeper.app/v1/players/nfl" -o "$CACHE.tmp"
jq -e 'type == "object"' "$CACHE.tmp" > /dev/null  # sanity check
mv "$CACHE.tmp" "$CACHE"
echo "cached $(jq 'length' "$CACHE") players -> $CACHE"
