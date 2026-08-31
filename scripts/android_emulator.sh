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
# Hạn giờ cho MỖI cú adb. Một máy ảo kẹt làm `adb shell` không bao giờ trả lời,
# và khi đó chính adb server cũng kẹt theo — đo được lúc 01:05 ngày 01/09:
# `adb devices` hết giờ 25s. Không có hạn giờ thì `down` treo ở bước NHẬN DIỆN
# và không bao giờ tới được bước tắt, tức là lệnh dọn dẹp bị chính cái nó phải
# dọn làm cho câm.
ADB_TIMEOUT="${RD_ADB_TIMEOUT:-8}"
# Chờ bao lâu sau SIGTERM trước khi SIGKILL. SIGTERM để emulator kịp lưu
# snapshot; nhưng máy đã kẹt thì có thể không xử lý nổi tín hiệu nào.
KILL_TIMEOUT="${RD_KILL_TIMEOUT:-25}"
# Cổng của adb server. Đọc cả biến chính thức của adb để không có hai ý kiến
# khác nhau trong cùng một shell.
ADB_SERVER_PORT="${ANDROID_ADB_SERVER_PORT:-${RD_ADB_SERVER_PORT:-5037}}"
# Chờ server tự bật lên bao lâu. Đo được: nó lên trong ~200ms.
ADB_SERVER_WAIT="${RD_ADB_SERVER_WAIT:-20}"
ADB_SERVER_LOG="${RD_ADB_SERVER_LOG:-/tmp/rd-adb-server-$ADB_SERVER_PORT.log}"
# Cổng đầu của bốn cổng dùng để THỬ loopback. Phải nằm ngoài ip_local_port_range
# và không được là cổng ai đó thật sự dùng — xem _cong_trong_de_thu.
CONG_THU_GOC="${RD_CONG_THU_GOC:-5987}"
# Địa chỉ host nhìn từ trong máy ảo. Hằng số của QEMU, không phải cấu hình.
HOST_FROM_GUEST=10.0.2.2

# Nơi emulator TỰ KHAI nó đang chạy: một file pid_<PID>.ini có `avd.name=`,
# `port.adb=`, `cmdline=`. Đường này KHÔNG đi qua adb, nên một máy đã câm với
# adb vẫn còn khai ở đây — đó là lý do nó tồn tại trong script này.
AVD_RUN_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/avd/running"

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

# Mọi cú adb đi qua đây. Xem ADB_TIMEOUT ở trên cho lý do.
# `-P` được ghi rõ chứ không dựa vào mặc định: trong một shell có
# ANDROID_ADB_SERVER_PORT đặt sẵn, "mặc định" của adb và của script sẽ là hai
# cổng khác nhau, và ta sẽ bật server ở cổng này rồi hỏi ở cổng kia.
adbq() {
    # Mọi lệnh adb đều phải đi qua cửa này, vì cú adb ĐẦU TIÊN của một tiến
    # trình mới chính là cú treo. Rẻ: khi server đã nghe thì đây là một lần đọc
    # bảng socket rồi thôi, không in gì.
    ensure_adb_server || return 1
    timeout "$ADB_TIMEOUT" "$ADB" -P "$ADB_SERVER_PORT" "$@"
}

# --- localhost trên WSL2 HÚT SYN, và đó là gốc của "adb treo vô hạn" --------
#
# Đo lúc 01:5x ngày 01/09, bằng socket thuần, không qua adb:
#
#     connect 127.0.0.1:5038  -> TREO (cắt ở 3s)     ::1:5038      -> refused 0.00s
#     connect 127.0.0.1:5037  -> nối được 0.00s      127.0.0.2:*   -> refused 0.00s
#     mọi cổng KHÔNG có ai nghe trên 127.0.0.1 đều treo, trừ cổng nằm trong dải
#     ip_local_port_range của kernel thì refused bình thường.
#     (đọc dải đó: cat /proc/sys/net/ipv4/ip_local_port_range)
#
# Vì sao: `ip route get 127.0.0.1` trên máy này trả
#     127.0.0.1 via <một gateway link-local> dev loopback0 table 127
# tức 127.0.0.1 KHÔNG đi qua `lo` mà ra một relay của Windows (WSL2 mirrored
# networking). Cổng không ai nghe thì SYN bị nuốt — không có RST — nên connect()
# treo vĩnh viễn thay vì ECONNREFUSED.
#
# HỆ QUẢ, và đây là chỗ cả đội mất một tiếng ngày 01/09: adb client LUÔN thử
# connect vào cổng server của chính nó TRƯỚC khi quyết định có cần bật server
# hay không. Không có server thì cú thăm dò đó treo, nên adb KHÔNG BAO GIỜ chạy
# tới đoạn bật server. Vì thế:
#
#   * `adb devices`      treo
#   * `adb start-server` treo — nó chính là cú thăm dò ấy
#   * `adb -P 5038 …`    (server mới, cổng mới) CŨNG treo
#
# Cái cuối làm người ta kết luận nhầm "không phải trạng thái cũ của server, vậy
# thì adbd trong máy ảo hỏng". Máy ảo không hỏng: đo được `shell echo hi` -> hi
# và `sys.boot_completed` -> 1 ngay sau khi bật server bằng đường dưới đây.
#
# Cách ra: đừng để adb client tự quyết. Nhìn xem có ai đang NGHE ở cổng server
# chưa (đọc bảng socket, không connect), và nếu chưa thì bật server THẲNG bằng
# `adb server nodaemon`. Lệnh đó bind luôn, không thăm dò, nên không treo.

# Có ai đang nghe ở cổng này không. Đọc bảng socket — KHÔNG connect, vì chính
# cú connect là thứ treo.
port_dang_nghe() {
    ss -ltn "sport = :$1" 2>/dev/null | awk 'NR>1{f=1} END{exit !f}'
}

# Cổng trống dùng để thử: phải NGOÀI ip_local_port_range, vì relay bỏ qua dải
# đó nên cổng trong dải vẫn refused tử tế và phép thử sẽ báo "không sao" nhầm.
_cong_trong_de_thu() {
    local lo p i
    lo="$(awk '{print $1}' /proc/sys/net/ipv4/ip_local_port_range 2>/dev/null)"
    : "${lo:=32768}"
    # Bốn cổng lẻ liên tiếp từ CONG_THU_GOC. Viết dạng tính chứ không dạng danh
    # sách vì repo guard đọc một dãy số dài liền nhau thành số tài khoản.
    for i in 0 1 2 3; do
        p=$(( CONG_THU_GOC + i * 2 ))
        [ "$p" -lt "$lo" ] || continue
        port_dang_nghe "$p" || { printf '%s\n' "$p"; return 0; }
    done
    return 1
}

# 0 = loopback đang hút SYN (connect treo thay vì bị từ chối).
# Đây là phép đo, không phải phỏng đoán theo tên hệ điều hành: cùng một máy WSL
# có thể bật/tắt mirrored networking, và một máy Linux thật thì không bao giờ có
# triệu chứng này.
loopback_nuot_syn() {
    local p; p="$(_cong_trong_de_thu)" || return 1
    timeout 3 bash -c "exec 3<>/dev/tcp/127.0.0.1/$p" 2>/dev/null
    [ "$?" -eq 124 ]
}

# Bảo đảm có adb server ĐANG NGHE trước khi bất kỳ lệnh adb nào chạy.
#
# Không dùng `adb start-server`: chính nó là cú thăm dò treo. `server nodaemon`
# thì bind thẳng. setsid+nohup để server sống qua shell đã gọi — nếu nó chết
# theo shell thì lệnh sau lại rơi vào đúng cái bẫy này.
# Mọi thứ hàm này in ra đi ra STDERR, không phải stdout. Nó được gọi từ trong
# `$(adbq …)`, nên một dòng thông báo lọt vào stdout sẽ bị bắt vào giá trị và
# trở thành một serial giả — đúng kiểu lỗi im lặng mà script này sinh ra để
# tránh.
ensure_adb_server() {
    port_dang_nghe "$ADB_SERVER_PORT" && return 0
    if loopback_nuot_syn; then
        printf 'adb server chưa chạy, và localhost máy này HÚT SYN (WSL2 mirrored networking).\n' >&2
        printf "  -> 'adb start-server' sẽ treo vĩnh viễn. Bật thẳng bằng 'server nodaemon'.\n" >&2
    else
        printf 'adb server chưa chạy ở cổng %s — bật lên…\n' "$ADB_SERVER_PORT" >&2
    fi
    setsid nohup "$ADB" -L "tcp:$ADB_SERVER_PORT" server nodaemon \
        >>"$ADB_SERVER_LOG" 2>&1 </dev/null &
    local deadline=$(( SECONDS + ADB_SERVER_WAIT ))
    while [ "$SECONDS" -lt "$deadline" ]; do
        if port_dang_nghe "$ADB_SERVER_PORT"; then
            printf '  adb server đã nghe ở %s.\n' "$ADB_SERVER_PORT" >&2
            return 0
        fi
        sleep 0.2
    done
    # KHÔNG `die`: hàm này chạy trong subshell của `$(…)`, ở đó `exit` chỉ giết
    # subshell rồi lệnh ngoài chạy tiếp với giá trị rỗng. Trả mã lỗi để adbq
    # hỏng thành tiếng.
    printf 'HỎNG: adb server không lên nổi ở cổng %s sau %ss. Log: %s\n' \
        "$ADB_SERVER_PORT" "$ADB_SERVER_WAIT" "$ADB_SERVER_LOG" >&2
    return 1
}

# PID của mọi emulator ĐANG SỐNG chạy đúng AVD này, đọc từ file tự khai.
#
# Vì sao không hỏi adb: câu hỏi ở đây là "có tiến trình nào đang GIỮ cái AVD
# này không", và câu đó phải trả lời được kể cả khi máy đã ngừng nói chuyện.
# `serial_for_avd` không trả lời được nó — hàm đó đòi sys.boot_completed=1, nên
# với nó một máy kẹt là một máy KHÔNG TỒN TẠI. Đúng lớp lỗi ấy làm `down` từ
# chối tắt máy hỏng và làm `up` bật instance thứ hai đè lên nó.
#
# `kill -0` lọc file mồ côi: emulator chết đột ngột thì .ini còn nằm lại, và
# đọc nó thành "đang chạy" sẽ chặn `up` vĩnh viễn.
pids_from_ini_for_avd() {
    local want="$1" f pid name
    [ -d "$AVD_RUN_DIR" ] || return 0
    for f in "$AVD_RUN_DIR"/pid_*.ini; do
        [ -e "$f" ] || continue
        pid="${f##*/pid_}"; pid="${pid%.ini}"
        case "$pid" in ''|*[!0-9]*) continue ;; esac
        kill -0 "$pid" 2>/dev/null || continue
        name="$(sed -n 's/^avd\.name=//p' "$f" 2>/dev/null | head -1 | tr -d '\r')"
        [ "$name" = "$want" ] && printf '%s\n' "$pid"
    done
    return 0
}

# Nguồn thứ hai: argv của chính tiến trình.
#
# Cần vì nguồn thứ nhất KHÔNG phải lúc nào cũng có. Đo được lúc 01:35 ngày
# 01/09: `qemu-system-x86_64-headless -avd rudi -port 5554` (pid 1057178) đang
# sống, còn AVD_RUN_DIR chỉ có một file khai mồ côi của pid đã chết.
#
# Điều kiện argv[0] PHẢI là binary qemu, không phải "dòng lệnh có chứa -avd
# rudi". `pgrep -f -- "-avd rudi"` khớp cả cái shell đang chạy chính script
# này, và khi đó `down` tự giết mình — bẫy pgrep -f tự khớp, đã cắn lane này
# một lần rồi. Cặp `-avd <tên>` cũng phải khớp theo VỊ TRÍ, vì một AVD tên
# 'rudi' và một AVD tên 'rudi-2' đều chứa chuỗi 'rudi'.
pids_from_argv_for_avd() {
    local want="$1" d p argv0 prev tok
    for d in /proc/[0-9]*; do
        p="${d#/proc/}"
        [ "$p" = "$$" ] && continue
        [ -r "$d/cmdline" ] || continue
        argv0="$(tr '\0' '\n' < "$d/cmdline" 2>/dev/null | head -1)"
        case "${argv0##*/}" in qemu-system*) ;; *) continue ;; esac
        prev=""
        while IFS= read -r tok; do
            if [ "$prev" = "-avd" ] && [ "$tok" = "$want" ]; then
                printf '%s\n' "$p"; break
            fi
            prev="$tok"
        done < <(tr '\0' '\n' < "$d/cmdline" 2>/dev/null)
    done
    return 0
}

# Hợp của hai nguồn, bỏ trùng. Một nguồn đủ để thấy; thiếu cả hai mới là không
# có máy nào.
live_pids_for_avd() {
    { pids_from_ini_for_avd "$1"; pids_from_argv_for_avd "$1"; } | sort -un
}

# Cổng console của mọi emulator đang chạy đúng AVD này.
#
# Cần vì máy quét emulator TRONG adb server cũng chết đúng cái chết ở trên: nó
# dò 127.0.0.1:5555,5557,… và hầu hết cổng đó không có ai nghe, nên mỗi cú dò
# treo. Đo được: một adb server mới bật KHÔNG hề thấy emulator sau 60 giây, dù
# máy ảo đang chạy và trả lời tốt. `adb connect 127.0.0.1:5561` thì gắn được
# NGAY — vì cổng đó CÓ người nghe nên không dính relay.
#
# Nên ta không nhờ adb đi tìm; ta đọc cổng từ chính hai nguồn đã dùng ở trên rồi
# gắn đích danh. Quy ước của emulator: console chẵn, adb = console + 1.
console_ports_for_avd() {
    local want="$1" f pid name port d argv0 prev tok
    if [ -d "$AVD_RUN_DIR" ]; then
        for f in "$AVD_RUN_DIR"/pid_*.ini; do
            [ -e "$f" ] || continue
            pid="${f##*/pid_}"; pid="${pid%.ini}"
            case "$pid" in ''|*[!0-9]*) continue ;; esac
            kill -0 "$pid" 2>/dev/null || continue
            name="$(sed -n 's/^avd\.name=//p' "$f" 2>/dev/null | head -1 | tr -d '\r')"
            [ "$name" = "$want" ] || continue
            port="$(sed -n 's/^port\.serial=//p' "$f" 2>/dev/null | head -1 | tr -d '\r')"
            case "$port" in ''|*[!0-9]*) ;; *) printf '%s\n' "$port" ;; esac
        done
    fi
    # Nguồn hai: argv. Cùng ràng buộc argv[0]=qemu như pids_from_argv_for_avd —
    # nếu nới ra thành "dòng lệnh có chứa tên AVD" thì chính shell chạy script
    # này cũng khớp.
    for d in /proc/[0-9]*; do
        p="${d#/proc/}"
        [ "$p" = "$$" ] && continue
        [ -r "$d/cmdline" ] || continue
        argv0="$(tr '\0' '\n' < "$d/cmdline" 2>/dev/null | head -1)"
        case "${argv0##*/}" in qemu-system*) ;; *) continue ;; esac
        prev=""; name=""; port=""
        while IFS= read -r tok; do
            [ "$prev" = "-avd" ] && name="$tok"
            [ "$prev" = "-port" ] && port="$tok"
            prev="$tok"
        done < <(tr '\0' '\n' < "$d/cmdline" 2>/dev/null)
        [ "$name" = "$want" ] || continue
        # emulator không ghi -port thì nó lấy 5554, cổng mặc định.
        case "$port" in ''|*[!0-9]*) port=5554 ;; esac
        printf '%s\n' "$port"
    done
    return 0
}

# Gắn đích danh mọi emulator của AVD này vào server, không chờ máy quét.
# Bỏ qua lỗi: cổng chưa mở thì lát nữa wait_boot thử lại.
attach_avd_transports() {
    local c
    for c in $(console_ports_for_avd "$1" | sort -un); do
        adbq connect "127.0.0.1:$(( c + 1 ))" >/dev/null 2>&1 || true
    done
}

# Serial mà AVD này CÓ THỂ mang. Hai dạng, vì hai đường vào khác nhau:
#   emulator-<console>      khi máy quét của adb tìm ra (đường bình thường)
#   127.0.0.1:<console+1>   khi ta phải gắn tay bằng `adb connect` (đường WSL2)
# Cùng một máy ảo, hai cái tên. Bảng nào chỉ biết một dạng thì mù một nửa.
serial_candidates_for_avd() {
    local c
    for c in $(console_ports_for_avd "$1" | sort -un); do
        printf 'emulator-%s\n127.0.0.1:%s\n' "$c" "$(( c + 1 ))"
    done
}

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
        # Gắn trước khi hỏi. Không có dòng này thì trên máy có loopback hút SYN
        # máy ảo KHÔNG BAO GIỜ xuất hiện trong `adb devices`: máy quét của adb
        # server không tới được nó, và ta thì chưa gắn tay. `check` khi đó chết
        # ở "không có máy ảo nào boot xong" trong khi máy đang chạy rất tốt.
        attach_avd_transports "$AVD_NAME"
        # Cả hai dạng tên: máy quét tìm ra thì `emulator-NNNN`, gắn tay thì
        # `127.0.0.1:NNNN`. Xem chú thích ở serial_for_avd.
        candidates="$(adbq devices 2>/dev/null \
            | awk '/^(emulator-[0-9]+|127\.0\.0\.1:[0-9]+)\tdevice$/{print $1}')"
    fi
    for s in $candidates; do
        if [ "$(boot_completed "$s")" = "1" ]; then
            printf '%s\n' "$s"; return 0
        fi
    done
    return 1
}

# AVD nào đang chạy sau serial này. Cần vì `emulator-5554` không tự nói nó là
# máy của ai.
avd_of_serial() {
    adbq -s "$1" emu avd name 2>/dev/null | head -1 | tr -d '\r\n'
}

# Serial đang chạy ĐÚNG AVD được hỏi — rỗng nếu không có.
#
# Bẫy đã cắn thật lúc 00:30 ngày 01/09, ngay trong lượt viết script này: `up`
# hỏi "có máy nào boot xong không", thấy emulator-5554 của một phiên khác, in
# "dùng lại" và LỜ HẲN `RD_AVD=rudi-gate` vừa được yêu cầu. Lệnh thoát 0, in
# một bảng xanh đẹp, và đo lên máy của người khác. Câu hỏi đúng không phải "có
# máy nào không" mà là "có ĐÚNG máy tôi hỏi không".
#
# Có HAI đường vào, và bảng nào chỉ biết một đường thì mù một nửa:
#   emulator-<console>     máy quét của adb tìm ra — hỏi `adb emu avd name` được
#   127.0.0.1:<console+1>  ta gắn tay bằng `adb connect` khi máy quét chết vì
#                          loopback hút SYN. Trên transport dạng này `adb emu`
#                          KHÔNG chạy (đo được: rc=1, không in gì), nên danh
#                          tính phải lấy từ CẤU TẠO — cổng đọc từ pid/ini/argv
#                          của chính AVD được hỏi — chứ không hỏi adb.
serial_for_avd() {
    local want="$1" s cand attached
    attach_avd_transports "$want"
    attached="$(adbq devices 2>/dev/null | awk '/\tdevice$/{print $1}')"

    for s in $attached; do
        case "$s" in emulator-*) ;; *) continue ;; esac
        if [ "$(avd_of_serial "$s")" = "$want" ] && [ "$(boot_completed "$s")" = "1" ]; then
            printf '%s\n' "$s"; return 0
        fi
    done

    for cand in $(serial_candidates_for_avd "$want"); do
        for s in $attached; do
            [ "$s" = "$cand" ] || continue
            [ "$(boot_completed "$s")" = "1" ] || continue
            printf '%s\n' "$s"; return 0
        done
    done
    return 1
}

boot_completed() {
    adbq -s "$1" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r\n'
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
        # Gắn đích danh mỗi vòng: cổng adb của máy ảo chỉ mở ra giữa chừng lúc
        # boot, và máy quét của adb server không tới được nó trên máy có
        # loopback hút SYN. Gắn lại một transport đã gắn là no-op.
        attach_avd_transports "$want"
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
    adbq -s "$serial" shell \
        "(echo -e 'GET /healthz HTTP/1.1\r\nHost: $host:$port\r\nConnection: close\r\n\r'; sleep 2) | timeout 8 nc $host $port 2>&1 | head -1" \
        2>/dev/null | tr -d '\r\n'
}

cmd_up() {
    local serial held
    # TRƯỚC ensure_kvm, vì câu trả lời không cần KVM và vì `ensure_kvm` có thể
    # exec lại chính script dưới `sg kvm` — kiểm sau đó là kiểm ở tiến trình
    # khác, muộn hơn một nhịp.
    #
    # Câu hỏi ở đây không phải "có máy nào boot xong chưa" mà "AVD này có đang
    # bị tiến trình nào giữ không". Bản trước chỉ hỏi câu đầu, nên khi 'rudi'
    # đang bị một qemu kẹt giữ, nó kết luận "chưa có" và bật cái THỨ HAI lên
    # cùng AVD. Đo được lúc 01:12 ngày 01/09: máy thứ hai nạp snapshot xong
    # 10.9s rồi bị yêu cầu tắt, không ai gõ lệnh tắt nào. Hai instance dùng
    # chung một file snapshot thì cùng thua.
    held="$(live_pids_for_avd "$AVD_NAME")"
    if [ -n "$held" ]; then
        serial="$(serial_for_avd "$AVD_NAME" || true)"
        if [ -z "$serial" ]; then
            say "AVD '$AVD_NAME' đang bị giữ bởi pid:$(printf ' %s' $held) nhưng chưa boot xong."
            say "  Chờ CHÍNH máy đó thay vì bật cái thứ hai đè lên nó…"
            serial="$(wait_boot "$AVD_NAME")" || die \
"AVD '$AVD_NAME' có tiến trình đang sống (pid:$(printf ' %s' $held)) mà quá ${BOOT_TIMEOUT}s vẫn chưa boot xong.
  Đây là máy KẸT, không phải máy chậm. Bật thêm một cái nữa trên cùng AVD sẽ
  giết cả hai — nên lệnh này dừng ở đây thay vì thử.
  Dọn rồi bật lại:
      $0 down && $0 up
  Muốn chạy song song với lane khác thì đặt AVD riêng:
      RD_AVD=${AVD_NAME}-2 $0 up"
        fi
    fi

    ensure_kvm
    [ -x "$ADB" ] || die "không thấy adb ở $ADB — đặt ANDROID_HOME cho đúng"
    [ -x "$EMULATOR" ] || die "không thấy emulator ở $EMULATOR"

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
    adbq -s "$serial" reverse "tcp:$METRO_PORT" "tcp:$METRO_PORT" >/dev/null 2>&1 || true
    say "Sẵn sàng: $serial"
    printf '%s\n' "$serial" > /tmp/rd-emulator-serial
    cmd_check
}

cmd_check() {
    local serial rc=0
    # `|| true` không phải để nuốt lỗi mà để lỗi NÓI ĐƯỢC. Dưới `set -e`, một
    # phép gán mà lệnh con trả khác 0 giết cả script NGAY tại đây — thoát 1,
    # không in một chữ nào, và dòng `die` ngay dưới không bao giờ chạy. Đo được
    # lúc 02:5x ngày 01/09: `check` thoát 1 với stdout rỗng và stderr rỗng,
    # trong khi máy ảo đang chạy tốt. Một lệnh chẩn đoán im lặng còn tệ hơn một
    # lệnh sai, vì không ai biết bắt đầu tìm từ đâu.
    serial="$(booted_serial || true)"
    [ -n "$serial" ] || die "không có máy ảo nào boot xong. Chạy: $0 up"

    say "== máy ảo =="
    say "  serial            $serial"
    say "  sys.boot_completed $(adbq -s "$serial" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r\n')"
    say "  bootanim           $(adbq -s "$serial" shell getprop init.svc.bootanim 2>/dev/null | tr -d '\r\n')"
    say "  Android            $(adbq -s "$serial" shell getprop ro.build.version.release 2>/dev/null | tr -d '\r\n') / SDK $(adbq -s "$serial" shell getprop ro.build.version.sdk 2>/dev/null | tr -d '\r\n')"

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
    if adbq -s "$serial" shell pm list packages 2>/dev/null | grep -q host.exp.exponent; then
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
    local serial; serial="$(booted_serial || true)"  # xem chú thích ở cmd_check
    [ -n "$serial" ] || die "chưa có máy ảo boot xong. Chạy: $0 up"
    if adbq -s "$serial" shell pm list packages 2>/dev/null | grep -q host.exp.exponent; then
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
# Hỏi HAI nguồn, vì chúng hỏng ở hai kiểu khác nhau:
#
#   serial_for_avd      chỉ thấy máy ĐÃ BOOT XONG  -> mù với máy kẹt
#   live_pids_for_avd   thấy mọi tiến trình đang giữ AVD, kể cả máy câm
#
# Bản trước chỉ hỏi nguồn thứ nhất, nên với một qemu 90% CPU đang giữ 'rudi' nó
# in "AVD 'rudi' không chạy — không tắt gì cả." rồi thoát 0. Lệnh dọn dẹp mù
# đúng với thứ duy nhất cần dọn.
cmd_down() {
    local serial pids pid remaining deadline
    serial="$(serial_for_avd "$AVD_NAME" || true)"
    pids="$(live_pids_for_avd "$AVD_NAME")"

    if [ -z "$serial" ] && [ -z "$pids" ]; then
        say "AVD '$AVD_NAME' không chạy — không tắt gì cả."
        local others; others="$(adbq devices 2>/dev/null | awk '/^emulator-[0-9]+\tdevice$/{print $1}' | tr '\n' ' ')"
        [ -n "$others" ] && say "  (đang có máy khác chạy: $others — KHÔNG đụng tới)"
        return 0
    fi

    # Đường lịch sự trước: emulator tự lưu snapshot rồi thoát. Chỉ thử khi máy
    # còn trả lời adb — với máy kẹt thì cú này chỉ tốn ADB_TIMEOUT.
    if [ -n "$serial" ]; then
        say "Tắt AVD '$AVD_NAME' ở $serial (adb emu kill)…"
        adbq -s "$serial" emu kill >/dev/null 2>&1 || true
    fi

    # Rồi mới tới tín hiệu. `pids` lấy từ file khai của CHÍNH AVD này, nên
    # không thể chạm vào máy của lane khác — tính chất mà bản trước giữ được
    # bằng cách không tắt gì cả, còn bản này giữ bằng cách gọi đúng tên.
    for pid in $pids; do
        kill -0 "$pid" 2>/dev/null || continue
        say "  SIGTERM $pid"
        kill -TERM "$pid" 2>/dev/null || true
    done

    deadline=$(( SECONDS + KILL_TIMEOUT ))
    while [ "$SECONDS" -lt "$deadline" ]; do
        remaining=""
        for pid in $pids; do
            kill -0 "$pid" 2>/dev/null && remaining="$remaining $pid"
        done
        [ -z "$remaining" ] && break
        sleep 1
    done

    # Máy đã kẹt có thể không xử lý nổi SIGTERM. Không leo thang thì `down`
    # thoát 0 với máy vẫn sống — lại đúng lời nói dối cũ, chỉ chậm hơn.
    for pid in $pids; do
        if kill -0 "$pid" 2>/dev/null; then
            say "  không thoát sau ${KILL_TIMEOUT}s -> SIGKILL $pid"
            kill -KILL "$pid" 2>/dev/null || true
        fi
    done

    rm -f /tmp/rd-emulator-serial
    for pid in $pids; do
        if kill -0 "$pid" 2>/dev/null; then
            die "pid $pid vẫn sống sau SIGKILL — không phải tiến trình của bạn?"
        fi
    done
    say "AVD '$AVD_NAME' đã tắt."
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
    # Hai dòng này KHÁC nhau, và chỗ chúng khác nhau chính là chỗ hỏng: một máy
    # kẹt giữ AVD mà không bao giờ boot xong thì dòng trên rỗng còn dòng dưới có
    # pid. Trước bản vá, script chỉ biết dòng trên.
    say "đang giữ '$AVD_NAME' $(live_pids_for_avd "$AVD_NAME" | tr '\n' ' ')"
    cmd_adb
}

# Trả lời đúng một câu: adb có dùng được không, và nếu không thì vì cái gì.
#
# Có mặt vì ngày 01/09 câu đó tốn của đội một tiếng và kết luận ra SAI địa chỉ
# ("adbd trong guest kẹt"). Triệu chứng thì giống hệt nhau, nên phải có một lệnh
# phân biệt được chúng thay vì đoán.
cmd_adb() {
    say "== adb =="
    if loopback_nuot_syn; then
        say "  loopback 127.0.0.1  HÚT SYN — cổng trống treo thay vì bị từ chối"
        say "    $(ip route get 127.0.0.1 2>/dev/null | head -1)"
        say "    Hệ quả: 'adb start-server' và 'adb -P <cổng khác>' đều TREO khi"
        say "    chưa có server. KHÔNG phải máy ảo hỏng — script tự bật server."
    else
        say "  loopback 127.0.0.1  bình thường (cổng trống bị từ chối ngay)"
    fi
    if port_dang_nghe "$ADB_SERVER_PORT"; then
        say "  adb server          đang nghe ở $ADB_SERVER_PORT"
    else
        say "  adb server          CHƯA chạy ở $ADB_SERVER_PORT"
    fi
    ensure_adb_server || { say "  -> không bật được server, xem $ADB_SERVER_LOG"; return 1; }
    attach_avd_transports "$AVD_NAME"
    local devs; devs="$(adbq devices 2>/dev/null | tail -n +2 | grep -c . || true)"
    say "  thiết bị thấy được  ${devs:-0}"
    adbq devices 2>/dev/null | tail -n +2 | sed 's/^/    /' | grep . || say "    (không có)"
}

case "${1:-check}" in
    up)            cmd_up ;;
    check)         cmd_check ;;
    install-expo)  cmd_install_expo ;;
    down)          cmd_down ;;
    doctor)        cmd_doctor ;;
    adb)           cmd_adb ;;
    *) die "dùng: $0 {up|check|install-expo|down|doctor|adb}" ;;
esac
