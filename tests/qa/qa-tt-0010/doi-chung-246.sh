#!/usr/bin/env bash
#
# Re-runnable counter-check for PR #246 ("cổng lint chấm bằng bản ruff đã ghim").
#
# ## Why this file exists
#
# A PR that says "I closed hole X" is a claim, not evidence. The only thing that
# turns it into evidence is: break the fix, watch the gate go red, restore it,
# watch it go green -- and separately confirm the red is for the RIGHT reason.
# This repo has been burned twice by a mutation table that was red everywhere:
# once because the mutation raised NameError (40 red cases, gate still blind),
# once because the red came from an incidental constant rather than the property.
# So this table has a control row that must stay GREEN.
#
# Usage:
#   tests/qa/qa-tt-0010/doi-chung-246.sh <đường-dẫn-cây-đã-gộp-#246>
#
# It never writes outside the tree it is pointed at, and it restores every file
# it mutates before exiting, including on failure.
#
# Exit 0 = every row landed where it should. Exit 1 = at least one row moved,
# which means the conclusion in docs/claude/2026-08-30/qa-tt-0010-*.md no longer
# describes this tree.

set -uo pipefail

TREE="${1:-}"
if [ -z "$TREE" ] || [ ! -d "$TREE/.git" ] && [ ! -f "$TREE/.git" ]; then
  echo "dùng: $0 <đường-dẫn-cây-đã-gộp-#246>" >&2
  exit 2
fi
cd "$TREE" || exit 2

for f in scripts/ruff_pinned.sh scripts/ruff_changed.sh tests/test_ruff_pinned.py; do
  if [ ! -f "$f" ]; then
    echo "::error::$f không có trong $TREE -- cây này chưa gộp #246, bảng dưới sẽ vô nghĩa" >&2
    exit 2
  fi
done

if ! git diff --quiet; then
  echo "::error::$TREE có thay đổi chưa commit -- đo trên cây bẩn thì không quy được kết quả về SHA nào" >&2
  exit 2
fi

BAN_DAU="$(git rev-parse HEAD)"
echo "đo tại $BAN_DAU"
echo

fails=0
restore() { git checkout -- scripts/ruff_pinned.sh scripts/ruff_changed.sh 2>/dev/null || true; }
trap restore EXIT

# Only this file's cases; the rest of the suite is the job of `make gate`.
chay_bo_test() {
  python3 -m pytest tests/test_ruff_pinned.py -q 2>&1 | tail -1
}

ghi() { # <nhãn> <mong đợi: DO|XANH> <dòng tổng kết pytest>
  local nhan="$1" mong="$2" dong="$3" thuc
  case "$dong" in
    *failed*) thuc=DO ;;
    *passed*) thuc=XANH ;;
    *)        thuc=KHONG_DOC_DUOC ;;
  esac
  if [ "$thuc" = "$mong" ]; then
    printf '  ĐÚNG   %-52s %s   (%s)\n' "$nhan" "$thuc" "$dong"
  else
    printf '  SAI    %-52s %s, mong %s   (%s)\n' "$nhan" "$thuc" "$mong" "$dong"
    fails=$((fails + 1))
  fi
}

echo "== Bảng đột biến =="

# Row 1 -- remove the property. The pre-#246 ruff_changed.sh takes whatever ruff
# is first on PATH, so a shim that answers "All checks passed!" gets to decide.
#
# The anchor is derived, not named. The first draft of this file wrote
# `git show origin/main:scripts/ruff_changed.sh`, which was the pre-fix version
# right up to the moment #246 landed on main -- after that the "mutation" was
# restoring the file to itself, and the row reported XANH while announcing it had
# removed the property. It was the control row that caught it: a table whose rows
# are all supposed to be red cannot notice a mutation that never happened.
#
# So: find the commit that ADDED the resolver and step back one. That survives a
# squash merge, which rewrites the SHA but not the fact that the file is new in it.
THEM_VAO="$(git log --diff-filter=A --format=%H -- scripts/ruff_pinned.sh | tail -1)"
if [ -z "$THEM_VAO" ]; then
  echo "::error::không tìm được commit thêm scripts/ruff_pinned.sh -- không có mốc trước-bản-sửa" >&2
  exit 2
fi
TRUOC="$THEM_VAO^"
if ! git show "$TRUOC:scripts/ruff_changed.sh" > /tmp/.qa-tt-0010-truoc.sh 2>/dev/null; then
  echo "::error::không đọc được scripts/ruff_changed.sh tại $TRUOC" >&2
  exit 2
fi
# Refuse rather than mislabel: if the anchor already carries the fix, the row
# below measures nothing and must not be printed as though it did.
if grep -q "ruff_pinned" /tmp/.qa-tt-0010-truoc.sh; then
  echo "::error::mốc $TRUOC đã chứa bản sửa -- hàng 'bỏ tính chất' sẽ không đột biến gì" >&2
  rm -f /tmp/.qa-tt-0010-truoc.sh
  exit 2
fi
cp /tmp/.qa-tt-0010-truoc.sh scripts/ruff_changed.sh
rm -f /tmp/.qa-tt-0010-truoc.sh
echo "  (mốc trước bản sửa: $TRUOC)"
ghi "bỏ tính chất (ruff_changed.sh về bản trước #246)" DO "$(chay_bo_test)"
restore

# Row 2 -- the control. Change a constant while KEEPING the property: the cache
# lives somewhere else, the resolver still resolves the pin. A gate that goes red
# here is red for a reason that has nothing to do with what it claims to guard,
# and row 1's red would prove nothing.
sed -i 's|/mobile-gate/ruff"|/mobile-gate-doi-chung-qa-tt-0010/ruff"|' scripts/ruff_pinned.sh
ghi "GIỮ tính chất, đổi hằng số (thư mục cache khác)" XANH "$(chay_bo_test)"
restore

echo
echo "== Hai biên của tính chất, đo trực tiếp =="

# The guarantee is worth stating precisely, because it is narrower than the PR
# wording suggests: what is enforced is "the binary that REPORTS the pinned
# version produces the verdict". A shim lying about --version is accepted. That
# is not a defect -- no version check can catch a lying binary -- but a reader
# who thinks the pinned BINARY is guaranteed is reading more than is there.
SHIM="$(mktemp -d)"
cat > "$SHIM/ruff" <<'SHIMEOF'
#!/usr/bin/env bash
if [ "$1" = "--version" ]; then echo "ruff 0.9.2"; exit 0; fi
echo "All checks passed!"; exit 0
SHIMEOF
chmod +x "$SHIM/ruff"
BAN="services/api/app/domain/place_search.py"
printf '# doi-chung qa-tt-0010\n' >> "$BAN"
PATH="$SHIM:$PATH" bash scripts/ruff_changed.sh HEAD >/dev/null 2>&1
noi_doi=$?
git checkout -- "$BAN"
rm -rf "$SHIM"
if [ "$noi_doi" -eq 0 ]; then
  echo "  BIÊN   shim nói dối đúng số hiệu bản ghim -> LỌT (exit 0), như dự kiến"
else
  echo "  ĐỔI    shim nói dối giờ bị chặn (exit $noi_doi) -- tốt hơn tài liệu, cập nhật báo cáo"
fi

# Provisioning added a dependency the lint stage did not have: a machine with an
# empty cache now needs PyPI. The thing that must hold is that failing to get the
# pin is HỎNG, never a quiet fallback to the wrong version -- the newer ruff is
# sitting right there on PATH and would happily answer.
RONG="$(mktemp -d)"
XDG_CACHE_HOME="$RONG" PIP_INDEX_URL=http://127.0.0.1:9/simple \
  bash scripts/ruff_pinned.sh >/dev/null 2>&1
dong_cua=$?
rm -rf "$RONG"
if [ "$dong_cua" -eq 2 ]; then
  echo "  BIÊN   cache rỗng + không tới được PyPI -> exit 2, không lùi về bản trên PATH"
else
  echo "  SAI    cache rỗng + không tới được PyPI -> exit $dong_cua, mong 2"
  fails=$((fails + 1))
fi

echo
if [ "$fails" -eq 0 ]; then
  echo "TẤT CẢ HÀNG ĐÚNG CHỖ tại $BAN_DAU"
  exit 0
fi
echo "$fails hàng lệch tại $BAN_DAU -- kết luận trong báo cáo không còn mô tả cây này"
exit 1
