#!/usr/bin/env bash
#
# Run the live Gemini tier: `services/api/tests/live`, against the real model,
# over the real network, with the real key.
#
# ## Why this exists
#
# "AI là THẬT" is the first of the two things settled with the leader, and the
# demo path is AI end to end -- chat suggests a place, the camera reads a bill,
# the model names every item, the split follows. `services/api/tests/live` is
# 34 cases and it is the ONLY tier that touches a real model. Every other test
# of those features runs against a fake reader and a fake suggester, which
# proves orchestration and proves nothing about the model.
#
# It ran nowhere. Measured on 2026-08-29 on this branch's merge base:
#
#   .github/workflows/*.yml          no job, no step, no mention of Gemini
#   scripts/gate.sh                  no stage
#   Makefile                         no target
#   python3 -m pytest services/api/tests tests -q
#                                    1278 passed, 285 skipped
#                                      240  set MOBILE_TEST_DATABASE_URL ...   <- covered by the postgres stage
#                                       23  live Gemini tier: needs GEMINI_API_KEY and MOBILE_REQUIRE_GEMINI_TESTS=1
#                                       10  live Gemini test is opt-in: set MOBILE_LIVE_GEMINI=1
#
# Those last 33 are the product's headline claim, and nothing sets either
# variable, so the tier has only ever skipped. A skip is not a pass -- CLAUDE.md
# says it outright, and this is the same shape that already bit this repository
# three times: a detector with no browser returning `[]` and exit 0, a postgres
# tier reporting 147 skips that read as green, and a migration that switched the
# app loggers off so "the secret never reached the log" was true of an empty log.
#
# What that costs on the day it matters: a revoked key, an exhausted quota or a
# retired model name changes nothing any gate can see. Every stage stays green
# and the hero path dies in front of the leader, as `503
# receipt_reader_not_configured` or a 422 that looks exactly like a blurry photo.
# `scripts/check_ai_key.sh` already carries that scar -- it exists because the
# key never reached the container and the only symptom was the feature failing
# like somebody else's mistake.
#
# ## Why this refuses to be quiet
#
# The tier's own guard cannot be trusted to make itself run:
#
#   @pytest.mark.skipif(not os.environ.get("GEMINI_API_KEY")
#                       or os.environ.get("MOBILE_REQUIRE_GEMINI_TESTS") != "1", ...)
#
# `MOBILE_REQUIRE_GEMINI_TESTS` does not require anything. With no key the
# cases skip even when it is set to 1 -- unlike the postgres tier, where
# `MOBILE_REQUIRE_POSTGRES_TESTS=1` turns the conftest's skip into a failure.
# So exporting the flag and trusting the exit code would reproduce the defect
# inside the fix. This script therefore counts what actually ran, from the JUnit
# report, and treats a skip as a failure: with a key present and both flags set,
# a skipped case means something silently stopped the tier, and that is the one
# answer that must never read as green. `test_gemini_receipt.py` skips its ten
# cases when the mockup it crops is not on the machine -- a real hole, invisible
# in a plain `pytest` exit code, and loud here.
#
# ## The key
#
# Resolved, never printed, and stripped out of the tier's output before it
# reaches the screen -- lanes paste gate output into pull requests, and the one
# rule with no exceptions is that this value never enters Git or a log.
#
# Order: the shell wins, then MOBILE_ENV_FILE, then `.env` at the repo root,
# then `.env` in the main worktree this one was created from. That last hop is
# why the resolution lives here rather than in `scripts/env_value.sh`: every
# lane works in a linked worktree, `.env` exists only in the checkout they were
# all cut from, so env_value.sh answers "no key" in all five of them. It is
# right to do that -- it answers for Compose, and Compose reads `.env` from the
# compose file's own directory, so agreeing with it is the whole point of that
# file. pytest is not Compose. Widening env_value.sh would make it disagree with
# the tool it exists to agree with, which is the bug it was written to fix,
# pointed the other way. The dotenv parsing is still not duplicated: this asks
# the main worktree's own copy of env_value.sh, so there is one parser.
#
# ## What this does NOT prove
#
# It proves a real model answered and that its answers still satisfy the
# assertions. It does not prove the answers are good -- a model that got worse
# but stayed inside the assertions passes here. It does not prove the phone app
# reaches the model: it calls the reader and the suggester directly, not through
# a running API, so a broken route or a container missing the key is out of
# scope (that is `scripts/check_ai_key.sh` and the docker stage). And it is a
# network test: a rate limit reads as a failure, correctly but unhelpfully. The
# tier prints which case failed, so the two are told apart by reading it.
#
# Cost, measured 2026-08-29: 34 cases, 33 passed and 1 xfailed, 185.73s, one
# live call per module-scoped fixture plus one per case that needs its own.
# That is real money and a real quota -- the same quota the demo runs on.
#
# Usage:
#   scripts/gemini_tier.sh                    the whole tier
#   scripts/gemini_tier.sh -k receipt         extra arguments go to pytest
#   scripts/gemini_tier.sh --check            is a key resolvable? print nothing else
#
# Exit codes: 0 the tier ran and passed, 1 it ran and failed (or went quiet),
# 2 it could not be run at all -- no key anywhere.

set -uo pipefail

cd "$(dirname "$0")/.." || exit 2
REPO_ROOT="$PWD"

CHECK_ONLY=0
PYTEST_ARGS=()

while [ $# -gt 0 ]; do
  case "$1" in
    --check) CHECK_ONLY=1 ;;
    -h|--help) sed -n '2,95p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) PYTEST_ARGS+=("$1") ;;
  esac
  shift
done

# --- the key --------------------------------------------------------------

# Reads `.env` next to a given checkout by asking THAT checkout's env_value.sh,
# so there is exactly one dotenv parser in the repository. GEMINI_API_KEY is
# unset for the call because env_value.sh gives the shell precedence -- which is
# correct for its own job and would make it hand back the empty value we are
# trying to replace.
key_from_checkout() {
  local root="$1"
  [ -r "$root/.env" ] || return 0
  [ -x "$root/scripts/env_value.sh" ] || [ -r "$root/scripts/env_value.sh" ] || return 0
  env -u GEMINI_API_KEY sh "$root/scripts/env_value.sh" GEMINI_API_KEY 2>/dev/null
}

# The checkout this worktree was created from, or empty when this IS that
# checkout. `--git-common-dir` is the shared `.git` of the whole worktree set;
# its parent is the main working tree.
main_worktree() {
  local common
  common="$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" || return 0
  [ -n "$common" ] || return 0
  local root="${common%/.git}"
  [ "$root" != "$common" ] || return 0
  [ "$root" != "$REPO_ROOT" ] || return 0
  printf '%s' "$root"
}

KEY=""
KEY_FROM=""

if [ -n "${GEMINI_API_KEY:-}" ]; then
  KEY="$GEMINI_API_KEY"; KEY_FROM="biến môi trường"
fi

if [ -z "$KEY" ] && [ -n "${MOBILE_ENV_FILE:-}" ] && [ -r "${MOBILE_ENV_FILE}" ]; then
  # A file named on purpose. Parsed by the same env_value.sh, by pointing it at
  # the directory that file sits in.
  env_dir="$(cd "$(dirname -- "$MOBILE_ENV_FILE")" && pwd)"
  if [ "$(basename -- "$MOBILE_ENV_FILE")" = ".env" ]; then
    KEY="$(key_from_checkout "$env_dir")"
    [ -n "$KEY" ] && KEY_FROM="MOBILE_ENV_FILE"
  else
    echo "MOBILE_ENV_FILE phải trỏ tới một file tên '.env' (env_value.sh chỉ đọc tên đó)" >&2
  fi
fi

if [ -z "$KEY" ]; then
  KEY="$(key_from_checkout "$REPO_ROOT")"
  [ -n "$KEY" ] && KEY_FROM=".env ở gốc cây làm việc này"
fi

if [ -z "$KEY" ]; then
  MAIN="$(main_worktree)"
  if [ -n "$MAIN" ]; then
    KEY="$(key_from_checkout "$MAIN")"
    [ -n "$KEY" ] && KEY_FROM=".env ở cây chính ($MAIN)"
  fi
fi

if [ -z "$KEY" ]; then
  # Names the variable, never a value, and says the two places that would fix
  # it. Exit 2 is "could not run", not "ran and failed" -- scripts/gate.sh reads
  # the difference and reports BỎ QUA with this reason rather than a red stage.
  echo "không tìm được GEMINI_API_KEY — tầng AI sống không chạy được." >&2
  echo "Đặt nó vào .env ở gốc repo, hoặc xuất ra shell, hoặc trỏ MOBILE_ENV_FILE tới file .env cần dùng." >&2
  exit 2
fi

if [ "$CHECK_ONLY" -eq 1 ]; then
  echo "GEMINI_API_KEY: có (nguồn: $KEY_FROM)"
  exit 0
fi

# --- run ------------------------------------------------------------------

REPORT_DIR="$(mktemp -d)"
trap 'rm -rf "$REPORT_DIR"' EXIT INT TERM
REPORT="$REPORT_DIR/live.xml"

# Everything this script prints goes through here first.
#
# Not decoration: pytest quotes the values it was given back into skip reasons,
# assertion messages and tracebacks, and lanes paste gate output straight into
# pull requests. The key reaches the filter through the environment and never
# on a command line, where `ps` would show it to every process on a machine
# running five lanes at once.
redact() {
  GEMINI_API_KEY="$KEY" python3 -c '
import os, sys
key = os.environ.get("GEMINI_API_KEY") or ""
for line in sys.stdin:
    sys.stdout.write(line.replace(key, "<GEMINI_API_KEY>") if key else line)
'
}

echo "Khoá đọc từ: $KEY_FROM"
echo "--- pytest tests/live (MOBILE_REQUIRE_GEMINI_TESTS=1, MOBILE_LIVE_GEMINI=1)"

# Both flags, because the tier is guarded by two different ones: the places
# suite reads MOBILE_REQUIRE_GEMINI_TESTS, the receipt suite reads
# MOBILE_LIVE_GEMINI. Setting one runs half the tier and looks complete.
#
# The output is filtered before it is shown. The key is passed to the filter
# through the environment and never on a command line, where `ps` would show it
# to every process on a machine that runs five lanes at once.
(
  cd "$REPO_ROOT/services/api" || exit 2
  GEMINI_API_KEY="$KEY" \
  MOBILE_REQUIRE_GEMINI_TESTS=1 \
  MOBILE_LIVE_GEMINI=1 \
    python3 -m pytest tests/live --junit-xml="$REPORT" "${PYTEST_ARGS[@]+"${PYTEST_ARGS[@]}"}"
) 2>&1 | redact
rc=${PIPESTATUS[0]}

# --- did it actually run? -------------------------------------------------
#
# pytest exits 0 for a run in which every case skipped. That is the whole
# defect being removed, so the exit code is not the answer on its own.

if [ ! -f "$REPORT" ]; then
  echo "pytest không ghi được báo cáo JUnit — không biết ca nào đã chạy, nên đây là HỎNG." >&2
  exit 1
fi

# The tally lives in scripts/junit_tally.py, not here, so that the one
# distinction it makes -- a real skip is a hole, an xfail is recorded intent
# -- can be tested against a handwritten report instead of against three
# minutes of live model calls. See its header for the bug that split them.
counts="$(python3 "$REPO_ROOT/scripts/junit_tally.py" "$REPORT")"
parse_rc=$?

if [ "$parse_rc" -ne 0 ]; then
  echo "không đọc được báo cáo JUnit — cổng này không chứng minh được gì, nên báo HỎNG." >&2
  exit 1
fi

read -r RAN SKIPPED XFAILED FAILURES ERRORS <<<"$(printf '%s\n' "$counts" | head -1)"
SKIP_LINES="$(printf '%s\n' "$counts" | tail -n +2)"

echo
echo "tầng AI sống: $RAN ca, $SKIPPED bỏ qua, $XFAILED xfail, $FAILURES hỏng, $ERRORS lỗi"

if [ "$RAN" -eq 0 ]; then
  echo "KHÔNG ca nào chạy — đây chính là hình dạng 'xanh vì không chạy gì'." >&2
  exit 1
fi

if [ "$SKIPPED" -gt 0 ]; then
  # With a key resolved and both flags exported there is no legitimate reason
  # for a case here to skip. Something removed it from the run, and reporting
  # that as a pass is the defect this file exists to remove.
  # Through the filter: a skip reason quotes back the value that caused it, and
  # this branch is reached precisely when something unexpected went into the
  # run. Printing it raw here would undo the redaction the pytest pipe does.
  printf '%s\n' "$SKIP_LINES" | redact >&2
  echo >&2
  echo "$SKIPPED ca BỎ QUA trong khi đã có khoá và đã bật cả hai cờ." >&2
  echo "Bỏ qua không phải đạt: mấy ca này không chứng minh gì cho lần chạy này." >&2
  exit 1
fi

exit "$rc"
