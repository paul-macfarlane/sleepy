#!/usr/bin/env bash
set -euo pipefail

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$TEST_DIR/.." && pwd)"
TEST_TMP="$(mktemp -d "${TMPDIR:-/tmp}/sleepy-agent-test.XXXXXX")"
trap 'rm -rf "$TEST_TMP"' EXIT

mkdir -p "$TEST_TMP/bin" "$TEST_TMP/home"
ln -s "$TEST_DIR/fixtures/fake_agent.sh" "$TEST_TMP/bin/claude"
ln -s "$TEST_DIR/fixtures/fake_agent.sh" "$TEST_TMP/bin/codex"
ln -s "$TEST_DIR/fixtures/fake_agent.sh" "$TEST_TMP/bin/custom-agent"

export PATH="$TEST_TMP/bin:$PATH"
export SLEEPY_HOME="$TEST_TMP/home"
export SLEEPY_TEST_OUTPUT="$TEST_TMP/args"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

assert_line() {
  local expected="$1"
  rg -Fx -- "$expected" "$SLEEPY_TEST_OUTPUT" >/dev/null || fail "missing argument: $expected"
}

# Auto preserves existing behavior by preferring Claude when both are installed.
SLEEPY_AGENT=auto "$REPO_DIR/scripts/run_agent.sh" "Sleepy: auto test"
head -1 "$SLEEPY_TEST_OUTPUT" | rg -q '/claude$' || fail "auto did not choose Claude"
assert_line "-p"
assert_line "Sleepy: auto test"
assert_line "--dangerously-skip-permissions"

# Config can select Codex and pin a model without an environment override.
cp "$TEST_DIR/fixtures/codex_config.json" "$SLEEPY_HOME/config.json"
env -u SLEEPY_AGENT -u SLEEPY_AGENT_MODEL "$REPO_DIR/scripts/run_agent.sh" "Sleepy: codex test"
head -1 "$SLEEPY_TEST_OUTPUT" | rg -q '/codex$' || fail "config did not choose Codex"
assert_line "exec"
assert_line "--skip-git-repo-check"
assert_line "--sandbox"
assert_line "workspace-write"
assert_line "--ask-for-approval"
assert_line "never"
assert_line "sandbox_workspace_write.network_access=true"
assert_line "--model"
assert_line "gpt-test"
assert_line "Sleepy: codex test"

# Environment selection wins over config.
SLEEPY_AGENT=claude SLEEPY_AGENT_MODEL=claude-test "$REPO_DIR/scripts/run_agent.sh" "Sleepy: override test"
head -1 "$SLEEPY_TEST_OUTPUT" | rg -q '/claude$' || fail "environment did not override config"
assert_line "claude-test"

# A custom adapter is the highest-priority, provider-neutral extension point.
SLEEPY_AGENT=unsupported SLEEPY_AGENT_RUNNER="$TEST_TMP/bin/custom-agent" \
  "$REPO_DIR/scripts/run_agent.sh" "Sleepy: custom test"
head -1 "$SLEEPY_TEST_OUTPUT" | rg -q '/custom-agent$' || fail "custom adapter was not used"
assert_line "Sleepy: custom test"

# The scheduled wrapper delegates through the same adapter and logs the run.
SLEEPY_AGENT_RUNNER="$TEST_TMP/bin/custom-agent" SLEEPY_EXTRA_PATH="$TEST_TMP/bin" \
  "$REPO_DIR/scripts/scheduled_run.sh" "scheduled test" scheduled-test
assert_line "Sleepy: scheduled test"
rg -q -- '----- exit 0' "$SLEEPY_HOME/logs/scheduled-test.log" || fail "scheduled run did not finish cleanly"

echo "run_agent tests passed"
