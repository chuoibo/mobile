#!/usr/bin/env bash
# Keep handing an agent its work until the agent can actually do it.
#
# Codex ran out of quota three times in one session. Each time the work stalled
# until somebody noticed and relaunched by hand. Noticing is not the scarce
# resource here, so this waits instead.
#
# The idea, and the reason this replaces `codex-autolaunch.sh`:
#
#   A cheap probe is not proof of usable quota. Asking for a one-word answer
#   costs almost nothing and succeeds even when the budget is nearly gone --
#   so a waiter that probes cheaply and then launches the real task can
#   report "quota is back" and hand over a job that immediately dies.
#
# That was Codex's observation about its own failure mode, and it was right
# about a waiter I had already written and was already using. So THE REAL TASK
# IS THE PROBE. `agent_supervisor.py` exits 2 on a provider refusal it cannot
# retry -- quota, auth, a denied permission -- and that exit code is the only
# honest signal that the budget is still closed.
#
#   scripts/agent_relaunch.sh codex /path/to/prompt.md [minutes-between-tries]
#
# Runs in the foreground; background it yourself. Every attempt is logged, so
# a run that never got started leaves the same trail as one that did.

set -uo pipefail

AGENT="${1:?need an agent name: codex or agy}"
PROMPT_FILE="${2:?need a prompt file}"
GAP_MINUTES="${3:-10}"

HARNESS="${AGENT_HARNESS:-$HOME/agent-harness}/agent_supervisor.py"
REPO="${CODEX_REPO:-$HOME/codex-repo}"
MIRROR="${PRODUCT_REPO:-$HOME/mobile}"

if [[ ! -f "$HARNESS" ]]; then
  echo "relaunch: khong thay $HARNESS" >&2
  echo "relaunch: cai ra ngoai cay lam viec truoc — doi nhanh git se lam no bien mat" >&2
  exit 1
fi

for attempt in $(seq 1 12); do
  echo "relaunch: lan $attempt cho $AGENT luc $(date +%H:%M)"

  if [[ "$AGENT" == "codex" ]]; then
    python3 "$HARNESS" codex \
      --prompt-file "$PROMPT_FILE" --cwd "$REPO" \
      --timeout 2400 --max-restarts 3 --checkpoint 60 \
      --mirror "$MIRROR" --push origin
  else
    python3 "$HARNESS" agy \
      --prompt-file "$PROMPT_FILE" --out-dir "${AGY_OUT:-/tmp/agy-run}" \
      --print-timeout 16m --timeout 1200 --max-restarts 2 --checkpoint 45
  fi
  status=$?

  # 2 is the supervisor's "the provider refused and retrying cannot help".
  # Anything else means the agent got to work, well or badly, and a waiter has
  # no business relaunching on top of that.
  if [[ $status -ne 2 ]]; then
    echo "relaunch: $AGENT da lam viec (exit=$status), dung cho"
    exit $status
  fi

  echo "relaunch: van bi tu choi, cho $GAP_MINUTES phut"
  sleep $((GAP_MINUTES * 60))
done

echo "relaunch: ALERT $AGENT bi tu choi suot 12 lan. Can nguoi vao xem." >&2
exit 1
