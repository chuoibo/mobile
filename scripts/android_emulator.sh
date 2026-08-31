#!/usr/bin/env bash
# Dựng emulator Android headless và CHỨNG MINH nó dùng được — không chỉ "đã bật".
#
# Vì sao script này tồn tại
# -------------------------
# Ngày 01/09 máy này đang có một emulator chạy tốt, Expo Go đã cài, app hiện dữ
# liệu thật. Nhưng toàn bộ trạng thái đó nằm trong MỘT shell tiền cảnh của một
# phiên khác, cộng hai lệnh gõ tay không ghi ở đâu cả:
#
#     EXPO_PUBLIC_API_URL=http://localhost:8199 ...     (biến môi trường của Metro)
#     adb reverse tcp:8199 tcp:8199                      (đường hầm trong adb server)
#
# Phiên đó kết thúc là mất cả ba. Người sau đọc README, chạy `expo start
# --android`, và nhận "Không nối được http://localhost:8099" mà không hiểu vì sao
# hôm qua nó chạy. Đây là script để chuyện đó không xảy ra lần nữa.
#
# BA ĐIỀU ĐO ĐƯỢC, KHÔNG PHẢI BA LỜI HỨA
#
#   1. Máy ảo BOOT XONG — `sys.boot_completed` = 1, không phải "tiến trình còn
#      sống". Một qemu treo ở logo cũng có tiến trình sống, cũng có `adb devices`
#      in ra một dòng. Hai dấu hiệu đó không phân biệt được máy đã boot với máy
#      chết cứng; `sys.boot_completed` thì có.
#   2. API tới được TỪ BÊN TRONG máy ảo, đo bằng một request thật đi hết đường,
#      không phải bằng `curl` trên host. Host với emulator là hai ngăn mạng khác
#      nhau — xem phần dưới.
#   3. Bấm được — một cú tap thật làm tab đang chọn đổi.
#
# CÁI BẪY LỚN NHẤT: `localhost` trong emulator KHÔNG phải máy của bạn
#
# Trong emulator, `localhost` là chính máy ảo. Máy chủ của bạn nằm ở
# `10.0.2.2` — địa chỉ cố định mà QEMU dành riêng cho host. Đo thật, cùng một
# lúc, cùng một API:
#
#     từ HOST      localhost:8099 -> 200        localhost:8199 -> 200
#     từ EMULATOR  localhost:8099 -> Connection refused
#                  10.0.2.2:8099  -> 200
#
# Nên mặc định `http://localhost:8099` trong apps/mobile/src/api.ts chạy trên web
# và CHẾT trên native. Nó không đỏ ở đâu cả: web xanh, test xanh, bundle dựng
# được. Chỉ người cầm điện thoại mới thấy.
#
# `adb reverse tcp:8199 tcp:8199` vá được (nó mở 8199 bên trong máy ảo và bắc
# sang host), nhưng nó là trạng thái VÔ HÌNH: không nằm trong repo, không sống
# qua lần adb restart, và `adb devices` không hề nhắc tới nó. Script này dùng
# 10.0.2.2 — đi thẳng, không cần đường hầm nào — rồi mới cài thêm reverse cho
# Metro (8081) vì cái đó thì Expo thật sự cần.
#
# CÁI SCRIPT NÀY KHÔNG CHỨNG MINH
#
#   * Không chứng minh app ĐÚNG. Nó chứng minh app CHẠY và GỌI ĐƯỢC máy chủ.
#   * Không chứng minh trên máy thật. Emulator x86_64 khác điện thoại ARM ở
#     codec, camera, hiệu năng và quyền.
#   * Không chứng minh mã QR quét được bằng app ngân hàng.
set -euo pipefail

ANDROID_HOME="${ANDROID_HOME:-$HOME/Android/Sdk}"
ADB="$ANDROID_HOME/platform-tools/adb"
EMULATOR="$ANDROID_HOME/emulator/emulator"
AVDMANAGER="$ANDROID_HOME/cmdline-tools/latest/bin/avdmanager"

AVD_NAME="${RD_AVD:-rudi}"
SYSTEM_IMAGE="${RD_SYSTEM_IMAGE:-system-images;android-35;google_apis;x86_64}"
API_PORT="${RD_API_PORT:-8199}"
METRO_PORT="${RD_METRO_PORT:-8081}"
BOOT_TIMEOUT="${RD_BOOT_TIMEOUT:-300}"
# Địa chỉ host nhìn từ trong máy ảo. Hằng số của QEMU, không phải cấu hình.
HOST_FROM_GUEST=10.0.2.2

say() { printf '%s\n' "$*"; }
die() { printf 'HỎNG: %s\n' "$*" >&2; exit 1; }

# argv NGUYÊN BẢN, giữ trước mọi `shift`. `ensure_kvm` chạy lại chính script
# dưới `sg kvm`, và lần chạy lại đó phải nhận đúng dòng lệnh người ta đã gõ.
#
# Đo được lúc 00:31 ngày 01/09: bản trước truyền `"$@"` của hàm gọi, tức argv
# ĐÃ shift mất tên lệnh con. `up` biến thành rỗng, rơi vào mặc định `check`,
# và script in một bảng xanh đầy đủ trong 5 giây mà không hề dựng máy nào.
# Thoát 0, không một dòng cảnh báo — dạng hỏng tệ nhất: im lặng và trông đúng.
RD_ARGV=("$@")

# --- /dev/kvm -------------------------------------------------------------
#
# Phân biệt hai thứ mà `id` gộp làm một, vì cách sửa KHÁC HẲN nhau:
#
#   (a) chưa ai chạy usermod  -> phải có sudo, phải phiền leader
#   (b) đã chạy usermod rồi, nhưng tiến trình này sinh ra TRƯỚC lúc đó
#
# Nhóm phụ được đóng vào tiến trình lúc đăng nhập và không bao giờ tự cập nhật.
# Nên ở (b) `/etc/group` đã đúng trong khi `id` vẫn thiếu, và người đọc `id` sẽ
# kết luận sai là "chưa cài" rồi đi xin quyền sudo không cần thiết.
#
# Đo thật trên máy này lúc 00:22 ngày 01/09:
#     getent group kvm  ->  kvm:x:993:lakiet      (đã có tên)
#     id                ->  ...,989(docker)       (KHÔNG có 993)
#     open('/dev/kvm')  ->  PermissionError 13
#
# `sg kvm -c ...` đọc lại /etc/group nên gỡ được (b) ngay, không cần đăng xuất,
# không cần sudo, không hỏi mật khẩu.
kvm_ready() { [ -r /dev/kvm ] && [ -w /dev/kvm ]; }

kvm_in_etc_group() {
    getent group kvm 2>/dev/null | awk -F: -v u="$(id -un)" \
        '{n=split($4,m,","); for(i=1;i<=n;i++) if (m[i]==u) found=1} END{exit !found}'
}

# Tự chạy lại chính mình dưới nhóm kvm. RD_SG_REEXEC chặn đệ quy vô hạn: nếu
# sau khi đổi nhóm mà vẫn không mở được /dev/kvm thì đó là lỗi khác, phải báo
# ra chứ không được quay vòng.
ensure_kvm() {
    if kvm_ready; then return 0; fi
    if [ "${RD_SG_REEXEC:-0}" = "1" ]; then
        die "đã chạy lại dưới nhóm kvm mà vẫn không mở được /dev/kvm.
  Không phải chuyện nhóm phụ. Kiểm: lsmod | grep kvm  ·  ls -l /dev/kvm"
    fi
    if ! [ -e /dev/kvm ]; then
        die "máy này không có /dev/kvm — không có ảo hoá phần cứng.
  Trong WSL2 cần kernel bật KVM. Không có nó thì emulator chậm tới mức vô dụng."
    fi
    if kvm_in_etc_group; then
        say "  /dev/kvm: chưa mở được, NHƯNG $(id -un) đã có trong nhóm kvm ở"
        say "  /etc/group. Đây là tiến trình cũ giữ nhóm phụ cũ, không phải thiếu"
        say "  quyền. Chạy lại chính mình dưới 'sg kvm' — không cần sudo."
        RD_SG_REEXEC=1 exec sg kvm -c "$(printf '%q ' "$0" "${RD_ARGV[@]}")"
    fi
    die "$(id -un) chưa nằm trong nhóm kvm. Cần một lần sudo:
      sudo usermod -aG kvm $(id -un)
  Rồi chạy lại lệnh này — script tự dùng 'sg kvm', KHÔNG cần đăng xuất."
}

# --- adb ------------------------------------------------------------------

# Serial của máy ảo đang boot xong. In ra rỗng nếu không có cái nào.
#
# ANDROID_SERIAL được tôn trọng và CHỈ nó được xét khi đã đặt. Máy này chạy năm
# worktree của cùng một repo và có lúc hai emulator cùng sống; "lấy cái đầu
# danh sách" thì lane A đo lên máy của lane B mà cả hai đều thấy màu xanh. Một
# phép đo không nói được nó đo CÁI NÀO thì không gác được gì.
booted_serial() {
    local candidates s
    if [ -n "${ANDROID_SERIAL:-}" ]; then
        candidates="$ANDROID_SERIAL"
    else
        candidates="$("$ADB" devices 2>/dev/null | awk '/^emulator-[0-9]+\tdevice$/{print $1}')"
    fi
    for s in $candidates; do
        if [ "$("$ADB" -s "$s" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r\n')" = "1" ]; then
            printf '%s\n' "$s"; return 0
        fi
    done
    return 1
}

# AVD nào đang chạy sau serial này. Cần vì `emulator-5554` không tự nói nó là
# máy của ai.
avd_of_serial() {
    "$ADB" -s "$1" emu avd name 2>/dev/null | head -1 | tr -d '\r\n'
}

# Serial đang chạy ĐÚNG AVD được hỏi — rỗng nếu không có.
#
# Bẫy đã cắn thật lúc 00:30 ngày 01/09, ngay trong lượt viết script này: `up`
# hỏi "có máy nào boot xong không", thấy emulator-5554 của một phiên khác, in
# "dùng lại" và LỜ HẲN `RD_AVD=rudi-gate` vừa được yêu cầu. Lệnh thoát 0, in
# một bảng xanh đẹp, và đo lên máy của người khác. Câu hỏi đúng không phải "có
# máy nào không" mà là "có ĐÚNG máy tôi hỏi không".
serial_for_avd() {
    local want="$1" s
    for s in $("$ADB" devices 2>/dev/null | awk '/^emulator-[0-9]+\tdevice$/{print $1}'); do
        if [ "$(avd_of_serial "$s")" = "$want" ] \
           && [ "$("$ADB" -s "$s" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r\n')" = "1" ]; then
            printf '%s\n' "$s"; return 0
        fi
    done
    return 1
}

# Chờ theo ĐIỀU KIỆN, không theo `sleep N`. Một `sleep 90` cố định vừa chậm khi
# máy nhanh vừa đỏ giả khi máy chậm — và cái đỏ giả đó trông y hệt emulator hỏng.
#
# Chờ ĐÚNG AVD vừa bật, không phải "một máy nào đó". Nếu chờ chung chung thì
# trên máy đã có sẵn emulator khác, hàm trả về NGAY ở vòng đầu — máy mới còn
# chưa kịp qua logo mà lệnh đã báo boot xong.
wait_boot() {
    local want="$1" deadline=$(( SECONDS + BOOT_TIMEOUT )) serial=""
    while [ "$SECONDS" -lt "$deadline" ]; do
        serial="$(serial_for_avd "$want" || true)"
        if [ -n "$serial" ]; then printf '%s\n' "$serial"; return 0; fi
        sleep 3
    done
    return 1
}

# --- đo TỪ BÊN TRONG máy ảo ----------------------------------------------
#
# `nc` có trong toybox của Android 15. `curl` thì KHÔNG — kiểm bằng curl trên
# host sẽ trả lời câu hỏi sai (host tới được API không), chứ không phải câu hỏi
# cần (máy ảo tới được API không). Hai câu đó cho hai đáp án khác nhau, và đó
# chính là cả điểm của cổng này.
#
# `sleep 2` sau request là bắt buộc: toybox nc đóng socket ngay khi stdin hết,
# nên nếu không giữ thì phản hồi bị cắt và ta đọc thành "không nối được" —
# một máy đo tự tạo ra finding giả.
http_from_guest() {
    local serial="$1" host="$2" port="$3"
    "$ADB" -s "$serial" shell \
        "(echo -e 'GET /healthz HTTP/1.1\r\nHost: $host:$port\r\nConnection: close\r\n\r'; sleep 2) | timeout 8 nc $host $port 2>&1 | head -1" \
        2>/dev/null | tr -d '\r\n'
}

cmd_up() {
    ensure_kvm
    [ -x "$ADB" ] || die "không thấy adb ở $ADB — đặt ANDROID_HOME cho đúng"
    [ -x "$EMULATOR" ] || die "không thấy emulator ở $EMULATOR"

    local serial
    serial="$(serial_for_avd "$AVD_NAME" || true)"
    if [ -n "$serial" ]; then
        say "AVD '$AVD_NAME' đã chạy ở $serial — dùng lại, không dựng thêm."
        export ANDROID_SERIAL="$serial"
    else
        if ! "$EMULATOR" -list-avds 2>/dev/null | grep -qx "$AVD_NAME"; then
            say "Chưa có AVD '$AVD_NAME' — tạo mới từ $SYSTEM_IMAGE"
            [ -x "$AVDMANAGER" ] || die "không thấy avdmanager ở $AVDMANAGER"
            printf 'no\n' | "$AVDMANAGER" create avd -n "$AVD_NAME" \
                -k "$SYSTEM_IMAGE" -d pixel_6 >/dev/null \
                || die "tạo AVD thất bại"
        fi
        say "Bật '$AVD_NAME' headless (nền, sống qua lượt này)…"
        # RD_EMU_PORT ghim serial thành emulator-<port>, để lane biết TRƯỚC nó
        # sắp đo lên máy nào thay vì đoán sau. Không đặt thì để emulator tự chọn.
        local portarg=()
        if [ -n "${RD_EMU_PORT:-}" ]; then
            portarg=(-port "$RD_EMU_PORT")
            export ANDROID_SERIAL="emulator-$RD_EMU_PORT"
            say "  ghim serial: $ANDROID_SERIAL"
        fi
        # -no-window vì máy không có màn hình; swiftshader_indirect vì không có
        # GPU. `setsid` + nohup để emulator KHÔNG chết theo shell gọi nó — đó
        # đúng là cách bản đang chạy hôm nay sẽ biến mất.
        setsid nohup "$EMULATOR" -avd "$AVD_NAME" "${portarg[@]}" \
            -no-window -no-audio -no-boot-anim \
            -gpu swiftshader_indirect -accel on \
            >/tmp/rd-emulator-"$AVD_NAME".log 2>&1 < /dev/null &
        say "  log: /tmp/rd-emulator-$AVD_NAME.log"
        say "  chờ sys.boot_completed=1 (tối đa ${BOOT_TIMEOUT}s)…"
        serial="$(wait_boot "$AVD_NAME")" || die "quá ${BOOT_TIMEOUT}s mà sys.boot_completed vẫn chưa =1.
  Đọc /tmp/rd-emulator-$AVD_NAME.log — đừng đọc 'tiến trình còn sống' thành 'đã boot'."
    fi

    # Metro thì THẬT SỰ cần reverse: Expo Go tải bundle từ máy bạn qua 8081.
    # API thì không cần, vì ta trỏ nó vào 10.0.2.2.
    "$ADB" -s "$serial" reverse "tcp:$METRO_PORT" "tcp:$METRO_PORT" >/dev/null 2>&1 || true
    say "Sẵn sàng: $serial"
    printf '%s\n' "$serial" > /tmp/rd-emulator-serial
    cmd_check
}

cmd_check() {
    local serial rc=0
    serial="$(booted_serial)"
    [ -n "$serial" ] || die "không có máy ảo nào boot xong. Chạy: $0 up"

    say "== máy ảo =="
    say "  serial            $serial"
    say "  sys.boot_completed $("$ADB" -s "$serial" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r\n')"
    say "  bootanim           $("$ADB" -s "$serial" shell getprop init.svc.bootanim 2>/dev/null | tr -d '\r\n')"
    say "  Android            $("$ADB" -s "$serial" shell getprop ro.build.version.release 2>/dev/null | tr -d '\r\n') / SDK $("$ADB" -s "$serial" shell getprop ro.build.version.sdk 2>/dev/null | tr -d '\r\n')"

    say "== API nhìn TỪ TRONG máy ảo =="
    local good bad
    good="$(http_from_guest "$serial" "$HOST_FROM_GUEST" "$API_PORT")"
    say "  $HOST_FROM_GUEST:$API_PORT   ${good:-<rỗng>}"
    case "$good" in
        *"200 OK"*) ;;
        *) say "  ^ KHÔNG tới được API. Máy chủ có chạy ở host:$API_PORT không?"; rc=1 ;;
    esac

    # Đối chứng ÂM. Nếu `localhost` cũng xanh thì hoặc có ai đó cắm adb reverse,
    # hoặc phép đo của ta không thật sự đi ra khỏi máy ảo. Cả hai đều làm con số
    # ở trên mất nghĩa, nên phải nói ra chứ không nuốt.
    bad="$(http_from_guest "$serial" localhost "$API_PORT")"
    say "  localhost:$API_PORT  ${bad:-<rỗng>}   <- PHẢI hỏng; nếu xanh là đang có adb reverse"
    case "$bad" in
        *"200 OK"*)
            say "  ^ CẢNH BÁO: localhost:$API_PORT xanh, tức có đường hầm adb reverse đang cắm."
            say "    Nó KHÔNG nằm trong repo và mất khi adb restart. Gỡ:"
            say "        $ADB -s $serial reverse --remove tcp:$API_PORT"
            ;;
    esac

    say "== Expo Go =="
    if "$ADB" -s "$serial" shell pm list packages 2>/dev/null | grep -q host.exp.exponent; then
        say "  host.exp.exponent  ĐÃ CÀI"
    else
        say "  host.exp.exponent  CHƯA CÀI  ->  $0 install-expo"
        rc=1
    fi

    say "== địa chỉ app PHẢI dùng =="
    say "  EXPO_PUBLIC_API_URL=http://$HOST_FROM_GUEST:$API_PORT"
    say "  (KHÔNG phải localhost — xem đầu file này)"
    return $rc
}

cmd_install_expo() {
    local serial; serial="$(booted_serial)"
    [ -n "$serial" ] || die "chưa có máy ảo boot xong. Chạy: $0 up"
    if "$ADB" -s "$serial" shell pm list packages 2>/dev/null | grep -q host.exp.exponent; then
        say "Expo Go đã có sẵn — không cài lại."; return 0
    fi
    command -v npx >/dev/null 2>&1 || die "cần npx để tải Expo Go"
    say "Cài Expo Go vào $serial…"
    ANDROID_SERIAL="$serial" npx --yes expo-cli client:install:android 2>&1 | tail -5 \
        || die "cài Expo Go thất bại — tải tay APK từ expo.dev rồi: $ADB install <apk>"
}

# Tắt ĐÚNG AVD được hỏi, không phải "máy đầu tiên tìm thấy".
#
# Bản đầu dùng booted_serial() và như thế `android-down` ở worktree này sẽ giết
# emulator của lane khác — đúng cái bẫy mà đầu Makefile đã cảnh báo cho `make
# down`. Một lệnh phá huỷ phải gọi tên thứ nó phá, bằng cấu tạo chứ không bằng
# may mắn.
cmd_down() {
    local serial; serial="$(serial_for_avd "$AVD_NAME" || true)"
    if [ -z "$serial" ]; then
        say "AVD '$AVD_NAME' không chạy — không tắt gì cả."
        local others; others="$("$ADB" devices 2>/dev/null | awk '/^emulator-[0-9]+\tdevice$/{print $1}' | tr '\n' ' ')"
        [ -n "$others" ] && say "  (đang có máy khác chạy: $others — KHÔNG đụng tới)"
        return 0
    fi
    say "Tắt AVD '$AVD_NAME' ở $serial…"
    "$ADB" -s "$serial" emu kill 2>/dev/null || true
    rm -f /tmp/rd-emulator-serial
}

cmd_doctor() {
    say "ANDROID_HOME   $ANDROID_HOME"
    say "adb            $([ -x "$ADB" ] && echo có || echo THIẾU)"
    say "emulator       $([ -x "$EMULATOR" ] && echo có || echo THIẾU)"
    say "avdmanager     $([ -x "$AVDMANAGER" ] && echo có || echo THIẾU)"
    say "/dev/kvm       $(if kvm_ready; then echo 'mở được'; \
        elif kvm_in_etc_group; then echo 'CHƯA mở được, nhưng đã ở /etc/group -> script tự dùng sg kvm'; \
        else echo "CHƯA có quyền -> sudo usermod -aG kvm $(id -un)"; fi)"
    say "AVD có sẵn     $("$EMULATOR" -list-avds 2>/dev/null | tr '\n' ' ')"
    say "máy đã boot    $(booted_serial || true)"
}

case "${1:-check}" in
    up)            cmd_up ;;
    check)         cmd_check ;;
    install-expo)  cmd_install_expo ;;
    down)          cmd_down ;;
    doctor)        cmd_doctor ;;
    *) die "dùng: $0 {up|check|install-expo|down|doctor}" ;;
esac
