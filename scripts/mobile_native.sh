#!/usr/bin/env bash
# Lái app RuDi trên máy ảo Android thật, qua Expo Go, và trả về một phán quyết.
#
# ## Vì sao có file này
#
# Mọi cổng đang có của `apps/mobile` chạy trên `react-native-web`: `npm test`
# render qua rnw trong jsdom, và bộ ảnh QA lái headless Chrome trên bản
# `expo export --platform web`. Đó là một target KHÁC target sẽ ship, và bộ nhớ
# dự án ghi lại ít nhất bốn lượt rnw nói dối theo bốn kiểu khác nhau — nuốt
# `accessibilityState`, không đưa URL ảnh vào markup, dùng chung class atomic,
# bundle thuần ASCII nên grep tiếng Việt luôn trả 0.
#
# `docs/architecture/01-duong-toi-production.md` mục 6 xếp Maestro vào «làm sau
# Mốc 3, trước đó không có gì để lái», với giả định là phải có bản dựng EAS.
# Giả định đó SAI: Expo Go nạp bundle từ Metro và Maestro lái được nó ngay hôm
# nay. Đó là lý do file này tồn tại sớm hơn lộ trình dự đoán.
#
# ## Cái nó cưỡng chế, và cái nó cố ý từ chối
#
# Ba cái neo, vì cả ba đều đã hỏng thật trên máy này:
#
#   1. Metro phải là Metro CỦA CÂY NÀY. Cổng 8081/8082/8083 là Metro của lane
#      khác, và bundle của họ là một bundle React Native hợp lệ, mới, hot-reload
#      đầy đủ — không có dấu hiệu nào ở phía thiết bị phân biệt được. Đo bằng
#      dòng `Starting project at` trong log của chính mình.
#   2. Thiết bị phải THẬT SỰ nạp bundle đó. `curl /status` trả 200 không chứng
#      minh gì: cổng bị lane khác chiếm cũng trả 200. Đo bằng `Android Bundled`.
#   3. Con canary phải ĐỎ. Một bảng xanh mà không có ca nào biết đỏ thì không
#      phân biệt được «đã gác» với «phép đo chết».
#
# Không đo được thì thoát mã 2 và NÓI RA. Bỏ qua im lặng là cổng chết —
# `make smoke` trong repo này đã học bài đó rồi.
set -euo pipefail

PORT="${MOBILE_METRO_PORT:-8095}"
API_PORT="${MOBILE_API_PORT_NATIVE:-}"
SERIAL="${ANDROID_SERIAL:-}"
FLOWS=".maestro"
KEEP=0

while [ $# -gt 0 ]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --api-port) API_PORT="$2"; shift 2 ;;
    --serial) SERIAL="$2"; shift 2 ;;
    --flows) FLOWS="$2"; shift 2 ;;
    --keep) KEEP=1; shift ;;
    *) echo "tham số lạ: $1" >&2; exit 64 ;;
  esac
done

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$REPO/apps/mobile"
LOG="$(mktemp -t metro-native-XXXXXX.log)"
METRO_PID=""

khong_do_duoc() { echo "KHÔNG ĐO ĐƯỢC: $*" >&2; exit 2; }
hong()          { echo "ĐỎ: $*" >&2; exit 1; }

# --- công cụ ---------------------------------------------------------------
export ANDROID_HOME="${ANDROID_HOME:-$HOME/Android/Sdk}"
export PATH="$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH"

command -v adb >/dev/null 2>&1 || khong_do_duoc "không có adb. Đặt ANDROID_HOME (mặc định ~/Android/Sdk)."
command -v maestro >/dev/null 2>&1 || khong_do_duoc "không có maestro trên PATH. https://maestro.mobile.dev"
[ -d "$APP/node_modules" ] || khong_do_duoc "apps/mobile/node_modules chưa có. Chạy 'npm ci' trong apps/mobile."
[ -d "$APP/$FLOWS" ] || khong_do_duoc "không thấy $APP/$FLOWS"

# --- thiết bị --------------------------------------------------------------
# `timeout` bọc mọi lệnh adb: trên WSL2 mirrored networking, 127.0.0.1 ở một
# cổng TRỐNG nuốt gói SYN, nên adb có thể treo vô hạn thay vì báo lỗi.
if [ -z "$SERIAL" ]; then
  SERIAL="$(timeout 30 adb devices 2>/dev/null | awk '$2=="device"{print $1; exit}')" || true
fi
[ -n "$SERIAL" ] || khong_do_duoc "không có máy ảo nào đang chạy. Bật một AVD rồi đặt ANDROID_SERIAL."
export ANDROID_SERIAL="$SERIAL"

# Máy này có nhiều lane dùng CHUNG một máy ảo, và `adb` không kèm -s rơi vào
# bất kỳ máy nào đang sống. Nêu tên ra để phán quyết biết nó nói về máy nào.
echo "máy: $ANDROID_SERIAL"

timeout 30 adb shell pm list packages 2>/dev/null | grep -q "host.exp.exponent" \
  || khong_do_duoc "máy $ANDROID_SERIAL chưa cài Expo Go (host.exp.exponent)."

EXPO_VER="$(timeout 30 adb shell dumpsys package host.exp.exponent 2>/dev/null \
             | sed -n 's/.*versionName=\([0-9.]*\).*/\1/p' | head -1)"
echo "Expo Go: ${EXPO_VER:-không đọc được}"
case "$EXPO_VER" in
  57.*) ;;
  "")   khong_do_duoc "không đọc được phiên bản Expo Go." ;;
  *)    hong "Expo Go $EXPO_VER không khớp SDK 57 của app. Bundle sẽ không nạp." ;;
esac

# --- Metro CỦA CÂY NÀY -----------------------------------------------------
# Giết cả `npx` lẫn `node` chứ không chỉ subshell. Lượt chạy đầu chỉ giết
# subshell, `node` ở lại giữ cổng 8095, và lượt sau `expo start` không bind
# được — nhưng nó vẫn IN "Starting project at" trước khi bỏ cuộc, nên neo 1 đi
# qua trong khi máy đang nói chuyện với Metro MỒ CÔI phục vụ bundle CŨ. Đúng
# họ với cái bẫy cổng này tồn tại để chặn, chỉ khác là tự mình gây ra.
giet_metro_cua_minh() {
  [ -n "$METRO_PID" ] && kill "$METRO_PID" 2>/dev/null || true
  # Tìm theo NGƯỜI GIỮ CỔNG, không tìm theo argv. Bản trước lọc `ps` theo hai
  # chuỗi và giết luôn shell của chính người gọi, vì argv của shell đó chứa cả
  # câu lệnh — đúng cái bẫy `pkill -f` đã biết. Cổng thì chỉ một tiến trình giữ.
  if command -v ss >/dev/null 2>&1; then
    ss -ltnp 2>/dev/null \
      | grep -E "127\.0\.0\.1:$PORT[[:space:]]" \
      | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u \
      | while read -r q; do kill "$q" 2>/dev/null || true; done
  fi
}

don_dep() {
  timeout 20 adb reverse --remove "tcp:$PORT" >/dev/null 2>&1 || true
  [ "$KEEP" = 1 ] && return 0
  giet_metro_cua_minh
}
trap don_dep EXIT

if timeout 20 adb reverse --list 2>/dev/null | grep -q "tcp:$PORT"; then
  hong "cổng $PORT đã có người cắm reverse. Đổi bằng MOBILE_METRO_PORT=<cổng khác>."
fi

# Đọc bảng socket bằng `ss`, KHÔNG connect: trên WSL2 mirrored networking, nối
# tới 127.0.0.1 ở một cổng TRỐNG nuốt gói SYN và treo vô hạn.
if command -v ss >/dev/null 2>&1 && ss -ltn 2>/dev/null | grep -qE "127\.0\.0\.1:$PORT[[:space:]]"; then
  hong "cổng $PORT đã có người nghe. Metro của lane khác phục vụ một bundle hợp lệ của CÂY KHÁC, và thiết bị không phân biệt được. Đổi bằng MOBILE_METRO_PORT=<cổng khác>."
fi

(
  cd "$APP"
  # `export` rather than an assignment prefix: bash decides what is an
  # assignment BEFORE expanding, so `${API_PORT:+EXPO_PUBLIC_API_URL=...}` in
  # prefix position is run as a COMMAND named "EXPO_PUBLIC_API_URL=http://...".
  # That is exactly how the first run of this script failed, and the anchor
  # below caught it as "Metro is not serving this tree" -- which was true.
  export CI=1 EXPO_NO_TELEMETRY=1 EXPO_NO_DEPENDENCY_VALIDATION=1
  if [ -n "$API_PORT" ]; then
    export EXPO_PUBLIC_API_URL="http://localhost:$API_PORT"
  fi
  npx expo start --localhost --port "$PORT" > "$LOG" 2>&1
) &
METRO_PID=$!

for _ in $(seq 1 60); do
  grep -q "Waiting on http://localhost:$PORT" "$LOG" && break
  sleep 1
done

# NEO 1. Cổng đúng số không chứng minh cây đúng. Lane khác giữ 8081/8082/8083
# và log của họ trông y hệt log này, chỉ khác đúng dòng dưới đây.
if ! grep -qF "Starting project at $APP" "$LOG"; then
  echo "--- log Metro ---" >&2; tail -20 "$LOG" >&2
  hong "Metro ở cổng $PORT không phục vụ $APP. Không đo được cây này."
fi
echo "Metro: $APP (cổng $PORT)"

timeout 20 adb reverse "tcp:$PORT" "tcp:$PORT" >/dev/null \
  || khong_do_duoc "adb reverse tcp:$PORT thất bại."
[ -n "$API_PORT" ] && { timeout 20 adb reverse "tcp:$API_PORT" "tcp:$API_PORT" >/dev/null || true; }

# --- thiết bị nạp bundle CỦA MÌNH ------------------------------------------
timeout 30 adb shell am force-stop host.exp.exponent >/dev/null 2>&1 || true
sleep 2
timeout 30 adb shell am start -a android.intent.action.VIEW \
  -d "exp://localhost:$PORT" host.exp.exponent >/dev/null 2>&1 \
  || khong_do_duoc "không mở được Expo Go trên $ANDROID_SERIAL."

for _ in $(seq 1 90); do
  grep -q "Android Bundled" "$LOG" && break
  sleep 2
done
# NEO 2. Không có dòng này thì màn hình đang hiện CÁI GÌ ĐÓ — màn chủ Expo Go,
# bundle của lane khác, hoặc app cũ — và mọi assert sau đó nói về cái đó.
grep -q "Android Bundled" "$LOG" \
  || { echo "--- log Metro ---" >&2; tail -20 "$LOG" >&2; \
       hong "thiết bị không nạp bundle từ Metro của cây này."; }
echo "thiết bị đã nạp bundle của $APP"

# --- chạy bảng, rồi chạy canary --------------------------------------------
# Duyệt từng file thay vì `maestro test <thư mục> --exclude-tags=canary`: đo
# ngày 2026-09-03, `--exclude-tags` KHÔNG lọc khi đích là một file, nên con
# canary vẫn chạy trong bảng và kéo cả bảng xuống đỏ. Vòng lặp cũng in được
# phán quyết theo từng flow, mà một lượt chạy cả thư mục không cho.
cd "$APP"
BANG=0
DA_CHAY=0
DO_LIST=""
for f in "$FLOWS"/*.yaml; do
  ten="$(basename "$f")"
  case "$ten" in
    _*)          continue ;;  # subflow, chạy qua runFlow chứ không tự chạy
    09-canary-*) continue ;;  # chạy riêng ở dưới, và nó PHẢI đỏ
  esac
  DA_CHAY=$((DA_CHAY + 1))
  set +e; maestro test "$f"; rc=$?; set -e
  if [ "$rc" -ne 0 ]; then BANG=1; DO_LIST="$DO_LIST $ten"; fi
done

# Danh sách nguồn RỖNG làm cổng tự tháo trong im lặng: không flow nào chạy thì
# không flow nào đỏ, và vòng lặp ở trên đi qua sạch sẽ.
[ "$DA_CHAY" -gt 0 ] || hong "không có flow nào trong $FLOWS. Bảng RỖNG không phải bảng xanh."
echo "đã chạy $DA_CHAY flow"

set +e; maestro test "$FLOWS/09-canary-phai-do.yaml"; CANARY=$?; set -e

[ "$BANG" -eq 0 ] || hong "flow đỏ:$DO_LIST"
# NEO 3. Canary xanh nghĩa là phép đo không phân biệt được đúng với sai, nên cả
# bảng xanh ở trên không chứng minh gì.
[ "$CANARY" -ne 0 ] || hong "canary XANH. Bảng trên không chứng minh gì."

echo "XANH: bảng qua, canary đỏ đúng thiết kế, trên $ANDROID_SERIAL / Expo Go $EXPO_VER"
