#!/bin/bash
# Sleepy scheduled-run wrapper — the entry point for launchd (macOS) and cron (Linux).
#
# Usage: scheduled_run.sh "<task>" <logname>
#   e.g. scheduled_run.sh "Tuesday waiver report" waivers
#
# Why a wrapper instead of a bare `claude -p`:
#   * An unattended `claude -p` auto-denies every tool call, so the run ends with
#     no Discord post and no error — the silent failure Sleepy forbids. The
#     wrapper runs claude with permission prompts turned off; Sleepy only reads
#     the public Sleeper API and writes to Discord and $SLEEPY_HOME.
#   * launchd and cron start with almost no PATH, so `claude`, `jq`, `python3`
#     would not be found.
#   * Output is appended to $SLEEPY_HOME/logs/<logname>.log, and if claude itself
#     exits non-zero a Discord alert is posted (the "fail loudly" rule).
#
# Environment: SLEEPY_HOME (default ~/sleepy); SLEEPY_EXTRA_PATH to prepend
# directories if your claude/jq/python3 live somewhere unusual.
set -u

TASK="${1:?usage: scheduled_run.sh \"<task>\" <logname>}"
LOGNAME="${2:?usage: scheduled_run.sh \"<task>\" <logname>}"

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export HOME="${HOME:?HOME is not set}"
export SLEEPY_HOME="${SLEEPY_HOME:-$HOME/sleepy}"
export LANG="${LANG:-en_US.UTF-8}"

# Common install locations: native claude installer, Homebrew, nvm's newest node, python.org.
NVM_BIN=""
if [ -d "$HOME/.nvm/versions/node" ]; then
  NVM_BIN="$(ls -d "$HOME"/.nvm/versions/node/*/bin 2>/dev/null | sort -V | tail -1)"
fi
export PATH="${SLEEPY_EXTRA_PATH:+$SLEEPY_EXTRA_PATH:}$HOME/.local/bin:${NVM_BIN:+$NVM_BIN:}/Library/Frameworks/Python.framework/Versions/Current/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

LOG="$SLEEPY_HOME/logs/$LOGNAME.log"
mkdir -p "$SLEEPY_HOME/logs"
exec >> "$LOG" 2>&1
cd "$SLEEPY_HOME" || { echo "scheduled_run.sh: $SLEEPY_HOME missing — run onboarding"; exit 1; }

echo
echo "===== $(date '+%Y-%m-%d %H:%M:%S %Z')  Sleepy: $TASK ====="

if ! command -v claude >/dev/null 2>&1; then
  echo "scheduled_run.sh: 'claude' not on PATH ($PATH). Set SLEEPY_EXTRA_PATH."
  "$SKILL_DIR/scripts/notify.sh" "⚠️ Sleepy scheduled run **$TASK** could not start: claude not found on PATH. See ~/sleepy/logs/$LOGNAME.log" || true
  exit 127
fi

# Headless run; nobody is there to answer permission prompts, so they are off.
claude -p "Sleepy: $TASK" --dangerously-skip-permissions
STATUS=$?

echo "----- exit $STATUS at $(date '+%H:%M:%S') -----"

if [ "$STATUS" -ne 0 ]; then
  "$SKILL_DIR/scripts/notify.sh" \
    "⚠️ Sleepy scheduled run failed: **$TASK** (exit $STATUS). Check ~/sleepy/logs/$LOGNAME.log" \
    || echo "notify.sh also failed"
fi
exit "$STATUS"
