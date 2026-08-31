#!/usr/bin/env bash
#
# A throwaway stack whose SERVER SIDE can be read afterwards.
#
# `scripts/e2e_slice.sh` already provisions a disposable Postgres and a uvicorn,
# and this file copies its recipe on purpose rather than inventing a second one.
# It differs in exactly two ways, both required by the question being asked:
#
#   1. uvicorn runs at `--log-level info`, so the ACCESS LOG exists. e2e_slice
#      pins `warning`, which is right for a test runner and useless here: the
#      whole point of this measurement is that a screen showing content while
#      the server logged no request is a screen inventing its own data. Without
#      access lines there is nothing to read but the screen, and the screen is
#      the least trustworthy instrument in the box.
#   2. `GEMINI_API_KEY` is passed through from the repo-root `.env`, because F37
#      is an AI feature and a reel measured against a missing key measures the
#      key, not the feature. The value is never printed, never written to the
#      log directory, and never committed -- only the fact that it is present.
#
# It stays in the foreground once the stack answers, so whoever started it owns
# the lifetime. The URLs are written to `$OUT_DIR/stack.env` for other processes.
#
#     tests/qa/qa3-123758-ruot-f37-f38/dung-stack.sh <out-dir>
set -uo pipefail

OUT_DIR="${1:?usage: dung-stack.sh <out-dir>}"
mkdir -p "$OUT_DIR"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
IMAGE="postgres:16-alpine"

CONTAINER=""
API_PID=""
cleanup() {
  [ -n "$API_PID" ] && kill "$API_PID" 2>/dev/null
  [ -n "$CONTAINER" ] && docker rm -f "$CONTAINER" >/dev/null 2>&1
  return 0
}
trap cleanup EXIT INT TERM

password="$(head -c 18 /dev/urandom | base64 | tr -d '/+=' | head -c 20)"
CONTAINER="qa3-ruot-pg-$$-$(head -c 4 /dev/urandom | od -An -tx1 | tr -d ' \n')"
docker run -d --rm --name "$CONTAINER" \
  -e POSTGRES_DB=mobile -e POSTGRES_USER=mobile -e POSTGRES_PASSWORD="$password" \
  -p 127.0.0.1::5432 "$IMAGE" \
  -c fsync=off -c full_page_writes=off -c synchronous_commit=off >/dev/null || exit 2

hostport="$(docker port "$CONTAINER" 5432/tcp | head -1)"; hostport="${hostport##*:}"
# -h 127.0.0.1 on purpose: during initdb the unix socket answers ready while the
# TCP port is still shut, and whatever trusts that answer dies of ECONNREFUSED.
for i in $(seq 1 60); do
  docker exec "$CONTAINER" pg_isready -h 127.0.0.1 -U mobile -d mobile >/dev/null 2>&1 && break
  sleep 1
done
DATABASE_URL="postgresql+psycopg://mobile:${password}@127.0.0.1:${hostport}/mobile"
echo "pg: 127.0.0.1:${hostport} ($CONTAINER)"

( cd "$REPO_ROOT/services/api" && MOBILE_DATABASE_URL="$DATABASE_URL" \
    python3 -m alembic upgrade head ) >"$OUT_DIR/alembic.log" 2>&1 || {
  echo "alembic hỏng — xem $OUT_DIR/alembic.log" >&2; tail -20 "$OUT_DIR/alembic.log" >&2; exit 1; }
echo "alembic: head"

port="$(python3 -c "import socket;s=socket.socket();s.bind(('127.0.0.1',0));print(s.getsockname()[1]);s.close()")"
id_key="$(head -c 48 /dev/urandom | base64 | tr -d '/+=' | head -c 44)"
GEMINI_API_KEY="$(sed -n 's/^GEMINI_API_KEY=//p' "$REPO_ROOT/../../../mobile/.env" 2>/dev/null | tr -d '"' | head -1)"
[ -n "$GEMINI_API_KEY" ] && echo "gemini: key có mặt (${#GEMINI_API_KEY} ký tự, không in)" || echo "gemini: KHÔNG có key"

(
  cd "$REPO_ROOT/services/api" || exit 2
  MOBILE_DATABASE_URL="$DATABASE_URL" \
  MOBILE_MEDIA_ROOT="$OUT_DIR/media" \
  MOBILE_PERSON_ID_KEY="$id_key" \
  GEMINI_API_KEY="$GEMINI_API_KEY" \
    python3 -m uvicorn app.api.main:app --host 127.0.0.1 --port "$port" --log-level info
) >"$OUT_DIR/uvicorn.log" 2>&1 &
API_PID=$!
API_URL="http://127.0.0.1:$port"

for i in $(seq 1 60); do
  curl -fsS --max-time 2 "$API_URL/healthz" >/dev/null 2>&1 && break
  kill -0 "$API_PID" 2>/dev/null || { echo "uvicorn chết" >&2; tail -20 "$OUT_DIR/uvicorn.log" >&2; exit 2; }
  sleep 1
done

{
  echo "API_URL=$API_URL"
  echo "DATABASE_URL=$DATABASE_URL"
  echo "MEDIA_ROOT=$OUT_DIR/media"
  echo "UVICORN_LOG=$OUT_DIR/uvicorn.log"
  echo "CONTAINER=$CONTAINER"
  echo "API_PID=$API_PID"
} >"$OUT_DIR/stack.env"
echo "SAN SANG $API_URL"
wait "$API_PID"
