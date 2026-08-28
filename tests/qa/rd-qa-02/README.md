# rd-qa-02 — Tiền không được sai

Commit đã kiểm: `4e09b55817fdcd883b256941a88924e24d91a623` (`origin/main`)
Ngày chạy: 2026-08-29 · Postgres 16 thật · API thật trên `127.0.0.1:8099`

Bộ này **không tự chia lại tiền**. Mọi con số kỳ vọng đều là con số máy chủ đã
gửi trên dây; kịch bản chỉ đọc lại và so. Viết một allocator thứ hai trong test
chỉ chứng minh hai lỗi giống nhau, nên chỗ nào cần "đáp án" thì lấy từ
`packages/shared/money.mjs` — đúng một implementation định dạng mà cả app lẫn
trang khách đang dùng, đã có golden case riêng.

## Chạy lại

```bash
docker compose up -d postgres
cd services/api && alembic upgrade head
MOBILE_DATABASE_URL='postgresql+psycopg://mobile:mobile-dev-only@localhost:5432/mobile' \
  python3 -m uvicorn app.api.main:app --port 8099 --host 127.0.0.1 &

cd apps/mobile && npm ci && npx tsc -p tsconfig.test.json && node tools/fixup-esm.mjs
EXPO_PUBLIC_API_URL=http://127.0.0.1:8099 npx expo export --platform web \
  --output-dir /tmp/rd-qa-02-web --clear
(cd /tmp/rd-qa-02-web && python3 -m http.server 8777 --bind 127.0.0.1 &)

cd tests/qa/rd-qa-02 && npm ci     # playwright + @axe-core/playwright

# 0. tự kiểm các bộ dò — không cần DB, không cần server, chạy trước mọi thứ
node --test tests/qa/rd-qa-02/name-leak.selfcheck.mjs
node --test tests/qa/rd-qa-02/keyboard-money.selfcheck.mjs   # cần playwright
# 1. bất biến phía máy chủ
EXPO_PUBLIC_API_URL=http://127.0.0.1:8099 node --test tests/qa/rd-qa-02/money-server-truth.mjs
# 2. số màn hình vs số máy chủ
node tests/qa/rd-qa-02/screen-vs-server.mjs /tmp/rd-qa-02-web http://127.0.0.1:8099 8777
# 3. đột biến có chủ đích
MOBILE_DATABASE_URL=... MOBILE_QA_API=http://127.0.0.1:8099 python3 tests/qa/rd-qa-02/run_mutations.py
# 4. trợ năng trên bề mặt tiền (dùng URL khách THẬT, không dùng preview)
EXPO_PUBLIC_API_URL=http://127.0.0.1:8099 node tests/qa/rd-qa-02/make-guest-url.mjs
node tests/qa/rd-qa-02/a11y-money-surfaces.mjs "<url vừa in ra>"
# 5. lỗi 404 chập chờn ở confirm
EXPO_PUBLIC_API_URL=http://127.0.0.1:8099 node tests/qa/rd-qa-02/repro-confirm-404.mjs 400
```

## Bảng đối chiếu: số màn hình vs số máy chủ

59 phép đối chiếu, **0 lệch**. Trình duyệt thật (Chromium 390×844), bundle web
thật, body API thật ghi lại trên dây rồi so với text render ra trong DOM.

> Bản đầu của tài liệu này ghi 47 phép đối chiếu. **Ba trong số đó không thể đỏ**
> — xem [Ba phép kiểm chết](#ba-phép-kiểm-chết-và-cách-chúng-bị-bắt) bên dưới.
> Con số 59 = 47 cũ + 12 phép **đối chứng dương** mới, mỗi phép kiểm tên đi kèm
> đúng một phép chứng minh bộ dò còn sống.

| bề mặt | số gì | trên màn hình | máy chủ gửi | khớp |
|---|---|---|---|---|
| NhapKhoanChi | tổng đã nhập | 1.234.567 đ | 1.234.567 đ | ✅ |
| DeXuat | phần của Nam | 246.914đ | 246.914đ | ✅ |
| DeXuat | phần của Hà | 246.914đ | 246.914đ | ✅ |
| DeXuat | phần của Quyên | 246.913đ | 246.913đ | ✅ |
| DeXuat | phần của Dũng | 246.913đ | 246.913đ | ✅ |
| DeXuat | phần của Linh | 246.913đ | 246.913đ | ✅ |
| DeXuat | tổng hoá đơn | 1.234.567đ | 1.234.567đ | ✅ |
| DeXuat | Σ các dòng trên màn hình | 1234567 | 1234567 | ✅ |
| DotThu | khoản Hà / Dũng / Linh / Quyên phải gửi | 246.914đ · 246.913đ ×3 | như máy chủ | ✅ ×4 |
| DotThu | Σ nợ = tổng − phần người ứng | 987653 | 987653 | ✅ |
| ChiaSe | phong bì của Hà / Dũng / Linh / Quyên | như máy chủ | như máy chủ | ✅ ×4 |
| trang khách | số tiền in ra (4 người) | như máy chủ | như máy chủ | ✅ ×4 |
| trang khách | `data-copy` (4 người) | như máy chủ | như máy chủ | ✅ ×4 |
| trang khách | không thấy phần người khác | không lộ | không lộ | ✅ ×6 |
| trang khách | **bộ dò thấy tên khi cắm vào** (đối chứng dương) | thấy | thấy | ✅ ×12 |
| trang khách | không thấy tên người khác | không lộ | không lộ | ✅ ×12 |
| trang khách | không thấy tổng nhóm | không lộ | không lộ | ✅ ×4 |

**Client không tự tính.** Đột biến M7 dựng lại `Math.floor(total / n)` trong
`apps/mobile/src/api.ts` và `offline.test.mjs` đỏ ngay — cổng chống mọc lại
allocator ở client có thật và có răng.

## Ba phép kiểm chết, và cách chúng bị bắt

Bộ dò tên rò rỉ từng được viết là `new RegExp(`>[^<]*\b${name}\b`)`. Trong
JavaScript `\b` định nghĩa trên `\w` == `[A-Za-z0-9_]`, và `à` **không** phải
word character:

```
node -e 'console.log(/\bHà\b/.test("· Hà ·"), /\bHa\b/.test("· Ha ·"))'
-> false true
```

Trong ROSTER chỉ `Hà` kết thúc bằng nguyên âm có dấu, nên đúng **3 trong 12**
phép kiểm tên — `Quyên/Dũng/Linh không thấy tên Hà` — không bao giờ đỏ được.
Chúng in ✅ trong bảng ở trên và không chứng minh gì cả.

Sai theo **cả hai chiều**, không chỉ mù:

| markup | `Hà` có trên trang? | `\bHà\b` nói |
|---|---|---|
| `<p>· Hà ·</p>` | **có** | không lộ ← bỏ sót thật |
| `<p>Hàn Quốc</p>` | không | **LỘ** ← báo động giả |

Chiều thứ hai chưa ai gặp vì trang khách chưa từng in chữ "Hàn"/"Hàng", nhưng nó
nằm sẵn ở đó: `à→n` **là** một chuyển tiếp `\w`, nên `\b` khớp.

### Đối chứng đỏ/xanh, chạy trên Postgres thật + API thật + trình duyệt thật

Đột biến dùng để chứng minh (`guest_view.py:117`, rò rỉ thật trên mọi trang):

```python
"occasion_label": obligation["occasion_label"] + " · Hà · 1.234.567",
```

uvicorn được **khởi động lại** sau mỗi lần sửa file — một tiến trình chạy từ
trước vẫn đang chạy code cũ, và đó đúng là cách một lượt đột biến tự nói dối.

| máy chủ | bộ dò | kết quả | 3 dòng `không thấy tên Hà` |
|---|---|---|---|
| sạch | `\b` (trước sửa) | 59 đối chiếu, **3 lệch**, exit 1 | — bị đối chứng dương bắt |
| sạch | Unicode (sau sửa) | 59 đối chiếu, **0 lệch**, exit 0 | ✅ đúng |
| đột biến | `\b` (trước sửa) | 59 đối chiếu, 7 lệch, exit 1 | **✅ XANH GIẢ** — Hà in trên mọi trang |
| đột biến | Unicode (sau sửa) | 59 đối chiếu, **7 lệch**, exit 1 | **❌ LỘ ×3** — bắt đúng |

Hàng 3 là lỗi gốc, tái lập nguyên vẹn: máy chủ rò rỉ tên `Hà` ra bốn trang khách
và ba phép kiểm phụ trách đúng chuyện đó vẫn in "không lộ".

Hàng 1 là điều đáng giá hơn: **trên cây sạch, không cần đột biến nào**, bộ dò mù
vẫn bị bắt — vì mỗi phép kiểm phủ định giờ đi kèm một **đối chứng dương** cắm tên
vào chính bytes của trang đó rồi bắt bộ dò phải nói "thấy". Không ai còn phải nhớ
chạy đột biến để phát hiện một phép kiểm đã chết.

### Tự kiểm không cần môi trường

`name-leak.selfcheck.mjs` cắm từng tên trong ROSTER vào markup hình dạng thật và
bắt bộ dò phải đỏ, cộng các ca không được báo động giả (`Hàn Quốc`, `Namibia`,
`Linhh`), ca NFD/NFC, và ca ghim lại chính tính chất ASCII của `\b` để không ai
"đơn giản hoá" ngược về:

| bộ dò | `node --test name-leak.selfcheck.mjs` |
|---|---|
| `\b` (trước sửa) | 32 ca, **10 pass / 22 fail**, exit 1 |
| Unicode (sau sửa) | 32 ca, **32 pass / 0 fail**, exit 0 |

Chạy trong 70ms, không cần DB, không cần server — nên nó là bước 0 của quy trình
chạy lại ở trên.

### Ô KHÔNG quét được bằng so chuỗi

Với hoá đơn 1.234.567 chia 5, ba người nợ đúng cùng 246.913đ. Kiểm "người này
không thấy phần người khác" bằng `includes` **không phân biệt được** ba người
đó, nên script đếm và in ra chứ không tính là đã quét (3 người × 2 cặp trùng).
Một phép kiểm không thể fail không phải là phép kiểm.

## Bất biến phía máy chủ (`money-server-truth.mjs`)

7/7 ca xanh, mọi con số do máy chủ trả về:

| ca | quy mô | kết quả |
|---|---|---|
| Σ phân bổ = tổng hoá đơn | 85 hoá đơn (17 tổng × 5 cỡ nhóm) | chênh lệch **đúng 0** ở cả 85 |
| mọi phần là số nguyên đồng, không âm | 357 phần | đạt |
| chia lại lần hai ra đúng kết quả cũ | 25 lần chia lại | trùng khít, kể cả `rounding_gainers` |
| sửa chữ số đọc sai (82.000 → 820.000) | 1 ca | Σ = 820.000, chênh 0, và phân bổ **có đổi** |
| máy chủ từ chối số chưa từng lên màn hình | dời 1đ giữa 2 người, tổng vẫn đúng | từ chối, `proposal_changed` |
| tổng nợ = tổng có | 4 nghĩa vụ | nợ 987.653 = có 987.653, chênh **0** |

Tổng dải đã quét: 1đ, 2đ, 3đ, 5đ, 7đ, 100, 101, 999, 82.000, 100.000, 100.001,
100.002, 246.000, 333.333, 1.000.000, 1.234.567, và một tỷ trừ 1đ — nhân với
nhóm 2, 3, 4, 5, 7 người.

## Đột biến: 8 ca, 7 bị bắt

Mỗi ca sửa đúng một chỗ trên đường tiền, chạy đúng cổng đáng lẽ phải bắt nó, rồi
`git checkout` trả lại file. Sau khi phục hồi, cả 5 cổng được chạy lại và **đều
xanh** — nếu không thì chữ "ĐỎ" ở trên không chứng minh gì.

| ca | đột biến | cổng | kết quả |
|---|---|---|---|
| M1 | Bỏ chia phần dư: Σ phân bổ nhỏ hơn hoá đơn | golden vectors (`tests/domain`) | **ĐỎ** (exit 1) |
| M2 | Đảo tie-break làm tròn: người ứng luôn thắng phần dư | golden vectors | **ĐỎ** (exit 1) |
| M3 | Máy chủ thôi so `expected_allocations` — client đẩy được số của mình | `money-server-truth` (ca chống giả mạo) | **ĐỎ** (exit 1) |
| M4 | Nghĩa vụ bớt 1đ so với phần chia: tổng nợ < tổng có | `money-server-truth` (ca nợ=có) | **ĐỎ** (exit 1) |
| M5 | Định dạng nhóm 4 chữ số: `1234567` in ra `123.4567` | `money.test.mjs` golden format | **ĐỎ** (exit 1) |
| M6 | `parseAmountVnd` thôi từ chối số vượt trần | `money.test.mjs` parse refusals | **ĐỎ** (exit 1) |
| M7 | Client tự chia lại: `Math.floor(total/n)` quay lại `api.ts` | `offline.test.mjs` | **ĐỎ** (exit 1) |
| M8 | Trang khách **in một số, chép một số khác** (lệch 1đ) | `tests/web` | **VẪN XANH** (exit 0) ⚠️ |

M3 và M4 khởi động lại uvicorn trước khi đo: một tiến trình chạy từ trước khi
sửa file vẫn đang chạy code cũ, và đó đúng là cách một lượt đột biến tự nói dối
mình là đã đỏ.

### M8 là lỗ thật trong bộ test hiện có

`tests/web` chỉ so chuỗi hiển thị với `format_vnd(...)` của chính nó, nên khi
`amount_display` lệch khỏi `amount_vnd` thì không có gì đối chứng. Đã dựng lại
đầy đủ theo `bug-reproduction`:

| bước | kết quả |
|---|---|
| áp M8, chạy `pytest services/api/tests/web -q` | **46 passed, 75 subtests** — xanh hoàn toàn |
| áp M8, chạy `screen-vs-server.mjs` | **exit 1** — `số tiền của Dũng: KHÔNG THẤY vs 246.914` |
| gỡ M8, chạy lại `screen-vs-server.mjs` | **exit 0**, 47 đối chiếu 0 lệch |

Đỏ-khi-có-lỗi, xanh-khi-gỡ-lỗi: `screen-vs-server.mjs` bịt được lỗ này,
`tests/web` thì không. `a11y-money-surfaces.mjs` cũng bắt độc lập (so số in ra
với `data-copy`).

Đây là **lỗ ở tầng test**, không phải lỗi đang có trên `main` — trên `main`
`amount_display` và `amount_vnd` khớp nhau.

## Trợ năng trên bề mặt tiền

Quét bằng axe-core (`wcag2a`, `wcag2aa`, `wcag22aa`) trên **URL khách thật** do
chính luồng sinh ra, 390×844:

Mọi dòng dưới đây **cộng vào exit code**. Trước đó hai dòng cuối chỉ là
`console.log` — xem [Hai phép đo chết](#hai-phép-đo-chết-trong-bảng-trợ-năng)
bên dưới.

| kiểm | kết quả |
|---|---|
| axe tự kiểm (trang cố tình hỏng) | 5 vi phạm (`button-name`, `color-contrast`, `document-title`, `html-has-lang`, `image-alt`) — axe **có** đọc DOM |
| axe trên trang khách thật | **0 vi phạm**, 16 luật đạt |
| số tiền có được đọc lên không | `aria-label="Sao chép số tiền 246.914 đồng"` — có, và chứa đúng con số đang in |
| số in ra vs số chép đi | `246.914` vs `246914` — cùng một khoản tiền |
| bàn phím tới được nút chép (WCAG 2.1.1) | tới được, ở **lần Tab thứ 1** — đo bằng cách bấm Tab thật rồi so `document.activeElement` |
| dấu hiệu focus thấy được (WCAG 2.4.7) | `:focus-visible=true`, `outlineStyle none→solid`, `outlineWidth →2px`, `outlineColor →rgb(0, 117, 107)` |

**Cảnh báo cho ai chạy lại:** quét `python3 -m app.web.preview` sẽ ra 1 vi phạm
`target-size` (7 nút, WCAG 2.2 AA 2.5.8). Bảy nút đó là thanh chuyển trạng thái
do **chính preview** chèn (`app/web/preview.py:129-131`), không có trong template
sản phẩm. Đó là lỗi của giàn giáo QA, **không phải lỗi sản phẩm** — dùng
`make-guest-url.mjs` để quét markup thật.

### Hai phép đo chết trong bảng trợ năng

Bảng trên từng có dòng `| bàn phím | Tab đầu tiên dừng đúng ở nút chép số tiền |`
kể như một phép kiểm **đã đạt**. Nó không phải phép kiểm. Trong
`a11y-money-surfaces.mjs` hai phép đo cuối chỉ `console.log`, không cộng vào
`failures`:

```js
await page.keyboard.press("Tab");
const reachable = await page.evaluate(...);
console.log(`  phím Tab đầu tiên dừng ở: ${reachable}`);   // <- không assert
const focusVisible = await amount.evaluate(...);
console.log(`  focus thấy được: outline=${focusVisible.outline} ...`); // <- không assert
```

Nên Tab dừng ở đâu cũng được, script vẫn in `0 vấn đề chặn` và exit 0.

Phép đo thứ hai còn hỏng theo một kiểu nữa. `getComputedStyle(el, x)` nhận
pseudo-**element** ở tham số hai; `:focus-visible` là pseudo-**class**, nên
Chromium trả về một declaration rỗng. Nó trả **cùng một đáp án rỗng** cho trang
CÓ vòng focus 2px và trang `outline: none` — nghĩa là kể cả có ai đó viết assert
lên trên nó, assert đó vẫn không phân biệt được hai trang. Cách đo thay thế:
bấm Tab thật (Chromium chỉ cấp `:focus-visible` cho focus từ bàn phím, nên
`el.focus()` bằng script sẽ báo thiếu), rồi đọc computed style **thường** và so
với style lúc chưa focus.

#### Đối chứng đỏ/xanh

Ba trang cắm lỗi, mỗi trang đổi đúng một thứ, đều sạch axe để phép kiểm bàn phím
là thứ **duy nhất** có thể đỏ:

| trang cắm lỗi | trước sửa | sau sửa |
|---|---|---|
| nút khác chen trước nút chép | `0 vấn đề chặn`, **exit 0** | `Tab đầu tiên dừng ở "button"…`, **exit 1** |
| nút chép có `tabindex="-1"` | `0 vấn đề chặn`, **exit 0** | `KHÔNG tới được bằng bàn phím… WCAG 2.1.1`, **exit 1** |
| focus không đổi gì trên màn hình | `0 vấn đề chặn`, **exit 0** | `không có dấu hiệu focus… WCAG 2.4.7`, **exit 1** |
| trang không có `[data-copy]` nào | `0 vấn đề chặn`, **exit 0** | `⚠ CHƯA QUÉT… 0/1 url`, **exit 1** |
| **URL khách THẬT** (đối chứng dương) | exit 0 | exit 0 — Tab #1, `:focus-visible=true`, `outline none→solid 2px` |

Hàng cuối là hàng phải có: không có nó, một probe báo "hỏng" cho mọi trang cũng
sẽ qua được cả bốn hàng trên.

Hàng 4 là cùng một lỗi ở dòng ngay bên cạnh: `if (await amount.count())` bọc
toàn bộ phần kiểm, nên một trang không có nút chép thì **mọi phép kiểm bên dưới
lặng lẽ không chạy** và script vẫn exit 0 — không phân biệt được với "đã quét và
sạch". Link bị thu hồi / hết hạn thì đúng là không có số tiền nào (`guest.html`
rẽ theo `view.link_state`), nên đó không tự nó là lỗi; script giờ nói thẳng ô đó
**chưa quét**, và chỉ đỏ khi cả lượt chạy không có url nào mang bề mặt tiền.

#### Tự kiểm không cần môi trường

`keyboard-money.selfcheck.mjs` chạy cả hai tầng — unit test cho phần chấm điểm
(thuần, không cần trình duyệt) và **chạy chính CLI** rồi đọc exit code thật:

| CLI | `node --test keyboard-money.selfcheck.mjs` |
|---|---|
| chỉ `console.log` (trước sửa) | 15 ca, **10 pass / 5 fail**, exit 1 |
| có assert (sau sửa) | 15 ca, **15 pass / 0 fail**, exit 0 |

Năm ca đỏ ở hàng 1 đúng là các ca chạy CLI trên trang cắm lỗi. Mười ca xanh
chứng minh probe và phần chấm điểm đã đúng từ trước — cái thiếu chỉ là nối chúng
vào exit code. Hàng 1 đo bằng `git stash` chính file CLI rồi chạy lại cùng một
file test, không phải bằng cách nhớ lại. Chạy trong ~8s, không cần DB, không cần
server — nên nó là bước 0 của quy trình chạy lại ở trên, cùng với bộ dò tên
(`npm run selfcheck` chạy cả hai: **47 ca, 47 pass**).

## Phát hiện phải chuyển cho lane khác

Hai cái dưới đây **không** phải lỗi chia tiền; Σ phân bổ, tổng nợ = tổng có và
số trên màn hình đều đúng. Nhưng cả hai nằm trên đường tiền và tái lập được.

### 1. `Idempotency-Key` không được máy chủ đọc ở bất kỳ route ghi nào

`apps/mobile/src/api.ts:80` ghi "The server enforces `Idempotency-Key` on every
write route", và client có sẵn bảng dịch `idempotency_key_reuse` /
`invalid_idempotency_key`. Không có code nào trong `services/api/app/` đọc
header đó (`grep -rn 'Idempotency-Key' services/api/app/` → rỗng).

```
POST /expenses  ×2, cùng Idempotency-Key
  lần 1: HTTP 201 expense_id=0e3e61bb-…
  lần 2: HTTP 201 expense_id=1598e22b-…   ← hai khoản chi
POST /expenses/{id}/confirm ×2, cùng Idempotency-Key
  lần 1: HTTP 201 version=9a524380-…
  lần 2: HTTP 201 version=62926eb0-…      ← hai phiên bản
```

Hệ quả **có giới hạn**, đã kiểm: gom cả hai phiên bản vào một đợt thu bị domain
từ chối `409 expense_versions_unavailable`, nên **tiền không nhân đôi**.
`POST /batches` lần hai cũng bị chặn bởi cùng luật đó. Dedupe thật sự chỉ tồn tại
ở `save_payment_report` và `save_receipt` — qua **field trong body**, không phải
header.

Test `bấm hai lần chỉ ghi một khoản chi`
(`apps/mobile/tests/e2e/vertical-slice.test.mjs:222`) vì thế **đang đỏ trên
`main`**: `npm run test:e2e` → 2 tests, 1 pass, 1 fail. CI không bắt được vì
không job nào dựng API (`grep -c uvicorn .github/workflows/test.yml` → 0), nên
`test:e2e` luôn `t.skip` và thoát 0.

### 2. `confirm` 404 chập chờn ngay sau khi `POST /expenses` trả 201

```
#84 confirm 404 {"code":"expense_not_found","detail":"Expense does not exist"}
    (expense_id=ecef11e1-e35c-4a13-9670-433fb1a585b0)
```

Hai lượt hôm nay: 1/400 (0,25%) và 0/400 (0%) → ~1/800 trên máy này. Lượt trước
đã ghi nhận 0,5–7%. Máy chủ vừa trả 201 kèm `expense_id`, lệnh confirm ngay sau
đó nói khoản chi không tồn tại. Người dùng thấy: bấm "Đúng rồi, ghi vào sổ" và
được báo khoản chi không tồn tại.

Chập chờn nên **một lượt sạch không phải bằng chứng đã hết** — script mặc định
400 vòng vì lý do đó.

## Cổng đã chạy trên cây sạch

| lệnh | kết quả |
|---|---|
| `python3 -m pytest services/api/tests tests -q` | **398 passed, 41 skipped, 4272 subtests** |
| `tests/postgres` với `MOBILE_REQUIRE_POSTGRES_TESTS=1` | **41 passed, 0 skipped** |
| migration render ra DDL (không cần DB) | exit 0 |
| `cd apps/mobile && npm test` (có bước bundle) | **70 passed, 0 fail** |
| `cd apps/mobile && npm run test:e2e` | **2 tests, 1 pass, 1 fail** ⚠️ (mục 1 ở trên) |
| `python3 scripts/repo_guard.py tree HEAD` | `Repo guard passed tracked tree: 241 file scan(s)` |

## Ô CHƯA quét

- **Mã QR có quét được bằng app ngân hàng thật không.** Không agent nào trả lời
  được; cần leader cầm điện thoại thật. `test_vietqr.py` chỉ kiểm chuỗi EMVCo và
  CRC — một chuỗi đúng CRC vẫn có thể là chuỗi không app ngân hàng nào nhận.
- **Rò rỉ giữa những người nợ đúng cùng một số tiền** — xem ô không quét được ở trên.
- **Tên rò rỉ trong thuộc tính HTML** (`aria-label`, `title`, `href`, `alt`).
  `name-leak.mjs` cố ý chỉ soi **text content**: tiền tố `>[^<]*` ghim phép khớp
  vào đoạn ký tự sau khi một thẻ đóng, nên một cái tên nằm trong giá trị thuộc
  tính không bị soi. Trình đọc màn hình thì đọc `aria-label`, nên đây là một lỗ
  thật, chỉ là chưa mở rộng ở lượt này. Có ca tự kiểm ghim đúng phạm vi đó lại
  (`does not fire on a name that only appears inside a tag`) để việc mở rộng sau
  này là một quyết định có ý thức, không phải một thay đổi lặng lẽ.
- **Đọc bill bằng AI**: chỉ kiểm đường sửa tay (đổi tổng → chia lại đúng). Chưa
  kiểm OCR đọc đúng bao nhiêu phần trăm trên ảnh bill thật.
- **Đua thật sự**: hai `confirm` đồng thời trên cùng một expense (khoá thật của
  PostgreSQL) chưa kiểm; ở đây chỉ gọi tuần tự.
- **Trình đọc màn hình thật** (VoiceOver/TalkBack/NVDA) chưa dùng; mới kiểm cây
  trợ năng qua axe + `aria-label`.
- **Tối ưu chuyển khoản dạng netting nhiều chiều** chưa tồn tại trong sản phẩm —
  hiện mọi nghĩa vụ đều trỏ về một người ứng tiền, nên "tổng nợ = tổng có" đã
  kiểm ở dạng một-người-nhận, không phải dạng đồ thị nhiều chiều.
