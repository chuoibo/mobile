# rd-qa-17 — PR #136 (F05 mã QR kết bạn · F46 check-in)

**PASS.**

Mã QR chỉ mang `person_id` + tên hiển thị — đã **giải mã bằng OpenCV từ ảnh chụp ô
vuông đã render** và in ra, không đọc từ source. Cầm mã của người khác không mở
được gì: đổi tên, tài chính, số tài khoản, vào nhóm đều 403. Check-in **không gửi
toạ độ nào từ máy** — thân request đọc trên dây đúng bằng `{"place_id":"..."}`, toạ
độ lưu là toạ độ catalogue của máy chủ, và client tự khai `lat/lng` bị 422.

## Đo trên cái gì

```
đo tại    611fb1c   (head PR #136 như đã đẩy lên origin)
sha này   CHƯA ở main — merge-base là 042f996 (#137)
          main hiện tại đã đi tiếp tới d18c3ad (#139)
cũng đo   8d8129f = 611fb1c ⊕ origin/main@d18c3ad (merge thử, sạch)
```

Đo cả hai vì head PR nằm sau main hai commit. Một bản dựng từ head là một sản phẩm
khác với cái sẽ vào main.

```
máy chủ   uvicorn từ /tmp/qa17/services/api, cổng 8717, DB riêng qa17f05f46
          curl /openapi.json → có /contexts/{id}/checkins và /outing-stops/{id}/checkins
          ⇒ không phải ảnh cũ trả 404 cho thứ nó chưa có
bundle    index-7363b8a114680b9014b0bf595df45e06.js, dựng bằng --clear
          chứa 5 tham chiếu tới 127.0.0.1:8717, **0 tham chiếu tới 8099**
          hash phục vụ ở cổng 4717 khớp hash vừa dựng ⇒ cổng không bị lane khác chiếm
```

## Cổng đã chạy

| Lệnh | Trên 611fb1c | Trên bản merge 8d8129f |
|---|---|---|
| `pytest services/api/tests tests -q` | 1023 pass · 4581 subtests | 1092 pass · 4582 subtests |
| `pytest tests/postgres` (`MOBILE_REQUIRE_POSTGRES_TESTS=1`) | **214 pass · 0 skip** | **214 pass · 0 skip** |
| `apps/mobile && npm test` | 388 pass · 0 fail | 409 pass · 0 fail |
| `check_alembic_heads.py` | — | exit 0, một head `e3b8c1d5720f` |
| `repo_guard tree` / `range` | 534 file | 4240 file / 8 commit |
| `test_repo_guard` | — | 33 OK |
| migration render ra DDL (offline) | exit 0 | — |

Tầng postgres chạy **0 skip**. Một dòng `skipped` ở tầng này không phải là xanh.

## Câu 1 — trong mã QR có gì?

Ảnh chụp phần tử `[role=img][aria-label^="Mã QR kết bạn"]` (180×180) rồi giải mã
bằng `cv2.QRCodeDetector` — một bộ giải mã **không chung dòng code nào** với
`src/ui/qr.ts`. Đọc đầu vào của bộ mã hoá rồi gọi đó là "trong mã có gì" chỉ chứng
minh bộ mã hoá được gọi với cái nó được gọi.

```
'http://127.0.0.1:4717/#ban=46b55e67-932b-5415-a5ee-08fb2641a4ff&tenban=Minh'

số điện thoại VN                     không có
chuỗi 9–19 chữ số (số tài khoản)     không có
toạ độ thập phân                     không có
token/jwt                            không có
email                                không có
mã EMVCo VietQR                      không có
```

Màn hình tự nói ra điều đó: *"Trong mã chỉ có mã tài khoản và tên hiển thị. Không
có số điện thoại."*

## Câu 2 — quét mã của người khác có kéo ai vào nhóm không?

Không. Mã là **danh tính, không phải giấy thông hành** — ngược hẳn với link mời của
#128/#132, vốn là bearer token nên mới cần hạn dùng.

Kẻ lạ chụp được ô vuông của Bích, cầm `person_id` của Bích:

```
PUT  /people/{Bích}                 403  permission_denied  is_self
GET  /people/{Bích}/finance         403  not_your_finances
GET  /people/{Bích}/bank-recipient  403  permission_denied  is_own_account
PUT  /people/{Bích}/bank-recipient  403  permission_denied  is_own_account
tự mời mình vào nhóm của Kiệt       403  permission_denied  is_group_member
```

Chiều ngược lại — bị người lạ mời — cũng không lộ gì. Bích ở trạng thái `invited`:

```
GET /contexts/{X}/members    403  is_group_member
GET /contexts/{X}/memories   403  is_group_member
GET /contexts/{X}/balances   403  is_group_member
roster kẻ lạ nhìn thấy: KHÔNG có trường display_name
```

## Câu 3 — mã có hết hạn không?

**Không, và ở đây tôi cho là đúng.** Hạn dùng của #132 gắn vào một *quyền*; cái này
là một *danh tính*, và một danh tính hết hạn thì tấm thẻ trở nên vô dụng chứ không
an toàn hơn.

Cái còn lại là phiền, không phải lộ: mời rác không có hạn mức.

```
kẻ lạ mời Bích 30 lần liên tiếp → 30/30 HTTP 201 trong 0.4s, không có chặn nào
```

Đường này (`POST /contexts/{id}/members`) có từ trước #136 và ai biết một
`person_id` cũng đi được. Nhưng mã QR làm việc lấy id rẻ đi — chụp một ô vuông qua
bàn ăn — nên nó **mới thành với tới được**. Ghi lại, không chặn merge: người bị mời
đọc được đúng con số không.

Phụ: mời một id có thật trả 201, id chưa đăng ký trả 409 `person_not_registered` —
phân biệt được hai trường hợp. Giá trị thấp, vì `people.id` suy từ số điện thoại
qua HMAC có khoá máy chủ nên không dò ngược offline được.

## Câu 4 — check-in có lộ vị trí GPS của ai không?

Không. Đo **trên dây**, không đọc source. Toàn bộ request app gửi khi bấm nút:

```
POST /contexts/{ctx}/checkins   body={"place_id":"p-tiem-nuong-xom-lao"}
```

Không có `lat`, không có `lng`, không có `accuracy`. Và server từ chối nếu client
cố khai:

```
body kèm lat/lng            422  extra_forbidden  (ApiModel đặt extra="forbid")
place_id bịa ("nhà Bích")   422  place_not_found  (không dội lại input)
```

Toạ độ **được lưu** là toạ độ catalogue của máy chủ, đối chiếu từng cặp:

```
p-lung-chung-cafe   catalogue=(11.9512, 108.4451)  lưu=(11.9512, 108.4451)  KHỚP
```

`catalog.py` nói rõ toạ độ trong đó là bịa cho demo, không mô tả cơ sở thật nào.

Check-in **theo chặng dừng** còn chặt hơn: route không nhận thân request nào
(`POST /outing-stops/{id}/checkins` không có requestBody trong openapi), và câu trả
lời không có trường toạ độ nào cả:

```
trường trả về: created_at, display_name, id, person_id, stop_id
có lat/lng/accuracy? KHÔNG
bấm hai lần         → 409 already_checked_in, vẫn đúng 1 dòng
```

Người ngoài **tự khai** `X-Actor-Roles: group_admin` + `X-Actor-Contexts: <ctx>` bị
chặn ở cả năm bề mặt F46:

```
POST /contexts/{ctx}/checkins            403 is_group_member
GET  /contexts/{ctx}/memories            403 is_group_member
GET  ...?kind=checkin&place_id=...       403 is_group_member
POST /outing-stops/{stop}/checkins       403 is_group_member
GET  /outings/{outing}/checkins          403 is_group_member
```

Bộ lọc `place_id` không kéo được nhóm khác sang: hai nhóm cùng check-in một chỗ,
Kiệt lọc trong nhóm mình ra đúng 1 dòng, đúng một `context_id`.

Trên màn: không chuỗi nào giống toạ độ hiện ra.

## Test của F05 có cắn không — 3/3 đột biến đỏ

Lead đã đột biến phần F46 (unique index, `is_group_member`); tôi không làm lại. F05
chưa ai kiểm nên tôi kiểm:

```
đối chứng cây sạch                       27 pass / 0 fail
bỏ chặn độ dài tên 200 ký tự khi đọc mã  26 pass / 1 FAIL
bỏ kiểm dạng id khi DỰNG mã              26 pass / 1 FAIL
bỏ kiểm dạng id khi ĐỌC mã               26 pass / 1 FAIL
khôi phục (git diff rỗng)                27 pass / 0 fail
```

**Cái bẫy tôi đã rơi vào, ghi ra để người sau khỏi rơi:** ba đột biến đầu tiên của
tôi ra **27/27 pass** — trông y hệt "test không cắn". Không phải. `tests/*.test.mjs`
import từ `dist-test/`, mà `npm test` mới là thứ chạy `tsc -p tsconfig.test.json`.
Gọi thẳng `node --test` sau khi sửa `src/` là đo một bản biên dịch cũ. Ai đột biến
`apps/mobile` phải biên dịch lại trước, nếu không sẽ kết luận ngược.

## a11y — số 0 có nghĩa vì canary xấu đã đỏ

```
canary XẤU   5 vi phạm — button-name, color-contrast, image-alt, label, target-size
canary SẠCH  0 vi phạm
```

Máy quét còn sống. Rồi mới tới màn thật (axe-core, tag `wcag2a wcag2aa wcag22aa`):

```
F05 "Mã kết bạn của bạn"  390×844    0 vi phạm / 22 quy tắc đạt
F05                       1280×900   0 vi phạm / 22 quy tắc đạt
F46 thẻ địa điểm          390×844    0 vi phạm
F46 sau khi đã check-in   390×844    0 vi phạm
nút "Nhóm đang ở đây"     324×48 px  (đạt 2.5.8 target size)
nhãn trình đọc màn hình   "Mã QR kết bạn của Minh" — không đọc URL ra từng ký tự
Tab đầu tiên dừng ở       BUTTON "Chỉ đường"
lỗi console               không có
```

Máy chủ tĩnh phục vụ đúng đường dẫn thật (`/khong-co-that-dau` → **404**, không
phải 200), nên ba trang canary không phải là chính cái app đội lốt.

## Mã hỏng và mã độc

Đo khi **đã mở nhóm** — thẻ bạn quét được chỉ hiện ở trạng thái đó, và lượt đo đầu
của tôi ở trạng thái chưa có nhóm đã suýt cho ra kết luận sai:

```
mã hợp lệ (đối chứng)   vào được, thẻ hiện, id cắt còn 8 ký tự "49871dab", nút bật
id không đúng dạng      KHÔNG vào, dừng ở màn mở đầu
id rỗng                 KHÔNG vào, dừng ở màn mở đầu
tên 300 ký tự           vào được, tên bị TỪ CHỐI → "Chưa rõ tên", nút TẮT
script trong tên        vào được, render thành CHỮ THƯỜNG, không dialog,
                        không pageerror, DOM không có HTML thô
id thật không tên       "Chưa rõ tên", nút TẮT cho tới khi gõ tên
id lạ chưa đăng ký      thẻ hiện, nút bật — bấm sẽ đúc một người mới (xem dưới)
```

## Phát hiện — không cái nào chặn merge

1. **Quét mã trước khi có nhóm thì app im lặng.** Thẻ "QUÉT ĐƯỢC MÃ KẾT BẠN" chỉ
   render sau khi đã mở nhóm. Người vừa chĩa camera vào ô vuông thấy màn nhóm trống
   trơn, không dấu hiệu nào cho biết mã đã đọc được. Đường đi vẫn thông (mở nhóm
   xong thẻ hiện, mời chạy đúng), nên là thiếu phản hồi chứ không phải cụt đường.

2. **Mời rác không có hạn mức** — 30/30 trong 0.4s. Xem câu 3.

3. **Mã bịa đúc ra người không có thật.** `#ban=<uuid chưa ai đăng ký>&tenban=Ma`
   cho thẻ với nút bật; bấm sẽ `PUT /people/{id}` tạo hàng mới rồi mời. Giống hệt
   đường gõ tay nên không phải lỗ mới, nhưng đáng biết.

4. **Máy sạch không chạy demo được** (có từ trước #136, không phải lỗi PR này).
   Bảy người demo trong `nhom-demo.ts` không được đăng ký ở máy chủ, nên `POST
   /contexts` trả **409** và màn nhóm nói *"Chưa có tên cho tài khoản này nên chưa
   mở được nhóm."* Tôi phải seed bảy người bằng `PUT /people/{id}` mới đi tiếp
   được. Bản demo nào dựng trên DB mới sẽ đâm vào đúng chỗ này.

5. **`GET /places?context_id=1aa00000-…-0000a0000001`** — app hỏi catalogue bằng một
   context ghim cứng chứ không phải nhóm vừa mở. `catalog.py` đã ghi rõ hồ sơ nhóm
   là hằng số cho lát cắt dọc; nhắc lại vì con số "ĐIỂM 69%" trên màn là tương đối
   với hồ sơ đó, không phải với nhóm người dùng đang mở.

6. **Oracle tồn tại** 201 / 409 `person_not_registered`. Giá trị thấp.

## Ô CHƯA QUÉT

- **Mã QR chưa được quét bằng camera điện thoại thật.** Tôi giải mã một ảnh chụp
  180×180 bằng OpenCV. Đó không phải một cái máy cầm tay chĩa qua bàn ăn dưới đèn
  vàng. Câu này chỉ leader đóng lại được.
- **Nhánh `ru-di.app`** — trên điện thoại không có `location` nên mã trỏ về tên miền
  chưa đăng ký. Chỉ đọc code, chưa chạy trên máy thật.
- **Bản React Native thật** (chỉ đo bản web).
- **Chủ đề tối** cho cả hai màn.
- **Màn dòng thời gian "đã tới"** của check-in theo chặng — tôi đo API, chưa đi bộ UI.
- **Hạn mức mời quá 30 lần** / dưới tải kéo dài.
- **Đột biến phần F46** — Lead đã làm, tôi không lặp lại.
- **`imp detect`** — tôi chạy axe với hai canary, không chạy imp detect.

## Chạy lại

```bash
# máy chủ
createdb qa17f05f46 && cd services/api && MOBILE_DATABASE_URL=... alembic upgrade head
MOBILE_DATABASE_URL=... python3 -m uvicorn app.api.main:app --port 8717

# thăm dò quyền riêng tư (API)
python3 tests/qa/rd-qa-17/probe-quyen-rieng-tu.py
python3 tests/qa/rd-qa-17/probe-checkin-chang.py

# bundle + đi bộ (cần playwright + @axe-core/playwright)
cd apps/mobile && EXPO_PUBLIC_API_URL=http://127.0.0.1:8717 \
  npx expo export --platform web --output-dir dist-qa17 --clear
cd dist-qa17 && python3 -m http.server 4717 --bind 127.0.0.1
node tests/qa/rd-qa-17/di-bo-f05-f46.mjs     # canary + axe + chụp ô vuông
node tests/qa/rd-qa-17/hanh-trinh-f46.mjs    # tạo nhóm → check-in, đọc trên dây
node tests/qa/rd-qa-17/hanh-trinh-f05.mjs    # mở đúng chuỗi camera đọc được

# giải mã ô vuông
python3 -c "import cv2;print(cv2.QRCodeDetector().detectAndDecode(
  cv2.resize(cv2.imread('/tmp/qa17-shots/f05-qr.png'),None,fx=4,fy=4,
  interpolation=cv2.INTER_NEAREST))[0])"
```

Ảnh chụp nằm ở `/tmp/qa17-shots/`, cố ý **không** đưa vào Git (repo guard fail
closed với binary, và ảnh QA không thuộc về repo).
