#!/usr/bin/env bash
# Lái app RuDi trên máy ảo Android thật — qua development build (mặc định) hay
# Expo Go (`--expo-go`) — và trả về một phán quyết.
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
#   2b. Màn hình phải hiện DẤU VÂN của lượt chạy này. Hai neo trên đọc log Metro;
#      không neo nào nói màn đang hiện gì — launcher của dev client, hay bundle
#      của lane khác, đều để hai neo xanh. Nên script inline một giá trị mỗi lượt
#      (EXPO_PUBLIC_TREE_FINGERPRINT), app vẽ nó ở chân màn chào, flow 00 assert,
#      và một canary chạy flow 00 với dấu vân SAI phải đỏ.
#
# Không đo được thì thoát mã 2 và NÓI RA. Bỏ qua im lặng là cổng chết —
# `make smoke` trong repo này đã học bài đó rồi.
set -euo pipefail

PORT="${MOBILE_METRO_PORT:-8095}"
API_PORT="${MOBILE_API_PORT_NATIVE:-}"
SERIAL="${ANDROID_SERIAL:-}"
FLOWS=".maestro"
KEEP=0
LIVE=0
DANG_NHAP=0
ACTOR=""
CONTEXT=""
MA_LOI_MOI=""
MODE="dev-client"
LAP=1
OTP=0
# Đối chứng âm cho phép đo bàn phím: tắt KeyboardAvoidingView trong bundle, và
# do_ban_phim.py PHẢI hỏng. Xanh ở đây là thước đo mù.
TAT_KAV=0
# --ai (cùng --otp): API phải có khoá Gemini còn sống; chạy thêm flow 40 và kiểm thẻ AI grounded.
AI=0
# Mã debug của API ở chế độ --otp. CHỈ hợp lệ khi API dùng log sender
# (MOBILE_OTP_DEBUG_CODE cạnh gateway thật làm create_app từ chối khởi động).
OTP_CODE="000000"
OTP_PHONE=""
OTP_PHONE_B=""
OTP_PHONE_C=""
OTP_PHONE_D=""

while [ $# -gt 0 ]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --api-port) API_PORT="$2"; shift 2 ;;
    --serial) SERIAL="$2"; shift 2 ;;
    --flows) FLOWS="$2"; shift 2 ;;
    --keep) KEEP=1; shift ;;
    --live) LIVE=1; shift ;;
    --dang-nhap) DANG_NHAP=1; shift ;;
    --actor) ACTOR="$2"; shift 2 ;;
    --context) CONTEXT="$2"; shift 2 ;;
    --expo-go) MODE="expo-go"; shift ;;
    --lap) LAP="$2"; shift 2 ;;
    --otp) OTP=1; shift ;;
    --tat-kav) TAT_KAV=1; shift ;;
    --ai) AI=1; shift ;;
    *) echo "tham số lạ: $1" >&2; exit 64 ;;
  esac
done

if [ "$LIVE" = 1 ]; then
  [ -n "$ACTOR" ] && [ -n "$CONTEXT" ] \
    || { echo "--live cần --actor <uuid> --context <uuid>" >&2; exit 64; }
  [ -n "$API_PORT" ] \
    || { echo "--live cần --api-port <cổng của API đã seed>" >&2; exit 64; }
fi

if [ "$DANG_NHAP" = 1 ]; then
  [ -n "$API_PORT" ] \
    || { echo "--dang-nhap cần --api-port <cổng của API chạy ở chế độ prod>" >&2; exit 64; }
  [ "$LIVE" = 0 ] \
    || { echo "--dang-nhap và --live loại trừ nhau: một cái ghim danh tính, cái kia đi lấy" >&2; exit 64; }
  [ "$LAP" = 1 ] \
    || { echo "--lap >1 chưa hỗ trợ cùng --dang-nhap: mỗi lượt cần xoá phiên và mint lời mời mới" >&2; exit 64; }
fi

if [ "$AI" = 1 ] && [ "$OTP" = 0 ]; then
  echo "--ai đi cùng --otp (flow 40 cần người và nhóm của flow 24)" >&2; exit 64
fi
if [ "$OTP" = 1 ]; then
  [ -n "$API_PORT" ] \
    || { echo "--otp cần --api-port <cổng API prod có MOBILE_OTP_DEBUG_CODE=$OTP_CODE và log sender>" >&2; exit 64; }
  [ "$LIVE" = 0 ] && [ "$DANG_NHAP" = 0 ] \
    || { echo "--otp loại trừ --live và --dang-nhap: mỗi chế độ một cửa vào" >&2; exit 64; }
fi

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$REPO/apps/mobile"
LOG="$(mktemp -t metro-native-XXXXXX.log)"
METRO_PID=""

khong_do_duoc() { echo "KHÔNG ĐO ĐƯỢC: $*" >&2; exit 2; }
hong()          { echo "ĐỎ: $*" >&2; exit 1; }

# --- công cụ ---------------------------------------------------------------
export ANDROID_HOME="${ANDROID_HOME:-$HOME/Android/Sdk}"
export PATH="$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$HOME/.maestro/bin:$PATH"

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

# Target ship là development build của CHÍNH app (com.lakiet.rudi), không phải
# Expo Go: Google Sign-In là mã native mà Expo Go không nạp được, và launcher của
# dev client mở lại bundle gần nhất nên flow chỉ cần `launchApp`. Expo Go còn
# giữ sau `--expo-go` cho máy chưa dựng được APK.
if [ "$MODE" = "dev-client" ]; then
  APP_ID="com.lakiet.rudi"
  timeout 30 adb shell pm list packages 2>/dev/null | grep -q "^package:$APP_ID\$" \
    || khong_do_duoc "máy $ANDROID_SERIAL chưa cài dev client ($APP_ID). Dựng: cd apps/mobile && npx expo prebuild --platform android && (cd android && ./gradlew :app:assembleDebug -PreactNativeArchitectures=x86_64) rồi adb install -r."
  APP_VER="$(timeout 30 adb shell dumpsys package "$APP_ID" 2>/dev/null \
               | sed -n 's/.*versionName=\([^ ]*\).*/\1/p' | head -1)"
  echo "dev client: $APP_ID ${APP_VER:-không đọc được}"
  # Bản native có khớp cây không: package.json và app.json quyết định mã native
  # (plugin, module). Đổi chúng mà không dựng lại thì APK trên máy là bản khác —
  # và mọi assert sau đó nói về bản đó. Kiểm bằng dấu vân ghi lúc build.
  FP_FILE="$APP/android/.rudi-native-fingerprint"
  FP_NOW="$(cd "$APP" && git hash-object package.json app.json | tr '\n' ' ')"
  if [ -f "$FP_FILE" ]; then
    [ "$(cat "$FP_FILE")" = "$FP_NOW" ] \
      || khong_do_duoc "dev client CŨ: package.json/app.json đã đổi sau lần build ghi ở $FP_FILE. Dựng lại, cài lại, rồi ghi: (cd apps/mobile && git hash-object package.json app.json | tr '\\n' ' ' > android/.rudi-native-fingerprint)"
  else
    echo "CHÚ Ý: chưa có $FP_FILE — không kiểm được APK trên máy có khớp package.json/app.json hiện tại."
  fi
  EXPO_VER="dev-client ${APP_VER:-?}"
else
  APP_ID="host.exp.exponent"
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
fi

# Dấu vân của lượt chạy (NEO 2b). Inline vào bundle lúc Metro khởi động, app vẽ
# ở chân màn chào, flow assert qua -e TREE_FINGERPRINT. Có $$ để hai lượt cùng
# giây trên cùng commit vẫn khác nhau.
DAU_VAN="$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo nogit)-$$-$(date +%s)"
ANH_DIR="$REPO/.impeccable/review/native/$(date +%Y%m%d-%H%M%S)-$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo nogit)"
mkdir -p "$ANH_DIR"
echo "dấu vân lượt này: $DAU_VAN — ảnh: $ANH_DIR"

# Xoá dữ liệu Expo Go: phiên đã đăng nhập nằm trong AsyncStorage của nó.
#
# Cần ở HAI chỗ, và cả hai đều là chuyện thật:
#
#  - Trước bảng ở chế độ `--dang-nhap`: một phiên còn sót từ lượt trước làm
#    flow 21 bắt đầu từ app ĐÃ đăng nhập, tức nó không còn đo cửa vào nữa.
#  - Trước canary ở cùng chế độ: sau flow 21 máy đang đăng nhập THẬT, nên màn
#    chào không còn nút «Vào bản trải nghiệm Team Đà Lạt» và con canary chết ở
#    bước 1. Đo ngày 2026-09-03: đúng như vậy, và cổng đọc nó thành "canary đỏ
#    đúng thiết kế" — hai lần liên tiếp, hai lý do khác nhau.
xoa_du_lieu_app() {
  timeout 60 adb shell pm clear "$APP_ID" >/dev/null 2>&1 \
    || khong_do_duoc "không xoá được dữ liệu $APP_ID trên $ANDROID_SERIAL."
  # Dev client: `pm clear` cũng xoá «bundle gần nhất», nên lần mở kế tiếp rơi vào
  # launcher («Development servers»). Ai gọi hàm này phải mo_link lại rồi mới
  # chạy flow; xem chỗ gọi.
}

# --- lời mời thật, cho lượt đăng nhập --------------------------------------
#
# Cả bảng mặc định lẫn `--live` đều đi vòng qua cửa đăng nhập: một cái dùng
# fixture, cái kia ghim sẵn danh tính vào bundle. Không cái nào chạm đường mà
# NGƯỜI THẬT đi. Chế độ này dựng đúng đường đó: phiên đầu tiên bằng
# `genesis_session.py` (cửa duy nhất ngoài HTTP trên một host sạch), rồi nhóm,
# chuyến, và một lời mời ĐÍCH DANH — toàn bộ qua HTTP ở chế độ prod.
#
# Người vừa nhận lời mời là `invited`, chưa phải thành viên, nên máy chủ vẫn từ
# chối dữ liệu nhóm. Thành viên duyệt là một bước riêng ở đây vì nó là một bước
# riêng trong đời thật — và vì màn hình phải nói được hai câu khác nhau cho hai
# trạng thái đó.
# --- cửa OTP, cho lượt --otp -------------------------------------------------
#
# Không ghim danh tính, không mint lời mời: app đi đúng đường một người lạ đi —
# gõ số, nhận mã, có phiên. Số sinh lúc chạy (mỗi lượt một số mới, vì người đã
# có nhóm không còn thấy «Chưa có nhóm nào») và không bao giờ nằm trong file:
# repo guard chặn số di động, và đó là ý đồ.
sinh_so_di_dong() {
  # 09 + 8 chữ số: hợp lệ với `chuanHoaSo` (đầu 3/5/7/8/9, chín số sau số 0).
  # `10 ** 8` chứ không viết số: repo guard đọc chín chữ số liền là số tài khoản.
  printf '09%08d' "$(( (RANDOM * 32768 + RANDOM) % (10 ** 8) ))"
}

# Đối chứng DƯƠNG môi trường, trước khi chạy flow: API này có nhận mã debug
# không? Không kiểm thì một API thiếu MOBILE_OTP_DEBUG_CODE làm flow 22 đỏ ở bước
# nhập mã, và màu đỏ đó đọc y hệt «app hỏng».
kiem_ma_debug() {
  local goc so id rc
  goc="http://127.0.0.1:$API_PORT"
  so="$(sinh_so_di_dong)"
  id="$(curl -sS -X POST "$goc/auth/otp/request" -H 'Content-Type: application/json' \
      -d "{\"phone\":\"$so\"}" \
    | python3 -c 'import json,sys;print(json.load(sys.stdin).get("challenge_id",""))' 2>/dev/null || true)"
  [ -n "$id" ] || khong_do_duoc "API $API_PORT không cấp challenge OTP (thiếu route /auth/otp/request, hay API không chạy?)."
  rc="$(curl -sS -o /dev/null -w '%{http_code}' -X POST "$goc/auth/otp/verify" \
      -H 'Content-Type: application/json' \
      -d "{\"challenge_id\":\"$id\",\"phone\":\"$so\",\"code\":\"$OTP_CODE\"}")"
  [ "$rc" = "201" ] || khong_do_duoc "API $API_PORT không nhận mã debug $OTP_CODE (HTTP $rc). Chạy API với MOBILE_OTP_DEBUG_CODE=$OTP_CODE và log sender, ví dụ scripts/e2e_slice.sh --keep."
  echo "API $API_PORT nhận mã debug: đối chứng dương môi trường qua"
}

# Đăng nhập một số qua curl với mã debug; in thân SessionResponse ra stdout.
# Mỗi số có nhịp gửi lại 60s và trần 5 mã/15 phút — các bước kiểm sau flow đăng
# nhập lại đúng những số flow vừa dùng, nên gặp 429 thì đợi 61s và thử lại MỘT
# lần thay vì đọc nhịp chống dò thành «máy chủ hỏng».
# Một phiên curl cho mỗi số trong một lượt. Hai kiểm máy chủ liền nhau trên
# cùng số (24 rồi 25 với D) không xin mã hai lần: lần hai đã ăn nhịp 60 s của
# lần một. Thân phiên được cache là bản lúc đăng nhập — `contexts` trong đó có
# thể cũ; kiểm nào cần trạng thái mới thì hỏi máy chủ bằng token, đừng đọc lại
# thân. Cache là FILE (tên = sha256 của số, không phải số): hàm này luôn được
# gọi trong `$(...)`, tức một subshell, nên một mảng bash gán ở đây không bao
# giờ tới được người gọi — lượt 8 của M3 đã xin mã hai lần dù «có cache».
PHIEN_CURL_DIR="$(mktemp -d)"

dang_nhap_curl() {
  local so="$1" goc id rc body lan tep ma khoa
  khoa="$PHIEN_CURL_DIR/$(printf '%s' "$so" | sha256sum | cut -c1-32)"
  if [ -s "$khoa" ]; then
    cat "$khoa"
    return 0
  fi
  goc="http://127.0.0.1:$API_PORT"
  tep="$(mktemp)"
  for lan in 1 2; do
    rc="$(curl -sS -o "$tep" -w '%{http_code}' -X POST "$goc/auth/otp/request" \
        -H 'Content-Type: application/json' -d "{\"phone\":\"$so\"}")"
    if [ "$rc" = "429" ] && [ "$lan" = 1 ]; then
      # 60 s theo đồng hồ máy chủ; 61 s theo đồng hồ này đã hụt vài trăm ms
      # (đồng hồ DB trong container lệch với WSL2). 66 s là đủ dư.
      echo "  (số đang trong nhịp gửi lại 60s, đợi rồi thử lại)" >&2
      sleep 66
      continue
    fi
    if [ "$rc" != "202" ]; then
      # Say which door refused: the phone cooldown, the per-IP window, or a
      # transport error. «429 twice» told nobody anything.
      ma="$(python3 -c 'import json,sys
try: print(json.load(open(sys.argv[1])).get("code", "?"))
except Exception: print("(không phải JSON)")' "$tep" 2>/dev/null)"
      echo "  (xin mã lần $lan: HTTP $rc, code=$ma)" >&2
      rm -f "$tep"; return 1
    fi
    id="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("challenge_id",""))' "$tep")"
    body="$(curl -sS -X POST "$goc/auth/otp/verify" -H 'Content-Type: application/json' \
        -d "{\"challenge_id\":\"$id\",\"phone\":\"$so\",\"code\":\"$OTP_CODE\"}")"
    rm -f "$tep"
    printf '%s' "$body" > "$khoa"
    printf '%s' "$body"
    return 0
  done
  rm -f "$tep"
  return 1
}

# Sau flow 24: người được mời (OTP_PHONE_D) chưa từng mở app. Đăng nhập bằng số
# đó qua curl và hỏi máy chủ nhóm nào đang chờ họ — nếu lời mời chỉ tồn tại trên
# màn hình của người mời thì đây là chỗ nó lộ ra.
kiem_may_chu_sau_24() {
  local body via ten
  body="$(dang_nhap_curl "$OTP_PHONE_D")" \
    || hong "sau flow 24: người được mời (số D) không đăng nhập được qua curl (429 hai lần hoặc lỗi)."
  via="$(printf '%s' "$body" | python3 -c '
import json, sys
d = json.load(sys.stdin)
# invited ngay sau flow 24; active nếu flow 25 cùng lượt đã cho D bấm «Đồng ý».
moi = [c for c in d.get("contexts", []) if c.get("my_state") in ("invited", "active")]
ten_nhom = moi[0]["display_name"] if moi else ""
ten_nguoi = d.get("profile", {}).get("display_name", "")
print("%d|%s|%s" % (len(moi), ten_nhom, ten_nguoi))')"
  IFS='|' read -r so_moi ten_nhom ten_nguoi <<< "$via"
  [ "$so_moi" = "1" ] && [ "$ten_nhom" = "Hoi QA" ] \
    || hong "sau flow 24: máy chủ không có «Hoi QA» cho người được mời (nhóm đếm=$so_moi, tên='$ten_nhom')."
  ten="$ten_nguoi"
  [ "$ten" = "Ban QA" ] || hong "sau flow 24: người được mời phải mang tên người mời đặt ('Ban QA'), máy chủ trả '$ten'."
  echo "máy chủ xác nhận: người được mời (số D) đăng nhập thấy «Hoi QA» (mời hoặc đã vào), tên «Ban QA» do người mời đặt"
}

# Sau flow 25: D (số D) vừa đồng ý vào «Hoi QA» và đồng ý kết bạn với C trên máy.
# Hỏi máy chủ với tư cách D: một bạn, một nhóm — không đọc từ màn hình.
kiem_may_chu_sau_25() {
  local goc body tok ket
  goc="http://127.0.0.1:$API_PORT"
  body="$(dang_nhap_curl "$OTP_PHONE_D")" \
    || hong "sau flow 25: D không đăng nhập được qua curl (429 hai lần hoặc lỗi)."
  tok="$(printf '%s' "$body" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("token",""))')"
  [ -n "$tok" ] || hong "sau flow 25: D không đăng nhập được."
  ket="$(curl -sS "$goc/people/me" -H "Authorization: Bearer $tok" | python3 -c '
import json, sys
d = json.load(sys.stdin)
c = d.get("counts", {})
print("%s|%s|%s" % (c.get("friends"), c.get("contexts"), d.get("display_name", "")))')"
  IFS='|' read -r so_ban so_nhom ten <<< "$ket"
  [ "$so_ban" = "1" ] && [ "$so_nhom" = "1" ] \
    || hong "sau flow 25: máy chủ đếm cho D friends=$so_ban contexts=$so_nhom, mong 1 và 1."
  echo "máy chủ xác nhận: D có 1 bạn (C) và 1 nhóm (Hoi QA) sau khi bấm hai lần «Đồng ý» trên máy"
}

# Sau flow 30: hỏi máy chủ với tư cách C — tin nhắn có thật, thẻ poll có thật,
# phản ứng heart có thật. Màn hình chỉ là nơi bấm.
# Sau flow 26: D bấm «Lưu địa điểm» trên máy → máy chủ giữ đúng một địa điểm đã
# lưu cho D (GET /people/me/saved-places), và đó là chỗ flow đã mở.
kiem_may_chu_sau_26() {
  local goc body tok ket
  goc="http://127.0.0.1:$API_PORT"
  body="$(dang_nhap_curl "$OTP_PHONE_D")" \
    || hong "sau flow 26: D không đăng nhập được qua curl."
  tok="$(printf '%s' "$body" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("token",""))')"
  [ -n "$tok" ] || hong "sau flow 26: D không có token."
  ket="$(curl -sS "$goc/people/me/saved-places" -H "Authorization: Bearer $tok" | python3 -c '
import json, sys
d = json.load(sys.stdin)
ds = [s.get("place_id") for s in d.get("saved", [])]
print("%d|%s" % (len(ds), ",".join(sorted(x for x in ds if isinstance(x, str)))))')"
  IFS='|' read -r so_luu ids <<< "$ket"
  [ "${so_luu:-0}" -eq 1 ] || hong "sau flow 26: máy chủ giữ $so_luu địa điểm đã lưu cho D, mong 1."
  [ "$ids" = "p-tiem-nuong-xom-lao" ] || hong "sau flow 26: địa điểm đã lưu là '$ids', mong p-tiem-nuong-xom-lao."
  echo "máy chủ xác nhận: D đã lưu đúng một địa điểm ($ids) từ chi tiết địa điểm"
}

# Sau flow 27: nhóm của D có kèo «Keo QA» với hai chặng (chặng đầu trỏ
# p-tiem-nuong-xom-lao) và một check-in của D — kèo, chặng, địa điểm và check-in
# đều là hàng trên máy chủ, không phải trạng thái trên máy.
kiem_may_chu_sau_27() {
  local goc body tok ctx ket
  goc="http://127.0.0.1:$API_PORT"
  body="$(dang_nhap_curl "$OTP_PHONE_D")" \
    || hong "sau flow 27: D không đăng nhập được qua curl."
  tok="$(printf '%s' "$body" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("token",""))')"
  ctx="$(curl -sS "$goc/people/me/contexts" -H "Authorization: Bearer $tok" | python3 -c '
import json, sys
d = json.load(sys.stdin)
act = [c for c in d.get("contexts", []) if c.get("my_state") == "active"]
print(act[0]["id"] if act else "")')"
  [ -n "$tok" ] && [ -n "$ctx" ] || hong "sau flow 27: D không có nhóm active."
  ket="$(python3 - "$goc" "$tok" "$ctx" <<'PY3'
import json, sys, urllib.request
goc, tok, ctx = sys.argv[1:4]
def get(path):
    req = urllib.request.Request(goc + path, headers={"Authorization": "Bearer " + tok})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)
keo = [o for o in get(f"/contexts/{ctx}/outings").get("outings", []) if o.get("title") == "Keo QA"]
if not keo:
    print("0|0||0"); sys.exit()
o = keo[0]
stops = sorted(o.get("stops", []), key=lambda s: s.get("position", 0))
ids = ",".join(str(s.get("place_id")) for s in stops)
ci = get(f"/outings/{o['id']}/checkins").get("checkins", [])
print("%d|%d|%s|%d" % (len(keo), len(stops), ids, len(ci)))
PY3
)"
  IFS='|' read -r so_keo so_chang ids so_ci <<< "$ket"
  [ "${so_keo:-0}" -eq 1 ] || hong "sau flow 27: máy chủ có $so_keo kèo «Keo QA» trong nhóm của D, mong 1."
  [ "${so_chang:-0}" -eq 2 ] || hong "sau flow 27: kèo có $so_chang chặng, mong 2."
  case "$ids" in *p-tiem-nuong-xom-lao*) ;; *) hong "sau flow 27: không chặng nào trỏ p-tiem-nuong-xom-lao (place_id: $ids)." ;; esac
  [ "${so_ci:-0}" -ge 1 ] || hong "sau flow 27: kèo không có check-in nào."
  echo "máy chủ xác nhận: kèo «Keo QA» có $so_chang chặng (place_id: $ids) và $so_ci check-in"
}

# Sau flow 28: sổ của nhóm D có khoản chi 200.000đ do D trả, chia C 75.000 /
# D 125.000 → /contexts/{ctx}/balances phải nói C chuyển D 75.000 (một khoản).
kiem_may_chu_sau_28() {
  local goc body tok ctx ket
  goc="http://127.0.0.1:$API_PORT"
  body="$(dang_nhap_curl "$OTP_PHONE_D")" \
    || hong "sau flow 28: D không đăng nhập được qua curl."
  tok="$(printf '%s' "$body" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("token",""))')"
  ctx="$(curl -sS "$goc/people/me/contexts" -H "Authorization: Bearer $tok" | python3 -c '
import json, sys
d = json.load(sys.stdin)
act = [c for c in d.get("contexts", []) if c.get("my_state") == "active" and c.get("display_name") == "Hoi QA"]
print(act[0]["id"] if act else "")')"
  [ -n "$tok" ] && [ -n "$ctx" ] || hong "sau flow 28: D không có nhóm «Hoi QA» active."
  ket="$(curl -sS "$goc/contexts/$ctx/balances" -H "Authorization: Bearer $tok" | python3 -c '
import json, sys
d = json.load(sys.stdin)
t = d.get("transfers", [])
print("%d|%s" % (len(t), ",".join(str(x.get("amount_vnd")) for x in t)))')"
  IFS='|' read -r so_chuyen tien <<< "$ket"
  # Flow 29 (same lap) publishes a round and D confirms the receipt, so the
  # ledger then owes nothing: zero transfers is the RIGHT answer once a round
  # with a confirmed obligation exists. Read the rounds before deciding.
  local da_ve
  da_ve="$(curl -sS "$goc/contexts/$ctx/batches" -H "Authorization: Bearer $tok" | python3 -c '
import json, sys
d = json.load(sys.stdin)
print(sum(int(b.get("confirmed_count") or 0) for b in d.get("batches", [])))' 2>/dev/null || echo 0)"
  if [ "${da_ve:-0}" -ge 1 ]; then
    [ "${so_chuyen:-0}" -eq 0 ] || hong "sau flow 28: đợt thu đã có $da_ve biên nhận mà sổ vẫn còn $so_chuyen khoản chuyển."
    echo "máy chủ xác nhận: khoản chuyển 75.000đ (C → D) đã được đợt thu tất toán (flow 29), sổ không còn nợ, tính lại từ sổ"
    return 0
  fi
  [ "${so_chuyen:-0}" -eq 1 ] || hong "sau flow 28: máy chủ có $so_chuyen khoản chuyển, mong 1 (C → D)."
  [ "$tien" = "75000" ] || hong "sau flow 28: khoản chuyển là $tien đồng, mong 75000."
  echo "máy chủ xác nhận: quyết toán nhóm có đúng một khoản chuyển 75.000đ (C → D), tính lại từ sổ"
}

kiem_may_chu_sau_29() {
  local goc body tok ctx ket
  goc="http://127.0.0.1:$API_PORT"
  body="$(dang_nhap_curl "$OTP_PHONE_D")" \
    || hong "sau flow 29: D không đăng nhập được qua curl."
  tok="$(printf '%s' "$body" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("token",""))')"
  ctx="$(curl -sS "$goc/people/me/contexts" -H "Authorization: Bearer $tok" | python3 -c '
import json, sys
d = json.load(sys.stdin)
act = [c for c in d.get("contexts", []) if c.get("my_state") == "active" and c.get("display_name") == "Hoi QA"]
print(act[0]["id"] if act else "")')"
  [ -n "$tok" ] && [ -n "$ctx" ] || hong "sau flow 29: D không có nhóm «Hoi QA» active."
  # The round list is the server's fold of the board: one round, published,
  # one obligation, one confirmed receipt, 75.000đ. Anything else is a lie the
  # screen told, or a write the screen claimed and the server never got.
  ket="$(curl -sS "$goc/contexts/$ctx/batches" -H "Authorization: Bearer $tok" | python3 -c '
import json, sys
d = json.load(sys.stdin)
b = d.get("batches", [])
if len(b) != 1:
    print("so_dot=%d" % len(b))
else:
    x = b[0]
    print("%s|%s|%s|%s|%s" % (x.get("status"), x.get("obligation_count"), x.get("confirmed_count"), x.get("disputed_count"), x.get("total_vnd")))')"
  case "$ket" in
    so_dot=*) hong "sau flow 29: máy chủ có ${ket#so_dot=} đợt thu, mong 1." ;;
  esac
  IFS='|' read -r trang_thai so_nv so_ve so_tc tong <<< "$ket"
  [ "$trang_thai" = "published" ] || hong "sau flow 29: đợt thu ở trạng thái $trang_thai, mong published."
  [ "${so_nv:-0}" -eq 1 ] && [ "${so_ve:-0}" -eq 1 ] && [ "${so_tc:-0}" -eq 0 ] \
    || hong "sau flow 29: nghĩa vụ $so_nv, đã về $so_ve, thắc mắc $so_tc; mong 1/1/0."
  [ "$tong" = "75000" ] || hong "sau flow 29: tổng đợt thu là $tong đồng, mong 75000."
  echo "máy chủ xác nhận: nhóm có đúng một đợt thu đã phát, 1/1 nghĩa vụ 75.000đ đã về (biên nhận do D, người được nhận, xác nhận)"
}

kiem_may_chu_sau_30() {
  local goc body tok ctx ket
  goc="http://127.0.0.1:$API_PORT"
  body="$(dang_nhap_curl "$OTP_PHONE_C")" \
    || hong "sau flow 30: C không đăng nhập được qua curl (429 hai lần hoặc lỗi)."
  tok="$(printf '%s' "$body" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("token",""))')"
  ctx="$(printf '%s' "$body" | python3 -c '
import json, sys
d = json.load(sys.stdin)
act = [c for c in d.get("contexts", []) if c.get("my_state") == "active"]
# Flow 40 adds «Plan QA» to C before these checks run; the flow-30 traffic
# (text, poll, heart) lives in «Hoi QA», so pick it by name, not by position.
hoi = [c for c in act if c.get("display_name") == "Hoi QA"]
print((hoi or act)[0]["id"] if act else "")')"
  [ -n "$tok" ] && [ -n "$ctx" ] || hong "sau flow 30: C không đăng nhập được hoặc không có nhóm."
  ket="$(curl -sS "$goc/contexts/$ctx/messages?limit=50" -H "Authorization: Bearer $tok" | python3 -c '
import json, sys
d = json.load(sys.stdin)
ms = d.get("messages", [])
texts = [m for m in ms if m.get("kind") == "text"]
polls = [m for m in ms if m.get("kind") == "ai_card" and (m.get("card") or {}).get("kind") == "poll"]
hearts = sum(r.get("count", 0) for m in texts for r in m.get("reactions", []) if r.get("kind") == "heart")
print("%d|%d|%d" % (len(texts), len(polls), hearts))')"
  IFS='|' read -r so_text so_poll so_heart <<< "$ket"
  [ "${so_text:-0}" -ge 3 ] && [ "${so_poll:-0}" -ge 1 ] && [ "${so_heart:-0}" -ge 1 ] \
    || hong "sau flow 30: máy chủ có text=$so_text poll=$so_poll heart=$so_heart, mong ≥3, ≥1, ≥1."
  echo "máy chủ xác nhận: nhóm của C có $so_text tin chữ, $so_poll thẻ bình chọn, $so_heart phản ứng ❤ — chat là thật"
}

# Khoá AI còn sống không — hỏi bằng đường sản phẩm, không hỏi biến môi trường.
kiem_khoa_ai() {
  local goc so body tok ctx ket
  goc="http://127.0.0.1:$API_PORT"
  so="$(sinh_so_di_dong)"
  body="$(dang_nhap_curl "$so")" || khong_do_duoc "không đăng nhập được người thăm dò AI."
  tok="$(printf '%s' "$body" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("token",""))')"
  ctx="$(curl -sS -X POST "$goc/contexts" -H 'Content-Type: application/json' -H "Authorization: Bearer $tok" \
      -H "Idempotency-Key: ai-probe-ctx-$so" -d '{"display_name":"Tham do AI"}' \
    | python3 -c 'import json,sys;print(json.load(sys.stdin).get("id",""))')"
  [ -n "$ctx" ] || khong_do_duoc "người thăm dò AI không mở được nhóm."
  curl -sS -o /dev/null -X POST "$goc/contexts/$ctx/messages" -H 'Content-Type: application/json' \
      -H "Authorization: Bearer $tok" -H "Idempotency-Key: ai-probe-msg-$so" \
      -d '{"kind":"text","body":"Toi nay ca hoi di an o Da Lat, ngan sach vua, goi y giup","image_url":null,"card":null}'
  ket="$(curl -sS -X POST "$goc/contexts/$ctx/ai-turn" -H 'Content-Type: application/json' \
      -H "Authorization: Bearer $tok" -d '{"requested":true}' \
    | python3 -c 'import json,sys;d=json.load(sys.stdin);print("%s|%s" % (d.get("spoke"), d.get("reason")))')"
  case "$ket" in
    True\|*) echo "khoá AI còn sống trên API $API_PORT (lượt thăm dò: mô hình đã trả lời)" ;;
    *\|unavailable) hong "khoá AI CHẾT hoặc thiếu trên API $API_PORT (ai-turn: unavailable). Flow AI không chạy, và đó là màu đỏ." ;;
    *\|ungrounded) echo "khoá AI sống nhưng lượt thăm dò trả thẻ không grounded ($ket) — vẫn đo tiếp" ;;
    *) khong_do_duoc "ai-turn thăm dò trả «$ket», không kết luận được về khoá." ;;
  esac
}

# Sau flow 40: thẻ AI có thật và GROUNDED — mọi place_id trong thẻ nằm trong
# catalogue GET /places. Một thẻ nêu chỗ không có trong danh mục là thứ ground_card
# phải chặn; ở đây đo lại từ ngoài.
kiem_may_chu_sau_40() {
  local goc body tok ctx ket
  goc="http://127.0.0.1:$API_PORT"
  # Flow 40 keeps whichever session flow 31 left (C, or D after a fallback
  # sign-in) and creates «Plan QA» there; find that group through the live
  # contexts list, not the cached sign-in body.
  local so
  tok=""; ctx=""
  for so in "$OTP_PHONE_C" "$OTP_PHONE_D"; do
    body="$(dang_nhap_curl "$so")" || continue
    tok="$(printf '%s' "$body" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("token",""))')"
    [ -n "$tok" ] || continue
    ctx="$(curl -sS "$goc/people/me/contexts" -H "Authorization: Bearer $tok" | python3 -c '
import json, sys
d = json.load(sys.stdin)
hit = [c for c in d.get("contexts", []) if c.get("display_name") == "Plan QA" and c.get("my_state") == "active"]
print(hit[0]["id"] if hit else "")')"
    [ -n "$ctx" ] && break
  done
  [ -n "$tok" ] && [ -n "$ctx" ] || hong "sau flow 40: không thấy nhóm «Plan QA» của C hay D trên máy chủ."
  ket="$(python3 - "$goc" "$tok" "$ctx" <<'PY2'
import json, sys, urllib.request
goc, tok, ctx = sys.argv[1:4]
def get(path):
    req = urllib.request.Request(goc + path, headers={"Authorization": "Bearer " + tok})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)
ms = get(f"/contexts/{ctx}/messages?limit=50").get("messages", [])
ai = [m for m in ms if m.get("kind") == "ai_card" and m.get("author_id") is None
      and (m.get("card") or {}).get("kind") in ("text", "places", "itinerary")]
places = {p.get("id") for p in get("/places").get("places", [])}
la = 0
mu = 0
for m in ai:
    card = m["card"]; p = card.get("payload") or {}
    ids = [pl.get("id") for pl in p.get("places", []) if isinstance(pl, dict)]
    ids += [(st.get("place") or {}).get("id") for st in p.get("stops", []) if isinstance(st, dict)]
    if card.get("kind") in ("places", "itinerary") and not ids:
        mu += 1
    la += sum(1 for i in ids if i and i not in places)
print("%d|%d|%d|%s" % (len(ai), la, mu, ",".join(sorted({m["card"]["kind"] for m in ai}))))
PY2
)"
  IFS='|' read -r so_ai so_la so_mu loai <<< "$ket"
  [ "${so_ai:-0}" -ge 1 ] || hong "sau flow 40: máy chủ không có thẻ AI nào (author null, kind text/places/itinerary)."
  # A places/itinerary card the check read zero ids from is a blind check, not
  # a grounded card: the keys drifted (that is exactly how the first version of
  # this check passed for a week while reading `items`/`days` nobody sends).
  [ "${so_mu:-1}" -eq 0 ] || hong "sau flow 40: $so_mu thẻ AI không đọc được place id nào — máy đo mù với hình dạng thẻ."
  [ "${so_la:-1}" -eq 0 ] || hong "sau flow 40: thẻ AI nêu $so_la place_id KHÔNG có trong GET /places — grounding thủng."
  echo "máy chủ xác nhận: nhóm «Plan QA» có $so_ai thẻ AI ($loai), mọi địa điểm đều trong catalogue"
}

# Canary cho chế độ --otp. Canary 09 đi đường fixture, mà ở đây cửa fixture tắt
# có chủ ý — nó sẽ chết ở bước 1, tức chứng minh harness hỏng chứ không chứng
# minh assert cắn. Đối chứng âm đúng của lượt này: chạy LẠI flow 22 với mã SAI
# làm «mã debug». Flow phải đỏ, và đỏ ĐÚNG ở bước chờ «Chưa có nhóm nào» —
# nghĩa là không có mã đúng thì app không bao giờ vào được trạng thái đăng nhập.
canary_otp() {
  local ra so rc dong
  ra="$(mktemp)"; so="$(sinh_so_di_dong)"
  set +e
  maestro test -e TREE_FINGERPRINT="$DAU_VAN" -e OTP_PHONE="$so" -e OTP_PHONE_B="$so" \
    -e OTP_PHONE_C="$so" -e OTP_PHONE_D="$so" -e OTP_CODE="999999" \
    "$FLOWS/22-dang-nhap-otp.yaml" > "$ra" 2>&1
  rc=$?
  set -e
  [ "$rc" -ne 0 ] || hong "canary OTP XANH: flow 22 qua với mã SAI. Assert đăng nhập không cắn."
  dong="$(grep -n 'FAILED' "$ra" | head -1 || true)"
  case "$dong" in
    *"Chưa có nhóm nào"*) echo "canary OTP: mã sai → đỏ đúng ở bước chờ «Chưa có nhóm nào». Không có mã đúng thì không vào được." ;;
    "") sed -n '1,40p' "$ra" >&2; hong "canary OTP thoát khác 0 mà không có bước nào FAILED — chết trước khi chạy." ;;
    *) sed -n '1,60p' "$ra" >&2; hong "canary OTP đỏ ở bước KHÁC ($dong). Chưa chứng minh được gì." ;;
  esac
  rm -f "$ra"
}

API_URL=""
dung_loi_moi() {
  API_URL="http://127.0.0.1:$API_PORT"
  local dsn owner_line owner_id owner_token ctx outing guest
  dsn="${MOBILE_DATABASE_URL:-}"
  [ -n "$dsn" ] || khong_do_duoc "--dang-nhap cần MOBILE_DATABASE_URL để mint phiên đầu tiên."

  owner_line="$(MOBILE_DATABASE_URL="$dsn" python3 "$REPO/scripts/genesis_session.py" \
      --display-name "Chu nhom e2e" --group "RuDi cua vao" --json)" \
    || khong_do_duoc "genesis_session.py hỏng."
  owner_id="$(printf '%s' "$owner_line" | python3 -c 'import json,sys;print(json.load(sys.stdin)["person_id"])')"
  owner_token="$(printf '%s' "$owner_line" | python3 -c 'import json,sys;print(json.load(sys.stdin)["token"])')"

  ctx="$(curl -fsS -X POST "$API_URL/contexts" \
      -H 'Content-Type: application/json' -H "Authorization: Bearer $owner_token" \
      -H "Idempotency-Key: native-ctx-$owner_id" \
      -d '{"display_name":"RuDi cua vao"}' \
    | python3 -c 'import json,sys;print(json.load(sys.stdin)["id"])')" \
    || khong_do_duoc "không tạo được nhóm."

  outing="$(curl -fsS -X POST "$API_URL/contexts/$ctx/outings" \
      -H 'Content-Type: application/json' -H "Authorization: Bearer $owner_token" \
      -H "Idempotency-Key: native-outing-$owner_id" \
      -d '{"title":"Chuyen cua vao","starts_on":"2030-10-17","ends_on":"2030-10-19","headcount":2,"budget_per_person_vnd":0}' \
    | python3 -c 'import json,sys;print(json.load(sys.stdin)["id"])')" \
    || khong_do_duoc "không tạo được chuyến."

  guest="$(python3 -c 'import uuid;print(uuid.uuid4())')"
  curl -fsS -X PUT "$API_URL/people/$guest" \
      -H 'Content-Type: application/json' -H "Authorization: Bearer $owner_token" \
      -d '{"display_name":"Khach RuDi"}' >/dev/null \
    || khong_do_duoc "không đặt được tên người được mời."

  MA_LOI_MOI="$(curl -fsS -X POST "$API_URL/outings/$outing/invites" \
      -H 'Content-Type: application/json' -H "Authorization: Bearer $owner_token" \
      -H "Idempotency-Key: native-invite-$guest" \
      -d "{\"source\":\"friend\",\"person_id\":\"$guest\"}" \
    | python3 -c 'import json,sys;print(json.load(sys.stdin)["invite_token"])')" \
    || khong_do_duoc "không mint được lời mời đích danh."

  # Người này sẽ dừng ở `invited`, và lượt đo dừng ở đó CÓ CHỦ Ý.
  #
  # Theo ADR-0014 mục 8, lời mời đích danh thì chính người được mời đồng ý
  # (`is_invitee`) — không phải thành viên khác duyệt. Nhưng để bấm nút đó,
  # client cần `membership_id`, mà `SessionResponse` không mang. Nên đường
  # `invited` → `active` chưa đi được từ RuDi, và flow 21 khẳng định đúng cái
  # nó đo được: đăng nhập thật xong, và màn tiền VẪN KHÔNG live.
  echo "lời mời đã dựng cho nhóm $ctx"
}

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

if [ "$DANG_NHAP" = 1 ]; then
  # Trước khi mint bất cứ thứ gì: một phiên còn sót từ lượt trước làm flow 21
  # bắt đầu từ app ĐÃ đăng nhập, và lúc đó nó không đo cửa vào nữa mà đo một
  # app đang mở sẵn — vẫn xanh, vẫn vô nghĩa.
  xoa_du_lieu_app
  dung_loi_moi
fi

if timeout 20 adb reverse --list 2>/dev/null | grep -q "tcp:$PORT"; then
  hong "cổng $PORT đã có người cắm reverse. Đổi bằng MOBILE_METRO_PORT=<cổng khác>."
fi

# Đọc bảng socket bằng `ss`, KHÔNG connect: trên WSL2 mirrored networking, nối
# tới 127.0.0.1 ở một cổng TRỐNG nuốt gói SYN và treo vô hạn.
if command -v ss >/dev/null 2>&1 && ss -ltn 2>/dev/null | grep -qE "127\.0\.0\.1:$PORT[[:space:]]"; then
  hong "cổng $PORT đã có người nghe. Metro của lane khác phục vụ một bundle hợp lệ của CÂY KHÁC, và thiết bị không phân biệt được. Đổi bằng MOBILE_METRO_PORT=<cổng khác>."
fi

if [ "$OTP" = 1 ]; then kiem_ma_debug; fi
# V4: khoá AI phải SỐNG trước khi đo AI, đo bằng chính đường sản phẩm: một người
# thăm dò đăng nhập, mở nhóm, nhắn một câu, xin một lượt AI (requested=true).
# `spoke=true` = khoá sống; `reason=unavailable` = khoá chết/thiếu → ĐỎ (một máy
# có khoá mà không dùng được là lỗi phải thấy); `ungrounded` = mô hình trả lời
# nhưng thẻ không đứng được → vẫn là khoá sống, ghi lại. check_demo_ai_key.py chỉ
# đối chiếu container demo, không dùng cho uvicorn trần.
if [ "$AI" = 1 ]; then kiem_khoa_ai; fi

(
  cd "$APP"
  # `export` rather than an assignment prefix: bash decides what is an
  # assignment BEFORE expanding, so `${API_PORT:+EXPO_PUBLIC_API_URL=...}` in
  # prefix position is run as a COMMAND named "EXPO_PUBLIC_API_URL=http://...".
  # That is exactly how the first run of this script failed, and the anchor
  # below caught it as "Metro is not serving this tree" -- which was true.
  export CI=1 EXPO_NO_TELEMETRY=1 EXPO_NO_DEPENDENCY_VALIDATION=1
  export EXPO_PUBLIC_TREE_FINGERPRINT="$DAU_VAN"
  # Cửa «Vào bản trải nghiệm» chỉ tồn tại khi cờ này lên (và __DEV__). Mọi chế
  # độ trừ --otp đi qua cửa đó — canary 09 đi `_vao-app-sach`, kể cả ở
  # --dang-nhap (đo 2026-09-04: tắt cờ ở --dang-nhap làm canary chết ở bước 1
  # dù flow 21 xanh). Bằng chứng «bản ship không có cửa fixture» nằm ở flow 22.
  if [ "$OTP" = 0 ]; then
    export EXPO_PUBLIC_RUDI_FIXTURE=1
  fi
  if [ "$TAT_KAV" = 1 ]; then
    export EXPO_PUBLIC_QA_TAT_KAV=1
  fi
  if [ -n "$API_PORT" ]; then
    export EXPO_PUBLIC_API_URL="http://localhost:$API_PORT"
  fi
  # Dev-actor mode. Inlined at bundle time, which is why it is set HERE and
  # never in eas.json -- `tests/cau-hinh-ban-dung.test.mjs` refuses it there,
  # because a shipped build carrying it shows everybody the same stranger's money.
  if [ "$LIVE" = 1 ]; then
    export EXPO_PUBLIC_RUDI_ACTOR="$ACTOR"
    export EXPO_PUBLIC_RUDI_CONTEXT="$CONTEXT"
  fi
  if [ "$MODE" = "dev-client" ]; then
    npx expo start --dev-client --localhost --port "$PORT" > "$LOG" 2>&1
  else
    npx expo start --localhost --port "$PORT" > "$LOG" 2>&1
  fi
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
timeout 30 adb shell am force-stop "$APP_ID" >/dev/null 2>&1 || true
sleep 2
# Ở chế độ đăng nhập, chính cái link mời là thứ mở app — giống hệt lúc một
# người bấm vào link bạn gửi. KHÔNG truyền mã qua biến của Maestro:
# `${...}` trong `openLink` không được thay, và `$`/`{`/`}` trong URL làm app
# đứng ở màn lỗi. Đo được: cùng flow đó với một mã thật thì màn nhận lời mời
# hiện đúng, kèm mã đã điền sẵn.
mo_link() {
  timeout 30 adb shell am start -a android.intent.action.VIEW \
    -d "$1" "$APP_ID" >/dev/null 2>&1 \
    || khong_do_duoc "không mở được $APP_ID trên $ANDROID_SERIAL."
}

# URL mở bundle của cây này. Dev client nhận địa chỉ Metro qua đường
# `expo-development-client/?url=`; đường `/--/route` KHÔNG đi được qua đó (đo
# 2026-09-03: launcher báo «There was a problem loading the project»), và một
# link `rudi://route` LẠNH thì launcher nuốt. Nên với dev client, route đi sau,
# khi bundle đã lên — link ẤM, qua Linking.addEventListener trong app/_layout.tsx.
url_metro() {
  if [ "$MODE" = "dev-client" ]; then
    printf 'rudi://expo-development-client/?url=http%%3A%%2F%%2Flocalhost%%3A%s' "$PORT"
  else
    printf 'exp://localhost:%s' "$PORT"
  fi
}
cho_bundle() {
  local _i
  for _i in $(seq 1 90); do
    grep -q "Android Bundled" "$LOG" && return 0
    sleep 2
  done
  return 1
}

if [ "$DANG_NHAP" = 1 ] && [ "$MODE" = "expo-go" ]; then
  # Hâm nóng TRƯỚC, rồi mới giao link mời.
  #
  # `pm clear` ở trên trả Expo Go về lần chạy đầu tiên, và lần chạy đầu tiên
  # của Expo Go KHÔNG phải lần chạy đầu tiên của app này: nó có màn riêng của
  # nó, và cái link mời giao vào lúc đó thì rơi vào đấy chứ không tới
  # `duong-vao.ts`. Đo ngày 2026-09-03: flow 21 đỏ ngay ở «Bạn được rủ đi»,
  # trong khi đúng flow ấy xanh khi Expo Go đã chạy trước đó ít nhất một lần.
  #
  # Nên: mở trắng cho Expo Go qua lần đầu và nạp bundle, force-stop, rồi mới
  # giao link. App vẫn KHỞI ĐỘNG LẠNH cùng cái link — đúng đường một người bấm
  # link bạn gửi — chỉ khác là cái nhận link là app chứ không phải màn chào của
  # Expo Go.
  mo_link "exp://localhost:$PORT"
  for _ in $(seq 1 90); do
    grep -q "Android Bundled" "$LOG" && break
    sleep 2
  done
  timeout 30 adb shell am force-stop host.exp.exponent >/dev/null 2>&1 || true
  sleep 2
fi

DUONG_MO="$(url_metro)"
if [ "$DANG_NHAP" = 1 ] && [ "$MODE" = "expo-go" ]; then
  DUONG_MO="exp://localhost:$PORT/--/moi/$MA_LOI_MOI"
fi
mo_link "$DUONG_MO"
cho_bundle || true
if [ "$DANG_NHAP" = 1 ] && [ "$MODE" = "dev-client" ]; then
  # Bundle đã lên; giờ mới giao lời mời, ẤM. Đây vẫn là đường một người thật đi
  # khi app đang mở và bạn gửi link — và là đường DUY NHẤT dev client cho phép.
  sleep 3
  mo_link "rudi://moi/$MA_LOI_MOI"
  sleep 2
fi
# NEO 2. Không có dòng này thì màn hình đang hiện CÁI GÌ ĐÓ — màn chủ Expo Go,
# bundle của lane khác, hoặc app cũ — và mọi assert sau đó nói về cái đó.
grep -q "Android Bundled" "$LOG" \
  || { echo "--- log Metro ---" >&2; tail -20 "$LOG" >&2; \
       hong "thiết bị không nạp bundle từ Metro của cây này."; }
echo "thiết bị đã nạp bundle của $APP"

# --- flow phải nói cùng CỔNG với Metro vừa dựng ----------------------------
#
# `_vao-app.yaml` và `_vao-app-sach.yaml` viết thẳng `exp://localhost:8095`,
# còn `--port` cho phép đổi cổng — một máy ảo dùng chung sáu lane thì đổi cổng
# là chuyện thường. Hai thứ đó lệch nhau im lặng, và kiểu hỏng thì tệ hơn là đỏ:
#
#   - Đo ngày 2026-09-03 với `--port 8096`: bảng đi qua (script tự giao deep
#     link nên không cần `_vao-app`), rồi canary đỏ vì mở 8095 — TRỐNG. Cổng in
#     "canary đỏ đúng thiết kế" cho một con canary chết vì sai địa chỉ, chứ
#     không phải vì điều kiện nó được viết ra để bắt.
#   - Và nếu 8095 KHÔNG trống — lane khác đang chạy Metro ở đó, đúng cái mặc
#     định — thì mọi flow dùng `_vao-app` lái BUNDLE CỦA HỌ, trong khi hai neo
#     ở trên vẫn xanh vì chúng đọc log Metro của cây NÀY.
#
# Nên bảng chạy từ một bản sao có cổng đã thay, và phép thay phải chứng minh nó
# đã xảy ra: `sed` không đổi gì cũng trả về 0.
if [ "$MODE" = "dev-client" ]; then
  # Không còn URL nào trong flow để lệch với --port: flow dùng `launchApp`, và
  # bundle nào đang là «gần nhất» là do script này quyết ở mo_link phía trên.
  # Một flow ghi lại `exp://` hay Expo Go là quay về đúng cái bẫy đã tả bên dưới.
  LOI_URL="$(grep -lE '^\s*-\s*openLink:\s*exp://|^appId:\s*host\.exp\.exponent' "$APP/$FLOWS"/*.yaml || true)"
  [ -z "$LOI_URL" ] || hong "flow còn ghim Expo Go / exp:// trong khi đang lái dev client:$(printf ' %s' $LOI_URL)"
elif [ "$PORT" != 8095 ]; then
  FLOWS_GOC="$FLOWS"
  FLOWS="$(mktemp -d)/maestro"
  cp -r "$APP/$FLOWS_GOC" "$FLOWS"
  DA_THAY=0
  for f in "$FLOWS"/*.yaml; do
    truoc="$(grep -c 'localhost:8095' "$f" || true)"
    [ "$truoc" -gt 0 ] || continue
    sed -i "s|localhost:8095|localhost:$PORT|g" "$f"
    DA_THAY=$((DA_THAY + truoc))
  done
  [ "$DA_THAY" -gt 0 ] \
    || hong "chạy ở cổng $PORT nhưng không flow nào ghi localhost:8095 — bản sao không sửa được gì, flow đang trỏ đi đâu không rõ."
  grep -rq 'localhost:8095' "$FLOWS" \
    && hong "còn flow trỏ về 8095 sau khi thay."
  echo "flow chạy từ bản sao đã đổi sang cổng $PORT ($DA_THAY chỗ)"
fi

# --- chạy bảng, rồi chạy canary --------------------------------------------
# Duyệt từng file thay vì `maestro test <thư mục> --exclude-tags=canary`: đo
# ngày 2026-09-03, `--exclude-tags` KHÔNG lọc khi đích là một file, nên con
# canary vẫn chạy trong bảng và kéo cả bảng xuống đỏ. Vòng lặp cũng in được
# phán quyết theo từng flow, mà một lượt chạy cả thư mục không cho.
cd "$APP"
BANG=0
DA_CHAY=0
DO_LIST=""
HA_TANG=""

# Một flow đỏ vì máy ảo rụng KHÔNG phải một flow đỏ vì app sai, và cổng nào
# không phân biệt được hai cái đó sẽ dạy người đọc bỏ qua màu đỏ của nó.
#
# Đo ngày 2026-09-03: bốn flow liên tiếp đỏ với `io.grpc.StatusRuntimeException:
# UNAVAILABLE` và `Command failed (tcp:46293): closed` — kết nối adb của Maestro
# đứt giữa lượt, không có bước nào chạy, rồi những flow sau lại chạy bình thường.
# Máy ảo này dùng chung với lane khác. Thử lại một lần; vẫn hạ tầng thì lượt đo
# HẾT HẠN (mã 2), không phải đỏ.
LOI_HA_TANG='StatusRuntimeException|Command failed \(tcp:|UNAVAILABLE|no devices/emulators found|device .* not found'

# Một flow đỏ phải in ra MÀN NÓ THẤY. Máy ảo bị lane khác cướp, launcher của dev
# client, hay tờ dev-menu — tất cả đều làm assert đỏ với cùng một dòng «not
# visible», và người đọc chép dòng đó thành «tính năng chưa có». Ảnh + chữ trên
# màn lúc đỏ là thứ phân biệt hai chuyện đó.
in_man_dang_thay() {
  local ten="$1"
  timeout 20 adb exec-out screencap -p > "$ANH_DIR/$ten-FAILED.png" 2>/dev/null || true
  echo "--- màn đang thấy lúc $ten đỏ ($ANH_DIR/$ten-FAILED.png) ---"
  timeout 20 adb exec-out uiautomator dump /dev/tty 2>/dev/null \
    | grep -oE 'text="[^"]{2,80}"' | head -12 || true
}

chay_flow() {
  local f="$1" ra rc
  local -a them=()
  # Số và mã chỉ đi qua -e, không bao giờ nằm trong file flow.
  if [ "$OTP" = 1 ]; then
    them=(-e OTP_PHONE="$OTP_PHONE" -e OTP_PHONE_B="$OTP_PHONE_B"
          -e OTP_PHONE_C="$OTP_PHONE_C" -e OTP_PHONE_D="$OTP_PHONE_D" -e OTP_CODE="$OTP_CODE")
  fi
  # Flow 30 rẽ theo AI: có khoá thì chờ thẻ của Rủ Đi AI, không thì câu nói thật.
  them+=(-e AI="$AI")
  ra="$(mktemp)"
  # `set -e` là toàn cục, không theo hàm: bật lại ở đây là bật lại cho cả vòng
  # lặp gọi hàm này, và `return "$rc"` khác 0 ngay sau đó giết cả script — bảng
  # dừng ở flow đỏ đầu tiên, các flow sau không chạy, dòng tổng kết không in.
  # Đo 2026-09-04 (M3 lượt 3: flow 30 đỏ, 31 và 40 biến mất, «đã chạy N flow»
  # không có). Người gọi tự `set -e` lại sau khi đọc rc.
  set +e
  maestro test -e TREE_FINGERPRINT="$DAU_VAN" "${them[@]}" --test-output-dir "$ANH_DIR" "$f" > "$ra" 2>&1
  rc=$?
  cat "$ra"
  if [ "$rc" -ne 0 ] && grep -qE "$LOI_HA_TANG" "$ra"; then
    rm -f "$ra"; return 99
  fi
  [ "$rc" -eq 0 ] || in_man_dang_thay "$(basename "$f" .yaml)"
  rm -f "$ra"; return "$rc"
}

# `--lap N`: cả bảng chạy N lượt liên tiếp. Một bảng xanh một lần không phân biệt
# được «đúng» với «may»; bộ nhớ dự án ghi cú bấm bị rơi ~1/4 lượt trên web.
for lap in $(seq 1 "$LAP"); do
[ "$LAP" -gt 1 ] && echo "=== lượt $lap/$LAP ==="
if [ "$OTP" = 1 ]; then
  # Mỗi lượt BỐN người mới, mỗi flow một cặp số chưa ai dùng: người của flow
  # trước đã có nhóm (22) hoặc đã có tên «Thành viên mới» (23), và flow 24 khẳng
  # định cả «Chưa có nhóm nào» lẫn tên «Ban QA» do người mời đặt.
  rm -rf "$PHIEN_CURL_DIR"; PHIEN_CURL_DIR="$(mktemp -d)"
  OTP_PHONE="$(sinh_so_di_dong)"; OTP_PHONE_B="$(sinh_so_di_dong)"
  OTP_PHONE_C="$(sinh_so_di_dong)"; OTP_PHONE_D="$(sinh_so_di_dong)"
fi
for f in "$FLOWS"/*.yaml; do
  ten="$(basename "$f")"
  case "$ten" in
    _*)          continue ;;  # subflow, chạy qua runFlow chứ không tự chạy
    09-canary-*) continue ;;  # chạy riêng ở dưới, và nó PHẢI đỏ
    # 20-* đọc dữ liệu THẬT: cần database đã seed và một danh tính được ghim.
    # Bảng mặc định cố ý không có hai thứ đó, nên chạy nó ở đây sẽ đỏ vì thiếu
    # môi trường chứ không phải vì app sai. `--live` chạy đúng và chỉ nhóm này.
    20-*)        [ "$LIVE" = 1 ] || continue ;;
    21-*)        [ "$DANG_NHAP" = 1 ] || continue ;;
    22-*|23-*|24-*|25-*|26-*|27-*|28-*|29-*|31-*) [ "$OTP" = 1 ] || continue ;;
    # Under the keyboard negative control the composer is meant to be covered,
    # so a flow that has to tap it (30, 40) would only fail for the reason the
    # probe already measures. The table for --tat-kav is the sign-in leg + 31.
    30-*) [ "$OTP" = 1 ] && [ "$TAT_KAV" = 0 ] || continue ;;
    40-*)        [ "$OTP" = 1 ] && [ "$AI" = 1 ] && [ "$TAT_KAV" = 0 ] || continue ;;
    *)           { [ "$LIVE" = 1 ] || [ "$DANG_NHAP" = 1 ] || [ "$OTP" = 1 ]; } && continue ;;
  esac
  DA_CHAY=$((DA_CHAY + 1))
  set +e; chay_flow "$f"; rc=$?; set -e
  if [ "$rc" -eq 99 ]; then
    echo "  hạ tầng rụng ở $ten, thử lại một lần"
    set +e; chay_flow "$f"; rc=$?; set -e
  fi
  if [ "$rc" -eq 99 ]; then HA_TANG="$HA_TANG $ten"; continue; fi
  if [ "$rc" -ne 0 ]; then BANG=1; DO_LIST="$DO_LIST $ten(lượt $lap)"; fi
  # V3: flow 31 để bàn phím mở rồi dừng; đo hình học ngay khi màn còn nguyên.
  # Exit 2 của script là «không đo được» — cũng đỏ, vì một lượt --otp không đo
  # được bàn phím là một lượt thiếu bằng chứng, không phải một lượt xanh.
  case "$ten" in
    31-*)
      if [ "$rc" -eq 0 ]; then
        set +e; python3 "$REPO/scripts/do_ban_phim.py" --serial "$ANDROID_SERIAL"; rc_bp=$?; set -e
        if [ "$TAT_KAV" = 1 ]; then
          # Đối chứng âm: KAV tắt thì bàn phím PHẢI che (rc 1). rc 0 = thước đo mù.
          [ "$rc_bp" -eq 1 ] || { BANG=1; DO_LIST="$DO_LIST doi_chung_ban_phim(lượt $lap, rc=$rc_bp, mong 1)"; }
        else
          [ "$rc_bp" -eq 0 ] || { BANG=1; DO_LIST="$DO_LIST do_ban_phim(lượt $lap, rc=$rc_bp)"; }
        fi
      fi
      ;;
  esac
done
done

# Nêu tên trước khi phán quyết: một flow không đo được mà im lặng thì bảng xanh
# ở dưới đang nói về ít flow hơn người đọc tưởng.
[ -z "$HA_TANG" ] || khong_do_duoc "máy ảo rụng ở:$HA_TANG (đã thử lại). Lượt đo này không kết luận được."

# Danh sách nguồn RỖNG làm cổng tự tháo trong im lặng: không flow nào chạy thì
# không flow nào đỏ, và vòng lặp ở trên đi qua sạch sẽ.
[ "$DA_CHAY" -gt 0 ] || hong "không có flow nào trong $FLOWS. Bảng RỖNG không phải bảng xanh."
echo "đã chạy $DA_CHAY flow"

# NEO 2b. Flow 00 vừa assert dấu vân THẬT ở trong bảng; giờ cùng flow với dấu vân
# SAI phải đỏ, và đỏ đúng ở dòng đó. Không thì `assertVisible` của dấu vân là một
# dòng trang trí và hai neo Metro ở trên lại là tất cả những gì ta có.
if [ "$LIVE" = 0 ] && [ "$DANG_NHAP" = 0 ] && [ "$OTP" = 0 ]; then
  RA_2B="$(mktemp)"
  set +e
  maestro test -e TREE_FINGERPRINT="KHONG_CO_DAU_VAN_NAY" "$FLOWS/00-smoke-deeplink.yaml" > "$RA_2B" 2>&1
  RC_2B=$?
  set -e
  DONG_2B="$(grep -n 'FAILED' "$RA_2B" | head -1 || true)"
  if [ "$RC_2B" -eq 0 ]; then
    hong "NEO 2b: flow 00 XANH với dấu vân SAI — assert dấu vân không cắn, màn có thể là bundle của cây khác."
  fi
  # Maestro in lại NGUYÊN VĂN YAML của bước đỏ — `${TREE_FINGERPRINT}` chưa thay —
  # chứ không in giá trị. Nên nhận diện theo TÊN BƯỚC (assert dấu vân), không
  # theo giá trị sai vừa truyền. Đo lượt 3 ngày 2026-09-03: khớp theo giá trị làm
  # cổng đỏ giả ngay khi canary vừa làm đúng việc của nó.
  case "$DONG_2B" in
    *TREE_FINGERPRINT*) echo "NEO 2b: dấu vân sai → đỏ đúng ở bước assert dấu vân. Màn hình đang hiện bundle của lượt này." ;;
    *) sed -n '1,30p' "$RA_2B" >&2; hong "NEO 2b: flow 00 đỏ nhưng không phải ở dòng dấu vân ($DONG_2B)." ;;
  esac
  rm -f "$RA_2B"
fi

[ "$BANG" -eq 0 ] || hong "flow đỏ:$DO_LIST"

if [ "$OTP" = 1 ]; then
  kiem_may_chu_sau_24
  kiem_may_chu_sau_25
  kiem_may_chu_sau_26
  kiem_may_chu_sau_27
  kiem_may_chu_sau_28
  kiem_may_chu_sau_29
  [ "$TAT_KAV" = 1 ] || kiem_may_chu_sau_30
  [ "$AI" = 1 ] && [ "$TAT_KAV" = 0 ] && kiem_may_chu_sau_40
  canary_otp
else
RA_CANARY="$(mktemp)"
# Canary chạy đường FIXTURE trên app CHƯA đăng nhập. Ở chế độ `--dang-nhap` thì
# bảng vừa đăng nhập thật xong, nên phải trả máy về trạng thái đó trước.
if [ "$DANG_NHAP" = 1 ]; then
  echo "xoá phiên trước khi chạy canary (canary đo đường chưa đăng nhập)"
  xoa_du_lieu_app
  # Sau pm clear, dev client về launcher: nạp lại bundle rồi mới chạy canary.
  mo_link "$(url_metro)"; cho_bundle || true; sleep 2
fi
set +e; maestro test -e TREE_FINGERPRINT="$DAU_VAN" "$FLOWS/09-canary-phai-do.yaml" 2>&1 | tee "$RA_CANARY"; CANARY=${PIPESTATUS[0]}; set -e

# NEO 3. Canary xanh nghĩa là phép đo không phân biệt được đúng với sai, nên cả
# bảng xanh ở trên không chứng minh gì.
[ "$CANARY" -ne 0 ] || hong "canary XANH. Bảng trên không chứng minh gì."

# NEO 3b. Và nó phải đỏ Ở BƯỚC CUỐI. Docstring của chính flow 09 nói thẳng điều
# này — «a red canary that dies early proves the harness is broken, not that the
# assertions bite» — nhưng cho tới hôm nay không có gì cưỡng chế nó, nên bất kỳ
# màu đỏ nào cũng được đọc thành «canary đỏ đúng thiết kế».
#
# Đã xảy ra thật, ngày 2026-09-03, chạy `--port 8096`: canary chết ngay ở bước 1
# vì `_vao-app-sach.yaml` mở `exp://localhost:8095` — một cổng TRỐNG. Không một
# assert nào của nó được thực thi, và cổng vẫn in dòng XANH ở cuối. Cùng lỗi ấy
# với 8095 KHÔNG trống thì tệ hơn nữa: canary lái bundle của lane khác.
CHUOI_CANARY="KHONG_BAO_GIO_CO_CHUOI_NAY_TREN_MAN"
DONG_DO_DAU="$(grep -n 'FAILED' "$RA_CANARY" | head -1 || true)"
case "$DONG_DO_DAU" in
  *"$CHUOI_CANARY"*) ;;
  "") hong "canary thoát khác 0 mà không có bước nào FAILED — nó chết trước khi chạy, không phải vì assert cắn." ;;
  *) echo "--- canary ---" >&2; sed -n '1,40p' "$RA_CANARY" >&2
     hong "canary đỏ ở bước KHÁC bước cuối ($DONG_DO_DAU). Nó chết vì hạ tầng, nên bảng trên vẫn chưa chứng minh gì." ;;
esac
rm -f "$RA_CANARY"
fi

echo "XANH: bảng qua ($LAP lượt), $([ "$OTP" = 1 ] && echo "canary OTP (mã sai) đỏ đúng chỗ" || echo "NEO 2b cắn, canary đỏ đúng thiết kế"), trên $ANDROID_SERIAL / $EXPO_VER / dấu vân $DAU_VAN"
