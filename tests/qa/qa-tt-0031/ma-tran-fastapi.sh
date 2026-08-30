#!/usr/bin/env bash
# The 2x2 that decides what PR #316's evidence actually proves.
#
# #316 fixes "the row is not committed yet when the 2xx goes out". Its evidence
# table says "before the patch: 2/2 FAILED". That measurement was taken with the
# fastapi that happens to be on this machine's PATH (0.135.3), NOT with the
# fastapi the image installs (0.115.6, pinned in requirements-dev.txt and applied
# as a --constraint by services/api/Dockerfile).
#
# The two versions place the dependency exit stack -- and therefore the COMMIT --
# on opposite sides of `await response(scope, receive, send)`:
#
#   0.115.6  fastapi.routing has NO request_response of its own; line 65-72 is
#            `from starlette.routing import (... request_response ...)`. The
#            yield-dependency exit stack lives INSIDE get_request_handler's app,
#            so it closes before the Response object is even returned.
#   0.135.3  fastapi.routing DEFINES request_response, with two stacks; the
#            request stack closes AFTER the body is sent. That is the bug.
#
# So the cell that matters is "fix removed, pinned fastapi". If it is GREEN, the
# postgres regression tests cannot go red where CI and the image run, and they
# do not guard the reintroduction they were written to guard.
#
# Usage, from the repo root:
#   tests/qa/qa-tt-0031/ma-tran-fastapi.sh <pinned-python> <database-url>
#
# Build <pinned-python> without touching the machine's interpreter:
#   python3 -m venv --system-site-packages /tmp/venv_pin
#   /tmp/venv_pin/bin/pip install "fastapi==0.115.6"
#
# Exit codes: 0 the matrix ran, 2 it could not run at all (never a silent pass).

set -uo pipefail

PINNED_PYTHON=${1:-/tmp/venv_pin/bin/python}
DB_URL=${2:-}

if [ ! -x "$PINNED_PYTHON" ]; then
  echo "khong chay duoc: $PINNED_PYTHON khong ton tai — xem huong dan dung venv o dau file" >&2
  exit 2
fi
if [ -z "$DB_URL" ]; then
  echo "khong chay duoc: thieu database url (tham so 2)" >&2
  exit 2
fi

REPO_ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
API_DIR="$REPO_ROOT/services/api"
MAIN_PY="$API_DIR/app/api/main.py"
CASES="tests/postgres/test_commit_before_response_postgres.py tests/api/test_commit_before_response_wiring.py"

MACHINE_PYTHON=$(command -v python3)
BACKUP=$(mktemp)
cp "$MAIN_PY" "$BACKUP"
# Restore on every exit path, including a mutated tree after Ctrl-C. Leaving a
# mutant behind is how a mutation run turns into a lost afternoon.
trap 'cp "$BACKUP" "$MAIN_PY"; rm -f "$BACKUP"' EXIT

export MOBILE_TEST_DATABASE_URL="$DB_URL"
export MOBILE_REQUIRE_POSTGRES_TESTS=1

run_cell() {
  local label=$1 interpreter=$2
  echo "--- $label"
  # shellcheck disable=SC2086
  (cd "$API_DIR" && "$interpreter" -m pytest $CASES -q -p no:randomly 2>&1 | tail -1)
}

apply_mutant() {
  "$MACHINE_PYTHON" - "$MAIN_PY" <<'PY'
import sys

path = sys.argv[1]
source = open(path).read()
call = "    install_commit_before_response(application)\n"
# An anchor that matched twice would patch the wrong copy and report a green
# that means nothing, so refuse rather than guess.
assert source.count(call) == 1, f"anchor found {source.count(call)} times"
open(path, "w").write(source.replace(call, "    # QA MUTANT: " + call.strip() + "\n"))
PY
}

echo "=== ban vá CÓ ==="
run_cell "fastapi may   ($("$MACHINE_PYTHON" -c 'import fastapi; print(fastapi.__version__)'))" "$MACHINE_PYTHON"
run_cell "fastapi GHIM  ($("$PINNED_PYTHON" -c 'import fastapi; print(fastapi.__version__)'))" "$PINNED_PYTHON"

echo
echo "=== ban vá GO (tuong duong main truoc PR) ==="
apply_mutant
run_cell "fastapi may   — mong doi DO" "$MACHINE_PYTHON"
run_cell "fastapi GHIM  — day la o quyet dinh" "$PINNED_PYTHON"
cp "$BACKUP" "$MAIN_PY"

echo
echo "Doc o cuoi cung: con 2 ca postgres XANH nghia la loi khong ton tai o ban ghim,"
echo "va ca hoi quy cua PR khong the do lai o noi CI va anh docker thuc su chay."
