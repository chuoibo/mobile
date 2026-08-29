#!/bin/sh
# Prove that a photo written by the API outlives the container that wrote it.
#
# WHY A LIVE CHECK AND NOT A YAML ASSERTION
#
# Reading `docker-compose.yml` proves somebody typed a volume. It does not
# prove the volume is mounted where the code writes, that the runtime user can
# write into it, or that a second container sees the first one's bytes. All
# three have to hold, and two of them are invisible to a parser:
#
#   * `MOBILE_MEDIA_ROOT` and the mount target are two independent strings.
#     Agreeing today is not a property, it is a coincidence.
#   * Docker creates a mount point that the image does not contain as
#     root:root. The API runs as uid 10001. Measured before this gate existed:
#     `touch: cannot touch '/var/lib/rudi/media/x': Permission denied`.
#
# HOW IT DESTROYS THE CONTAINER
#
# Two `compose run --rm` invocations, not `compose restart`. This distinction
# is the whole gate. `restart` stops and starts the SAME container, so its
# writable layer survives and the check would pass with no volume at all --
# a green light for the exact defect it exists to catch. Measured, no volume
# mounted: restart -> file still readable; a second `run --rm` -> gone.
#
# Everything happens under a throwaway compose project, so the shared
# `mobile-local` stack the whole machine calls is never touched: different
# project name means different volume name and different containers. Ports are
# not published either -- `compose run` without `--service-ports` publishes
# nothing, so 8099 stays with whoever holds it.
set -eu

REPO_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$REPO_ROOT"

PROJECT="${MOBILE_MEDIA_GATE_PROJECT:-mobile-media-gate}"

# An override that renames the image and NOTHING else. Two reasons, both
# learned the hard way in one run of this script:
#
#   1. Without a build, compose reuses whatever `mobile-local/api:dev` happens
#      to be on the machine. The first run of this gate measured an image built
#      before the fix and reported the fix broken. A gate that grades a stale
#      artifact is measuring someone else's commit.
#   2. With a build but no rename, the build would retag `mobile-local/api:dev`
#      -- the shared tag every worktree's stack points at -- from whichever
#      branch happened to run the gate.
#
# Everything the gate actually judges (MOBILE_MEDIA_ROOT, the mount, the
# volume, the runtime user) still comes from the real docker-compose.yml.
OVERRIDE="$(mktemp -t rd-do-21-override.XXXXXX.yml)"
cat >"$OVERRIDE" <<'YAML'
services:
  api:
    image: mobile-media-gate/api:test
YAML

# A fixed key rather than a random one: `PhotoStorage` demands exactly 32
# lowercase hex characters, and a gate whose input can drift is a gate that
# fails for reasons unrelated to what it measures.
KEY=00112233445566778899aabbccddeeff
# Bytes chosen to be recognisable in a hexdump and to contain a NUL, so a
# transport that silently treats the payload as text cannot pass.
PAYLOAD_PY='bytes(range(256)) * 4'

compose() {
  docker compose -p "$PROJECT" -f docker-compose.yml -f "$OVERRIDE" "$@"
}

# `-v` here removes only THIS project's volumes. It is safe precisely because
# PROJECT is not the shared stack; that is why the name is not configurable to
# an empty string.
#
# Split from `cleanup` because the run STARTS by tearing down leftovers, and a
# teardown that also deleted the override file left the build reading a path
# that no longer existed.
teardown() { compose down -v --remove-orphans >/dev/null 2>&1 || true; }
cleanup() { teardown; rm -f "$OVERRIDE"; }

if ! docker compose version >/dev/null 2>&1; then
  echo "BỎ QUA: máy này không có 'docker compose'." >&2
  echo "  Cổng này cần Docker vì nó chứng minh một hành vi của Docker:" >&2
  echo "  ảnh còn sống sau khi container bị xoá. Không có cách nào" >&2
  echo "  chứng minh điều đó mà không dựng container." >&2
  exit 77
fi

[ -n "$PROJECT" ] || { echo "MOBILE_MEDIA_GATE_PROJECT rỗng — từ chối chạy." >&2; exit 1; }
case "$PROJECT" in
  mobile-local) echo "Từ chối: '$PROJECT' là bộ dùng chung; cổng này sẽ 'down -v' nó." >&2; exit 1 ;;
esac

trap cleanup EXIT INT TERM
teardown

echo "--- dựng ảnh từ CÂY NÀY (không đụng tag dùng chung mobile-local/api:dev)"
compose build api >/dev/null || { echo "HỎNG: không dựng được ảnh api." >&2; exit 1; }

echo "--- container thứ nhất: ghi ảnh qua chính PhotoStorage của app"
compose run --rm --no-deps -T api python -c "
import pathlib
from app.media.storage import PhotoStorage

storage = PhotoStorage()
print('MOBILE_MEDIA_ROOT ->', storage.root)
storage.write('$KEY', $PAYLOAD_PY)
written = pathlib.Path(storage.root) / '$KEY'[:2] / '$KEY'[2:4] / '$KEY'
print('đã ghi', written.stat().st_size, 'byte tại', written)
" || { echo "HỎNG: không ghi được ảnh." >&2; exit 1; }

echo "--- container đó đã bị xoá (--rm); dựng container MỚI để đọc lại"
compose run --rm --no-deps -T api python -c "
import sys
from app.media.storage import PhotoStorage

expected = $PAYLOAD_PY
try:
    got = PhotoStorage().read('$KEY')
except FileNotFoundError:
    sys.exit(
        'HỎNG: ảnh biến mất cùng container. Thư mục ảnh đang nằm trong lớp ghi\n'
        '  của container, không nằm trong volume. Đây đúng là lỗi rd-do-21.'
    )
if got != expected:
    sys.exit(f'HỎNG: đọc lại {len(got)} byte, mong đợi {len(expected)}.')
print('đọc lại đúng', len(got), 'byte từ một container khác')
" || exit 1

echo "ĐẠT: ảnh sống sót qua việc xoá và dựng lại container api."
