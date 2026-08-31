#!/usr/bin/env bash
#
# Export the client bundle, but only from a tree that matches `main` -- and
# stamp the SHA into the artifact so whoever opens it can tell what it is.
#
# ## Why the export goes through a wrapper instead of being typed by hand
#
# At 03:20 on 2026-08-31 the export WAS typed by hand, from a checkout four
# commits behind `origin/main` with tracked screen files sitting deleted. The
# bundle that reached the demo box was missing `AlbumChuyenDi` and `CaNhanHoa`,
# and every signal stayed green: the export succeeded, the static server
# answered 200, and the gates that read the client tree read the SAME broken
# tree they were meant to be checking.
#
# `scripts/check_tree_matches_main.py` answers that. But a gate only mentioned
# in a comment is a gate nobody runs -- `qr-roundtrip.py` sat in this repo doing
# its job correctly for days with no Makefile entry and no caller, which is
# indistinguishable from not existing. So the check is not advice here; it is
# the first thing this script does, and a LỆCH tree stops the export.
#
# ## The stamp
#
# Even a correct bundle is unreadable from outside: open port 8081 and there is
# no way to ask "which commit is this?". So on success this writes
# `BUILD-SHA.txt` into the output directory, carrying the SHA, the ref, the
# verdict and the tree it came from. That turns "the demo looks wrong" from an
# argument into a lookup.
#
# ## What this does NOT do
#
# It does not publish. Copying the output somewhere and serving it is still a
# separate, manual step -- this script only refuses to hand you an artifact
# built from the wrong tree, and labels the one it does hand you.
# It also does not prove the bundle works; `make gate ONLY=mobile` is that.
#
# Usage:
#   scripts/xuat_bundle.sh                          # web bundle, gate first
#   scripts/xuat_bundle.sh --platform all
#   scripts/xuat_bundle.sh --output-dir /tmp/bundle
#   scripts/xuat_bundle.sh --tree /home/lakiet/mobile
#   scripts/xuat_bundle.sh --no-fetch               # offline; says so
#   scripts/xuat_bundle.sh --du-biet                # export anyway, loudly
#
# Exit codes: 0 exported from a matching tree, 1 the tree does not match (or
# the export failed), 2 the check could not run -- which is never a pass.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

TREE="$REPO_ROOT"
PLATFORM="web"
OUTPUT_DIR=""
REF="origin/main"
NO_FETCH=""
DU_BIET=""

while [ $# -gt 0 ]; do
  case "$1" in
    --tree)       TREE="$2"; shift 2 ;;
    --platform)   PLATFORM="$2"; shift 2 ;;
    --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
    --ref)        REF="$2"; shift 2 ;;
    --no-fetch)   NO_FETCH="--no-fetch"; shift ;;
    --du-biet)    DU_BIET="1"; shift ;;
    -h|--help)    sed -n '2,45p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "xuat_bundle: không hiểu tham số '$1'" >&2; exit 2 ;;
  esac
done

TREE="$(cd "$TREE" 2>/dev/null && pwd)" || { echo "xuat_bundle: không có thư mục --tree" >&2; exit 2; }
[ -n "$OUTPUT_DIR" ] || OUTPUT_DIR="$TREE/apps/mobile/dist"

echo "== 1/3 Cây này có khớp $REF không? =========================================="
# Deliberately run the checker that lives in THIS repo against the tree being
# built, which may be a different checkout. Running the copy inside the target
# tree would mean a stale tree gets to grade itself.
python3 "$REPO_ROOT/scripts/check_tree_matches_main.py" \
  --tree "$TREE" --ref "$REF" $NO_FETCH
verdict=$?

if [ "$verdict" -ne 0 ]; then
  if [ -z "$DU_BIET" ]; then
    echo >&2
    if [ "$verdict" -eq 2 ]; then
      echo "!! DỪNG: không kiểm được cây. Không kiểm được không phải là khớp." >&2
    else
      echo "!! DỪNG: không xuất bundle từ cây lệch. Đây đúng là lỗi 03:20." >&2
    fi
    echo "   Sửa cây rồi chạy lại. Cố tình vẫn muốn xuất: --du-biet." >&2
    exit "$verdict"
  fi
  echo >&2
  echo "!! --du-biet: VẪN XUẤT từ một cây KHÔNG khớp $REF." >&2
  echo "   Bundle này không đại diện cho $REF. Đừng đẩy nó lên máy demo." >&2
fi

echo
echo "== 2/3 expo export --platform $PLATFORM ====================================="
APP_DIR="$TREE/apps/mobile"
[ -d "$APP_DIR" ] || { echo "xuat_bundle: không có $APP_DIR" >&2; exit 2; }

# --clear: Metro's cache can serve a module from a tree that no longer exists,
# which would put the 03:20 bug back inside a tree that passes the gate.
( cd "$APP_DIR" && npx expo export --platform "$PLATFORM" --output-dir "$OUTPUT_DIR" --clear )
export_rc=$?
if [ "$export_rc" -ne 0 ]; then
  echo >&2
  echo "!! expo export thoát $export_rc — không có bundle, không đóng dấu." >&2
  exit 1
fi

echo
echo "== 3/3 Đóng dấu SHA vào chính bundle ========================================"
HEAD_SHA="$(git -C "$TREE" rev-parse HEAD)"
REF_SHA="$(git -C "$TREE" rev-parse --verify "$REF^{commit}" 2>/dev/null || echo "?")"
STAMP="$OUTPUT_DIR/BUILD-SHA.txt"
{
  echo "sha        = $HEAD_SHA"
  echo "ref        = $REF"
  echo "ref_sha    = $REF_SHA"
  echo "khop_main  = $([ "$verdict" -eq 0 ] && echo "KHỚP" || echo "KHÔNG — xuất bằng --du-biet")"
  echo "cay        = $TREE"
  echo "platform   = $PLATFORM"
} > "$STAMP"
cat "$STAMP"
echo
echo "Bundle: $OUTPUT_DIR"
[ "$verdict" -eq 0 ] || exit 1
