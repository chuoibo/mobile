#!/bin/sh
# Rebuild the ledger from empty WITHOUT destroying uploaded photos.
#
# THE GAP THIS FILLS
#
# The stack keeps two named volumes and `make clean` takes both:
#
#     <project>_mobile-postgres-data   the ledger: groups, expenses, batches
#     <project>_mobile-media-data      every photo anybody uploaded
#
# `docker compose down -v` removes every volume of the project, so until now
# "give me a clean ledger" and "throw away the bills people photographed" were
# the same command. The Makefile says so in `clean`'s own refusal text: photos
# cannot be re-seeded, because the seed builds money data, not other people's
# pictures.
#
# That coupling is what made a dirty demo machine unfixable. The demo persona's
# personal screen sums `confirmed_allocations` across every group, those tables
# are append-only behind BEFORE DELETE OR UPDATE triggers, so a person who has
# spent money in a scratch group carries it forever. The only honest way back to
# a clean screen is a ledger that never saw the scratch group -- and reaching for
# it used to cost every uploaded photo.
#
# HOW THIS DIFFERS FROM THE TWO NEIGHBOURING COMMANDS
#
#   make demo-reset   renames the demo GROUP so the fixture's name lookup misses
#                     it. Ledger untouched, people untouched. Use it to re-seed
#                     onto a machine you want to keep.
#   make clean        destroys BOTH volumes. Use it when the photos are junk too.
#   make db-reset     this. Destroys the ledger, keeps the photos.
#
# WHY IT REFUSES RATHER THAN GUESSES
#
# The failure that matters is not "it errored". It is "it reported success and
# removed nothing", which leaves the operator believing the ledger is empty
# while the old rows answer every query. Compose derives a volume's real name by
# prefixing the project name, so a project named differently than this script
# assumes yields a name that matches no volume -- and `docker volume rm` on a
# missing volume is the kind of no-op that reads as success. So the ledger
# volume must be found BEFORE anything is torn down, and its absence is an
# abort, never a shrug.
set -eu

REPO_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$REPO_ROOT"

PROJECT="${PROJECT:-}"
CONFIRM="${CONFIRM:-}"

if [ -z "$PROJECT" ]; then
  echo "Từ chối: PROJECT rỗng." >&2
  echo "  Script này xoá volume theo tên '<project>_mobile-postgres-data'." >&2
  echo "  Project rỗng thì cái tên đó không trỏ tới gì, và một lệnh xoá không" >&2
  echo "  biết mình xoá gì thì không được chạy." >&2
  exit 1
fi

LEDGER_VOL="${PROJECT}_mobile-postgres-data"
MEDIA_VOL="${PROJECT}_mobile-media-data"

if [ "$CONFIRM" != "$PROJECT" ]; then
  echo "Từ chối: db-reset XOÁ TOÀN BỘ SỔ CÁI của project '$PROJECT'." >&2
  echo >&2
  echo "Project này dùng chung giữa mọi worktree trên máy. Mất sổ là mất của" >&2
  echo "cả đội: nhóm, khoản chi, đợt thu, và mọi link trang khách đang mở." >&2
  echo >&2
  echo "  XOÁ   $LEDGER_VOL   — sổ cái" >&2
  echo "  GIỮ   $MEDIA_VOL      — ảnh đã tải lên" >&2
  echo >&2
  echo "Đây là chỗ khác 'make clean': clean lấy cả hai volume, lệnh này chỉ" >&2
  echo "lấy volume sổ. Ảnh không seed lại được nên nó không nằm trong tầm tay." >&2
  echo >&2
  echo "Chắc thì gõ đúng tên project ra:" >&2
  echo "    make db-reset CONFIRM=$PROJECT" >&2
  echo >&2
  echo "Chỉ muốn seed lại nhóm demo mà GIỮ sổ:   make demo-reset APPLY=1" >&2
  exit 1
fi

if ! docker volume inspect "$LEDGER_VOL" >/dev/null 2>&1; then
  echo "Từ chối: không có volume nào tên '$LEDGER_VOL'." >&2
  echo >&2
  echo "Không tự suy ra tên khác và không chạy tiếp. Nếu chạy tiếp thì lệnh" >&2
  echo "sẽ 'xoá' một volume không tồn tại — thoát 0, không xoá gì — rồi dựng" >&2
  echo "lại stack với NGUYÊN sổ cũ, và bạn tưởng máy đã sạch." >&2
  echo >&2
  echo "Volume của repo này đang có trên máy:" >&2
  docker volume ls --format '  {{.Name}}' | grep -E 'mobile-(postgres|media)-data' >&2 || true
  exit 1
fi

# Captured BEFORE the teardown so the after-check has something to compare
# against. A volume that gets deleted and recreated comes back with a new
# CreatedAt, which is how this script tells "kept" apart from "replaced by an
# empty one of the same name" -- the two are indistinguishable by existence
# alone, and only one of them still has the photos.
MEDIA_BEFORE=""
if docker volume inspect "$MEDIA_VOL" >/dev/null 2>&1; then
  MEDIA_BEFORE="$(docker volume inspect -f '{{.CreatedAt}}' "$MEDIA_VOL")"
  echo "--- ảnh: $MEDIA_VOL (tạo lúc $MEDIA_BEFORE) — sẽ KHÔNG bị đụng tới"
else
  echo "--- ảnh: chưa có volume $MEDIA_VOL trên máy này (chưa ai tải ảnh nào)"
fi

echo "--- tắt project '$PROJECT' (down, KHÔNG -v: -v sẽ lấy cả ảnh)"
docker compose -p "$PROJECT" down

echo "--- xoá volume sổ cái: $LEDGER_VOL"
docker volume rm "$LEDGER_VOL" >/dev/null

if docker volume inspect "$LEDGER_VOL" >/dev/null 2>&1; then
  echo "HỎNG: '$LEDGER_VOL' vẫn còn sau khi xoá — sổ cũ sẽ quay lại." >&2
  exit 1
fi

# The post-condition that gives this script its reason to exist. If the media
# volume is gone, or is a different volume wearing the same name, everything
# above was an expensive way to run `make clean`.
if [ -n "$MEDIA_BEFORE" ]; then
  if ! docker volume inspect "$MEDIA_VOL" >/dev/null 2>&1; then
    echo "HỎNG: '$MEDIA_VOL' BIẾN MẤT. Ảnh đã tải lên không lấy lại được." >&2
    exit 1
  fi
  MEDIA_AFTER="$(docker volume inspect -f '{{.CreatedAt}}' "$MEDIA_VOL")"
  if [ "$MEDIA_AFTER" != "$MEDIA_BEFORE" ]; then
    echo "HỎNG: '$MEDIA_VOL' bị dựng lại ($MEDIA_BEFORE -> $MEDIA_AFTER)." >&2
    echo "  Cùng cái tên nhưng là volume khác, và volume khác thì rỗng." >&2
    exit 1
  fi
  echo "--- ảnh còn nguyên: $MEDIA_VOL vẫn là volume cũ ($MEDIA_AFTER)"
fi

echo
echo "ĐÃ XOÁ SỔ CÁI của '$PROJECT'. Ảnh giữ nguyên."
echo "Stack đang tắt — dựng lại và nạp dữ liệu demo bằng:"
echo "    MOBILE_PROJECT=$PROJECT make demo"
