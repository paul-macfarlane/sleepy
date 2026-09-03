#!/bin/bash
# Install Sleepy's season-mode launchd agents (macOS).
#
#   install.sh            render the plist templates for this machine, load them
#   install.sh --test     same, then fire a one-off smoke test that posts to Discord
#   install.sh --uninstall  unload and remove the agents
#
# Re-run after editing a template in this directory (e.g. to change a time).
# Schedules use local time; a job missed while the Mac was asleep runs at wake,
# one missed while it was shut down is skipped.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$HERE/../.." && pwd)"
WRAPPER="$SKILL_DIR/scripts/scheduled_run.sh"
SLEEPY_HOME="${SLEEPY_HOME:-$HOME/sleepy}"
LOGDIR="$SLEEPY_HOME/logs"
DST="$HOME/Library/LaunchAgents"
DOMAIN="gui/$(id -u)"
JOBS="waivers lineups-thu lineups-sun"

render() {  # render <job> -> writes $DST/com.sleepy.<job>.plist
  sed -e "s|__WRAPPER__|$WRAPPER|g" -e "s|__LOGDIR__|$LOGDIR|g" \
    "$HERE/com.sleepy.$1.plist" > "$DST/com.sleepy.$1.plist"
}
load()   { launchctl bootout "$DOMAIN/com.sleepy.$1" 2>/dev/null || true; launchctl bootstrap "$DOMAIN" "$DST/com.sleepy.$1.plist"; }
unload() { launchctl bootout "$DOMAIN/com.sleepy.$1" 2>/dev/null || true; rm -f "$DST/com.sleepy.$1.plist"; }

if [ "${1:-}" = "--uninstall" ]; then
  for j in $JOBS smoketest; do unload "$j"; done
  echo "Sleepy launchd agents removed."
  exit 0
fi

[ -f "$SLEEPY_HOME/config.json" ] || { echo "$SLEEPY_HOME/config.json not found — run 'Sleepy: onboard me' first." >&2; exit 1; }
[ -x "$WRAPPER" ] || chmod +x "$WRAPPER"
mkdir -p "$DST" "$LOGDIR"

for j in $JOBS; do render "$j"; load "$j"; echo "loaded com.sleepy.$j"; done

if crontab -l 2>/dev/null | grep -q "Sleepy"; then
  echo
  echo "NOTE: your crontab still has Sleepy entries — remove them (crontab -e) or runs will double-post."
fi

echo
launchctl list | grep com.sleepy || true

if [ "${1:-}" = "--test" ]; then
  echo
  echo "Firing smoke test — expect a Discord post within a minute or two..."
  render smoketest; load smoketest
  : > "$LOGDIR/smoketest.log"
  launchctl kickstart "$DOMAIN/com.sleepy.smoketest"
  for _ in $(seq 1 36); do  # up to 3 minutes
    grep -q -- "----- exit" "$LOGDIR/smoketest.log" 2>/dev/null && break
    sleep 5
  done
  if grep -q -- "----- exit 0" "$LOGDIR/smoketest.log" 2>/dev/null; then
    echo "Smoke test passed (see $LOGDIR/smoketest.log)."
  else
    echo "Smoke test did not finish cleanly — check $LOGDIR/smoketest.log and $LOGDIR/launchd.log:"
    tail -20 "$LOGDIR/smoketest.log" 2>/dev/null || true
  fi
  unload smoketest
fi
