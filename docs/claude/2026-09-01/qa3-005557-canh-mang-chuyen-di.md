# Mảng CHUYẾN ĐI đo trên NATIVE — F15 · F16 · F46 · F17

- task_id: `qa3-005557` · hậu tố `96373001`  <!-- tách đôi: repo guard đọc 14 chữ số liền thành số tài khoản -->
- nhánh: `qa3/canh-mang-chuyen-di`, dựng từ `origin/main` = `f8fbf49`
- protocol_version: v1
- verdict: **không phải review PR** — đây là báo cáo phép đo
- kỹ năng bắt buộc đã gọi: `mobile-testing`

**Mọi con số dưới đây đo trên ANDROID NATIVE** — Expo Go 57.0.9 trên Android 15
(SDK 35), AVD `rudi-qa3`, `emulator-5560`, 1080×2400. Không phải Chrome, không
phải React Native Web. Mỗi cú bấm là một `adb shell input tap x y`; mỗi câu chữ
đọc từ `uiautomator dump`, tức chính cây trợ năng mà TalkBack đọc.

Cái nó **không** chứng minh: emulator x86_64 không phải điện thoại ARM thật —
khác ở codec, camera, hiệu năng, quyền. Và nó không nói gì về việc màn hình
**đúng** hay **đọc được**; nó chỉ trả lời "người dùng bấm tới được không, và
lúc đó app gọi route nào".

---

## Bảng bốn ô — mỗi tính năng một dòng

| Ô | Trạng thái | Đường bấm (từ màn đăng nhập, KHÔNG sửa URL) | Route nó gọi |
|---|---|---|---|
| **F15 Outing Timeline** | **TỚI ĐƯỢC, có ruột** | `Đăng ký với Apple` → `Vào app với tư cách Minh` → tab **Lên plan** → thẻ **Mở dòng thời gian Chuyến Đà Lạt tháng 6** | `GET /contexts/{id}/outings` → 200 (2089B) |
| **F46 Group Check-in** | **TỚI ĐƯỢC, bấm là ĂN** | …tiếp theo F15 → nút **Đã tới** trên chặng `07:30 Xe khách Sài Gòn – Đà Lạt` | `POST /outing-stops/{id}/checkins` → **201** (210B), rồi `GET /outings/{id}/checkins` → 200 |
| **F17 Voting** | **TỚI ĐƯỢC MÀN, nút BỊ KHOÁ** | tab **Tin nhắn** → chip **Plan** → khối `Bình chọn của nhóm` + nút `Mở bình chọn mới` | *không gọi gì* — nút disabled |
| **F16 AI Itinerary** | **TỚI ĐƯỢC MÀN, RỖNG** | tab **Tin nhắn** → chip **Plan** → khối `Kế hoạch` | *không gọi gì* — chưa có kế hoạch nào |

### F15 — dòng thời gian chuyến đi

Màn hiện đúng dữ liệu thật của máy chủ, không phải chữ dựng sẵn:

```
Chuyến Đà Lạt tháng 6 · 15 - 17/06/2026 · 7 người · Tổng dự kiến 6.300.000đ
07:30  Xe khách Sài Gòn – Đà Lạt   [Đã tới]
14:00  Nhận phòng · Homestay Cỏ Hồng   [Đã tới]
19:00  Ăn tối · Tiệm Nướng Xóm Lèo   [Đã tới]
Thêm chặng — Giờ 07:00 · Nhãn chặng "Ăn sáng" · Tên quán "Lưng Chừng Cafe"
```

Danh sách trước đó có ba chuyến thật, kèm số tiền lấy từ sổ:
`Chuyến Đà Lạt tháng 6 — Đã tiêu 4.200.000đ / ngân sách 6.300.000đ` ·
`Chuyến Đà Lạt tháng 8 — 1.625.000đ / 4.200.000đ` ·
`Bữa nướng cuối tuần — 960.000đ / 1.400.000đ`.

### F46 — check-in nhóm

Đây là ô duy nhất trong bốn ô **ghi được vào máy chủ** trong lượt đo này:

```
bấm "Đã tới"  ->  POST /outing-stops/fe3433ce-…/checkins  ->  201 (210B)
                  GET  /outings/f7617bce-…/checkins       ->  200
```

Bằng chứng nó **thật sự ghi**, không phải 201 rỗng: cùng một route đọc lại,
**66 B trước khi bấm → 276 B sau khi bấm**. Số byte đổi là thứ một cú bấm giả
không tạo ra được.

### F17 — bình chọn

Màn tới được, nút có thật, và nút **tự khai lý do bị khoá**:

```
Bình chọn của nhóm
Chưa có bình chọn nào.
Cần ít nhất hai chỗ AI đã gợi ý trong nhóm thì mới mở được bình chọn.
[ Mở bình chọn mới ]        <- aria-disabled
```

Đây **không** phải vỏ: `TinNhan.tsx:1023` truyền `disabled={!coDiaDiem}` với
`coDiaDiem = diaDiem.length >= 2`. Nghĩa là F17 nằm **sau** F16 trên đường đi:
phải có AI gợi ý chỗ trong nhóm trước thì mới mở được bình chọn. Nói cách khác
khoảng cách còn lại của F17 là **một cuộc trò chuyện AI**, không phải một màn
hình chưa xây.

### F16 — AI lên lịch trình

```
Kế hoạch
Chưa có kế hoạch nào trong nhóm này.
AI sẽ tự lên tiếng khi nhóm bàn đủ rõ chỗ đi và thời gian.
Không có kế hoạch nào được bịa sẵn.
```

**Chưa đo được** phần quan trọng nhất của ô này: tôi **không** hoàn thành được
một lượt chat thật để AI sinh ra thẻ lịch trình. Hai lần thử gõ câu hỏi vào ô
chat rồi bấm Gửi đều bị cắt ngang khi app bị đá khỏi màn (xem *Ba thứ suýt làm
hỏng phép đo*, mục 2). Nên dòng F16 ở bảng trên chỉ nói được "màn tới được và
trạng thái rỗng là trung thực", **không** nói được "AI viết ra lịch trình khi
người ta hỏi". Cái đó vẫn là câu hỏi mở.

---

## Đối chứng đường bắt buộc — chia bill

Luật của đợt: một tính năng tôi **biết** là tới được phải được chính thước đo
này xếp đúng. Chạy trên cùng máy, cùng phiên, cùng thước đo:

```
tab "Tạo mới"  ->  "Tạo khoản chi. Chụp bill hoặc nhập tay, AI chia tiền"
->  màn Chụp bill:
    "Đưa bill vào khung hình · AI sẽ nhận diện từng món ngay sau khi chụp"
    "Cho phép dùng camera" · "Chọn ảnh bill" · "Ảnh chụp màn hình"
    "Máy chủ: http://10.0.2.2:8299"
```

Thước đo xếp chia bill là **TỚI ĐƯỢC**. Nó không phải máy in chữ "chưa có".

Dòng `Máy chủ: http://10.0.2.2:8299` do chính app in ra, và 8299 là proxy ghi
nhật ký của lượt đo này — tức app đang nói chuyện qua đúng cái đường tôi đo,
không phải qua một máy chủ nào khác.

## Đối chứng âm — thước đo có im lặng in PASS lên hư không không?

Đây là chỗ #490 bị FAIL: thước đo cũ in chữ ký PASS lên một tính năng ĐÃ TẮT.
Lần này, **bốn lần** app bị đá ra khỏi màn giữa chừng, thước đo in:

```
[1] KHÔNG THẤY nút khớp 'Đăng ký với Apple' — dừng ở đây.
    màn: Development servers · HELP · … · Expo Go logo · Expo Go · Log In
```

Nó dừng, và nó **in ra màn nó thật sự thấy** — màn chủ của Expo Go, đọc là
"app không chạy" chứ không phải "tính năng không có". Không lượt nào in ra một
kết luận khi không có gì để đo. Đó là điều kiện tối thiểu, không phải thành tựu.

---

## Ba thứ suýt làm hỏng phép đo — ghi lại vì lane sau sẽ gặp

### 1. Một adbd treo làm CHẾT adb của cả máy, kể cả `adb kill-server`

Lúc 01:00 mọi lệnh `adb` trên máy này hết hạn — `devices`, `shell`,
**và cả `kill-server`**. Giết tiến trình adb server rồi khởi động lại: server
mới cũng treo ngay. Hàng đợi accept của `127.0.0.1:5037` leo lên 16–19 kết nối
chờ. Một lane khác đang kẹt ở `adb -s emulator-5554 shell getprop
init.svc.bootanim` suốt 2 phút 12.

Cách gỡ chạy được: **giết máy ảo qua console 5554** (console vẫn sống khi adb
đã chết), rồi adb tự lành.

```bash
TOK=$(cat ~/.emulator_console_auth_token)
python3 - "$TOK" <<'PY'
import socket,sys,time
s=socket.create_connection(("127.0.0.1",5554),timeout=10); s.settimeout(5); time.sleep(1)
s.recv(4096); s.sendall(("auth "+sys.argv[1]+"\n").encode()); time.sleep(1); s.recv(4096)
s.sendall(b"kill\n"); time.sleep(2); print(s.recv(4096).decode())
PY
```

**Giả thuyết `ADB_MDNS` ĐÃ BỊ BÁC BỎ.** Lần đầu `ADB_MDNS=0 adb devices` chạy
tức thì ngay sau khi bản thường hết hạn, và tôi đã suýt viết "tìm ra rồi". Đo
lại tử tế — giết server, **xác nhận cổng 5037 đã trống**, ba vòng A/B:

```
vòng 1 KHÔNG ADB_MDNS=0 → rc=0 110ms      vòng 1 CÓ → rc=0  58ms
vòng 2 KHÔNG ADB_MDNS=0 → rc=0 111ms      vòng 2 CÓ → rc=0  57ms
vòng 3 KHÔNG ADB_MDNS=0 → rc=0  40ms      vòng 3 CÓ → rc=0  19ms
```

Không có mDNS nào ở đây cả. Lượt "nhanh" đầu tiên chỉ là lượt đầu tiên **sau
khi máy ảo đã chết**. Ghi lại đúng cái bác bỏ này để lane sau đừng đuổi theo nó.

### 2. Một emulator, sáu lane — và lane thua đọc thành "tính năng không có"

Hai chuyện đã xảy ra thật trong lượt này:

- Đang đo dở trên `rudi`/`emulator-5554` thì máy ảo bị **một lane khác tắt**.
  Log emulator ghi đúng chuỗi tắt (`Saving snapshot… stop: Not implemented`).
  Mọi lệnh sau đó trả `device 'emulator-5554' not found` — mà cái đó, nếu không
  đọc kỹ, trông y hệt "màn này không tồn tại".
- Sau khi tôi dựng AVD **riêng** `rudi-qa3` ở cổng 5560, app của tôi vẫn bị đá
  về màn chủ Expo Go **bốn lần**. Nguyên nhân có tên: lane frontend đang chạy
  `expo start --port 8090` ở `wt/frontend/apps/mobile` (pid 1109268), và Expo Go
  trên máy ảo hiện `exp://192.168.1.7:8090` — tức máy chủ của họ. Vì đó là **máy
  ảo duy nhất đang sống**, mọi lệnh `adb` không kèm `-s` của mọi lane đều rơi
  vào nó. `adb reverse --list` của máy tôi có `tcp:8199` mà tôi chưa bao giờ cắm.

AVD riêng chặn được `android-down` của lane khác, **nhưng không chặn được**
`adb` không có `-s`. Muốn hai lane đo native song song thì phải có hai máy ảo
sống cùng lúc và mọi lệnh đều gắn `ANDROID_SERIAL`.

### 3. Dải LogBox nuốt đúng nút mở luồng chia tiền

Cảnh báo trong phiếu là thật, và đo được bằng toạ độ. Trên màn Khám phá,
1080×2400:

```
dải LogBox   [26,2146] – [1054,2271]
thanh tab    bắt đầu ở y = 2253
4 nhãn tab   y ≈ 2311   -> nằm DƯỚI dải, bấm được
nút "Tạo mới" [469,2195] – [611,2337], tâm y = 2266  -> nằm TRONG dải
```

Nên đúng một nút — nút mở luồng tạo khoản chi, tức cửa vào hero — bị nuốt.
Bấm vào không có lỗi, không có điều hướng, không có log. Trên màn hình nó giống
hệt "tính năng này chưa có". Đã cắn thật hai lần trong lượt này trước khi
`dismiss_logbox` xử được.

Còn một bẫy nữa của cây trợ năng RN: **cả màn dev menu của Expo Go, kể cả nút
`Continue`, đều báo `clickable="false"`**. Thước đo nào lọc theo `clickable` sẽ
trả lời "không có nút" cho những nút ngón tay bấm được. Nên `find()` mặc định
`clickable_only=False`: bấm toạ độ trước, rồi xét màn có đổi không.

---

## Chạy lại

```bash
export PATH=$HOME/Android/Sdk/platform-tools:$PATH
export ANDROID_SERIAL=emulator-5560            # BẮT BUỘC: máy này có nhiều lane

# 1. máy ảo riêng cho lane (một lần)
$HOME/Android/Sdk/cmdline-tools/latest/bin/avdmanager create avd -n rudi-qa3 \
    -k "system-images;android-35;google_apis;x86_64" -d pixel_6 <<< "no"
setsid nohup sg kvm -c "$HOME/Android/Sdk/emulator/emulator -avd rudi-qa3 -port 5560 \
    -no-window -no-audio -no-boot-anim -gpu swiftshader_indirect -accel on -no-snapshot" \
    > /tmp/qa3-emulator.log 2>&1 < /dev/null &
until [ "$(adb shell getprop sys.boot_completed | tr -d '\r\n')" = 1 ]; do sleep 5; done
adb install -r ~/.expo/android-apk-cache/Expo-Go-57.0.9.apk

# 2. proxy ghi lại ĐÚNG request của app này (8199 dùng chung, log của nó không tách được)
python3 tests/qa/qa3-005557-canh-chuyen-di/proxy_ghi_day.py 8299 8199 /tmp/qa3-wire.log &

# 3. Metro ghim vào proxy. 10.0.2.2 là host nhìn từ trong máy ảo — KHÔNG phải localhost
cd apps/mobile && EXPO_PUBLIC_API_URL=http://10.0.2.2:8299 CI=1 npx expo start --port 8081 &
adb reverse tcp:8081 tcp:8081
adb shell am start -a android.intent.action.VIEW -d "exp://10.0.2.2:8081" host.exp.exponent

# 4. bấm thật
cd tests/qa/qa3-005557-canh-chuyen-di
python3 buoc.py "Đăng ký với Apple" "Vào app với tư cách Minh" \
    "Lên plan: chuyến đi của nhóm" "Mở dòng thời gian Chuyến Đà Lạt tháng 6" "Đã tới"
```

`wire-do-that.jsonl` trong cùng thư mục là nhật ký thô của lượt đo này: 31
request, đủ để đối chiếu từng dòng của bảng trên.

## Đã đụng vào tài nguyên chung — nói thẳng

- Giết máy ảo `rudi` ở 5554 qua console (nó đang treo adb của cả máy).
- Dựng lại `rudi` **có `-wipe-data`**. Đây là chỗ tôi làm quá tay: `-wipe-data`
  gỡ luôn Expo Go. Tôi đã cài lại ngay trong cùng lượt từ bản cache sẵn có
  `~/.expo/android-apk-cache/Expo-Go-57.0.9.apk`, nhưng nếu ai đó có state
  trong máy ảo đó thì nó đã mất. Máy `rudi` hiện **không chạy** (bị lane khác
  tắt sau đó). Lệnh cài lại Expo Go nằm ngay ở mục *Chạy lại* phía trên.
- Tạo AVD mới `rudi-qa3` (cổng 5560) và để nó chạy — mọi phép đo trên là của máy này.

## Không chứng minh

- Không nói gì về máy thật ARM: đây là emulator x86_64.
- Không đo F16 tới nơi: chưa có lượt chat thật nào ra được thẻ lịch trình AI.
- Không đo mở-bình-chọn tới nơi: nút bị khoá đúng luật, chưa gỡ khoá được vì
  điều kiện gỡ khoá chính là F16.
- Không nói màn hình **đẹp** hay **đọc được** — không chạy tương phản, không
  chạy trình đọc màn hình, chỉ một cỡ màn 1080×2400.
- Không đụng `:8099`, không đụng Postgres dùng chung. API `:8199` là container
  `demo-api-1` có sẵn; tôi chỉ đọc qua proxy, không khởi động lại nó.
