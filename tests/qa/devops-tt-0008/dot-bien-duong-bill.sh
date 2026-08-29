#!/usr/bin/env bash
# Chặng `e2e` có thật sự gác bước bill không, hay chỉ đang xanh?
#
# `apps/mobile/tests/e2e/duong-bill.test.mjs` xanh ngay từ lượt chạy đầu, vì
# đường bill trên `main` đang chạy đúng. Một cổng xanh ngay từ đầu không
# chứng minh được gì -- CLAUDE.md gọi đúng tên nó là đồ trang trí. Script này
# là phần sống sót của phép đỏ-trước: chạy lại được, nên câu "bước bill đã
# được gác" còn kiểm được sau khi có người sửa client sáu tuần nữa.
#
# Sáu hàng, và hàng cuối mới là hàng khó.
#
#   Năm hàng đầu phải ĐỎ, mỗi hàng ở một tầng khác nhau của cùng một đường:
#   bảo vệ phía máy chủ (#247), động từ HTTP, thân request, khoá idempotency,
#   và nhãn "đây là phỏng đoán". Đỏ thôi chưa đủ -- mỗi hàng còn khai báo ca
#   test nào phải đỏ, vì một đột biến làm đỏ NHẦM ca đọc y hệt một cổng tốt.
#
#   Hàng `thứ tự ids bị đảo` phải XANH. Một bảng mà mọi hàng đều đỏ thì không
#   phân biệt được "cổng chạy" với "cổng hàn dính vào một chi tiết tình cờ".
#   Hàng này đổi thứ tự client gửi mà không đổi ai được gán món; đỏ ở đây
#   nghĩa là test ghim vào thứ tự mảng chứ không ghim vào ai ăn món nào.
#
# Cái bẫy script này phải tự tránh: trong `src/bill.ts` chuỗi
# `participant_ids:` là hậu tố của `suggested_participant_ids:`, và
# `suggested_...` đứng TRƯỚC trong file. Một `str.replace(old, new, 1)` sẽ vá
# nhầm hàm rồi báo cáo tự tin. Nên mọi anchor ở đây bị đếm, và khớp != 1 là
# một lần hỏng có tiếng, không phải một lần vá im lặng.
#
# Chạy từ đâu cũng được. `scripts/e2e_slice.sh` tự dựng API + PostgreSQL dùng
# một lần rồi tự xoá, nên không đụng máy demo 8099 và không cần biến môi
# trường nào. Khôi phục cây sau mỗi mutant -- commit phải có trước, vì
# `git checkout --` ném luôn bản sửa chưa commit đi cùng với đột biến.
set -uo pipefail

cd "$(dirname "$0")/../../.." || exit 1

SERVICE=services/api/app/api/service.py
API=apps/mobile/src/api.ts
BILL=apps/mobile/src/bill.ts
TARGETS=("$SERVICE" "$API" "$BILL")

for t in "${TARGETS[@]}"; do
  if ! git diff --quiet -- "$t"; then
    echo "REFUSING: $t đang có thay đổi chưa commit; commit trước đã." >&2
    exit 1
  fi
done

restore() {
  git checkout -- "${TARGETS[@]}" 2>/dev/null
  # Bytecode cũ sống sót qua `git checkout` và làm cây sạch chạy như cây đột
  # biến. Đã mất một lượt vì đúng chuyện này.
  find services/api -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null
}
trap restore EXIT

LAST_FAILED=""

# Chạy cổng, trả 0 nếu XANH. Chỉ đọc dòng tổng kết TAP và các dòng `not ok`:
# grep cả output sẽ đọc trúng một docstring có chữ "passed" trong đó.
run_gate() {
  local out rc tests fails
  out=$(bash scripts/e2e_slice.sh 2>&1)
  rc=$?
  tests=$(printf '%s\n' "$out" | sed -n 's/^# tests \([0-9]*\)$/\1/p' | tail -n 1)
  fails=$(printf '%s\n' "$out" | sed -n 's/^# fail \([0-9]*\)$/\1/p' | tail -n 1)
  LAST_FAILED=$(printf '%s\n' "$out" | sed -n 's/^not ok [0-9]* - //p' | paste -sd'|' -)

  if [ -z "$tests" ]; then
    # Không có TAP nghĩa là API/DB chưa dựng nổi. Đó là một lần đỏ KHÔNG nói
    # gì về cổng, và đọc thành "cổng bắt được" là tự lừa mình.
    printf '    rc=%d  KHÔNG CÓ TAP — không dựng được API/DB, kết quả vô nghĩa\n' "$rc"
    LAST_FAILED="<setup-failed>"
    return 2
  fi
  printf '    rc=%d  tests=%s fail=%s  [%s]\n' "$rc" "$tests" "$fails" "${LAST_FAILED:-không có ca nào đỏ}"
  [ "$fails" = "0" ]
}

FAILURES=0

# <tên> <file> <patcher-python> <kỳ vọng red|green> <ca phải đỏ, rỗng nếu green>
mutant() {
  local name=$1 target=$2 patcher=$3 want=$4 want_case=${5:-}
  echo "== $name"
  python3 - "$target" <<PY || { echo "    VÁ HỎNG"; restore; FAILURES=$((FAILURES + 1)); return 1; }
import sys, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text()
$patcher
p.write_text(s)
PY
  if git diff --quiet -- "$target"; then
    echo "    VÁ KHÔNG ĐỔI GÌ — đột biến chưa từng áp dụng, số ở dưới vô nghĩa"
    restore
    FAILURES=$((FAILURES + 1))
    return 1
  fi

  local state
  if run_gate; then state=green; else state=red; fi
  restore

  if [ "$state" != "$want" ]; then
    echo "    TRẬT  $state (muốn $want)"
    FAILURES=$((FAILURES + 1))
    return 1
  fi
  if [ -n "$want_case" ] && [[ "$LAST_FAILED" != *"$want_case"* ]]; then
    echo "    TRẬT  đỏ nhưng SAI CA: muốn ca chứa \"$want_case\", đỏ ở [$LAST_FAILED]"
    FAILURES=$((FAILURES + 1))
    return 1
  fi
  echo "    ĐÚNG  $state"
}

# Anchor phải khớp đúng một lần. Đây là phần chống vá-nhầm-bản-sao.
only() {
  cat <<'PY'
def once(s, anchor):
    n = s.count(anchor)
    if n != 1:
        raise SystemExit(f"anchor khớp {n} lần, cần đúng 1: {anchor!r}")
    return n
PY
}

echo "# nền — cây sạch phải XANH, nếu không thì mọi hàng dưới đây vô nghĩa"
if run_gate; then
  echo "    ĐÚNG  green"
else
  echo "    TRẬT  cây sạch đã đỏ sẵn; dừng."
  exit 1
fi
echo

mutant "máy chủ bỏ kiểm thành viên khi gán món (đảo #247)" "$SERVICE" "$(
  only
  cat <<'PY'
anchor = """        self._require_participants_are_members(
            record.context_id,
            [
                participant_id
                for assignment in request.assignments
                for participant_id in assignment.participant_ids
            ],
        )
"""
once(s, anchor)
s = s.replace(anchor, "")
PY
)" red "người ngoài nhóm"

mutant "client gửi POST thay vì PUT khi lưu gán món" "$API" "$(
  only
  cat <<'PY'
anchor = """  return call<BillWire>(`/bills/${billId}/assignments`, {
    method: "PUT","""
once(s, anchor)
s = s.replace(anchor, anchor.replace('"PUT"', '"POST"'))
PY
)" red "mang tên người trong nhóm"

mutant "thân request lưu gán món về rỗng (ticks bay mất)" "$BILL" "$(
  only
  cat <<'PY'
anchor = """      item_key: line.id,
      participant_ids: whoOn(assignment, line.id),"""
once(s, anchor)
s = s.replace(anchor, """      item_key: line.id,
      participant_ids: [],""")
PY
)" red "mang tên người trong nhóm"

mutant "taoBill mint khoá mới mỗi lần bấm (mất idempotency)" "$API" "$(
  only
  cat <<'PY'
anchor = """  return call<BillWire>("/bills", {
    body: billCreateBody(reading, contextId, assignment),
    actorId,
    attempt,"""
once(s, anchor)
s = s.replace(anchor, anchor.replace("    attempt,", "    attempt: newAttempt(),"))
PY
)" red "bấm hai lần"

mutant "bill tạo ra không mang gợi ý nào của AI" "$BILL" "$(
  only
  cat <<'PY'
anchor = "    suggested_participant_ids: whoOn(assignment, line.id),"
once(s, anchor)
s = s.replace(anchor, "    suggested_participant_ids: [],")
PY
)" red "mang tên người trong nhóm"

# Hàng chứng minh cổng không hàn dính vào thứ tự mảng. Cùng những người đó,
# gửi ngược thứ tự. Tính chất "ai ăn món nào" không đổi, nên phải XANH.
mutant "GIỮ TÍNH CHẤT: đảo thứ tự ids client gửi lên" "$BILL" "$(
  only
  cat <<'PY'
anchor = """      item_key: line.id,
      participant_ids: whoOn(assignment, line.id),"""
once(s, anchor)
s = s.replace(anchor, """      item_key: line.id,
      participant_ids: [...whoOn(assignment, line.id)].reverse(),""")
PY
)" green

echo
if [ "$FAILURES" -eq 0 ]; then
  echo "TẤT CẢ 6 HÀNG ĐÚNG NHƯ THIẾT KẾ."
else
  echo "$FAILURES HÀNG TRẬT."
fi
exit "$FAILURES"
