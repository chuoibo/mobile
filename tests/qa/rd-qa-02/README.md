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

47 phép đối chiếu, **0 lệch**. Trình duyệt thật (Chromium 390×844), bundle web
thật, body API thật ghi lại trên dây rồi so với text render ra trong DOM.

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
| trang khách | không thấy tên người khác | không lộ | không lộ | ✅ ×12 |
| trang khách | không thấy tổng nhóm | không lộ | không lộ | ✅ ×4 |

**Client không tự tính.** Đột biến M7 dựng lại `Math.floor(total / n)` trong
`apps/mobile/src/api.ts` và `offline.test.mjs` đỏ ngay — cổng chống mọc lại
allocator ở client có thật và có răng.

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

| kiểm | kết quả |
|---|---|
| axe tự kiểm (trang cố tình hỏng) | 5 vi phạm (`button-name`, `color-contrast`, `document-title`, `html-has-lang`, `image-alt`) — axe **có** đọc DOM |
| axe trên trang khách thật | **0 vi phạm**, 16 luật đạt |
| số tiền có được đọc lên không | `aria-label="Sao chép số tiền 246.914 đồng"` — có, và chứa đúng con số đang in |
| số in ra vs số chép đi | `246.914` vs `246914` — cùng một khoản tiền |
| bàn phím | Tab đầu tiên dừng đúng ở nút chép số tiền |

**Cảnh báo cho ai chạy lại:** quét `python3 -m app.web.preview` sẽ ra 1 vi phạm
`target-size` (7 nút, WCAG 2.2 AA 2.5.8). Bảy nút đó là thanh chuyển trạng thái
do **chính preview** chèn (`app/web/preview.py:129-131`), không có trong template
sản phẩm. Đó là lỗi của giàn giáo QA, **không phải lỗi sản phẩm** — dùng
`make-guest-url.mjs` để quét markup thật.

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
- **Đọc bill bằng AI**: chỉ kiểm đường sửa tay (đổi tổng → chia lại đúng). Chưa
  kiểm OCR đọc đúng bao nhiêu phần trăm trên ảnh bill thật.
- **Đua thật sự**: hai `confirm` đồng thời trên cùng một expense (khoá thật của
  PostgreSQL) chưa kiểm; ở đây chỉ gọi tuần tự.
- **Trình đọc màn hình thật** (VoiceOver/TalkBack/NVDA) chưa dùng; mới kiểm cây
  trợ năng qua axe + `aria-label`.
- **Tối ưu chuyển khoản dạng netting nhiều chiều** chưa tồn tại trong sản phẩm —
  hiện mọi nghĩa vụ đều trỏ về một người ứng tiền, nên "tổng nợ = tổng có" đã
  kiểm ở dạng một-người-nhận, không phải dạng đồ thị nhiều chiều.
