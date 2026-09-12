#!/bin/bash
# Sleepy scheduled-run wrapper — the entry point for launchd (macOS) and cron (Linux).
#
# Usage: scheduled_run.sh "<task>" <logname>
#   e.g. scheduled_run.sh "Tuesday waiver report" waivers
#
# Why a wrapper instead of calling an agent CLI directly:
#   * Unattended agents need provider-specific non-interactive and permission
#     flags. scripts/run_agent.sh owns those differences.
#   * launchd and cron start with almost no PATH, so the agent CLI, jq, python3,
#     and other dependencies might not be found.
#   * Output is appended to $SLEEPY_HOME/logs/<logname>.log, and if the agent
#     exits non-zero a Discord alert is posted (the "fail loudly" rule).
#
# Environment: SLEEPY_HOME (default ~/sleepy); SLEEPY_AGENT selects claude,
# codex/openai, or auto; SLEEPY_AGENT_RUNNER supplies another provider adapter;
# SLEEPY_EXTRA_PATH prepends directories for locally installed binaries.
set -u

TASK="${1:?usage: scheduled_run.sh \"<task>\" <logname>}"
LOGNAME="${2:?usage: scheduled_run.sh \"<task>\" <logname>}"

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USER_HOME="${HOME:?HOME is not set}"
export SLEEPY_HOME="${SLEEPY_HOME:-$USER_HOME/sleepy}"
export LANG="${LANG:-en_US.UTF-8}"

# Common install locations: Codex desktop app, native agent installers, Homebrew,
# nvm's newest node, and python.org.
NVM_BIN=""
if [ -d "$USER_HOME/.nvm/versions/node" ]; then
  NVM_BIN="$(ls -d "$USER_HOME"/.nvm/versions/node/*/bin 2>/dev/null | sort -V | tail -1)"
fi
CODEX_APP_BIN=""
if [ -x "/Applications/ChatGPT.app/Contents/Resources/codex" ]; then
  CODEX_APP_BIN="/Applications/ChatGPT.app/Contents/Resources"
fi
export PATH="${SLEEPY_EXTRA_PATH:+$SLEEPY_EXTRA_PATH:}${CODEX_APP_BIN:+$CODEX_APP_BIN:}$USER_HOME/.local/bin:${NVM_BIN:+$NVM_BIN:}/Library/Frameworks/Python.framework/Versions/Current/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

LOG="$SLEEPY_HOME/logs/$LOGNAME.log"
mkdir -p "$SLEEPY_HOME/logs"
exec >> "$LOG" 2>&1
cd "$SLEEPY_HOME" || { echo "scheduled_run.sh: $SLEEPY_HOME missing — run onboarding"; exit 1; }

echo
echo "===== $(date '+%Y-%m-%d %H:%M:%S %Z')  Sleepy: $TASK ====="

# The adapter supplies the selected provider's non-interactive invocation.
"$SKILL_DIR/scripts/run_agent.sh" "Sleepy: $TASK"
STATUS=$?

echo "----- exit $STATUS at $(date '+%H:%M:%S') -----"

if [ "$STATUS" -ne 0 ]; then
  "$SKILL_DIR/scripts/notify.sh" \
    "⚠️ Sleepy scheduled run failed: **$TASK** (exit $STATUS). Check ~/sleepy/logs/$LOGNAME.log" \
    || echo "notify.sh also failed"
fi
exit "$STATUS"
