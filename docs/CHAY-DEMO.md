# Chạy app Rủ Đi để tự bấm thử

Bản này thay bản 31/08 (Expo Go + dữ liệu fixture). Mọi lệnh dưới đây đã chạy
thật trên máy này ngày **04/09/2026** trên cây `apps/mobile` sau khi xoá App B
(#547) và lô đánh bóng dark/font 1.3 (#549). Chỗ nào chưa chạy tay thì ghi rõ ở
mục cuối — đừng đọc sự im lặng thành "cái đó chạy được".

---

## Cái gì đổi so với bản 31/08

| | 31/08 | 04/09 |
|---|---|---|
| App mở lên | vỏ RuDi đọc fixture, App B ẩn sau `/legacy` | một app, mọi màn đọc máy chủ; App B đã xoá |
| Chạy bằng | Expo Go trên điện thoại thật | **development build** `com.lakiet.rudi` (có module native Google Sign-In, Expo Go không nạp được) |
| Đăng nhập | lời mời đích danh / «Vào bản trải nghiệm» | **OTP thật** trên API chế độ `prod`; Google chờ client id của leader |
| Dữ liệu | seed cũ `make demo` (roster 7 người, App B) | **`make demo-rudi`**: «Team Đà Lạt» 8 người, chat, kèo, bill, đợt thu, kỷ niệm — chạy lại là no-op |
| Bằng chứng | ảnh React Native Web trong Chrome | 11 flow Maestro trên emulator Android, light/dark, font 1.0/1.3 |

Cửa fixture chỉ còn khi `__DEV__` **và** `EXPO_PUBLIC_RUDI_FIXTURE=1`; bản dựng
thường không có nút «Vào bản trải nghiệm».

---

## Cần gì trên máy

Tất cả đã có sẵn trên máy này (đường dẫn ghi để tìm lại, không phải để cài mới):

- Android SDK ở `~/Android/Sdk` (không nằm trên PATH; script tự thêm), AVD `rudi`
  (Android 15, 1080x2400 @420dpi, x86_64), chạy emulator qua `sg kvm`.
- JDK 17 ở `~/.jdks/` (Maestro cần JDK, JRE không đủ), Maestro 2.10.0 ở `~/.maestro/bin`.
- Node 22 qua nvm (`~/.nvm/versions/node/v22.*/bin`); Postgres 16 qua `docker compose`.
- APK debug đã dựng và đã cài: `wt-m0-devbuild/apps/mobile/android/app/build/outputs/apk/debug/app-debug.apk`
  (`adb install -r` lại nếu emulator mới). Dấu vân native của cây phải khớp APK
  (`apps/mobile/android/.rudi-native-fingerprint`), sai là harness thoát mã 2 và
  nói phải build lại — đừng ép.

Chi tiết bẫy khi build lại: memory «dev client android build trên máy này»
(JRE ≠ JDK, worklets 0.12.1, chỉ x86_64, keystore debug ở `android/app/debug.keystore`).

---

## Bước 1 — API chế độ `prod` và thế giới «Team Đà Lạt»

```bash
scripts/e2e_slice.sh --keep          # dựng Postgres + API prod trên một cổng ngẫu nhiên, in cổng ra
make demo-rudi API=<cổng>            # 8 người OTP, nhóm, bạn, chat + /vote, kèo 3 chặng + check-in,
                                     # bill Xóm Lèo 1.280.000đ → sổ → đợt thu phát, 5 kỷ niệm
make demo-rudi API=<cổng>            # chạy lại: mọi bước «đã có», không ghi thêm gì
make demo-rudi API=<cổng> FRESH=1    # dựng thêm nhóm «Team Đà Lạt (n)» mới với số điện thoại lệch đi
```

Stack `e2e_slice --keep` chạy **không có** `MOBILE_AUTH_MODE` (tức `prod`,
ADR-0014), SMS sender là `log`, và `MOBILE_OTP_DEBUG_CODE=000000` — mã debug chỉ
hợp lệ với sender `log`; có gateway thật mà còn mã debug thì API từ chối khởi
động (ADR-0016). Không có khoá Gemini: AI trong chat nói thật là chưa cấu hình;
muốn AI thật thì đặt `GEMINI_API_KEY` trong môi trường trước khi dựng stack và
chạy harness với `--ai` (kiểm khoá trước, khoá chết là ĐỎ).

Seed là script Node dùng chính module client đã test (`apps/mobile/tools/seed-rudi-world.mjs`);
mỗi bước đọc trước ghi sau nên chạy lại an toàn. Số điện thoại của 8 người là
**số tổng hợp sinh bằng số học lúc chạy**, không nằm trong repo; lấy số của
người thứ `i` (0–7) bằng:

```bash
cd apps/mobile && node -e "import('./tools/seed-rudi-world-lib.mjs').then(m => console.log(m.soDienThoai(0)))"
```

---

## Bước 2 — Emulator và bảng Maestro (đường khuyên dùng)

```bash
export PATH="$HOME/Android/Sdk/platform-tools:$HOME/Android/Sdk/emulator:$PATH"
sg kvm -c "emulator -avd rudi -port 5554 -no-audio -no-boot-anim -gpu swiftshader_indirect -accel on &"
timeout 300 adb -s emulator-5554 wait-for-device            # rồi chờ sys.boot_completed=1
make mobile-native-otp API=<cổng>                             # 11 flow + 8 kiểm máy chủ + canary
```

Harness (`scripts/mobile_native.sh --otp`) tự: kiểm mã debug bằng curl, bật Metro
ở cổng 8095 với `EXPO_PUBLIC_API_URL=http://localhost:<cổng>`, `adb reverse` cả
hai cổng, nạp bundle vào dev client, chạy 22 → 23 → 24 → 25 → 26 → 27 → 28 → 29 →
30 → 31 → 32 rồi canary (flow 22 với mã SAI phải đỏ ở «Chưa có nhóm nào»).
Dòng cuối của log là `XANH: bảng qua (…)` hoặc `ĐỎ: flow đỏ: <flow>`. Ảnh nằm ở
`.impeccable/review/native/<ngày>-<giờ>-<sha>/<thời điểm>/<flow>/takeScreenshot/*.png`;
flow đỏ có thêm `screencap` và dump UI ngay trong log.

Muốn xem dark và chữ to trước khi chạy:

```bash
adb -s emulator-5554 shell cmd uimode night yes
adb -s emulator-5554 shell settings put system font_scale 1.3
# … chạy bảng … rồi trả lại:
adb -s emulator-5554 shell cmd uimode night no
adb -s emulator-5554 shell settings put system font_scale 1.0
```

Bảng đối chiếu 21 mockup với ảnh vừa chụp:

```bash
python3 scripts/bang_doi_chieu_mockup.py --run .impeccable/review/native/<lượt> [--run …] \
  --out docs/claude/<ngày>/bang-doi-chieu-mockup.md --sheet-dir /tmp/sheet   # mã thoát 2 khi còn ô CHƯA CHỤP
```

---

## Bước 3 — Tự bấm trên emulator

Harness tắt Metro và gỡ `adb reverse` khi xong, nên để bấm tay thì bật lại bằng tay (đã chạy đúng thứ tự này lúc 14:41 ngày 04/09: sau link, app lên màn chào «Rủ Đi thôi!» trong dưới 75 giây):

```bash
cd apps/mobile
EXPO_PUBLIC_API_URL=http://localhost:<cổng> npx expo start --dev-client --localhost --port 8095 &
adb -s emulator-5554 reverse tcp:8095 tcp:8095
adb -s emulator-5554 reverse tcp:<cổng> tcp:<cổng>
adb -s emulator-5554 shell am start -a android.intent.action.VIEW \
  -d 'rudi://expo-development-client/?url=http%3A%2F%2Flocalhost%3A8095'
```

Rồi trên máy: **Chào bạn → nhập số của một người trong roster → mã `000000`** →
vào thẳng «Team Đà Lạt» (đường OTP này là flow 22 của bảng, chạy xanh nhiều lượt trong ngày;
seed đã đăng nhập đúng cách đó cho cả 8 người). Nút bánh răng xám góc phải trên là của dev-launcher,
không phải app; chạm vào header phải cẩn thận vì nó che 48dp góc đó.

## Có gì để bấm

- **Khám phá**: 12 nơi Đà Lạt từ danh mục máy chủ, lọc theo danh mục, tìm theo tên,
  tìm bằng câu (không khoá thì thẻ «Rủ Đi AI» nói thật), chi tiết địa điểm với
  Chỉ đường (`geo:`), Lưu, «Thêm vào kèo».
- **Lên plan**: kèo của nhóm, tạo kèo, thêm chặng gắn địa điểm danh mục, «Tôi đã tới».
- **Tin nhắn**: danh sách nhóm và lời mời, chat FlatList đảo với phản ứng, lệnh
  `/plan` `/vote` `/chia-bill` và `@Rủ Đi` (thẻ AI chỉ khi có khoá và được grounding).
- **Tạo mới → Chia hóa đơn**: chọn ảnh hoặc nhập tay → xem lại → gán món → máy chủ
  chia → ghi vào sổ → quyết toán → đợt thu (phát một lần, link khách chia sẻ).
- **Kỷ niệm**: tường nhóm (check-in, tim, bình luận), thả khoảnh khắc, album kèo,
  thước phim (có nhịp giới hạn, `reeled: false` là bình thường).
- **Cá nhân**: hồ sơ thật, bạn bè (kết bạn theo số), tài chính của tôi, thành tích.

Sản phẩm **dừng ở chỗ nói mỗi người phải bỏ ra bao nhiêu** (ADR-0015): không có
VietQR, không có nút thanh toán; mockup còn vẽ những nút đó là decision comp
chưa cập nhật.

---

## Cạm bẫy đã biết

- OTP: 60 s mới được gửi lại cho cùng số, 5 challenge / 15 phút / số, 10 yêu cầu /
  phút / IP — bấm liên tiếp là 429, không phải hỏng.
- Một emulator một lane: đừng chạy hai harness cùng lúc; cổng 8095 còn `node` giữ
  thì lượt sau không bind được (`ps -eo args | grep "[e]xpo start"`).
- Không sửa `src/`, `app/` hay `scripts/mobile_native.sh` khi harness đang chạy cây đó.
- `npm test` và Metro không chạy chung một worktree; `rm -rf dist-test` trước `npm test`.
- adb trên WSL2 có thể treo vì loopback nuốt SYN — mọi lệnh adb bọc `timeout`.
- `pm clear` làm dev client về launcher; mở lại bằng link ở Bước 3.

## Tắt

```bash
pkill -f "[e]xpo start"                                 # Metro (mẫu ngoặc để không tự giết shell)
adb -s emulator-5554 reverse --remove-all
adb -s emulator-5554 emu kill
# Stack `--keep` là một container Postgres + một tiến trình uvicorn; nó in sẵn dòng
# «dọn bằng: docker rm -f <container>; kill <pid>» lúc dựng xong — dùng đúng dòng đó,
# hoặc để stack sống cho lượt sau (seed chạy lại là no-op).
```

## Cái gì CHƯA chạy tay — đọc trước khi kết luận

- **Google**: nút «Tiếp tục với Google» nói thật là chờ client id; leader tạo
  client id từ SHA-1 keystore debug (ghi ở #527) rồi mới có đường này.
- **Máy thật**: mọi bằng chứng là emulator x86_64; máy thật cần APK arm64 (chưa dựng)
  và `EXPO_PUBLIC_API_URL` là IP LAN, không phải `localhost`.
- **Tablet, iOS**: chưa đo.
- **SMS thật**: chưa có nhà cung cấp; ngoài stack demo, không có mã debug.
