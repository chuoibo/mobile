#!/usr/bin/env bash
# Wait for Codex's quota window, then hand it the queue without being asked.
#
# Codex has run out of quota three times in one session. Each time the work
# stalled until somebody noticed and re-launched it by hand. The reset time is
# printed in the failure message, so waiting for it is something a machine can
# do; a person noticing is not the scarce resource here.
#
# Usage: scripts/codex-autolaunch.sh HH:MM /path/to/prompt-file

set -uo pipefail

TARGET="${1:?need HH:MM}"
PROMPT_FILE="${2:?need a prompt file}"
COMPANION="$HOME/.claude/plugins/cache/openai-codex/codex/1.0.6/scripts/codex-companion.mjs"
REPO="${CODEX_REPO:-$HOME/codex-repo}"

echo "codex-autolaunch: chờ tới $TARGET"
while [[ "$(date +%H%M)" < "${TARGET/:/}" ]]; do sleep 60; done

# One cheap probe is not proof of usable quota: a single-line answer costs
# almost nothing and succeeds even when the budget is nearly gone. So the real
# task is the probe, and a failure is retried rather than reported as success.
for attempt in 1 2 3 4 5 6; do
  echo "codex-autolaunch: lần $attempt"
  if node "$COMPANION" task --write --cwd "$REPO" --prompt-file "$PROMPT_FILE" >/dev/null 2>&1; then
    echo "codex-autolaunch: Codex đã nhận việc"
    exit 0
  fi
  echo "codex-autolaunch: chưa được, chờ 10 phút"
  sleep 600
done
echo "codex-autolaunch: sáu lần đều hỏng, cần người xem"
