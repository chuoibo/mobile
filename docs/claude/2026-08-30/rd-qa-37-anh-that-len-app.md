# rd-qa-37 — Ảnh thật lên app, đo bằng trình duyệt thật

**FAIL** (không chặn PoC — không có PR nào đang chờ; đây là phán quyết trên `main`)

**Lý do, viết trước phần chi tiết:**

1. **Luồng chụp bill CHẠY THẬT và chia đúng tiền** — chọn ảnh bill → AI đọc → 5 món,
   tổng `235.000đ`, khớp dòng tổng in trên bill. Có ảnh chụp màn.
2. **Nhưng cùng MỘT FILE, byte y hệt nhau, lúc đọc được lúc không: 6/11 lần thành công.**
   Người dùng chụp bill, bị báo "chưa đọc được", chụp lại y hệt thì lại ra. Đây là lỗi
   nằm ngay trên đường hero của PoC.
3. **Chọn một file không phải ảnh → màn in `[object HTMLCanvasElement]` hai chỗ.**
   Tái lập 3/3. Rác lập trình viên hiện thẳng lên mặt người dùng.
4. **`/receipts/scan` không gọi bộ lột EXIF của #197.** GPS đi nguyên vẹn qua biên
   máy chủ. Hôm nay client web/native đều tự lột trước khi gửi nên chưa rò ra thật —
   đây là **lỗ hổng đang ngủ**, không phải đang chảy máu.
5. **Chốt chặn URL ngoài của #195 GIỮ ĐƯỢC** — 7 dạng địa chỉ độc hại, 0 lần chạm
   tracker, với canary xanh chứng minh máy đo còn sống.
6. **Khung ảnh `Anh.tsx` đúng cả ba hành vi** — không nhảy layout, URL chết không bắn
   lại request, trình đọc màn hình đọc đúng một lần.

---

## Đo tại đâu

```
đo tại   0889408  (= tip của origin/main lúc bắt đầu)
sha này  ĐÃ ở main
bundle   apps/mobile/dist-qa37, dựng từ chính cây này bằng
         EXPO_PUBLIC_API_URL=http://localhost:9611 npx expo export --platform web --clear
         -> 6 tham chiếu localhost:9611, 0 tham chiếu 8099, 0 tham chiếu 8000
API      uvicorn ở 127.0.0.1:9614, DB riêng mobile_qa37 (không đụng DB chung)
tap      127.0.0.1:9611 -> 9614, ghi lại nguyên văn body multipart
đếm route  44 qua tap == 44 trực tiếp  (KHÔNG dùng máy demo 8099)
trình duyệt Chromium thật của Playwright, viewport 390x844
```

Ảnh chụp nằm **ngoài repo** (repo guard fail-closed với binary): `/tmp/rd-qa-37-shots/`,
37 tấm. Ảnh bill là ảnh **sinh ra**, không phải bill thật; toạ độ GPS nhúng vào là chợ
Bến Thành, không phải nhà ai.

---

## 1. Chụp bill đầu-cuối, sáu tấm ảnh khác nhau

Chọn file qua đúng ô chọn ảnh mà `expo-image-picker` mở ra (`filechooser` của Playwright),
không tiêm DOM. Gemini thật, khoá thật, độ trễ thật.

| Ảnh | Người dùng thấy | Chờ | HTTP | Màn trắng | Rác/mã lỗi |
|---|---|---|---|---|---|
| `ro.jpg` bill rõ | "Chưa đọc được bill này. Thường là do ảnh mờ, thiếu sáng…" | 8.4s | 422 | không | không |
| `mo.jpg` bill mờ | "Ảnh bill quá mờ. Vui lòng chụp lại ảnh rõ hơn." | 10.1s | 422 | không | không |
| `xoay.jpg` EXIF=6 + GPS | **"Đã nhận diện 5 món", tổng 235.000đ, "Khớp với dòng Tổng cộng in trên bill"** | 11.3s | **200** | không | không |
| `thucdon.jpg` bảng giá | "Đây là thực đơn hoặc bảng giá, không phải hoá đơn…" | 4.5s | 422 | không | không |
| `gia.jpg` text đổi đuôi | **`[object HTMLCanvasElement]`** | — | **không gửi** | không | **CÓ** |
| `to.jpg` 4000×3000, 42MB | "Ảnh bill quá mờ. Vui lòng chụp lại ảnh rõ hơn." | 6.5s | 422 | không | không |

**Trong lúc chờ màn nói gì** (đây là câu hỏi leader hỏi): có nói, và nói tử tế —
`"Đang chuẩn bị ảnh bill"` → `"Thu nhỏ ảnh và xoá vị trí chụp trước khi gửi đi."` →
`"AI đang đọc từng món"` → `"Ảnh đã gửi. Đang chờ máy chủ đọc xong tên món và số tiền."`
→ và một đồng hồ đếm `"Đã chờ N giây"`. Không có khoảng im lặng nào.

**Ảnh xoay hiện đúng chiều.** `xoay.jpg` lưu 1200×900 nằm ngang với `Orientation=6`;
tới máy chủ nó là **900×1200 dựng đứng**. Trình duyệt đã áp thẻ xoay khi re-encode.

Ảnh: `bill-*-1-dangcho.png` (lúc chờ) và `bill-*-2-ketqua.png` (kết quả), `mot-xoay.jpg.png`
(màn kết quả đọc được đủ 5 món).

### 1a. Quan sát phụ — tên món bị cắt trong ô nhập

Trên màn "Kết quả nhận diện", ô tên món hiển thị `Cơm tấm sườn bì c…` / `Cơm tấm sườn nư…`.
Không mất dữ liệu (giá trị vẫn đủ), nhưng người dùng không đọc được tên món mình đang
duyệt. Suggestion, không phải blocker. Xem `mot-xoay.jpg.png`.

---

## 2. LỖI — cùng một file, hai kết quả (type-4: hỏng tính hợp lệ / độ tin cậy)

Không phải hai ảnh khác nhau. **Cùng một file, cùng một sha256.**

```
xoay.jpg  sha256 43bcfa4a056f…   52.806 bytes   900x1200
```

Bắn thẳng vào API, mỗi lần một request độc lập:

```
lần  1 -> 200  OK 5 món tổng=235000
lần  2 -> 422  receipt_unreadable
lần  3 -> 422  receipt_unreadable
lần  4 -> 422 | 5 -> 422 | 6 -> 200 | 7 -> 200 | 8 -> 200 | 9 -> 200 | 10 -> 200 | 11 -> 422
```

**Tổng: 6/11 lần đọc được (≈55%) trên byte y hệt nhau.**

Điểm quan trọng cho ba luật tiền: **khi nó đọc được thì tiền LUÔN đúng** — 5 món,
`235.000đ`, khớp dòng tổng. Không có lần nào ra số sai. Nên đây **không phải lỗi tiền**;
đây là lỗi **độ tin cậy**: cùng một tấm bill, khoảng một nửa số lần app nói "chưa đọc được".

Hậu quả trên sân khấu demo: người trình bày chụp bill, app từ chối, họ chụp lại — rd-qa-05
đã ghi đúng kiểu hành vi này ("người trình bày chụp lại ba lần trước khi nghi ngờ máy chủ").
Lần này nguyên nhân không phải thiếu khoá; là chính mô hình không nhất quán.

Tiêu chí gỡ chặn: đo lại tỉ lệ trên ≥20 lần với một tấm bill thật; nếu vẫn <90% thì cần
một cơ chế thử lại (tự retry 2 lần trước khi báo thất bại) hoặc đổi tham số gọi model.

Không tái lập được bằng đọc nguồn — chỉ lộ ra khi gọi thật nhiều lần.

---

## 3. LỖI — `[object HTMLCanvasElement]` lên màn (type-1: vi phạm chất lượng người dùng thấy)

**Tái lập: 3/3 lần.**

Bước tái lập tối thiểu:
1. Mở app → "Bỏ qua" → `[+]` → "Tạo khoản chi"
2. Bấm "Chọn ảnh bill", chọn một file **không phải ảnh** đã đổi đuôi `.jpg`
   (`printf 'khong phai anh' > gia.jpg`)
3. Màn hiện `[object HTMLCanvasElement]` ở **hai chỗ**: banner giữa màn và thanh lỗi đỏ dưới đáy

Không có request nào được gửi đi (hỏng ở bước nén phía client), không màn trắng,
app không sập — nhưng chuỗi hiện ra là rác lập trình viên.

**Nguyên nhân gốc:** `apps/mobile/App.tsx:321`

```ts
setError(problem instanceof Error ? problem.message : String(problem));
```

Trên web, `expo-image-manipulator` không giải mã được file này và ném ra một
`HTMLCanvasElement` chứ không phải `Error`. Nhánh `String(problem)` biến nó thành
`"[object HTMLCanvasElement]"` rồi đưa thẳng lên màn.

Đây đúng là nhánh mà comment ngay trên nó nói là đã được dọn ("nhánh cũ … không bao giờ
khớp"): nhánh `instanceof Error` chạy tốt, nhánh `else` mới là chỗ chưa ai đi qua.

Tiêu chí gỡ chặn: chọn file không phải ảnh → màn hiện một câu tiếng Việt nói được
"file này không phải ảnh", và không chứa chuỗi `[object `.

Ảnh: `lap-gia.jpg-1.png`, `-2`, `-3`.

---

## 4. Chốt chặn URL ngoài (#195) — GIỮ ĐƯỢC

Tiêm địa chỉ độc hại bằng cách viết lại phản hồi `GET /places` (đúng mô hình đe doạ mà
`nguon-anh.ts` mô tả: địa chỉ là chuỗi do **thành viên** ghi). Tracker là server thật ở
9613, ghi lại IP + thời điểm của mọi request.

| Ca | Địa chỉ | Tracker nhận | `<img>` trong DOM | iframe |
|---|---|---|---|---|
| **canary XANH** | `http://localhost:9611/qa37-anh/that.png` | 0 | **12 tải được** | 0 |
| host người khác | `http://localhost:9613/theo-doi.png` | **0** | 0 | 0 |
| protocol-relative | `//localhost:9613/pr.png` | **0** | 0 | 0 |
| backslash | `/\localhost:9613/bs.png` | **0** | 0 | 0 |
| tiền tố lừa | `http://localhost:9611.localhost:9613/x.png` | **0** | 0 | 0 |
| `javascript:` | `javascript:fetch('http://localhost:9613/js.png')` | **0** | 0 | 0 |
| `data:text/html` | `data:text/html,<img src="…9613/data.png">` | **0** | 0 | 0 |
| cùng gốc nhưng 404 | `…/khong-ton-tai-404.png` | **0** | 0 | 0 |

**Canary xanh tải được 12 ảnh** → máy đo còn sống, nên bảy số 0 kia có nghĩa. Không có
`javascript:` nào chạy, không `data:text/html` nào render, không iframe nào sinh ra.

Ảnh: `anh-canary-xanh.png` (có ảnh) so với `anh-ngoai-host.png` (về chỗ chờ).

---

## 5. Khung ảnh `Anh.tsx` (#195) — cả ba hành vi đúng

Đo trên **DOM đã render**, không đọc nguồn — `rnw` nuốt thuộc tính, và bài học
`rnw-nuot-accessibilitystate` nói đúng chỗ này.

**a. Không nhảy layout.** Hộp khung y hệt nhau khi chưa có và khi có ảnh:

```
chưa có ảnh : {w:172, h:124, y:428}
có ảnh      : {w:172, h:124, y:428}
```

**b. URL chết → về chỗ chờ, và KHÔNG bắn lại.** Sau 3 lần ép re-render:
`goiThemSauReRender: 0`. Tổng cộng đúng **1** request cho URL hỏng. Trong DOM còn
**0** `<img>` vỡ, không icon vỡ, không chuỗi `ECONNREFUSED`/`404` nào trên màn.
`hong` sticky theo URI hoạt động đúng như docstring hứa.

**c. Trình đọc màn hình đọc đúng một lần.** 13 khung, 13 khung có nhãn, **0 tên bị đọc
hai lần**. DOM thật:

```html
<div role="img" aria-label="Ảnh Tiệm Nướng Xóm Lào" style="overflow:hidden;height:124px">
  <div aria-hidden="true" style="position:absolute;inset:0">   <!-- chỗ chờ -->
    <img alt="" draggable="false" src="http://localhost:9611/qa37-anh/that.png">
```

Ghi chú cho người đọc lại số của tôi: phép đo đầu tiên của tôi đếm ra "12 `<img>` không
bị ẩn" và **đó là finding giả do chính phép đo đẻ ra** — tôi chỉ đọc thuộc tính trên
`<img>` mà không đi ngược lên tổ tiên. `aria-hidden` nằm ở thẻ cha. Sửa phép đo rồi mới
ra con số đúng.

---

## 6. EXIF trên đường bill — lỗ hổng đang NGỦ

**Câu hỏi:** #197 đã có `app/media/images.py::sanitize_image`. `/receipts/scan` có gọi nó không?

**Trả lời: KHÔNG.** `grep` ra 0 nơi import `app.media`. Đường đi thật:

```
UploadFile -> image.file.read() -> run_receipt_skill(content, …)
           -> reader.read(image, mime) -> types.Part.from_bytes(data=image)  # thẳng sang Google
```

Chứng minh bằng hành vi, không bằng đọc nguồn — `tests/qa/rd-qa-37/test_exif_duong_bill.py`
ghi lại đúng bytes mà route giao ra ngoài, qua chính seam `get_receipt_reader` của app:

```
GPS survived the upload boundary and was handed to the receipt reader:
{0: b'\x02\x03\x00\x00', 1: 'N', 2: (10.0, 46.0, 22.0), 3: 'E', 4: (106.0, 41.0, 53.0)}
```

**Đã chứng minh nó là cổng thật, không phải một dòng đỏ:**

```
3 failed   # main @ 0889408, không đụng gì
3 passed   # + sanitize_image() nối vào scan_receipt
3 failed   # gỡ bản sửa ra, cây sạch lại
```

Bản sửa thử nghiệm đã được **gỡ hoàn toàn** (`git status services/api/` sạch). QA chứng
minh, không vá.

### Nhưng hôm nay chưa rò ra thật — và phải nói rõ điều đó

Ảnh chụp trên dây (tap ghi lại nguyên văn body multipart, có nhãn rõ ràng):

```
scan-01.bin = xoay.jpg -> 200   900x1200  orientation=None  GPS=KHÔNG CÓ
scan-02.bin = ro.jpg   -> 422   900x1200  orientation=None  GPS=KHÔNG CÓ
```

Client **web** re-encode qua canvas trước khi gửi → EXIF rụng, thẻ xoay được áp.
Client **native** cũng luôn đi qua `compressForReading` → `backend.compress` →
`renderAsync()` + `saveAsync()` (re-encode là vô điều kiện; chỉ bước resize mới có điều kiện).

Nên xếp loại đúng là: **lỗ hổng ngủ chờ tính năng bật lên** — máy chủ nhận và chuyển tiếp
EXIF nguyên vẹn cho bất cứ client nào **không** phải app này (gọi API trực tiếp, một client
khác, hay ngày nào đó bước nén phía client hỏng/bị bỏ). Không phải type-3 đang chảy máu
hôm nay; là một tầng phòng thủ **đang thiếu** ở đúng chỗ nó nên có.

Tiêu chí gỡ chặn: `/receipts/scan` gọi `sanitize_image` → 3 ca trên XPASS → gỡ marker
`xfail` và giữ chúng làm cổng sống.

---

## Ô CHƯA QUÉT — đọc kỹ phần này

- **Điện thoại thật: chưa quét.** Toàn bộ báo cáo này đo trên **web** trong Chromium.
  Brief nói "điện thoại là chính". Đường native (`expo-camera` chụp thật, `ImageManipulator`
  native) **chưa ai chạy**. Kết luận "native cũng lột EXIF" ở mục 6 là **suy từ đường code**,
  không phải số đo trên máy.
- **Mã VietQR chưa được quét bằng app ngân hàng thật.** Vẫn nguyên như mọi lượt trước.
- **Bill thật chưa dùng.** Mọi ảnh đều sinh bằng Pillow. Tỉ lệ 6/11 ở mục 2 đo trên bill
  tổng hợp; bill giấy thật có thể tốt hơn hoặc tệ hơn.
- **Chưa đo quá 11 lần** cho câu hỏi bất định. 11 lần đủ để nói "có bất định", chưa đủ để
  chốt con số 55%.
- **Chưa quét:** ảnh HEIC (iPhone chụp mặc định ra HEIC; `ALLOWED_MIME_TYPES` có nhận
  `image/heic` nhưng chưa ai đẩy một file HEIC thật qua).
- **Chưa quét:** nhiều người cùng quét bill một lúc; hành vi khi mất mạng giữa chừng.
- **Chưa quét:** `image_url` trên `memories` — màn kỷ niệm không dùng `Anh.tsx`, nên chốt
  chặn ở mục 4 **không phủ** đường đó. Ai render ảnh kỷ niệm sau này phải đi qua `Anh`,
  nếu không thì lỗ theo dõi-bằng-IP quay lại nguyên vẹn.

---

## Cổng đã chạy trong cây sạch

```
python3 -m pytest services/api/tests tests -q
  -> 1309 passed, 294 skipped, 3 xfailed, 4607 subtests passed in 75.21s

cd apps/mobile && npm test
  -> # tests 554   # pass 554   # fail 0

git status --short services/api/     -> (rỗng: bản sửa thử nghiệm đã gỡ hết)
```

294 skipped là tầng `tests/postgres` thiếu `MOBILE_TEST_DATABASE_URL` — **chưa chạy**,
không phải "xanh". Lượt này không chạm tầng persistence nên tôi không mở nó.

## Kỹ năng đã dùng

`e2e-testing` (chặng 1 xếp rủi ro, chặng 4 lát cắt qua client thật, chặng 6 thăm dò,
chặng 7 kết luận + ô chưa quét), `bug-reproduction` (bước 2 thu nhỏ repro cho `gia.jpg`,
bước 5 viết test đỏ trước khi có bản sửa, bước 6 revert-to-verify cho cổng EXIF,
bước 7 phân loại bất định vs môi trường cho `xoay.jpg`).

## Việc cho lane khác

- **frontend** — `App.tsx:321` in `[object HTMLCanvasElement]`. Tái lập 3/3, bước ở mục 3.
- **backend** — `/receipts/scan` chưa gọi `sanitize_image`; 3 ca `xfail(strict)` đã đặt sẵn
  ở `tests/qa/rd-qa-37/test_exif_duong_bill.py`, nối vào là chúng tự XPASS và bắt gỡ marker.
- **backend/lead** — tỉ lệ đọc bill 6/11 trên byte y hệt nhau. Cần quyết định: tự retry,
  hay đổi tham số gọi model.
