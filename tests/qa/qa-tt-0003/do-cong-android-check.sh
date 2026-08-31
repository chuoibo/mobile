#!/usr/bin/env bash
# Đối chứng cho `scripts/android_emulator.sh check` (PR #505).
#
# CÂU HỎI
# -------
# `make android-check` khai nó trả lời "MÁY ẢO CỦA TÔI đã sẵn sàng chưa".
# Câu hỏi của bài đo này: nó có thật sự hỏi về máy của người gọi không, hay nó
# trả lời bằng bất kỳ emulator nào tình cờ đứng đầu `adb devices`?
#
# VÌ SAO PHẢI ĐO BẰNG adb GIẢ
# ---------------------------
# Trên máy tác giả có đúng MỘT emulator, nên lỗi này vô hình. Nó chỉ lòi ra khi
# có HAI máy — đúng tình huống repo này sống trong đó (năm worktree, nhiều lane).
# Dựng hai emulator thật tốn ~2 phút, 4GB RAM và một /dev/kvm; như thế bằng
# chứng chỉ chạy được trên một máy, và bằng chứng chỉ chạy trên một máy thì
# không phải bằng chứng.
#
# Nên ta thay `adb` bằng một bản giả có thể khai bất kỳ đội hình máy ảo nào.
# Ta KHÔNG sửa script đang bị đo một byte nào — `android_emulator.sh` đọc
# `ANDROID_HOME` từ môi trường, đó là cửa do chính nó mở ra.
#
# HAI CANARY, CHẠY MỖI LƯỢT, KHÔNG ĐƯỢC BỎ
# ----------------------------------------
# Một máy đo luôn-xanh và một máy đo luôn-đỏ đều in ra những con số trông hợp lý.
# Nên trước khi tin bất kỳ kết luận nào ở dưới, bài đo này bắt chính nó phải:
#   * ra XANH trên một đội hình lành lặn  (nếu không: máy đo hỏng, không phải sản phẩm sai)
#   * ra ĐỎ  trên một đội hình hỏng      (nếu không: máy đo mù, mọi số xanh vô nghĩa)
# Canary hỏng thì bài đo tự bỏ cuộc và KHÔNG nộp finding nào.
#
# POLARITY
# --------
# Script này khẳng định HÀNH VI ĐÚNG. Trên bản e7644ad nó ĐỎ. Khi devops sửa
# xong, chính nó phải XANH mà không sửa một dòng nào ở đây.
#
# CHẠY
# ----
#   tests/qa/qa-tt-0003/do-cong-android-check.sh
#
# Không cần Android SDK, không cần /dev/kvm, không cần emulator. Chỉ cần bash.
# Đo file `scripts/android_emulator.sh` trong cây hiện tại; nhánh chưa có file
# đó thì đặt SUT_REF trỏ tới ref chứa nó:
#   SUT_REF=origin/devops/emulator-android-tai-lap-duoc tests/qa/qa-tt-0003/do-cong-android-check.sh

set -uo pipefail

# Gốc repo tính từ vị trí CHÍNH file này, không từ thư mục người ta đang đứng và
# không từ một đường tuyệt đối nào. Chạy được từ bất kỳ cwd nào, trên bất kỳ máy nào.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$HERE" rev-parse --show-toplevel 2>/dev/null || printf '%s' "${HERE%/tests/qa/*}")"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# --- lấy đúng bản đang bị đo ---------------------------------------------
SUT="${SUT:-$REPO_ROOT/scripts/android_emulator.sh}"
if [ ! -f "$SUT" ]; then
    REF="${SUT_REF:-origin/devops/emulator-android-tai-lap-duoc}"
    if ! git -C "$REPO_ROOT" show "$REF:scripts/android_emulator.sh" > "$WORK/sut.sh" 2>/dev/null; then
        printf 'BỎ CUỘC: không thấy scripts/android_emulator.sh trong cây, và cũng không\n' >&2
        printf '  đọc được từ ref "%s". Đặt SUT= hoặc SUT_REF= cho đúng.\n' "$REF" >&2
        exit 2
    fi
    SUT="$WORK/sut.sh"
    chmod +x "$SUT"
fi
SUT_ID="$(sha256sum "$SUT" | cut -c1-16)"

# --- SDK giả --------------------------------------------------------------
# Đội hình máy ảo khai qua FAKE_EMUS: "<serial>:<avd>:<boot 0|1>:<api ok|dead>",
# cách nhau bằng khoảng trắng, THEO ĐÚNG THỨ TỰ `adb devices` sẽ in ra.
FAKE_HOME="$WORK/sdk"
mkdir -p "$FAKE_HOME/platform-tools" "$FAKE_HOME/emulator"

cat > "$FAKE_HOME/platform-tools/adb" <<'FAKE_ADB'
#!/usr/bin/env bash
# adb giả: đủ dùng cho android_emulator.sh, không hơn.
set -uo pipefail
field() {  # field <serial> <chỉ số 2..4>
    local e
    for e in ${FAKE_EMUS:-}; do
        IFS=: read -r s a b p <<< "$e"
        if [ "$s" = "$1" ]; then
            case "$2" in 2) printf '%s' "$a";; 3) printf '%s' "$b";; 4) printf '%s' "$p";; esac
            return 0
        fi
    done
    return 1
}

serial=""
if [ "${1:-}" = "-s" ]; then serial="$2"; shift 2; fi
sub="${1:-}"; shift || true

case "$sub" in
  devices)
    echo "List of devices attached"
    for e in ${FAKE_EMUS:-}; do
        IFS=: read -r s _ _ _ <<< "$e"
        printf '%s\tdevice\n' "$s"
    done
    ;;
  emu)
    # `adb -s S emu avd name`
    [ "${1:-} ${2:-}" = "avd name" ] && { field "$serial" 2; echo; echo OK; }
    ;;
  reverse) : ;;
  shell)
    rest="$*"
    case "$rest" in
      "getprop sys.boot_completed")
          [ "$(field "$serial" 3)" = "1" ] && echo 1 ;;
      "getprop init.svc.bootanim")          echo stopped ;;
      "getprop ro.build.version.release")   echo 15 ;;
      "getprop ro.build.version.sdk")       echo 35 ;;
      "pm list packages")                   echo package:host.exp.exponent ;;
      *" nc "*)
          # Trích host+port từ chính dòng lệnh android_emulator.sh dựng ra.
          host="$(sed -E 's/.* nc ([^ ]+) ([0-9]+).*/\1/' <<< "$rest")"
          if [ "$host" = "localhost" ]; then
              # Không cắm adb reverse trong bài đo này -> localhost PHẢI hỏng.
              echo "nc: connect: Connection refused"
          elif [ "$(field "$serial" 4)" = "ok" ]; then
              echo "HTTP/1.1 200 OK"
          fi
          ;;
    esac
    ;;
esac
exit 0
FAKE_ADB

cat > "$FAKE_HOME/emulator/emulator" <<'FAKE_EMU'
#!/usr/bin/env bash
if [ "${1:-}" = "-list-avds" ]; then
    for e in ${FAKE_EMUS:-}; do IFS=: read -r _ a _ _ <<< "$e"; echo "$a"; done
fi
exit 0
FAKE_EMU
chmod +x "$FAKE_HOME/platform-tools/adb" "$FAKE_HOME/emulator/emulator"

# --- cách chạy một ca -----------------------------------------------------
# In ra: "<exit> <số byte đầu ra> <serial script đã đo>"
run_check() {  # run_check <FAKE_EMUS> <RD_AVD>
    local out rc
    out="$(env -u ANDROID_SERIAL \
              ANDROID_HOME="$FAKE_HOME" FAKE_EMUS="$1" RD_AVD="$2" \
              bash "$SUT" check 2>&1)"
    rc=$?
    LAST_OUT="$out"
    LAST_RC=$rc
    LAST_SERIAL="$(sed -n 's/^  serial  *//p' <<< "$out" | head -1)"
}

BANNER() { printf '\n=== %s ===\n' "$*"; }
verdict=0
note() { printf '%s\n' "$*"; }

printf 'đo bản      %s  (sha256[0:16] %s)\n' "$SUT" "$SUT_ID"
printf 'adb thật    KHÔNG dùng — thay bằng adb giả ở %s\n' "$FAKE_HOME"

# Đội hình dùng lại nhiều lần.
LANH="emulator-5554:lane-khac:1:ok"          # máy của lane khác, khoẻ
CUA_TOI_CHUA_BOOT="emulator-5556:rudi-gate:0:ok"   # máy TÔI hỏi, chưa boot xong
CUA_TOI_MAT_MANG="emulator-5556:rudi-gate:1:dead"  # máy TÔI hỏi, boot rồi, không tới được API

# ---------------------------------------------------------------- CANARY --
BANNER "CANARY 1 — đội hình LÀNH, phải XANH"
run_check "$LANH" "lane-khac"
note "  exit=$LAST_RC serial=$LAST_SERIAL"
if [ "$LAST_RC" -ne 0 ]; then
    note "  HỎNG: máy đo không ra nổi màu xanh trên đội hình lành."
    note "  -> Bài đo tự bỏ cuộc. KHÔNG nộp finding nào."
    exit 2
fi
note "  đạt"

BANNER "CANARY 2 — chỉ có máy MẤT MẠNG, phải ĐỎ"
run_check "$CUA_TOI_MAT_MANG" "rudi-gate"
note "  exit=$LAST_RC serial=$LAST_SERIAL"
if [ "$LAST_RC" -eq 0 ]; then
    note "  HỎNG: máy đo in xanh cho một máy không tới được API."
    note "  -> Máy đo mù. Bài đo tự bỏ cuộc, KHÔNG nộp finding nào."
    exit 2
fi
note "  đạt (cắn)"

# Hai canary đã cắn -> từ đây một dấu xanh mới có nghĩa là xanh.

# ------------------------------------------------------------------ CA 1 --
BANNER "CA 1 — máy TÔI hỏi CHƯA BOOT XONG, máy lane khác thì khoẻ"
note "  đội hình : emulator-5554=lane-khac(boot=1)  emulator-5556=rudi-gate(boot=0)"
note "  hỏi      : RD_AVD=rudi-gate"
note "  kỳ vọng  : ĐỎ — máy tôi hỏi chưa boot xong"
run_check "$LANH $CUA_TOI_CHUA_BOOT" "rudi-gate"
note "  thực tế  : exit=$LAST_RC, đo lên serial=$LAST_SERIAL"
if [ "$LAST_RC" -eq 0 ]; then
    note "  LỖI: XANH. Cổng trả lời bằng $LAST_SERIAL (AVD lane-khac) trong khi"
    note "       được hỏi về rudi-gate. rudi-gate còn chưa qua logo."
    verdict=1
else
    note "  đạt"
fi

# ------------------------------------------------------------------ CA 2 --
BANNER "CA 2 — máy TÔI hỏi boot rồi nhưng KHÔNG tới được API"
note "  đội hình : emulator-5554=lane-khac(api ok)  emulator-5556=rudi-gate(api dead)"
note "  hỏi      : RD_AVD=rudi-gate"
note "  kỳ vọng  : ĐỎ — canary 2 đã chứng minh máy đo bắt được đúng ca này"
run_check "$LANH $CUA_TOI_MAT_MANG" "rudi-gate"
note "  thực tế  : exit=$LAST_RC, đo lên serial=$LAST_SERIAL"
if [ "$LAST_RC" -eq 0 ]; then
    note "  LỖI: XANH. Cùng một máy ảo hỏng, cùng một cổng: một mình thì ĐỎ (canary 2),"
    note "       đứng cạnh máy của lane khác thì XANH. Máy hỏng không đổi — chỉ hàng xóm đổi."
    verdict=1
else
    note "  đạt"
fi

# ------------------------------------------------------------------ CA 3 --
BANNER "CA 3 — không có máy nào boot xong: cổng có NÓI gì không"
note "  kỳ vọng  : ĐỎ, kèm chẩn đoán đọc được (script có sẵn câu die)"
run_check "emulator-5556:rudi-gate:0:ok" "rudi-gate"
bytes=${#LAST_OUT}
note "  thực tế  : exit=$LAST_RC, đầu ra $bytes byte"
if [ "$LAST_RC" -ne 0 ] && [ "$bytes" -eq 0 ]; then
    note "  LỖI: ĐỎ nhưng CÂM — 0 byte trên cả stdout lẫn stderr."
    note "       Câu die 'không có máy ảo nào boot xong. Chạy: \$0 up' không tới được"
    note "       người đọc: dưới 'set -e', serial=\$(booted_serial) thất bại là thoát"
    note "       ngay tại dòng gán, trước khi câu die kịp chạy."
    verdict=1
elif [ "$LAST_RC" -eq 0 ]; then
    note "  LỖI: XANH khi không có máy nào boot xong."
    verdict=1
else
    note "  đạt — có chẩn đoán:"; sed 's/^/    | /' <<< "$LAST_OUT"
fi

BANNER "TỔNG"
if [ "$verdict" -eq 0 ]; then
    note "ĐẠT — cổng chỉ trả lời về đúng AVD được hỏi, và nói ra khi không có."
else
    note "KHÔNG ĐẠT — xem các dòng LỖI ở trên."
    note ""
    note "Gốc: cmd_check() và cmd_doctor() gọi booted_serial(), hàm này KHÔNG lọc"
    note "theo AVD — nó trả về emulator đầu tiên có sys.boot_completed=1. Cùng file,"
    note "cmd_down() dùng serial_for_avd() và lọc đúng; phần chú thích ngay trên nó"
    note "mô tả chính lớp lỗi này. Bản vá dừng lại một hàm trước cái cổng."
fi
exit "$verdict"
