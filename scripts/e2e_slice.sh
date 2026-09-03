#!/usr/bin/env bash
#
# Run the vertical slice against an API and a database this script starts and
# destroys itself.
#
# ## Why this exists
#
# `apps/mobile/tests/e2e/vertical-slice.test.mjs` is the only test in this
# repository that proves the client and the server connect. Everything else
# proves a piece with the other side faked: `tests/api/` runs on a fake
# repository, `apps/mobile`'s suite runs on a fake API, and CLAUDE.md's table
# says outright what each cannot see. The slice drives `src/api.ts` -- the same
# module the app imports -- against a real FastAPI on a real PostgreSQL, from
# propose through confirm, batch, publish, the guest page, and receipt.
#
# Nothing ran it. Measured on 2026-08-30 at 1649c16:
#
#   - `npm test` cannot: `scripts.test` prunes `tests/e2e` by construction
#     (`find tests -path tests/e2e -prune -o -name '*.test.mjs' -print`), so
#     the 55 files it runs are exactly the ones that fake the server.
#   - `.github/workflows/test.yml`'s mobile job runs that same `npm test`.
#   - `scripts/gate.sh` had no stage for it, and `grep -rn test:e2e` over every
#     .yml, .sh, .py, .json and .md found one definition in package.json and
#     not one caller. Every other hit is a QA report written by hand.
#
# So the hero path -- the one thing the product is being built to demonstrate
# -- was proven by a file that ran when somebody remembered, and the QA reports
# record the times nobody did: "chua chay", "khong chay trong luot nay".
#
# ## Why it provisions instead of pointing at what is already running
#
# `BASE_URL` in `apps/mobile/src/api.ts` falls back to `http://localhost:8099`,
# and 8099 on this machine is the shared `make up` stack that every worktree
# uses. Measured 2026-08-30 while writing this: that container served 52 routes
# and this tree renders 58. Aiming the slice there does not test this branch,
# it tests whatever was built last and passes or fails for reasons no reader
# can attribute -- the shape CLAUDE.md's "do tai <sha>" rule exists to stop.
#
# The answer is the one `scripts/postgres_tier.sh` already reached for the
# repository tier: have nothing to guess. A PostgreSQL container of this
# script's own on a random loopback port, a uvicorn of its own on another,
# both removed on the way out including on Ctrl-C. It never reads or names a
# compose project, so no lane's stack can be caught by it.
#
# ## A skip is not a pass
#
# The slice skips when it cannot reach a server, on purpose -- a developer with
# no Postgres should still be able to run the rest of the suite. That makes its
# honest summary "1 skipped", which reads exactly like a pass in a summary
# line. `MOBILE_REQUIRE_E2E=1` is what turns the skip into a failure, and this
# script always sets it. Running the slice without it is how the slice sat
# unproven for a week.
#
# ## What this does NOT prove
#
# It drives the client over `node --test`, which is not a browser: `fetch` in
# node does not enforce CORS, so a CORS misconfiguration that kills the web
# build passes here exactly as it passes every other gate in this repository.
# It exercises two flows, not the API's whole surface -- `gate.sh api` and the
# postgres tier remain the breadth. It runs one uvicorn worker on a database
# with no other traffic, so it says nothing about races or query plans. And the
# disposable database runs with `fsync=off`, correct for something deleted
# thirty seconds later and indefensible for anything else.
#
# Usage:
#   scripts/e2e_slice.sh                provision, run the slice, tear down
#   scripts/e2e_slice.sh --keep         leave the stack up, print its URL
#   scripts/e2e_slice.sh -- -t "ten"    extra arguments go to `node --test`
#
# Exit codes: 0 the slice passed, 1 the slice failed,
# 2 it could not be run at all -- no docker, no node, never healthy.

set -uo pipefail

cd "$(dirname "$0")/.." || exit 2
REPO_ROOT="$PWD"

IMAGE="${MOBILE_TEST_POSTGRES_IMAGE:-postgres:16-alpine}"
KEEP=0
TEST_ARGS=()

while [ $# -gt 0 ]; do
  case "$1" in
    --keep) KEEP=1 ;;
    --) shift; TEST_ARGS=("$@"); break ;;
    -h|--help) sed -n '2,72p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Tham số lạ: $1 (xem scripts/e2e_slice.sh --help)" >&2; exit 2 ;;
  esac
  shift
done

CONTAINER=""
API_PID=""
WORK_DIR=""

cleanup() {
  # EXIT so Ctrl-C and early returns are covered too. A uvicorn that outlives
  # the run is worse than none: it holds a port and answers /healthz, and the
  # next reader diagnoses a stale answer as somebody else's bug.
  if [ "$KEEP" -eq 1 ]; then
    return
  fi
  if [ -n "$API_PID" ]; then
    kill "$API_PID" >/dev/null 2>&1 || true
    wait "$API_PID" 2>/dev/null || true
  fi
  if [ -n "$CONTAINER" ]; then
    docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
  fi
  if [ -n "$WORK_DIR" ]; then
    rm -rf "$WORK_DIR"
  fi
}
trap cleanup EXIT INT TERM

# --- the database ---------------------------------------------------------

provision_db() {
  command -v docker >/dev/null 2>&1 || {
    echo "không có docker — không dựng được database dùng một lần" >&2; return 2; }
  docker info >/dev/null 2>&1 || {
    echo "docker daemon không chạy" >&2; return 2; }
  docker image inspect "$IMAGE" >/dev/null 2>&1 || {
    echo "chưa có ảnh $IMAGE tại máy — chạy 'docker pull $IMAGE' một lần" >&2; return 2; }

  local password
  password="$(head -c 18 /dev/urandom | base64 | tr -d '/+=' | head -c 20)"
  CONTAINER="mobile-e2e-pg-$$-$(head -c 4 /dev/urandom | od -An -tx1 | tr -d ' \n')"

  # Random loopback port: a fixed one is the single thing guaranteed to collide
  # on a machine running five worktrees. fsync off is safe exactly here, where
  # the volume dies with the container and there is no crash to survive.
  docker run -d --rm --name "$CONTAINER" \
    -e POSTGRES_DB=mobile \
    -e POSTGRES_USER=mobile \
    -e POSTGRES_PASSWORD="$password" \
    -p 127.0.0.1::5432 \
    "$IMAGE" \
    -c fsync=off -c full_page_writes=off -c synchronous_commit=off >/dev/null || {
      echo "không khởi động được container postgres" >&2; return 2; }

  local hostport
  hostport="$(docker port "$CONTAINER" 5432/tcp 2>/dev/null | head -1)"
  hostport="${hostport##*:}"
  [ -n "$hostport" ] || { echo "không đọc được cổng đã publish" >&2; return 2; }

  # `-h 127.0.0.1` is not decoration. During initdb PostgreSQL runs a temporary
  # server bound to the unix socket only, so a `pg_isready` without -h answers
  # "ready" while the TCP port is still closed, and whatever starts on that
  # answer dies of connection refused. docker-compose.yml carries the same scar.
  local i
  for i in $(seq 1 60); do
    if docker exec "$CONTAINER" pg_isready -h 127.0.0.1 -U mobile -d mobile >/dev/null 2>&1; then
      DATABASE_URL="postgresql+psycopg://mobile:${password}@127.0.0.1:${hostport}/mobile"
      echo "database dùng một lần: 127.0.0.1:${hostport} (container ${CONTAINER}, sẵn sàng sau ${i}s)"
      return 0
    fi
    if [ "$(docker inspect --format '{{.State.Running}}' "$CONTAINER" 2>/dev/null)" != "true" ]; then
      echo "container postgres thoát trước khi sẵn sàng" >&2
      docker logs "$CONTAINER" 2>&1 | tail -20 >&2
      return 2
    fi
    sleep 1
  done
  echo "container postgres không bao giờ sẵn sàng" >&2
  docker logs "$CONTAINER" 2>&1 | tail -20 >&2
  return 2
}

# --- the API --------------------------------------------------------------

start_api() {
  # MOBILE_DATABASE_URL is set for every command below, never left to default.
  # `app/db/session.py` and `app/db/migrations/env.py` both fall back to the
  # shared dev database on localhost:5432 when it is unset, so an unset
  # variable here would migrate a database five other worktrees are using --
  # the accident that produced the orphaned-revision incident on 2026-08-29.
  echo "--- alembic upgrade head (database dùng một lần)"
  ( cd "$REPO_ROOT/services/api" \
      && MOBILE_DATABASE_URL="$DATABASE_URL" python3 -m alembic upgrade head ) || {
    echo "migration hỏng — không dựng được schema để chạy lát cắt" >&2; return 1; }

  local port
  port="$(python3 -c "import socket
s = socket.socket()
s.bind(('127.0.0.1', 0))
print(s.getsockname()[1])
s.close()")" || { echo "không tìm được cổng trống" >&2; return 2; }

  WORK_DIR="$(mktemp -d)"
  API_LOG="$WORK_DIR/uvicorn.log"

  # A key of this run's own. The API answers 503 identity_key_missing without
  # one, and a literal in the repository would be the enumeration bug of
  # bug-140342 with extra steps -- see scripts/check_identity_key.sh.
  local id_key
  id_key="$(head -c 48 /dev/urandom | base64 | tr -d '/+=' | head -c 44)"

  (
    cd "$REPO_ROOT/services/api" || exit 2
    MOBILE_DATABASE_URL="$DATABASE_URL" \
    MOBILE_MEDIA_ROOT="$WORK_DIR/media" \
    MOBILE_PERSON_ID_KEY="$id_key" \
      python3 -m uvicorn app.api.main:app \
        --host 127.0.0.1 --port "$port" --log-level warning
  ) >"$API_LOG" 2>&1 &
  API_PID=$!

  API_URL="http://127.0.0.1:$port"

  # /healthz deliberately does not touch the database, so this loop proves a
  # process is answering and nothing more. The schema is proven by alembic's
  # exit code above, which is the right place for it: restarting the API never
  # fixed Postgres, and CLAUDE.md says so.
  local i
  for i in $(seq 1 60); do
    if curl -fsS --max-time 2 "$API_URL/healthz" >/dev/null 2>&1; then
      echo "API dùng một lần: $API_URL (sẵn sàng sau ${i}s)"
      return 0
    fi
    if ! kill -0 "$API_PID" 2>/dev/null; then
      echo "uvicorn thoát trước khi trả lời /healthz" >&2
      tail -30 "$API_LOG" >&2
      API_PID=""
      return 2
    fi
    sleep 1
  done
  echo "API không bao giờ trả lời /healthz" >&2
  tail -30 "$API_LOG" >&2
  return 2
}

# --- sessions -------------------------------------------------------------

# The API above runs with no MOBILE_AUTH_MODE, so it runs in `prod` (ADR-0014):
# it does not believe `X-Actor-ID`. That is deliberate and is the point of this
# stage. Running the slice in `dev` would keep it green and would stop it
# saying anything about the adapter the product actually ships.
#
# So the three demo people need real sessions. They are minted the way a real
# host mints its first one -- `scripts/genesis_session.py`, straight at the
# database, no HTTP -- because the HTTP route that issues a session requires an
# invitation, and issuing an invitation requires a session. On a fresh database
# that loop has no entry point, which is exactly why that script exists.
mint_sessions() {
  local people
  people="$(python3 "$REPO_ROOT/scripts/e2e_demo_people.py" \
              "$REPO_ROOT/apps/mobile/src/navigation/nhom-demo.ts")" \
    || { echo "khong lay duoc danh sach nguoi demo" >&2; return 2; }

  SESSION_FILE="$WORK_DIR/sessions.json"
  local first=1
  printf '{' >"$SESSION_FILE"
  while IFS=$'\t' read -r pid name; do
    [ -n "$pid" ] || continue
    local line token
    line="$(
      MOBILE_DATABASE_URL="$DATABASE_URL" python3 "$REPO_ROOT/scripts/genesis_session.py" \
        --person-id "$pid" --display-name "$name" --group "E2E genesis" --json
    )" || { echo "genesis_session.py hong cho $name" >&2; return 2; }
    token="$(printf '%s' "$line" | python3 -c 'import json,sys;print(json.load(sys.stdin)["token"])')" \
      || { echo "khong doc duoc token cho $name" >&2; return 2; }
    [ "$first" -eq 1 ] || printf ',' >>"$SESSION_FILE"
    first=0
    printf '"%s":"%s"' "$pid" "$token" >>"$SESSION_FILE"
  done <<<"$people"
  printf '}' >>"$SESSION_FILE"

  echo "--- phien that cho 3 nguoi demo (che do prod, khong tin X-Actor-ID)"
  return 0
}

# --- run ------------------------------------------------------------------

command -v node >/dev/null 2>&1 || { echo "không có node" >&2; exit 2; }
command -v npm  >/dev/null 2>&1 || { echo "không có npm" >&2; exit 2; }
[ -d "$REPO_ROOT/apps/mobile/node_modules" ] || {
  echo "chưa 'npm ci' trong apps/mobile" >&2; exit 2; }

provision_db || exit $?
start_api || exit $?
mint_sessions || exit $?

if [ "$KEEP" -eq 1 ]; then
  echo "--keep: giữ stack lại."
  echo "  API:       $API_URL"
  echo "  database:  $DATABASE_URL"
  echo "  dọn bằng:  docker rm -f $CONTAINER; kill $API_PID"
fi

# EXPO_PUBLIC_API_URL is pinned, not defaulted. `src/api.ts` falls back to
# localhost:8099 -- the shared stack -- and a slice that silently tested
# another lane's container would be worse than no slice, because it would
# report a colour about code nobody can identify.
#
# MOBILE_REQUIRE_E2E=1 is the whole point: without it an unreachable server is
# `t.skip` and exit 0, and this script would provision a stack, fail to reach
# it, and report success.
echo "--- npm run test:e2e (EXPO_PUBLIC_API_URL=$API_URL, MOBILE_REQUIRE_E2E=1)"
(
  cd "$REPO_ROOT/apps/mobile" || exit 2
  EXPO_PUBLIC_API_URL="$API_URL" \
  MOBILE_REQUIRE_E2E=1 \
  MOBILE_E2E_SESSIONS="$SESSION_FILE" \
    npm run --silent test:e2e ${TEST_ARGS[0]+-- "${TEST_ARGS[@]}"}
)
rc=$?

if [ "$rc" -ne 0 ] && [ -n "${API_LOG:-}" ] && [ -s "$API_LOG" ]; then
  echo
  echo "---- 30 dòng cuối log uvicorn ----"
  tail -30 "$API_LOG"
fi

exit "$rc"
