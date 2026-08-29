#!/usr/bin/env bash
#
# Run the gates that .github/workflows/*.yml run, on this machine, in one
# command.
#
# ## Why this exists
#
# GitHub Actions stopped starting jobs at 07:45Z on 2026-08-29: every run since
# ends in three to five seconds with "The job was not started because recent
# account payments have failed or your spending limit needs to be increased".
# Measured on 2026-08-29T12:0xZ: the last 100 runs are 100 failures and 0
# successes. Nothing is wrong with the code. `gh run view --log-failed` answers
# "log not found" and exits 0, so from the outside a dead account and a broken
# build look identical -- and nine pull requests merged that day under a red X
# that meant billing.
#
# `tests/test_workflow_gates_have_local_callers.py` (#148) already closed half
# of this: every gate that is a *script* must have a caller outside the
# workflows. It states the half it cannot close, in its own words:
#
#   "It also says nothing about workflow steps written inline rather than as a
#    script. Those cannot be detected this way."
#
# That is this file. The inline steps -- the offline DDL render, the image
# running as non-root, the container actually answering /healthz, the native
# bundle, and the one environment variable that turns three accessibility
# checks from decoration into a gate -- exist only inside YAML that currently
# cannot execute. Here they are, callable.
#
# ## The rule this file is built around
#
# A skip is not a pass. CLAUDE.md says it outright ("skip khong phai la xanh"),
# and the repository has been bitten by the other kind: a detector with no
# browser returning `[]` and exit 0, a postgres tier reporting 254 skips that
# read as green. So every stage here ends in exactly one of PASS, FAIL or SKIP;
# a SKIP must carry a reason; the summary prints the counts; and `--strict`
# turns every SKIP into a FAIL for use before a merge.
#
# The workflows' own distinction is kept too, because it is the right one:
# an absent directory is an absence and skipping is honest, but a directory
# that is present and has lost the file the stage runs is a defect, and
# skipping that would turn the stage green for the one reason it must not.
#
# ## What this does NOT prove
#
# It runs the same commands on a different machine. It does not prove the
# workflow YAML is well-formed, that the runner image still has what the jobs
# assume, or that the two will not drift apart -- nobody can check that while
# Actions is down. `tests/test_gate_covers_every_workflow_job.py` holds the
# narrower line that every job in the workflows is at least named here.
#
# Usage:
#   scripts/gate.sh                 every stage whose prerequisites are present
#   scripts/gate.sh api mobile      only those stages
#   scripts/gate.sh --strict        a SKIP is a failure (use before merging)
#   scripts/gate.sh --list          stage names and what each one runs
#
# Exit codes: 0 every stage that ran passed, 1 a stage failed,
# 2 the gate could not do its job -- bad arguments, or nothing ran at all.

set -uo pipefail

cd "$(dirname "$0")/.." || exit 2
REPO_ROOT="$PWD"

# Every stage, in run order: cheapest and most likely to fail first, so a
# broken tree is reported in seconds rather than after a docker build.
STAGES=(guard ruff contract api migration shared mobile docker postgres)

stage_help() {
  case "$1" in
    guard)     echo "repo_guard.py tree HEAD (repo-guard.yml)" ;;
    ruff)      echo "ruff on the files this branch changes, uncommitted ones included (test.yml: lint)" ;;
    contract)  echo "every route wanting X-Actor-ID is called with it (test.yml: contract)" ;;
    api)       echo "pytest services/api/tests tests (test.yml: api)" ;;
    migration) echo "alembic upgrade head --sql, no database (test.yml: api, inline)" ;;
    shared)    echo "node packages/shared/money.test.mjs (test.yml: shared)" ;;
    mobile)    echo "tsc, npm test with MOBILE_REQUIRE_WEB_A11Y=1, expo export --platform all (test.yml: mobile)" ;;
    docker)    echo "image pinned, builds, non-root, no dev tooling, serves /healthz (test.yml: docker)" ;;
    postgres)  echo "pytest tests/postgres against a real PostgreSQL (postgres-repository.yml)" ;;
  esac
}

STRICT=0
SELECTED=()

while [ $# -gt 0 ]; do
  case "$1" in
    --strict) STRICT=1 ;;
    --list)
      echo "Các chặng của cổng (thứ tự chạy):"
      for s in "${STAGES[@]}"; do printf '  %-10s %s\n' "$s" "$(stage_help "$s")"; done
      exit 0
      ;;
    -h|--help) sed -n '2,60p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) echo "Tham số lạ: $1 (xem scripts/gate.sh --help)" >&2; exit 2 ;;
    *)
      # An unknown stage name must not quietly select nothing and exit 0 --
      # that is the "green because it ran nothing" failure this file exists
      # to prevent, reproduced in its own argument parser.
      found=0
      for s in "${STAGES[@]}"; do [ "$s" = "$1" ] && found=1; done
      if [ "$found" -eq 0 ]; then
        echo "Không có chặng tên '$1'. Có: ${STAGES[*]}" >&2
        exit 2
      fi
      SELECTED+=("$1")
      ;;
  esac
  shift
done

[ ${#SELECTED[@]} -eq 0 ] && SELECTED=("${STAGES[@]}")

PASSED=(); FAILED=(); SKIPPED=(); SKIP_WHY=()
LOG_DIR="$(mktemp -d)"

banner() { printf '\n\033[1m=== %s ===\033[0m %s\n' "$1" "$(stage_help "$1")"; }
pass() { PASSED+=("$1"); printf '\033[32mĐẠT\033[0m     %s (%ss)\n' "$1" "$2"; }
fail() { FAILED+=("$1"); printf '\033[31mHỎNG\033[0m    %s (%ss)\n' "$1" "$2"; }
skip() { SKIPPED+=("$1"); SKIP_WHY+=("$1: $2"); printf '\033[33mBỎ QUA\033[0m  %s -- %s\n' "$1" "$2"; }

# Stage output is teed to a file so a failure can be re-printed at the end: on
# an eight-stage run the thing that broke has otherwise scrolled off.
have() { command -v "$1" >/dev/null 2>&1; }

# --- stage bodies ---------------------------------------------------------

do_guard() { python3 scripts/repo_guard.py tree HEAD; }

do_ruff() {
  # The one-argument form compares <base> against the WORKING TREE, so this
  # covers changes not yet committed. CI can only ever see pushed commits;
  # locally the useful moment is before the commit exists.
  local base
  base="$(git merge-base origin/main HEAD 2>/dev/null)" || base=""
  if [ -z "$base" ]; then
    git fetch --no-tags --quiet origin main 2>/dev/null || true
    base="$(git merge-base origin/main HEAD 2>/dev/null)" || base=""
  fi
  if [ -z "$base" ]; then
    echo "không tìm được merge base với origin/main" >&2
    return 1
  fi
  echo "so với merge base $base"
  scripts/ruff_changed.sh "$base"
}

do_contract() {
  # Runs before `api` on purpose. It is seconds, and it answers a question no
  # other stage here asks: the two sides of one HTTP contract are checked by
  # two suites that each mock the other, so a route that starts demanding a
  # header leaves both suites green and the screen dead. See the file header.
  echo "--- self-test: the checker has to be able to be red"
  python3 scripts/check_actor_headers.py --selftest || return 1
  echo "--- client vs OpenAPI"
  python3 scripts/check_actor_headers.py
}

do_api() { python3 -m pytest services/api/tests tests -q; }

do_migration() {
  # The inline step from test.yml's api job. No database: this is the check
  # that was missing when five foreign-key names ran past PostgreSQL's
  # 63-character limit and the migration could not compile at all.
  ( cd services/api && python3 - <<'PY'
import contextlib, io
from alembic import command
from alembic.config import Config
config = Config("alembic.ini")
config.set_main_option("sqlalchemy.url", "postgresql+psycopg://offline/offline")
with contextlib.redirect_stdout(io.StringIO()):
    command.upgrade(config, "head", sql=True)
print("migration renders")
PY
  )
}

do_shared() { node packages/shared/money.test.mjs; }

do_mobile() {
  cd apps/mobile || return 1
  echo "--- tsc --noEmit"
  npx --no-install tsc --noEmit || return 1
  echo "--- npm test (MOBILE_REQUIRE_WEB_A11Y=1)"
  # The flag is the whole point of running this here. Without it a machine
  # with no browser skips the three render checks in tests/vo-tab-web.test.mjs
  # and `npm test` still exits 0 -- which is the exact shape of the hole they
  # were added to close.
  MOBILE_REQUIRE_WEB_A11Y=1 npm test || return 1
  echo "--- expo export --platform all"
  # Lives only in the workflow otherwise, on purpose (so it cannot be removed
  # by editing one line of package.json). Web is about a third of the native
  # module graph, so a react-native module with no web counterpart leaves
  # `npm test` perfectly green. Export outside the checkout so no artifact
  # lands in the tree.
  EXPO_NO_TELEMETRY=1 npx --no-install expo export --platform all \
    --output-dir "$LOG_DIR/expo-export" >/dev/null || return 1
  echo "bundled for web, ios and android"
}

do_docker() {
  echo "--- base image pinned by digest"
  scripts/check_dockerfile_pinning.sh services/api/Dockerfile || return 1
  echo "--- build"
  ( cd services/api && docker build -t mobile-api:gate . ) || return 1
  echo "--- runs as a non-root user"
  local uid
  uid="$(docker run --rm --entrypoint id mobile-api:gate -u)"
  echo "container uid = $uid"
  [ "$uid" = "0" ] && { echo "ảnh chạy bằng root" >&2; return 1; }
  echo "--- no test tooling in the runtime image"
  if docker run --rm --entrypoint sh mobile-api:gate -c "ls /venv/bin" | grep -qE '^(pytest|ruff)$'; then
    echo "pytest hoặc ruff lọt vào ảnh chạy thật" >&2; return 1
  fi
  echo "--- the container actually serves /healthz"
  # No published host port, for the reason the workflow gives: curling the
  # host passes whenever *anything* answers on that port. Polling the
  # container's own HEALTHCHECK cannot be satisfied by a stranger.
  docker rm -f mobile-api-gate >/dev/null 2>&1 || true
  docker run -d --name mobile-api-gate mobile-api:gate >/dev/null || return 1
  local i status
  for i in $(seq 1 60); do
    status="$(docker inspect --format '{{.State.Health.Status}}' mobile-api-gate 2>/dev/null)"
    case "$status" in
      healthy) echo "container healthy sau ${i}s"; docker rm -f mobile-api-gate >/dev/null; return 0 ;;
      unhealthy) echo "container unhealthy" >&2; docker logs mobile-api-gate; docker rm -f mobile-api-gate >/dev/null; return 1 ;;
    esac
    if [ "$(docker inspect --format '{{.State.Running}}' mobile-api-gate 2>/dev/null)" != "true" ]; then
      echo "container thoát trước khi healthy" >&2; docker logs mobile-api-gate; docker rm -f mobile-api-gate >/dev/null; return 1
    fi
    sleep 1
  done
  echo "container không bao giờ healthy" >&2; docker logs mobile-api-gate; docker rm -f mobile-api-gate >/dev/null; return 1
}

do_postgres() {
  ( cd services/api && MOBILE_REQUIRE_POSTGRES_TESTS=1 python3 -m pytest tests/postgres -q )
}

# --- prerequisites --------------------------------------------------------
#
# Answers exactly one of: run it, skip it with a reason, or fail because the
# thing is present but broken. The third case is the workflows' rule and it
# matters most: `apps/mobile` with no lockfile is a defect, not an absence.

check_prereq() {
  case "$1" in
    ruff)
      git rev-parse --git-dir >/dev/null 2>&1 || { echo "không phải git repo"; return 1; } ;;
    contract)
      # Needs both sides of the contract. Without `apps/mobile` there is no
      # client to check and skipping is the honest answer; with it present but
      # no `src`, the checker itself would find nothing and report green, so
      # that case is a defect and refuses to skip.
      [ -d apps/mobile ] || { echo "apps/mobile không có trên nhánh này"; return 1; }
      [ -d apps/mobile/src ] || return 2
      python3 -c "import fastapi" 2>/dev/null || {
        echo "chưa cài fastapi (pip install -r services/api/requirements-dev.txt)"; return 1; } ;;
    shared)
      have node || { echo "không có node"; return 1; }
      [ -d packages/shared ] || { echo "packages/shared không có trên nhánh này"; return 1; }
      [ -f packages/shared/money.test.mjs ] || return 2 ;;
    mobile)
      have npx || { echo "không có npx"; return 1; }
      [ -d apps/mobile ] || { echo "apps/mobile không có trên nhánh này"; return 1; }
      [ -f apps/mobile/package-lock.json ] || return 2
      [ -d apps/mobile/node_modules ] || { echo "chưa 'npm ci' trong apps/mobile"; return 1; } ;;
    docker)
      have docker || { echo "không có docker"; return 1; }
      docker info >/dev/null 2>&1 || { echo "docker daemon không chạy"; return 1; } ;;
    postgres)
      # Only an explicitly given URL. Guessing a connection string would point
      # the tier at the shared `mobile-local` database that every worktree on
      # this machine uses, and the postgres tier migrates a schema.
      [ -n "${MOBILE_TEST_DATABASE_URL:-}" ] || {
        echo "chưa đặt MOBILE_TEST_DATABASE_URL (xem CLAUDE.md; 'docker compose up -d postgres' rồi export)"
        return 1; } ;;
  esac
  return 0
}

# The "present but broken" message, kept next to the rule it enforces.
broken_why() {
  case "$1" in
    contract) echo "apps/mobile có mặt nhưng thiếu src/ -- từ chối bỏ qua" ;;
    shared) echo "packages/shared có mặt nhưng thiếu money.test.mjs -- từ chối bỏ qua" ;;
    mobile) echo "apps/mobile có mặt nhưng thiếu package-lock.json -- từ chối bỏ qua" ;;
    *) echo "thiếu file mà chặng này cần -- từ chối bỏ qua" ;;
  esac
}

# --- run ------------------------------------------------------------------

echo "Cổng chạy tại máy — cùng các lệnh mà .github/workflows chạy."
echo "HEAD $(git rev-parse --short HEAD 2>/dev/null || echo '?')  chặng: ${SELECTED[*]}$([ "$STRICT" -eq 1 ] && echo '  [strict]')"

for stage in "${SELECTED[@]}"; do
  banner "$stage"
  why="$(check_prereq "$stage")"; prereq=$?
  if [ "$prereq" -eq 2 ]; then
    # Present but broken. Never a skip.
    echo "$(broken_why "$stage")" >&2
    fail "$stage" 0
    continue
  fi
  if [ "$prereq" -ne 0 ]; then
    if [ "$STRICT" -eq 1 ]; then
      echo "strict: bỏ qua bị tính là hỏng -- $why" >&2
      fail "$stage" 0
    else
      skip "$stage" "$why"
    fi
    continue
  fi
  # The subshell isolates cwd (`do_mobile` cd's into apps/mobile). PIPESTATUS
  # rather than `$?`: `$?` after a pipe is tee's status, which is 0 even when
  # the stage failed -- a gate that reads the wrong exit code is worse than no
  # gate, because it reports green with evidence scrolling past saying red.
  start=$SECONDS
  ( cd "$REPO_ROOT" && "do_$stage" ) 2>&1 | tee "$LOG_DIR/$stage.log"
  rc=${PIPESTATUS[0]}
  if [ "$rc" -eq 0 ]; then
    pass "$stage" "$((SECONDS - start))"
  else
    fail "$stage" "$((SECONDS - start))"
  fi
done

# --- summary --------------------------------------------------------------

echo
echo "================ TỔNG KẾT ================"
printf 'ĐẠT %d   HỎNG %d   BỎ QUA %d\n' "${#PASSED[@]}" "${#FAILED[@]}" "${#SKIPPED[@]}"
[ ${#PASSED[@]}  -gt 0 ] && echo "  đạt:     ${PASSED[*]}"
[ ${#FAILED[@]}  -gt 0 ] && echo "  hỏng:    ${FAILED[*]}"
if [ ${#SKIPPED[@]} -gt 0 ]; then
  echo "  bỏ qua:"
  for w in "${SKIP_WHY[@]}"; do echo "    $w"; done
  echo
  echo "BỎ QUA KHÔNG PHẢI ĐẠT. Trước khi merge chạy lại với --strict."
fi

# Guard the guard. If every stage was filtered away, the run proved nothing,
# and exiting 0 here would be this file committing the sin it was written for.
if [ ${#PASSED[@]} -eq 0 ] && [ ${#FAILED[@]} -eq 0 ]; then
  echo "Không chặng nào CHẠY -- cổng này không chứng minh gì cả." >&2
  exit 2
fi

if [ ${#FAILED[@]} -gt 0 ]; then
  for f in "${FAILED[@]}"; do
    echo
    echo "---- 30 dòng cuối của chặng hỏng: $f ----"
    [ -f "$LOG_DIR/$f.log" ] && tail -30 "$LOG_DIR/$f.log"
  done
  echo
  echo "Log đầy đủ: $LOG_DIR"
  exit 1
fi

rm -rf "$LOG_DIR"
echo "Tất cả chặng đã chạy đều ĐẠT."
exit 0
