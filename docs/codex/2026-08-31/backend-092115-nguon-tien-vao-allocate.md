# Một số tiền vào `allocate()` đến từ 9 nguồn; 5 trong đó không đi qua `MoneyVnd`

- task_id: `backend-092115` (hậu tố `22643301`)
- protocol_version: v1
- đo tại: `cf16166` — **sha này ĐÃ ở main** (`origin/main` lúc bắt việc)
- nhánh báo cáo: `backend/nguon-tien-vao-allocate`, mọc thẳng từ `cf16166`
- không sửa một dòng nào trong `services/api/app/`. Đây là việc đo, không phải việc vá.

## Câu hỏi

qa2 ở #452 đã hỏi từ phía ngoài vào: rào `MoneyVnd` dày mấy lớp, và đi vòng được không
(`model_construct` đi vòng được). Đây là câu hỏi ngược lại, từ phía máy chủ: **một giá
trị tiền đi vào `allocate()` có thể đến từ bao nhiêu NGUỒN, và nguồn nào không đi qua
`MoneyVnd`?**

Trục call site đã đếm rồi và ra **3** (`service.py:3624`, `:3636`, `:3754`). Nguồn là
trục khác: call site là nơi allocator được GỌI, nguồn là nơi một số tiền được TẠO RA.
Một call site đứng trên nhiều nguồn, và hai call site dùng chung một nguồn.

## Đơn vị đếm, và vì sao người đi chép không đổi được nó

Bài học của chính tôi ở #437 là con số chỉ hội tụ khi đếm bằng thứ code không đổi được.
Ở đây đơn vị là:

> **một nguồn = một cặp (ô tiền, biểu thức sinh ra giá trị), trong đó ô tiền được đọc
> ra từ chính các phép subscript của `allocator.py`.**

Ba cái neo, mỗi cái suy ra từ cái trước, không cái nào viết tay:

1. **Ô tiền** = mọi khoá hằng chuỗi kết thúc `_vnd` mà `allocator.py` TỰ subscript
   → `{total_vnd, amount_vnd}`. Người chép allocator không đổi được khoá này mà vẫn
   được allocator đọc.
2. **Producer** = mọi dict literal trong `app/` buộc một trong các khoá đó, nằm trong
   hàm tới được `allocate` (đồ thị gọi hàm dựng bằng AST). Thêm producer thứ mười thì
   danh sách tự dài ra.
3. **Rào** = mọi `X = Annotated[int, Field(strict=True, ...)]` ở mức module trong
   `schemas.py`, nhận diện theo HÌNH DẠNG chứ không theo tên. Bí danh thứ tư thêm vào
   ngày mai được đếm mà không phải sửa máy quét.

Máy quét: `services/api/tests/qa/backend-092115-nguon-tien-vao-allocate/dan_xuat_nguon.py`.
Nó `exit 1` khi tập ô tiền rỗng, khi không thấy `allocate(` nào, hoặc khi gặp một hình
dạng nó chưa biết. **Một danh sách rỗng làm nó ĐỎ**, không im lặng in "0 nguồn".

## Kết quả: 9 nguồn

| ô tiền | gốc | ở đâu | biểu thức | rào |
|---|---|---|---|---|
| `total_vnd` | PYDANTIC | `app/api/service.py:489` | `proposal.total_amount_vnd` | `MoneyVnd` |
| `amount_vnd` | PYDANTIC | `app/api/service.py:493` | `item.amount_vnd` | `MoneyVnd` |
| `amount_vnd` | PYDANTIC | `app/api/service.py:502` | `surcharge.amount_vnd` | `MoneyVnd` |
| `amount_vnd` | PYDANTIC | `app/api/service.py:510` | `discount.amount_vnd` | `MoneyVnd` |
| `total_vnd` | DB_RECORD | `app/api/service.py:3573` | `record.printed_total_vnd` | **không có** |
| `amount_vnd` | DB_RECORD | `app/api/service.py:3577` | `item.line_total_vnd` | **không có** |
| `amount_vnd` | DB_RECORD | `app/api/service.py:3592` | `surcharge.amount_vnd` | **không có** |
| `amount_vnd` | DB_RECORD | `app/api/service.py:3600` | `discount.amount_vnd` | **không có** |
| `total_vnd` | COMPUTED | `app/domain/bill.py:104` | `sum(items) + sum(surcharges) - sum(discounts)` | **không có** |

**9 nguồn · 4 qua rào strict · 5 không.**

Bốn nguồn `DB_RECORD` không có rào vì `BillRecord`/`BillItemRecord`/… là
`@dataclass(frozen=True)` — dataclass không kiểm gì khi đọc. Nguồn `COMPUTED` không có
rào vì nó là một phép cộng: nó không có annotation nào để mà kiểm, kiểu của nó là kiểu
của các số hạng.

## Hai trục lệch ở đâu, và chỗ lệch nói gì

Lấy hợp hai danh sách rồi đi từng mục, đúng cách anh dặn ở 06:22:

| call site | nguồn nó đứng lên | nhận xét |
|---|---|---|
| `propose_expense` @3636 | A1–A4 | |
| `confirm_expense` @3754 | A1–A4 — **trùng hệt** | trục call site đếm 2, đây là 1 tập nguồn |
| `split_bill` @3624 | 4 × DB_RECORD + 1 × COMPUTED | trục call site đếm 1, thật ra là 5 |

Không có mục nào ở danh sách call site mà không có nguồn. Nhưng chiều ngược lại thì
lệch nặng, và **chỗ lệch chính là chỗ chưa ai nhìn**:

> `POST /bills/{id}/split` — thân request của nó là `BillSplitRequest`, gồm đúng
> `for_ledger` và `paid_by_id`. **Không có một trường tiền nào.** Toàn bộ tiền mà
> `split_bill` chia đến từ database. Rào `MoneyVnd` che đường đó có thật, nhưng nó nằm
> ở một endpoint KHÁC (`POST /bills`, `PositiveMoneyVnd`), trong một request KHÁC, ở một
> thời điểm sớm hơn.

Trục call site không thể thấy điều đó: nó đếm ba chỗ trông giống nhau và được bảo vệ như
nhau. Trục nguồn cho thấy một trong ba chỗ được bảo vệ bởi quá khứ.

## Chạy thật: cái gì thực sự chặn đường DB

Probe: `services/api/tests/qa/backend-092115-nguon-tien-vao-allocate/probe_nguon_tien.py`,
chạy trên **PostgreSQL 16 thật** (schema riêng, alembic tới head, drop sau khi xong).
Chặng HTTP cố ý KHÔNG đo lại — qa2 đã đi 5/5 đường đó ở #452 và không đường nào lọt;
đo lại không mua thêm gì.

Mô phỏng một người ghi bill **không** qua `POST /bills` (seed, script sửa dữ liệu, một
route mới mai mốt):

```
-- line_total_vnd = 1500.5 (float)
   GHI ĐƯỢC. Đọc lại: items=[('i1', 1500, 'int'), ...]
-- line_total_vnd = True (bool)
   GHI BỊ TỪ CHỐI: (psycopg.errors.CannotCoerce) cannot cast type boolean to bigint
-- printed_total_vnd = 135000.7 (float)
   GHI ĐƯỢC. Đọc lại: printed_total_vnd=135001
```

**Postgres không từ chối float. Nó LÀM TRÒN, im lặng.** Và bỏ tổng in đi để không còn
`RECONCILIATION_MISMATCH` che nữa thì phép làm tròn đi thẳng vào tiền người ta trả:

```
   ghi   : [('i1', 1500.5), ('i2', 1501.5)]
   đọc lại: [('i1', 1500), ('i2', 1502)]
   allocate() -> ok: {An: 1500, Bình: 1502}
```

1500.5 → 1500 còn 1501.5 → 1502: **làm tròn nửa về chẵn**, không phải làm tròn lên.
Không lỗi, không cảnh báo, không mã trả về. Luật 1 ("không float, kể cả ở giá trị trung
gian") ở nguồn này được cưỡng chế bằng đúng cái nó sinh ra để cấm.

Cùng phép ghi đó qua fake repository của `tests/api`:

```
   FakeRepository.create_bill có kiểm kiểu không? -> KHÔNG — lưu nguyên xi
   Ghi 1500.5 / 135000.7 -> đọc lại 1500.5 / 135000.7
```

Hai tầng trả **hai số khác nhau** cho cùng một phép ghi. Một ca xanh ở tầng fake không
nói gì về tầng Postgres, và ngược lại.

Nguồn COMPUTED, chạy thẳng `allocator_input_from_bill` + `allocate` (tại `cf16166`):

```
-- một dòng là float →  total_vnd = 135000.5  →  allocate() crash: TypeError (tức 500)
-- một dòng là bool  →  total_vnd = 70001     →  allocate() ok: {an: 1, binh: 70000}
```

`True` thành **1 đồng**, im lặng, đi qua đường tổng-tự-cộng. Đó chính là lỗi #450 đang
chờ qa gác, và số đo này cho thấy nó tới được allocator từ nguồn COMPUTED chứ không chỉ
từ đường HTTP.

## Nguồn thứ tư anh hỏi: giá trị mặc định trong schema

Đo bằng thực nghiệm, không bằng lời:

```
   Thu().x  (dùng mặc định) = 0.5 (float)
   Thu(x=0.5) (gửi vào)     = TỪ CHỐI (ValidationError)
```

Cùng một annotation `MoneyVnd`: **từ chối khi được gửi, nhận khi là mặc định.** pydantic 2
không kiểm default trừ khi `validate_default=True`.

Hôm nay `schemas.py` có **3** trường tiền mang giá trị mặc định — `ReceiptItem.unit_price_vnd`,
`ReceiptScanResponse.total_vnd`, `ReceiptScanResponse.total_difference_vnd`, cả ba đều
`= None` và **không** cái nào nằm trên đường tới `allocate()`. Nên đây là **lỗ ngủ**: chưa
mở, và ngày ai đó đặt một mặc định là số trên đường tiền thì không cổng nào kêu.

## Cái này chứng minh gì, và KHÔNG chứng minh gì

Chứng minh:
- Đúng 9 nguồn, suy ra tự động; 5 nguồn không có rào của riêng mình.
- Postgres làm tròn float thay vì từ chối, và làm tròn nửa-về-chẵn.
- Fake và Postgres bất đồng về cùng một phép ghi.
- pydantic không kiểm giá trị mặc định.

KHÔNG chứng minh:
- **Đây không phải một lỗ đang mở.** Hôm nay `Bill`/`BillItem`/`BillSurcharge`/`BillDiscount`
  chỉ có **một** chỗ ghi trong `app/` (`SqlAlchemyApiRepository.create_bill`, chỉ được gọi
  từ `ApiService.create_bill`), và chỗ đó nằm sau `BillCreateRequest` strict. Không có
  đường HTTP nào hôm nay đưa float vào bảng bill.
- Nó cũng không chứng minh cây nào khác ngoài `cf16166`, và không chứng minh gì về #450
  (nhánh khác, chưa merge).

Điều nó nói là một tính chất cấu trúc: **bốn nguồn DB không kế thừa rào nào từ chỗ đọc.**
Người viết chỗ ghi thứ hai — một seed, một script sửa dữ liệu, một route mới — không có
gì nhắc, và thứ bắt lỗi hộ họ sẽ là một phép làm tròn im lặng.

## Đã chạy

```
cd services/api && python3 tests/qa/.../dan_xuat_nguon.py        → exit 0, 9 nguồn
cd services/api && MOBILE_TEST_DATABASE_URL=... python3 .../probe_nguon_tien.py → exit 0
$(scripts/ruff_pinned.sh) check  <2 file mới>                    → All checks passed
$(scripts/ruff_pinned.sh) format <2 file mới>                    → 2 files reformatted
python3 -m pytest services/api/tests tests -q
    → 2798 passed, 581 skipped, 5049 subtests passed (407.95s), exit 0
```

Đột biến trên chính máy quét (chạy rồi hoàn nguyên bằng `git checkout --`):

| đột biến | nền | sau |
|---|---|---|
| xoá ô `amount_vnd` của item trong `_allocator_input` | 9 nguồn | **8 nguồn** |
| `ExpenseItemInput.amount_vnd`: `MoneyVnd` → `int` trần | 4 qua rào | **3 qua rào** |
| `allocator.py` đọc `expense["tong_dong"]` thay vì `["total_vnd"]` | 9 nguồn | **6 nguồn** |

Và một lần đỏ **không dàn dựng**: lượt chạy đầu tiên gặp `item["amount_vnd"]` ở
`bill.py:121`, không phân loại được, in `UNRESOLVED` và `exit 1` — đúng như thiết kế.
Dạy nó hình dạng đó xong, con số đứng ở 9 và relay được gộp chứ không đếm hai lần.
