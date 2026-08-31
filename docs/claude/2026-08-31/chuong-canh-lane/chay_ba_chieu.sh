#!/usr/bin/env bash
# Re-runnable test rig for the Lead's lane bell (the Monitor loop that prints
# RỖI HẲN / KẸT READY / SẮP RỖI / ĐỢI HẠN MỨC).
#
# The bell under test is chuong_goc.sh, copied byte-for-byte out of the Lead's
# session transcript. The ONE edit this rig makes is the root path -- line 1,
# `R=...` -- so the bell reads a sandbox instead of the live harness. Nothing
# else is touched; `diff` proves it (printed below). Modifying the thing under
# test to make it pass is the failure mode this rig exists to avoid.
#
#   ./chay_ba_chieu.sh          fast cases only (~15s)
#   ./chay_ba_chieu.sh --cham   adds the two timed cases (~2.5 min): the real
#                               clock crossing the 10-minute threshold, and the
#                               repeat check over three passes
#
# Exit code 0 = every expectation held, 1 = at least one did not.
set -u
cd "$(dirname "$0")" || exit 2

GOC="$PWD/chuong_goc.sh"
DUNG="$PWD/dung_ca.py"
SHA_MONG_DOI="0287cd9bf5ac8899209b0bc242e3163b8c90b732521697931b32620317ed9e63"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

sha_thuc=$(sha256sum "$GOC" | cut -d' ' -f1)
echo "chuông đang kiểm: chuong_goc.sh sha256=$sha_thuc"
if [ "$sha_thuc" != "$SHA_MONG_DOI" ]; then
  echo "  !! KHÁC bản đã trích từ transcript ($SHA_MONG_DOI) — kết luận dưới đây"
  echo "     nói về một cái chuông khác. Dừng."
  exit 2
fi

# The single edit, made here rather than committed, so the copy on disk stays
# provably identical to what the Lead is running.
sed 's|^R=/home/lakiet/agent-harness$|R="${SANDBOX:?}"|' "$GOC" > "$TMP/chuong.sh"
echo "sửa đúng một dòng để trỏ vào hộp cát:"
diff "$GOC" "$TMP/chuong.sh" | sed 's/^/  /'

hong=0
# ca <tên> <kỳ vọng: CO|KHONG> <chuỗi phải có/không có> <lane> <state> <tuổi phút> <assigned> <done> [bug_filed]
ca() {
  local ten=$1 kyvong=$2 chuoi=$3; shift 3
  local dir="$TMP/$ten"; mkdir -p "$dir/state/lanes"
  local mota; mota=$(python3 "$DUNG" "$dir" "$@")
  local out; out=$(SANDBOX="$dir" timeout 8 bash "$TMP/chuong.sh" 2>&1)
  local thay="KHONG"
  case "$out" in *"$chuoi"*) thay="CO";; esac
  local dau="ĐẠT"
  if [ "$thay" != "$kyvong" ]; then dau="HỎNG"; hong=$((hong + 1)); fi
  printf '\n[%s] %s\n' "$dau" "$ten"
  printf '   dựng   : %s\n' "$mota"
  printf '   mong   : %s "%s"\n' "$kyvong" "$chuoi"
  if [ -z "$out" ]; then printf '   chuông : (IM LẶNG)\n'; else
    printf '%s\n' "$out" | sed 's/^/   chuông : /'; fi
}

echo
echo "═══ CHIỀU 1 — READY lâu mà vẫn còn việc thì PHẢI kêu ═══"
# The shape of the real incident: qa2 held READY 41.5 minutes on 2026-08-31
# (events.jsonl: 06:50:17 BUSY->READY, 07:31:47 READY->BUSY).
ca "C2-READY-41-phut-nhu-su-that" CO    "KẸT READY" qa2 READY 41.5 1 0
ca "C3-doi-chung-am-READY-9-phut" KHONG "KẸT READY" qa2 READY 9    1 0

echo
echo "═══ CHIỀU 2 — RATE_LIMITED thì KHÔNG được giục giao việc ═══"
ca "C4a-RATE-LIMITED-moi"    CO    "ĐỢI HẠN MỨC" qa2 RATE_LIMITED 1  5 0
ca "C4b-RATE-LIMITED-moi"    KHONG "giao việc"   qa2 RATE_LIMITED 1  5 0
ca "C4c-RATE-LIMITED-40-phut" KHONG "nạp thêm"   qa2 RATE_LIMITED 40 5 0

echo
echo "═══ CHIỀU 3 — BUSY bình thường thì KHÔNG được kêu gì cả ═══"
ca "C5a-BUSY-con-2-viec" KHONG "SẮP RỖI" qa2 BUSY 3 2 0
ca "C5b-BUSY-con-1-viec" KHONG "SẮP RỖI" qa2 BUSY 3 1 0
ca "C5c-BUSY-con-0-viec" KHONG "SẮP RỖI" qa2 BUSY 3 1 1

echo
echo "═══ Hàng đợi mà chuông KHÔNG nhìn thấy ═══"
# `bug-to` emits BUG_FILED and files a P0 into the inbox. That is real queued
# work, and the bell's PEND only counts events whose type contains "ASSIGN".
ca "C7-READY-3-phut-CO-3-loi-P0" KHONG "hàng đợi TRỐNG" qa2 READY 3  0 0 3
ca "C6-READY-11-phut-CO-3-loi-P0" KHONG "hàng đợi còn 0" qa2 READY 11 0 0 3

echo
echo "═══ CANARY — chứng minh 'IM LẶNG' ở trên là đọc thật, không phải trỏ sai ═══"
# Same directory as C5a, which was silent. Change ONLY the state; if the rig
# were pointing at nothing, this would stay silent too.
canary="$TMP/C5a-BUSY-con-2-viec"
python3 "$DUNG" "$canary" qa2 READY 41 2 0 >/dev/null
out=$(SANDBOX="$canary" timeout 8 bash "$TMP/chuong.sh" 2>&1)
case "$out" in
  *"KẸT READY"*) echo "[ĐẠT] canary: cùng thư mục, chỉ đổi state -> chuông kêu"
                 echo "   chuông : $out";;
  *) echo "[HỎNG] canary: đổi state mà chuông vẫn im — hộp cát không được đọc"
     hong=$((hong + 1));;
esac

if [ "${1:-}" = "--cham" ]; then
  echo
  echo "═══ CHẬM — đồng hồ THẬT vượt mốc 10 phút trong lúc chuông đang chạy ═══"
  d="$TMP/C1-vuot-nguong"; mkdir -p "$d/state/lanes"
  python3 "$DUNG" "$d" qa2 READY 9.3 2 0 | sed 's/^/   dựng   : /'
  echo "   (PEND=2 nên trước mốc phải im hẳn; chạy 150s = 3 lượt)"
  log="$TMP/c1.log"
  SANDBOX="$d" timeout 150 bash "$TMP/chuong.sh" 2>&1 |
    while IFS= read -r l; do echo "$(date +%H:%M:%S) $l"; done > "$log"
  if grep -q "KẸT READY" "$log"; then
    echo "[ĐẠT] chuông kêu khi tuổi vượt 10 phút:"; sed 's/^/   /' "$log"
  else
    echo "[HỎNG] chạy 150s qua mốc mà chuông không kêu"; hong=$((hong + 1))
  fi
  n=$(grep -c "KẸT READY" "$log")
  echo "   số lần kêu trong 3 lượt: $n (1 là đúng — không lụt)"

  echo
  echo "═══ CHẬM — RATE_LIMITED qua 3 lượt có giục lại không ═══"
  d2="$TMP/C4r"; mkdir -p "$d2/state/lanes"
  python3 "$DUNG" "$d2" qa2 RATE_LIMITED 2 5 0 | sed 's/^/   dựng   : /'
  log2="$TMP/c4r.log"
  SANDBOX="$d2" timeout 150 bash "$TMP/chuong.sh" 2>&1 > "$log2"
  n2=$(grep -c . "$log2")
  if [ "$n2" -eq 1 ]; then echo "[ĐẠT] đúng 1 dòng trong 3 lượt, không nhắc lại"
  else echo "[HỎNG] $n2 dòng trong 3 lượt"; hong=$((hong + 1)); fi
  sed 's/^/   /' "$log2"
fi

echo
if [ "$hong" -eq 0 ]; then echo "TỔNG: mọi kỳ vọng đều đúng"; else
  echo "TỔNG: $hong kỳ vọng KHÔNG đúng"; fi
exit $((hong > 0))
