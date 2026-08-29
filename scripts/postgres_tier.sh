#!/usr/bin/env bash
#
# Run the PostgreSQL repository tier against a database this script creates and
# destroys itself.
#
# ## Why this exists
#
# `services/api/tests/postgres` is 224 cases and it is the only tier that
# exercises `SqlAlchemyApiRepository` against a real PostgreSQL. CLAUDE.md's own
# table is blunt about what the cheaper tiers cannot stand in for: the API suite
# runs on a fake repository and proves "khong bat ky cau SQL, index, view,
# trigger nao". JSONB, partial unique indexes, views and append-only triggers
# are only ever executed here.
#
# It costs 17 seconds. Measured on 2026-08-29 against a warm image:
# `224 passed in 17.18s`. Nobody ran it, because running it required knowing a
# connection string and which of the ten Postgres containers on this machine
# belonged to you. So the tier skipped -- in CI 147 skips and 0 runs, and
# locally `scripts/gate.sh postgres` reported BO QUA every time.
#
# A skip is not a pass. CLAUDE.md says it outright, and this repository has been
# bitten by the same shape twice already: a detector with no browser returning
# `[]` and exit 0, and a postgres tier reporting skips that read as green.
#
# ## Why it provisions instead of guessing
#
# `scripts/gate.sh` refused to guess a URL, and the reason it gave was right:
#
#   "Guessing a connection string would point the tier at the shared
#    `mobile-local` database that every worktree on this machine uses, and the
#    postgres tier migrates a schema."
#
# The answer is not to guess better. It is to have nothing to guess: a container
# of this script's own, on a random loopback port, with a password generated per
# run, removed on the way out including on Ctrl-C. It never reads, names or
# touches a compose project, so no lane's stack can be caught by it -- the
# failure mode the refusal was protecting against cannot occur.
#
# An explicitly given MOBILE_TEST_DATABASE_URL still wins. Somebody who has
# pointed this at a database on purpose is not to be second-guessed.
#
# ## What this does NOT prove
#
# It runs the tier. It does not prove the tier covers every method, race or
# query plan -- CLAUDE.md's table already says it does not. It does not prove
# the disposable container matches production tuning: it runs with `fsync=off`,
# which is correct for a database that is deleted 17 seconds later and would be
# indefensible for one that is not.
#
# Usage:
#   scripts/postgres_tier.sh                 provision, run the whole tier, tear down
#   scripts/postgres_tier.sh -k tests_name   extra arguments go to pytest
#   scripts/postgres_tier.sh --keep          leave the container up, print its URL
#
# Exit codes: 0 the tier passed, 1 the tier failed,
# 2 the tier could not be run at all -- no docker, no image, never healthy.

set -uo pipefail

cd "$(dirname "$0")/.." || exit 2
REPO_ROOT="$PWD"

IMAGE="${MOBILE_TEST_POSTGRES_IMAGE:-postgres:16-alpine}"
KEEP=0
PYTEST_ARGS=()

while [ $# -gt 0 ]; do
  case "$1" in
    --keep) KEEP=1 ;;
    -h|--help) sed -n '2,60p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) PYTEST_ARGS+=("$1") ;;
  esac
  shift
done

# --- the database ---------------------------------------------------------

CONTAINER=""

cleanup() {
  # Runs on EXIT, so it covers Ctrl-C and `set -e`-style early returns too. A
  # throwaway database that outlives the run is worse than no throwaway
  # database: this machine already carries ten Postgres containers, and an
  # eleventh nobody remembers starting is how a port collision gets diagnosed
  # as somebody else's bug.
  if [ -n "$CONTAINER" ] && [ "$KEEP" -eq 0 ]; then
    docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

provision() {
  command -v docker >/dev/null 2>&1 || {
    echo "không có docker — không dựng được database dùng một lần" >&2; return 2; }
  docker info >/dev/null 2>&1 || {
    echo "docker daemon không chạy" >&2; return 2; }

  # Pulling inside a gate would make the gate's runtime depend on the network.
  # The image is already here because docker-compose.yml uses the same tag.
  docker image inspect "$IMAGE" >/dev/null 2>&1 || {
    echo "chưa có ảnh $IMAGE tại máy — chạy 'docker pull $IMAGE' một lần" >&2; return 2; }

  # Per-run credentials. Not a security boundary -- the container is on
  # loopback and lives for seconds -- but a fixed password here would be a
  # third copy of a literal that must never be mistaken for a real one.
  local password
  password="$(head -c 18 /dev/urandom | base64 | tr -d '/+=' | head -c 20)"
  CONTAINER="mobile-tier-pg-$$-$(head -c 4 /dev/urandom | od -An -tx1 | tr -d ' \n')"

  # `-p 127.0.0.1::5432` publishes to a RANDOM free port on loopback only.
  # Random because a fixed port is the one thing guaranteed to collide on a
  # machine running five worktrees; loopback-only because nothing outside this
  # machine has any business reaching a test database.
  #
  # fsync off is safe exactly here and nowhere else: the volume is deleted with
  # the container, so there is no crash to survive.
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

  # `-h 127.0.0.1` is not decoration, and docker-compose.yml already carries the
  # scar that explains it: during initdb PostgreSQL runs a temporary server
  # bound to the unix socket only, so a `pg_isready` without -h answers "ready"
  # while the TCP port is still closed. Anything that starts on that answer
  # dies of connection refused.
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

# --- run ------------------------------------------------------------------

if [ -n "${MOBILE_TEST_DATABASE_URL:-}" ]; then
  # Somebody aimed this on purpose. Say so, and do not provision anything.
  echo "Dùng MOBILE_TEST_DATABASE_URL đã đặt sẵn — không dựng container."
  DATABASE_URL="$MOBILE_TEST_DATABASE_URL"
else
  echo "Chưa đặt MOBILE_TEST_DATABASE_URL — dựng database dùng một lần."
  provision || exit 2
fi

if [ "$KEEP" -eq 1 ]; then
  echo "--keep: giữ container lại. Xoá bằng: docker rm -f $CONTAINER"
fi

# MOBILE_REQUIRE_POSTGRES_TESTS=1 is the point of the whole file. Without it a
# conftest that cannot reach the database calls pytest.skip and the run exits 0
# having proved nothing -- the exact shape this script was written to remove.
echo "--- pytest tests/postgres (MOBILE_REQUIRE_POSTGRES_TESTS=1)"
(
  cd "$REPO_ROOT/services/api" || exit 2
  MOBILE_TEST_DATABASE_URL="$DATABASE_URL" \
  MOBILE_REQUIRE_POSTGRES_TESTS=1 \
    python3 -m pytest tests/postgres "${PYTEST_ARGS[@]+"${PYTEST_ARGS[@]}"}"
)
rc=$?

exit "$rc"
