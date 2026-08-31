# FAIL #505 — cổng `android-check` đo bằng emulator ĐẦU DANH SÁCH, không phải máy được hỏi

- **task_id**: qa-tt-0003
- **commit đo**: `e7644ad` (`origin/devops/emulator-android-tai-lap-duoc`), nhánh **chưa merge**, cắt thẳng từ `origin/main` `f8fbf49`. Head còn nguyên `e7644ad` lúc kết thúc lượt đo (01:29) — phán quyết này áp đúng SHA đó.
- **protocol_version**: v1
- **skill bắt buộc đã gọi**: `e2e-testing`, `bug-reproduction`
- **verdict**: `FAIL`. (QA nộp phép đo; `APPROVE`/`REQUEST_CHANGES`/`REJECT` vẫn là chữ ký người — ADR-0007.)

## Lý do, viết trước phần chi tiết

`cmd_check()` — chính cái cổng — gọi `booted_serial()`, hàm **không lọc theo AVD**:
nó trả về emulator đầu tiên trong `adb devices` có `sys.boot_completed=1`. Nên
`RD_AVD` bị **bỏ qua hoàn toàn** ở lệnh mà cả PR tồn tại để phục vụ. Cùng file,
`cmd_down()` dùng `serial_for_avd()` và lọc đúng; phần chú thích ngay trên nó mô tả
chính lớp lỗi này ("Câu hỏi đúng không phải *có máy nào không* mà là *có ĐÚNG máy
tôi hỏi không*"). Bản vá dừng lại **một hàm trước cái cổng**.

Hậu quả đo được: cùng một máy ảo hỏng, cùng một cổng — **đứng một mình thì ĐỎ,
đứng cạnh máy của lane khác thì XANH**. Máy hỏng không đổi; chỉ hàng xóm đổi.

Đây là blocker loại **"hỏng tính hợp lệ thí nghiệm"**: con số của cổng không quy
được về máy đang được đo. Nó là đúng cái luận điểm PR tự viết ra — *"Một phép đo
không nói được nó đo CÁI NÀO thì không gác được gì."*

**Sửa hết ba lỗi dưới đây tốn 3 dòng.** Tôi đã chạy thử bản vá đó và bài đo lật
từ ĐỎ sang XANH — xem mục "Đối chứng bản vá".

## Ba phát hiện

| # | Phát hiện | Loại | Ở đâu |
|---|---|---|---|
| 1 | `cmd_check()` và `cmd_doctor()` bỏ qua `RD_AVD` — đo lên emulator đầu danh sách | blocker (hợp lệ thí nghiệm) | `scripts/android_emulator.sh` `cmd_check`, `cmd_doctor` |
| 2 | `check` thất bại với **0 byte** đầu ra — câu `die` không bao giờ tới người đọc | suggestion (chẩn đoán) | cùng dòng với #1 |
| 3 | Đối chứng âm `localhost` **cảnh báo nhưng không chặn** — cổng xanh trong khi đường hầm vô hình đang cắm | suggestion → cân nhắc blocker | `cmd_check`, nhánh `case "$bad"` |

### 1. `RD_AVD` bị bỏ qua ở `check` và `doctor`

`booted_serial()` không nhận tham số AVD. `cmd_check()` gọi nó. Nên câu hỏi thực
tế cổng trả lời là "có emulator nào đó khoẻ không", chứ không phải "máy của tôi
khoẻ không".

Đo thật trên máy này lúc 01:22, có đúng một emulator (`emulator-5554`, AVD `rudi`),
`emulator -list-avds` chỉ ra `rudi`:

```
$ ./android_emulator.sh check                                  -> EXIT=0, serial emulator-5554
$ RD_AVD=avd-khong-he-ton-tai-abc123 ./android_emulator.sh check -> EXIT=0, serial emulator-5554
$ diff A.txt B.txt  ->  GIỐNG HỆT NHAU TỪNG BYTE (723 bytes)
```

AVD `avd-khong-he-ton-tai-abc123` **không tồn tại trên máy**. Cổng in bảng xanh đầy
đủ cho nó, không lệch một byte so với lượt hỏi đúng tên máy.

Đối chứng trong **chính file đó**, cùng biến môi trường, hàm tác giả **đã** vá:

```
$ RD_AVD=avd-khong-he-ton-tai-abc123 ./android_emulator.sh down
AVD 'avd-khong-he-ton-tai-abc123' không chạy — không tắt gì cả.
  (đang có máy khác chạy: emulator-5554  — KHÔNG đụng tới)

$ RD_AVD=avd-khong-he-ton-tai-abc123 ./android_emulator.sh doctor
máy đã boot    emulator-5554              <- cũng bỏ qua RD_AVD
```

`down` gọi tên thứ nó không tìm thấy và từ chối. `check` và `doctor` thì không.

**Vì sao nó quan trọng hơn một lỗi vặt:** máy này chạy năm worktree; PR nói rõ "có
lúc hai emulator cùng sống". Lane A chạy `make android-check`, nhận XANH từ máy của
lane B, rồi kết luận môi trường native của mình sẵn sàng. `make android-up` cũng
dính: đường boot mới (không đặt `RD_EMU_PORT`) **không** export `ANDROID_SERIAL`,
nên sau khi `wait_boot` tìm đúng máy mình, nó bàn giao cho `cmd_check` và
`booted_serial()` lại chọn máy khác. Tức lệnh cờ đầu "bật rồi tự kiểm" có thể bật
máy MÌNH và nghiệm thu máy NGƯỜI KHÁC.

### 2. Cổng đỏ mà câm

Lúc 01:19 emulator trên máy này đang boot dở (`uptime` sau đó cho thấy `up 1 min`;
`sys.boot_completed` rỗng, `adb devices` vẫn in `device`). Cổng **từ chối đúng** —
đó là điểm cộng thật cho luận điểm chính của PR. Nhưng:

```
$ ./android_emulator.sh check > out.txt 2> err.txt ; echo $?
1
stdout 0 bytes
stderr 0 bytes
```

Câu `die "không có máy ảo nào boot xong. Chạy: $0 up"` không chạy. Dưới
`set -euo pipefail`, `serial="$(booted_serial)"` thất bại là thoát **ngay tại dòng
gán**, trước khi `[ -n "$serial" ] || die ...` kịp chạy. Repro tối thiểu 5 dòng:

```bash
set -euo pipefail
booted() { return 1; }
serial="$(booted)"
echo "DÒNG NÀY KHÔNG BAO GIỜ CHẠY"
# -> EXIT=1, không in gì
```

Trong file, đúng hai chỗ thiếu `|| true`: `cmd_check` và `cmd_install_expo`.
`cmd_up`, `cmd_down`, `cmd_doctor` đều đã có `|| true` nên không dính.

Script này tồn tại để người sau không phải đoán vì sao hôm nay khác hôm qua. Trả về
một mã thoát trần trụi là để họ đoán tiếp.

### 3. Đối chứng âm nói ra rồi nuốt

`cmd_check` đo `localhost:$API_PORT` làm đối chứng âm và tự khai: nếu nó xanh thì
"hoặc có ai đó cắm adb reverse, hoặc phép đo của ta không thật sự đi ra khỏi máy
ảo. **Cả hai đều làm con số ở trên mất nghĩa**". Rồi `case` chỉ `say`, không đặt
`rc=1`.

Nó **đã cắn thật** trong lượt đo này, không phải giả định:

```
== API nhìn TỪ TRONG máy ảo ==
  10.0.2.2:8199   HTTP/1.1 200 OK
  localhost:8199  HTTP/1.1 200 OK   <- PHẢI hỏng; nếu xanh là đang có adb reverse
  ^ CẢNH BÁO: localhost:8199 xanh, tức có đường hầm adb reverse đang cắm.
EXIT=0
```

Đường hầm `adb reverse tcp:8199` — đúng cái trạng thái vô hình gõ tay mà PR trích
nguyên văn ở đầu file như thứ nó tồn tại để xoá bỏ — **đang cắm trên máy này**, và
cổng cấp cho nó một dấu xanh. Ai đọc EXIT=0 rồi chạy app trỏ `localhost` sẽ thấy nó
chạy, tới khi adb restart.

Đây có thể là lựa chọn thiết kế (cảnh báo, không phải lỗi). Tôi không tự quyết hộ
lane devops — nhưng nếu để nguyên thì nên nói rõ trong `--help`/Makefile rằng
EXIT=0 **không** bảo đảm phép đo đã rời khỏi máy ảo.

## Bài đo, chạy lại được ở máy khác

`tests/qa/qa-tt-0003/do-cong-android-check.sh` — bash thuần. **Không cần Android
SDK, không cần `/dev/kvm`, không cần emulator.** Nó dựng một `adb` giả và khai đội
hình máy ảo qua biến, vì lỗi này vô hình khi chỉ có một máy — mà dựng hai emulator
thật thì bằng chứng chỉ chạy được trên một máy, và như thế không phải bằng chứng.

Không sửa một byte nào của `android_emulator.sh`: script tự đọc `ANDROID_HOME` từ
môi trường, đó là cửa chính nó mở.

```bash
SUT_REF=origin/devops/emulator-android-tai-lap-duoc \
  tests/qa/qa-tt-0003/do-cong-android-check.sh          # ĐỎ trên e7644ad, exit 1
```

Sau khi #505 merge, file có trong cây thì chạy trần, không cần `SUT_REF`.

**Hai canary chạy mỗi lượt, không được bỏ.** Canary hỏng thì bài đo tự bỏ cuộc
(exit 2) và không nộp finding nào:

```
CANARY 1  đội hình LÀNH        -> phải XANH   -> exit=0  đạt
CANARY 2  chỉ máy MẤT MẠNG     -> phải ĐỎ     -> exit=1  đạt (cắn)
```

Chỉ khi canary 2 cắn thì ba dấu xanh dưới đây mới đọc được là "cổng mù":

```
CA 1  máy tôi hỏi CHƯA BOOT, lane khác khoẻ   kỳ vọng ĐỎ -> exit=0, đo lên emulator-5554  LỖI
CA 2  máy tôi hỏi MẤT MẠNG,  lane khác khoẻ   kỳ vọng ĐỎ -> exit=0, đo lên emulator-5554  LỖI
CA 3  không máy nào boot xong                 kỳ vọng ĐỎ+chẩn đoán -> exit=1, 0 byte      LỖI
```

CA 2 đặt cạnh CANARY 2 là phần đáng đọc nhất: **cùng một máy ảo hỏng, cùng một
cổng.** Một mình → ĐỎ. Có hàng xóm → XANH.

## Đối chứng bản vá — bài đo có lật được không

Một bài đo luôn-đỏ cũng in ra ba dòng LỖI y hệt. Nên tôi vá thử trên một **bản
chép ngoài repo** (không đụng sản phẩm, không commit), đúng 3 dòng trong `cmd_check`:

```bash
serial="$(serial_for_avd "$AVD_NAME" || true)"
[ -n "$serial" ] || die "AVD '$AVD_NAME' chưa boot xong (hoặc không chạy). Chạy: $0 up"
```

Chạy lại **chính bài đo đó**, không sửa một dòng nào trong nó:

```
CANARY 1 đạt · CANARY 2 đạt (cắn)
CA 1  exit=1                          đạt
CA 2  exit=1, đo lên emulator-5556    đạt   <- giờ đo ĐÚNG máy được hỏi
CA 3  exit=1, 90 byte:
      | HỎNG: AVD 'rudi-gate' chưa boot xong (hoặc không chạy). Chạy: ... up
TỔNG: ĐẠT   EXIT=0
```

ĐỎ trên `e7644ad` → XANH sau 3 dòng, cùng một máy đo. Bài đo đo được thứ nó khai.
(Bản vá là gợi ý, không phải yêu cầu về hình dạng — `cmd_doctor` cũng cần sửa
tương tự và tôi không vá nó trong lần thử này.)

## Cái PR này làm ĐÚNG, đo được

Không phải mọi thứ đều hỏng; ba điều dưới đây tôi xác nhận bằng phép đo, không
bằng đọc diff:

- **Cổng boot thật sự phân biệt được "adb thấy device" với "đã boot xong".** Lúc
  01:19 emulator đang boot dở: `adb devices` in `emulator-5554 device`, nhưng
  `sys.boot_completed` rỗng và cổng từ chối. Đúng cái phân biệt PR nêu ở đầu file.
- **Phép đo API TỪ TRONG máy ảo là thật và ĐỎ được.** Canary dương trên máy thật:
  `RD_API_PORT=9 ./android_emulator.sh check` → `10.0.2.2:9 <rỗng>` → `EXIT=1`.
  Cổng không phải đồ trang trí luôn-xanh.
- **`down` gọi tên đúng thứ nó phá** và không đụng máy của lane khác (dẫn chứng ở
  mục 1). Ba lỗi tác giả tự khai trong mô tả PR đều đã thật sự được vá.

Và một xác nhận ngoài ý muốn: lúc **01:26**, giữa lượt đo này, `emulator-5554` biến
mất (`adb devices` rỗng). Đó chính là kiểu hỏng PR này tồn tại để chặn — tôi không
dựng lại giả thuyết đó, tôi đứng nhìn nó xảy ra lần thứ hai trong một đêm.

## Ô CHƯA quét — phần quan trọng nhất

- **Cross-measurement trên HAI emulator THẬT.** Chứng minh ở đây đi qua `adb` giả
  cộng một ca máy thật (AVD không tồn tại → vẫn xanh). Tôi **không** dựng hai
  emulator thật cùng lúc để xem lane A đo lên máy lane B. Logic thì không phụ
  thuộc vào chuyện đó (`booted_serial` không có tham số AVD, đọc thẳng ở source, và
  `down` cho đối chứng), nhưng phép đo thì chưa có.
- **`make android-up` đường boot mới.** Suy luận từ đọc code (không export
  `ANDROID_SERIAL` khi thiếu `RD_EMU_PORT`), **chưa chạy** — dựng AVD mới tốn ~60s
  và máy đang có lane khác dùng. Đây là lời khai đọc-nguồn, không phải phép đo.
- **`install-expo`, `up`, `doctor` chạy thật.** Chưa chạy `up`/`install-expo` lần
  nào; `doctor` chỉ chạy đọc.
- **Cổng 8099 (mặc định `api.ts`) nhìn từ trong máy ảo.** Định đo để đối chứng độc
  lập phát hiện của devops thì emulator biến mất lúc 01:26. **Chưa đo.** Phát hiện
  `api.ts` của devops vẫn chưa được lane nào ngoài devops xác nhận.
- **Hành vi trên máy ARM thật** (codec, camera, quyền, hiệu năng) — PR tự khai
  không chứng minh, tôi cũng không.
- **Mã QR quét được bằng app ngân hàng thật** — chưa ai quét, còn nguyên là ô trống
  cho tới khi leader cầm điện thoại thật.

## Cổng repo trên nhánh phán quyết này

Nhánh `qa/cong-android-check-do-nham-may`, cắt từ `origin/main` `f8fbf49`. Chỉ thêm
hai file (một script bash đo, một trang này); không đụng một dòng code sản phẩm nào.

Số liệu dán ở mô tả PR.

## Ghi chú bắt buộc về bề mặt đo

Mọi con số ở trang này đo trên **Android emulator x86_64 (API 35) headless trong
WSL2**, và trên một `adb` giả cho phần đội hình nhiều máy. **Chưa đo trên máy Android
thật, chưa đo trên iOS.** Bài đo này nói về *cổng đo môi trường native*, nó không
nói gì về sản phẩm chạy đúng trên native.
