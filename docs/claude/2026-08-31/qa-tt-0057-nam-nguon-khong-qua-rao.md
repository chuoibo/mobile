# PASS — #450 chặn cả 5 nguồn không qua rào, kể cả phép cộng ở `bill.py:104`

- **protocol_version**: v1
- **verdict**: `PASS` (bổ sung cho phán quyết #461 đã merge, trả lời câu 2 phiên bản mới)
- **đo tại**: `875d507` trên nhánh `qa/tt-0057-nam-nguon-khong-qua-rao`, cắt từ `origin/main@fee2d73`
- **sha này**: nhánh chưa merge, nhưng **mọi code sản phẩm được đo đều ĐÃ ở main** —
  nhánh chỉ thêm một file probe, không sửa một dòng `app/` nào.
- **nền đối chứng**: `b632d53` (cha của `f9a3b68`, tức main ngay TRƯỚC #450)
- **blocker còn mở**: không

## Lý do (đọc dòng này là đủ)

Lead hỏi: *"#450 có chặn được cả 5 nguồn không qua rào không? Đặc biệt phép cộng ở
`bill.py:104` — cộng int với float ra float, và nó không ở trong bất kỳ model nào."*

**Có, cả 5 nguồn, 21/21 ô.** Và phép cộng ở `bill.py:104` hoá ra là chỗ **nguy hiểm hơn**
Lead lo: với `float` nó giữ lại dấu vết (int + float → float), nhưng với `bool` nó **XOÁ
SẠCH dấu vết** — `True + 70_000 = 70_001`, một số **int hoàn toàn sạch**. Một cổng chỉ
kiểm tổng đã cộng xong sẽ mù hoàn toàn ở đúng ca đó. #450 kiểm **từng slot một**, nên nó
bắt ở slot món ăn chứ không cần nhìn vào tổng.

## Đo cái gì, đo thế nào

`POST /bills/{id}/split` không có trường tiền nào trong thân request (#460). Nên probe
không đi qua HTTP — nó đi đúng con đường mà tiền thật đi:

```
bản ghi bill đã lưu → allocator_input_from_bill()  (app/domain/bill.py)
                    → allocate()                    (app/domain/allocator.py)
```

Fixture là bữa ăn hai người lấy nguyên từ `tests/domain/test_bill_projection.py`
(65.000 + 70.000). Ma trận: **5 slot × 4 hình dạng + 1 ca giặt tiền = 21 ô**.

Năm slot đúng theo phân loại của #460:

| # | nguồn | gốc |
|---|---|---|
| 1 | `item.amount_vnd` | DB_RECORD |
| 2 | `surcharge.amount_vnd` | DB_RECORD |
| 3 | `discount.amount_vnd` | DB_RECORD |
| 4 | `printed_total_vnd` | DB_RECORD |
| 5 | tổng tự cộng ở `bill.py:104` | COMPUTED |

Bốn hình dạng: `float` lẻ · `float` `.0` · `True` · `False`. Ô `float .0` có mặt riêng vì
nó **đúng về giá trị** — một cổng so giá trị thay vì so hình dạng sẽ cho nó đi qua.

Probe: `services/api/tests/qa/qa-tt-0057-gac-450/probe_nam_nguon_khong_qua_rao.py`

Bốn phán quyết mỗi ô: `BLOCKED` (AMOUNT_NOT_INTEGER) · `OTHER_CODE` (từ chối đúng, lý do
sai) · `CRASH` (lỗi không phải AllocationError thoát ra → 500, vi phạm ADR-0004 7.2
property 10) · `WRONG` (`allocate()` trả kết quả dựng từ số không nguyên).

## Kết quả — đối chứng TRƯỚC/SAU trên hai cây thật

`bill.py` **y hệt từng byte** giữa `b632d53` và main (`git diff` rỗng), nên toàn bộ chênh
lệch dưới đây đến từ đúng thay đổi của #450 ở `allocator.py` (+38/−8). `money.py` cũng
không đổi — `vnd_violation` đã có sẵn từ trước, #450 là lần đầu allocator **gọi** nó.

| cây | BLOCKED | OTHER_CODE | WRONG | CRASH | exit |
|---|---|---|---|---|---|
| `b632d53` — main TRƯỚC #450 | **0** | 7 | **5** | **9** | 2 |
| `fee2d73` — main SAU #450 | **21** | 0 | **0** | **0** | 0 |

Nền đối chứng được xác minh là nền thật, không phải bản sao: `grep -c AMOUNT_NOT_INTEGER`
trên `allocator.py` ở `b632d53` ra **0**. Probe chạy ở hai cây là **cùng một file**
(`md5 = 6b7280e9…`).

Đối chứng dương chạy trước mọi ô: bill sạch → `{'an': 65000, 'binh': 70000}`. Không có
dòng này thì một bảng toàn "từ chối" không phân biệt được với một lần import chết.

Bốn ca `WRONG` ở nền là **tiền sai im lặng**, không phải lỗi:

```
item.amount_vnd = True       -> {'an': 1,     'binh': 70000}   món 65.000₫ tính 1₫
surcharge = True             -> {'an': 65000, 'binh': 70001}
discount  = True             -> {'an': 65000, 'binh': 69999}
```

Chín ca `CRASH` là `TypeError: slice indices must be integers` thoát ra ngoài
`AllocationError` — tức 500 chứ không phải 422.

## Ca quyết định: phép cộng ở `bill.py:104` GIẶT SẠCH bằng chứng

Đây là phần trả lời thẳng câu Lead hỏi.

```
items = [ {amount_vnd: True}, {amount_vnd: 70_000} ]   # printed_total_vnd = None
tổng sau phép cộng ở dòng 104:  70001  (kiểu int)  <- SẠCH, không còn vết bool
```

Với `float`, phép cộng **giữ** dấu vết (`135000.5`, `135000.0` — vẫn là float). Với
`bool`, phép cộng **huỷ** dấu vết: `True + 70_000` ra `70001`, một `int` không có gì đáng
ngờ. Nên `bill.py:104` không chỉ *truyền* lỗi đi — ở ca bool nó *xoá bằng chứng*.

Chứng minh điều đó là load-bearing bằng đột biến, không bằng lập luận:

| đột biến trên main | BLOCKED | OTHER_CODE | WRONG |
|---|---|---|---|
| **B — chỉ kiểm slot `total`**, bỏ kiểm từng slot | 12 | 4 | **5** |
| **A — bỏ vế `bool` khỏi `_not_an_integer`** | 10 | 6 | **5** |
| (không đột biến) | **21** | 0 | **0** |

Đột biến B là phép đo quan trọng nhất trong báo cáo này: một cổng chỉ nhìn tổng đã cộng
xong **trả lại đúng 5 ô tiền sai**, gồm cả ca giặt tiền —
`{'an': 1, 'binh': 70000}` với tổng `70001` sạch sẽ. Việc #450 kiểm **từng slot** chứ
không chỉ kiểm tổng chính là thứ đóng đường `bill.py:104`.

Đột biến A cho thấy cổng phân biệt được "quên bool" với "quên hẳn" — nó không xanh vì một
lý do rẻ tiền nào đó.

Cả hai đột biến đã hoàn nguyên; cây sạch chạy lại ra 21 BLOCKED.

## Vì sao `allocate()` là lớp DUY NHẤT trên đường này

Ở `service.py`, `split_bill` trả `total_amount_vnd` **sau** khi `allocate()` đã qua:
`allocate()` ném thì không con số nào rời khỏi hàm. Nên với 5 nguồn này, allocator không
phải "lớp thứ hai chồng lên rào" — nó là lớp **duy nhất** chúng gặp.

Điều đó khép lại câu 2 nguyên bản của Lead: **KHÔNG**, #450 không phải lớp thừa cho một
cửa đã an toàn.

## Ô CHƯA QUÉT — đọc phần này trước khi dùng chữ PASS

1. **Đường ĐỌC bill chưa đo.** Bốn route trả `BillResponse` (`POST /bills`,
   `GET /bills/{id}`, `PUT .../assignments`, `POST .../my-items`) **không đi qua
   `allocate()`**. Tôi *đọc* thấy các trường tiền của chúng khai `PositiveMoneyVnd` /
   `NonNegativeMoneyVnd` (strict), nên response validation của FastAPI nhiều khả năng
   chặn — **nhưng tôi ĐỌC chứ chưa ĐO**, và đọc nguồn không phải đo hành vi. Không thuộc
   phạm vi #450; nêu ra để không ai đọc "5/5 bị chặn" thành "mọi đường bill đã được gác".
2. **#450 không sửa đường GHI.** Phát hiện của #460 vẫn nguyên: Postgres **làm tròn im
   lặng** thay vì từ chối float khi ghi (`1500.5 → 1500`). #450 đổi hậu quả từ *tiền sai
   im lặng* thành *422 ồn ào lúc chia*, nó không ngăn bản ghi hỏng ra đời.
3. **Chưa đo trên PostgreSQL thật cho đúng ma trận này** — probe chạy ở tầng domain. Tầng
   `tests/postgres` xanh 523/523 nhưng không chứa ma trận 21 ô này.
4. Mã VietQR **vẫn chưa được quét bằng app ngân hàng thật** (ADR-0010 mục 8).

## Cổng đã chạy (cây sạch, `git status` rỗng)

```
python3 -m pytest services/api/tests tests -q
    -> 2833 passed, 580 skipped, 5272 subtests passed (345.33s)

# đóng skip thay vì giải thích skip:
MOBILE_TEST_DATABASE_URL=... MOBILE_REQUIRE_POSTGRES_TESTS=1 \
  python3 -m pytest services/api/tests tests -q
    -> 3373 passed, 40 skipped, 5272 subtests passed (366.90s)
       540 skip đã đóng; 40 còn lại là tầng Gemini live (cần GEMINI_API_KEY)

cd services/api && MOBILE_REQUIRE_POSTGRES_TESTS=1 pytest tests/postgres -q
    -> 523 passed, 0 skipped (86.96s)

cd apps/mobile && npm test
    -> 1008 tests, 1007 pass, 1 fail   <- xem ghi chú dưới
cd apps/mobile && node --test tests/stacked-branch.test.mjs
    -> 4 tests, 4 pass (trên nhánh này)

probe (main)      -> 21 BLOCKED, exit 0
probe (b632d53)   -> 9 CRASH · 5 WRONG · 7 OTHER_CODE, exit 2
```

**Về 1 ca đỏ của `npm test`:** nó đỏ trên nhánh *cũ* `qa/tt-0057-gac450-v4`, và đỏ vì
**hình dạng nhánh**, không vì sản phẩm — `stacked-branch.test.mjs` phát hiện nhánh đó
*merge* `origin/main` vào thay vì cắt lại từ nó, sau khi PR #461 của chính tôi đã được
merge. Sửa bằng cách cắt nhánh mới từ `origin/main` (không force-push, đúng luật đội).
Trên nhánh này ca đó **xanh**.

## Kỹ năng đã dùng

`bug-reproduction` — đối chứng đỏ-trước/xanh-sau trên hai cây thật, nền được xác minh là
nền thật, probe cùng md5, đối chứng dương chạy trước, và revert-to-verify bằng hai đột
biến. `e2e-testing` — chặng 2 (cổng rẻ), chặng 3 (`MOBILE_REQUIRE_POSTGRES_TESTS=1`,
0 skipped), chặng 6 (đâm vào chỗ test hiện có không chạm), chặng 7 (ô chưa quét ở trên).
