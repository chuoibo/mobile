# rd-qa-07 · Màn Cá nhân: ba luật tiền không ai gác, và tab bar hỏng ngữ nghĩa

**FAIL** — không chặn merge cái gì (mọi thứ đã ở trên `main`), nhưng hai nhóm phát
hiện cần chủ sở hữu xử lý trước demo.

**Lý do, viết trước phần chi tiết:** ba luật tiền của route `/people/{id}/finance`
được phát biểu trong comment và **không có test nào cưỡng chế**. Lật ngược từng
luật rồi chạy toàn bộ cổng — 987 pass, 4434 subtest — không một ca nào đỏ. Nguy
hiểm nhất là M3: cho **lời tự khai của người trả** ("Tôi đã chuyển") tính là đã
thanh toán, tức ai cũng tự xoá nợ của mình bằng một nút bấm. Đó đúng là bản sửa mà
người ta sẽ viết để đóng lỗi rd-qa-06 đã báo, và không có gì chặn lại. Song song,
tab bar dùng `role="tablist"` chứa `role="button"` — lỗi **critical** WCAG 1.3.1,
có mặt ở **cả 4 tab**, tức toàn bộ vỏ app.

- protocol_version: v1
- Đo trên: `main @ aaefbfa3433a890db9f05566fb6576613dcc004e`
- Verdict: `FAIL` (báo cáo, không phải cổng merge — code đã ở trên `main`)
- Bộ đo: `tests/qa/rd-qa-07/`

## 0. Vì sao lượt này nhắm vào đây

`gh pr list --state open` rỗng — không PR nào chờ phán quyết. Nhưng `main` vừa nhận
ba lần merge (#95, #96, #97) và **cả ba đều merge bằng APPROVE của Lead, không có
phán quyết QA nào**. #96 mang vào một route tiền mới (`finance.py`) cộng 298 dòng
repository, và tự khai bất biến 3 trong docstring của chính nó.

Cổng mặc định che đúng chỗ đó: `python3 -m pytest services/api/tests tests -q` cho
`856 passed, **148 skipped**`, và phần skipped là toàn bộ tầng PostgreSQL — nơi 14
ca tiền của màn này sống. Skip không phải xanh.

## 1. Cổng đầy đủ trên `main` — xanh

| Lệnh | Kết quả |
|---|---|
| `python3 -m pytest services/api/tests tests -q` | `856 passed, 148 skipped` |
| `tests/postgres` với `MOBILE_REQUIRE_POSTGRES_TESTS=1` | `131 passed`, **0 skipped** |
| `cd apps/mobile && npm test` | `231 pass / 0 fail` |
| Toàn bộ cổng + tầng live | `987 passed, 17 skipped, 4434 subtests` |

`main` không đỏ. Phát hiện dưới đây là **thiếu test**, không phải code đang sai.

## 2. BLOCKER — ba luật tiền không có gì cưỡng chế

Loại 2 (sai tiền) và loại 1 (vi phạm cổng) theo charter.

`03-mutation-gate.py` lật ngược từng luật rồi chạy **toàn bộ** cổng có PostgreSQL
thật. Ba control chết đúng như phải chết, nên bộ test và harness đều còn sống:

```
control M1-oldest-version-wins                KILLED   red: test_correcting_an_expense_does_not_count_both_versions
control M2-payer-owes-their-own-share         KILLED   red: test_the_person_who_fronted_the_bill_owes_nothing_for_their_own_share
control M6-settled-stops-adding-back-up       KILLED   red: test_the_two_figures_under_the_total_always_add_back_up_to_it
        M3-a-self-report-settles-the-debt     SURVIVED  987 passed
        M4-over-confirmation→negative-debt    SURVIVED  987 passed
        M5-decimal-escapes-as-money           SURVIVED  987 passed
```

### M3 — lời tự khai tự xoá nợ (nghiêm trọng nhất)

`repository.py` viết: *"Counting reports would let anybody clear their own debt by
pressing a button."* Đúng, và **không test nào giữ câu đó**.

Fixture `Slice` trong `test_person_finance_postgres.py` **chưa bao giờ tạo một
`PaymentReport` nào** — `confirm_receipt` truyền cứng `payment_report_id=None`.
Docstring của `test_a_confirmed_receipt_clears_the_debt...` khẳng định "A payment
*report* is not [cái làm settle]", nhưng thân test chỉ chứng minh chiều thuận. Chiều
nghịch không được viết ra, nên không được bảo vệ.

**Tiền điều kiện là thật, không phải giả định:** `PaymentReport` sinh ra từ route
khách đang chạy `POST /g/{token}/da-chuyen` (`app/api/routes/guests.py:67`) — đúng
cái nút "Tôi đã chuyển" mà rd-qa-06 đã đi bằng tay.

**Vì sao đây là bẫy chứ không phải lỗi lý thuyết:** rd-qa-06 báo rằng khách bấm "Tôi
đã chuyển" nhưng bảng đợt thu vẫn ghi "chưa gửi". Bản sửa tự nhiên nhất cho lỗi đó
là cho lời khai tính vào. Làm thế thì nợ tự bốc hơi, và cổng vẫn xanh 987/987.

- **Gỡ chặn khi**: có ca chứng minh một `PaymentReport` **không kèm**
  `ReceiptConfirmation` để `outstanding_vnd` nguyên vẹn.

### M4 — xác nhận thừa thành nợ âm

Bỏ `max(0, ...)` → không ca nào đỏ. Đã kiểm **tiền điều kiện có thật** bằng thăm dò
trực tiếp: xác nhận 150.000 rồi thêm 50.000 nữa trên nghĩa vụ 150.000 — repository
**nhận cả hai**:

```
PROBE-OVERCONFIRM reachable=YES outstanding=0 settled=150000 spend=150000
```

Có clamp thì `outstanding=0` (đúng). Không có clamp thì `outstanding=-50.000` và
`settled` phồng lên `200.000` trên khoản chi `150.000`. Test
`..._always_add_back_up_to_it` **có** assert `outstanding >= 0` — nhưng nó không bao
giờ lái tới trạng thái xác nhận thừa, nên assert đó không bao giờ được thực thi. Sổ
là append-only: một lần xác nhận thừa nằm lại vĩnh viễn.

- **Gỡ chặn khi**: có ca xác nhận vượt số nợ rồi assert `outstanding_vnd >= 0`.

### M5 — `Decimal` thoát ra thành tiền

Bỏ `int(...)` → không ca nào đỏ. PostgreSQL `SUM` một cột bigint trả `numeric`,
psycopg đưa về `Decimal`, và JSON hoá thành `750000.0`. Luật tiền 1 là **số nguyên
đồng end-to-end**. Hôm nay đúng (`PROBE-TYPES spend=int settled=int out=int`), nhưng
không gì giữ nó.

- **Gỡ chặn khi**: có ca assert `type(...) is int` cho cả bốn trường tiền.

**Chủ sở hữu:** `services/api/` và test backend là của Codex. Tôi **không** tự viết
ba ca này vào cây của họ. Đã gửi `bug-to backend`.

## 3. BLOCKER — tab bar hỏng ngữ nghĩa trên cả 4 tab

Loại 1. axe 4.13, WCAG 2.2 A/AA, Chromium 390×844.

```
kham-pha   aria-prohibited-attr(serious), aria-required-children(critical)
len-plan   aria-prohibited-attr(serious), aria-required-children(critical)
tin-nhan   aria-prohibited-attr(serious), aria-required-children(critical)
ca-nhan    aria-prohibited-attr(serious), aria-required-children(critical)
```

**Detector đã được chứng minh còn sống TRƯỚC**, không phải sau: trồng một `<img>`
thiếu `alt` và một `<button>` không tên, đếm đi từ 2 → 4 đúng bằng hai rule dự kiến
(`image-alt`, `button-name`). Chỉ sau đó con số 2 mới đáng tin.

**`aria-required-children` (critical, WCAG 1.3.1):**

```
target: div[role="tablist"]
why:    Element has children which are not allowed: [role=button]
```

`role="tablist"` bắt buộc con phải là `role="tab"`. Đang là `role="button"`. Trình
đọc màn hình mất hoàn toàn ngữ nghĩa tab: không có "tab 2 trên 5", không có trạng
thái đang chọn. Đây là điều hướng chính của app, có mặt ở mọi màn.

**`scrollable-region-focusable` (serious, WCAG 2.1.1 + 2.1.3):** vùng cuộn nội dung
không focus được bằng bàn phím — người dùng bàn phím không cuộn được màn Cá nhân.

Đi Tab 10 lần chỉ ra **6 điểm dừng phân biệt**, và các mục tab hiện ra dưới dạng
`div` chứ không phải `tab`.

**Chủ sở hữu:** `apps/mobile/` là của lane frontend. Đã gửi `bug-to frontend`.

## 4. Cái ĐÚNG — và đã đo trên màn, không phải trên API

`01-ca-nhan-doi-chung.mjs`, PASS toàn bộ:

- **Số trên màn = số máy chủ trả về, từng chữ số.** `750.000đ` / `550.000đ` /
  `200.000đ` in trên màn khớp `spend_vnd` / `settled_vnd` / `outstanding_vnd` của
  `GET /people/{id}/finance`. Harness **không tự chia lại tiền** — nó lấy số nguyên
  của API, định dạng đúng một cách app định dạng, rồi tìm chuỗi đó.
- **Client không làm toán tiền.** `tai-chinh.ts` không có `Number(text)`, không phép
  chia; chỉ nhóm chữ số và dấu `+`/`-`. Kiểm bằng grep, không bằng lời khai.
- **"Chia bill xong quay lại thì tổng đã đổi"** — chứng minh qua HTTP thật:
  Minh `600.000 → 750.000`, Trang `còn nợ 400.000 → 550.000`.
- **`settled + outstanding == spend`** đúng cho cả hai người, trên dây lẫn trên màn.
- **Không rò rỉ**: màn của Minh không in `837.003đ` hay `287.003đ` — hai số chỉ
  Trang mới có, cố tình tạo bằng một khoản chi lẻ chỉ Trang tham gia.
- **0 lỗi console / pageerror.**
- Màn tự nói đúng phạm vi: *"Hai số đầu đọc từ sổ. Kỷ niệm và đánh giá chưa có trong
  sản phẩm nên để trống."*

## 5. Một phát hiện giả tôi tự tạo ra rồi tự gỡ

Lượt đầu, phép kiểm rò rỉ đỏ ở `550.000đ`. Không phải rò rỉ: đó là *đã thanh toán
của chính Minh*, trùng số với *khoản nợ của Trang*, thuần tuý trùng hợp số học. Đã
sửa thành chỉ đối chiếu số **chỉ Trang mới có**, và khi không tồn tại số như vậy thì
in `skip` chứ không in `ok` — một ô chưa quét phải trông như chưa quét. Ghi lại vì
rd-qa-06 dính đúng loại này (bắt nhầm footer làm ô QR).

## 6. Ô CHƯA quét

- **Mã QR quét bằng app ngân hàng thật** — vẫn mở, chỉ leader đóng được (ADR-0010 §8).
- Màn Cá nhân trên **thiết bị thật**; đây là Chromium 390×844.
- Trình đọc màn hình thật (VoiceOver / TalkBack).
- WCAG 2.4.11, 2.5.7, 2.5.8 — axe không có rule tự động hoặc chỉ phủ một phần.
- Danh sách `movements` **rỗng** trong lượt đo này, nên phần giao dịch của màn chưa
  được đo khi có dữ liệu.
- Chế độ tối, khung 320px, cỡ chữ 200%.
- Bộ lỗi axe **không hoàn toàn tất định** — lỗi thứ hai đổi giữa
  `scrollable-region-focusable` và `aria-prohibited-attr` tuỳ thời điểm chụp.

## 7. Bằng chứng chạy lại được

```bash
docker compose up -d postgres
python3 tests/qa/rd-qa-07/03-mutation-gate.py    # exit 1, 3 survivor
```

Đầy đủ lệnh cho hai script trình duyệt nằm trong `tests/qa/rd-qa-07/README.md`.
