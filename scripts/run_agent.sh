#!/usr/bin/env bash
# Run one Sleepy prompt through a supported coding agent.
#
# Provider selection, in order:
#   1. SLEEPY_AGENT_RUNNER: executable that accepts the prompt as its only arg
#   2. SLEEPY_AGENT: claude, codex/openai, or auto
#   3. config.json agent.provider
#   4. auto (Claude first for backward compatibility, then Codex)
#
# SLEEPY_AGENT_MODEL or config.json agent.model optionally pins a model.
set -euo pipefail

PROMPT="${1:?usage: run_agent.sh \"<prompt>\"}"
SLEEPY_DATA_HOME="${SLEEPY_HOME:-${HOME:?HOME is not set}/sleepy}"
CONFIG="$SLEEPY_DATA_HOME/config.json"

config_value() {
  local expression="$1"
  if [ -f "$CONFIG" ] && command -v jq >/dev/null 2>&1; then
    jq -r "$expression // empty" "$CONFIG"
  fi
}

run_custom() {
  local runner="$1"
  if [ ! -x "$runner" ]; then
    echo "run_agent.sh: SLEEPY_AGENT_RUNNER is not executable: $runner" >&2
    exit 126
  fi
  exec "$runner" "$PROMPT"
}

if [ -n "${SLEEPY_AGENT_RUNNER:-}" ]; then
  run_custom "$SLEEPY_AGENT_RUNNER"
fi

PROVIDER="${SLEEPY_AGENT:-$(config_value '.agent.provider')}"
PROVIDER="${PROVIDER:-auto}"
MODEL="${SLEEPY_AGENT_MODEL:-$(config_value '.agent.model')}"

if [ "$PROVIDER" = "auto" ]; then
  if command -v claude >/dev/null 2>&1; then
    PROVIDER="claude"
  elif command -v codex >/dev/null 2>&1; then
    PROVIDER="codex"
  else
    echo "run_agent.sh: neither 'claude' nor 'codex' is on PATH; set SLEEPY_AGENT or SLEEPY_AGENT_RUNNER" >&2
    exit 127
  fi
fi

case "$PROVIDER" in
  claude)
    command -v claude >/dev/null 2>&1 || {
      echo "run_agent.sh: provider is claude, but 'claude' is not on PATH" >&2
      exit 127
    }
    args=(-p "$PROMPT" --dangerously-skip-permissions)
    [ -z "$MODEL" ] || args+=(--model "$MODEL")
    exec claude "${args[@]}"
    ;;
  codex|openai)
    command -v codex >/dev/null 2>&1 || {
      echo "run_agent.sh: provider is $PROVIDER, but 'codex' is not on PATH" >&2
      exit 127
    }
    # Scheduled analysis only needs the Sleepy data workspace plus outbound
    # access to the public Sleeper API and web sources. Keep Codex sandboxed.
    args=(exec --skip-git-repo-check --sandbox workspace-write --ask-for-approval never
          -c sandbox_workspace_write.network_access=true)
    [ -z "$MODEL" ] || args+=(--model "$MODEL")
    args+=("$PROMPT")
    exec codex "${args[@]}"
    ;;
  *)
    echo "run_agent.sh: unsupported provider '$PROVIDER' (expected auto, claude, codex/openai, or SLEEPY_AGENT_RUNNER)" >&2
    exit 2
    ;;
esac
