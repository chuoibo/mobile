#!/usr/bin/env bash
#
# Cổng `test_money_columns_are_integer_postgres.py` mất gì thì im lặng, mất gì
# thì nổ? Script này trả lời bằng đột biến có hệ thống, không bằng lấy mẫu.
#
# ## Vì sao đo ở CÂU SQL chứ không lọc danh sách trong Python
#
# Nguyên nhân mà chính #493 nêu tên là `information_schema.columns` **lọc theo
# quyền**. Lọc đó làm PHÉP ĐỌC trả về ít dòng hơn. Một phép đo lọc kết quả sau
# khi đọc chỉ kiểm được hàm thuần `_tables_missing_from_read`; đột biến ngay
# trong mệnh đề `where` kiểm cả đường từ database ra tới assertion — tức là
# đúng thứ sẽ hỏng khi một grant biến mất.
#
# ## Hai độ mịn, vì cơ chế có hai độ mịn
#
#   MODE=bang  bỏ một BẢNG khỏi phép đọc, lần lượt đủ 41 bảng
#   MODE=cot   bỏ một CỘT  khỏi phép đọc, lần lượt đủ 287 cột của model
#
# `MODE=cot` là độ mịn THẬT của cơ chế: trong PostgreSQL, quyền SELECT cấp được
# theo từng cột, nên một grant thiếu làm MỘT CỘT rời `information_schema.columns`
# trong khi bảng vẫn còn nguyên trong đó. Đo được bằng:
#
#   grant select (id, ghi_chu) on t to r;   -- cố tình bỏ cột amount_vnd
#   -- role r đọc information_schema.columns: thấy 2 cột, KHÔNG thấy amount_vnd,
#   -- và vẫn thấy bảng t.
#
# ## Hai canary, chạy mỗi lượt, không được bỏ
#
# Trước vòng lặp và sau khi khôi phục, cây pristine phải XANH. Nền đỏ sẵn thì
# mọi con số bên dưới vô nghĩa, và một harness để lại rác sẽ làm cả bảng đọc
# sai. Script tự dừng (mã 2) nếu một trong hai canary không xanh.
#
# Mỗi lượt đột biến còn tự đối chứng rằng bản vá THẬT SỰ vào được file trước khi
# chấm điểm — một đột biến không áp dụng được sẽ in "xanh" y hệt một đột biến bị
# cổng bắt.
#
# ## Cách chạy
#
#   tests/qa/qa-tt-0004/do_phep_doc_mat_gi.sh bang
#   tests/qa/qa-tt-0004/do_phep_doc_mat_gi.sh cot
#
# Tự dựng Postgres dùng một lần rồi tự xoá, KHÔNG đụng `make up` của lane nào.
# Đặt sẵn MOBILE_TEST_DATABASE_URL thì dùng cái đó và không dựng gì.
#
# Mã thoát: 0 chạy xong, 2 không dựng được môi trường hoặc canary hỏng.

set -uo pipefail

MODE="${1:-bang}"
case "$MODE" in bang|cot) ;; *) echo "MODE phải là 'bang' hoặc 'cot'" >&2; exit 2 ;; esac

cd "$(dirname "$0")/../../.." || exit 2
REPO="$PWD"
FILE="$REPO/services/api/tests/postgres/test_money_columns_are_integer_postgres.py"
[ -f "$FILE" ] || { echo "không thấy $FILE" >&2; exit 2; }

WORK="$(mktemp -d)"
PRISTINE="$WORK/pristine.py"
OUT="$WORK/ket-qua.tsv"
CONTAINER=""

cleanup() {
  [ -f "$PRISTINE" ] && cp "$PRISTINE" "$FILE"
  [ -n "$CONTAINER" ] && docker rm -f "$CONTAINER" >/dev/null 2>&1
  rm -rf "$WORK"
}
trap cleanup EXIT INT TERM

# --- database dùng một lần -------------------------------------------------

if [ -n "${MOBILE_TEST_DATABASE_URL:-}" ]; then
  echo "Dùng MOBILE_TEST_DATABASE_URL đã đặt sẵn — không dựng container."
  DSN="$MOBILE_TEST_DATABASE_URL"
else
  command -v docker >/dev/null 2>&1 || { echo "không có docker" >&2; exit 2; }
  IMAGE="${MOBILE_TEST_POSTGRES_IMAGE:-postgres:16-alpine}"
  docker image inspect "$IMAGE" >/dev/null 2>&1 || {
    echo "chưa có ảnh $IMAGE — chạy 'docker pull $IMAGE' một lần" >&2; exit 2; }
  PW="$(head -c 18 /dev/urandom | base64 | tr -d '/+=' | head -c 20)"
  CONTAINER="qa-tt-0004-pg-$$-$(head -c 4 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  docker run -d --rm --name "$CONTAINER" \
    -e POSTGRES_DB=mobile -e POSTGRES_USER=mobile -e POSTGRES_PASSWORD="$PW" \
    -p 127.0.0.1::5432 "$IMAGE" \
    -c fsync=off -c full_page_writes=off -c synchronous_commit=off >/dev/null || {
      echo "không khởi động được container" >&2; exit 2; }
  HP="$(docker port "$CONTAINER" 5432/tcp | head -1)"; HP="${HP##*:}"
  # -h 127.0.0.1: trong lúc initdb, PostgreSQL chạy một server tạm CHỈ nghe unix
  # socket, nên pg_isready không có -h trả "ready" khi cổng TCP còn đóng.
  ready=0
  for _ in $(seq 1 60); do
    docker exec "$CONTAINER" pg_isready -h 127.0.0.1 -U mobile -d mobile >/dev/null 2>&1 && { ready=1; break; }
    sleep 1
  done
  [ "$ready" -eq 1 ] || { echo "container không bao giờ sẵn sàng" >&2; exit 2; }
  DSN="postgresql+psycopg://mobile:${PW}@127.0.0.1:${HP}/mobile"
  echo "database dùng một lần: 127.0.0.1:${HP}"
fi

cp "$FILE" "$PRISTINE"

run_file() {
  # Xoá bytecode: một bản vá cùng cỡ file có thể để .pyc cũ được dùng lại, và
  # cả bảng đột biến sẽ xanh giả.
  find "$REPO/services/api" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null
  (
    cd "$REPO/services/api" || exit 99
    MOBILE_TEST_DATABASE_URL="$DSN" MOBILE_REQUIRE_POSTGRES_TESTS=1 \
      python3 -m pytest tests/postgres/test_money_columns_are_integer_postgres.py \
        -q -p no:cacheprovider --no-header -rf
  ) 2>&1
}

last_line() { printf '%s\n' "$1" | grep -vE '^[[:space:]]*$' | tail -1; }

base_log="$(run_file)"; base_rc=$?
echo "canary NỀN (cây pristine): mã $base_rc — $(last_line "$base_log")"
[ "$base_rc" -eq 0 ] || { echo "NỀN ĐỎ — không đo đột biến trên cây đã đỏ sẵn." >&2; exit 2; }

# --- danh sách nạn nhân, suy từ chính models -------------------------------

python3 - "$MODE" "$WORK/victims.tsv" <<'PY' || exit 2
import sys
sys.path.insert(0, "services/api")
from app.db.models import Base
mode, out = sys.argv[1], sys.argv[2]
with open(out, "w") as f:
    if mode == "bang":
        for t in sorted(Base.metadata.tables):
            f.write(f"{t}\t\n")
    else:
        rows = sorted((t.name, c.name) for t in Base.metadata.sorted_tables for c in t.columns)
        for t, c in rows:
            f.write(f"{t}\t{c}\n")
PY
total_victims="$(wc -l < "$WORK/victims.tsv")"
[ "$total_victims" -gt 0 ] || { echo "danh sách nạn nhân RỖNG — vòng lặp rỗng in xanh." >&2; exit 2; }
echo "sẽ đột biến $total_victims $([ "$MODE" = bang ] && echo bảng || echo cột)"

: > "$OUT"
while IFS=$'\t' read -r tbl col; do
  [ -n "$tbl" ] || continue
  TBL="$tbl" COL="$col" MODE="$MODE" python3 - "$FILE" "$PRISTINE" <<'PY' || exit 2
import os, sys
path, pristine = sys.argv[1], sys.argv[2]
tbl, col, mode = os.environ["TBL"], os.environ["COL"], os.environ["MODE"]
src = open(pristine).read()
needle = "where table_schema = :schema"
assert src.count(needle) == 1, f"không tiêm được: thấy {src.count(needle)} chỗ"
extra = (
    f"and table_name <> '{tbl}'" if mode == "bang"
    else f"and not (table_name = '{tbl}' and column_name = '{col}')"
)
open(path, "w").write(src.replace(needle, f"{needle}\n                  {extra}"))
PY

  # Đối chứng: đột biến phải THẬT SỰ nằm trong file. Một bản vá không áp dụng
  # được in ra "xanh" y hệt một bản vá bị cổng bắt.
  if ! grep -q "table_name = '$tbl'\|table_name <> '$tbl'" "$FILE"; then
    echo "ĐỘT BIẾN KHÔNG VÀO ĐƯỢC FILE tại $tbl.$col" >&2; exit 2
  fi

  log="$(run_file)"; rc=$?
  failed="$(printf '%s' "$log" | grep -oE '^FAILED [^ ]+' | sed 's#^FAILED .*::##; s/\[.*//' | sort -u | paste -sd, -)"
  [ -n "$failed" ] || failed="-"
  printf '%s\t%s\t%s\t%s\n' "$tbl" "$col" "$rc" "$failed" >> "$OUT"
  [ "$rc" -eq 0 ] && printf 'LỌT  %-30s %s\n' "$tbl" "$col"

  cp "$PRISTINE" "$FILE"
done < "$WORK/victims.tsv"

cp "$PRISTINE" "$FILE"
end_log="$(run_file)"; end_rc=$?
echo "canary CUỐI (đã khôi phục): mã $end_rc — $(last_line "$end_log")"
[ "$end_rc" -eq 0 ] || { echo "KHÔI PHỤC HỎNG — bảng ở trên không dùng được." >&2; exit 2; }

ran="$(wc -l < "$OUT")"
[ "$ran" -eq "$total_victims" ] || {
  echo "chạy $ran / $total_victims — vòng lặp đứt giữa chừng, không kết luận." >&2; exit 2; }

echo
echo "=== $MODE — trên $ran nạn nhân"
echo "    LỌT (mã 0, không ca nào đỏ): $(awk -F'\t' '$3==0' "$OUT" | wc -l)"
echo "    BỊ BẮT                     : $(awk -F'\t' '$3!=0' "$OUT" | wc -l)"
if [ "$MODE" = cot ]; then
  echo "    trong đó cột TÊN TIỀN (_vnd / *amount*):"
  echo "      tổng $(awk -F'\t' '$2 ~ /_vnd$|amount/' "$OUT" | wc -l) — lọt $(awk -F'\t' '$2 ~ /_vnd$|amount/ && $3==0' "$OUT" | wc -l)"
fi
echo
echo "chi tiết từng nạn nhân:"
awk -F'\t' '{printf "  %-28s %-26s mã=%s  %s\n", $1, $2, $3, $4}' "$OUT"
