#!/usr/bin/env bash
set -euo pipefail
: "${SLEEPY_TEST_OUTPUT:?SLEEPY_TEST_OUTPUT is required}"
printf '%s\n' "$0" "$@" > "$SLEEPY_TEST_OUTPUT"
exit "${SLEEPY_TEST_EXIT:-0}"
