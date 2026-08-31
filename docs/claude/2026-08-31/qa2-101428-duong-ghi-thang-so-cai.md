# Có đường nào ghi tiền xuống sổ cái mà không đi qua `allocate()` không?

- protocol_version: v1
- commit đo: `d1b485e` (origin/main sau khi #450 và #461 vào)
- verdict: **KHÔNG có hàng kẹt — nhưng lý do là kiểu cột, không phải rào nào ta chọn**
- blocker còn mở: không
- skill dùng: `database-testing`

## Câu hỏi

#450 đóng cửa `allocate()` với float/bool. `allocate()` gác phép CHIA, không gác
lệnh GHI. Kịch bản Lead muốn loại trừ tệ hơn "float đi lọt": một float **nằm sẵn**
trong sổ cái do seed / migration / bản vá dữ liệu / fixture đặt vào, rồi bốn nguồn
`DB_RECORD` (#460) đọc thẳng lên và đưa vào `allocate()` — lúc đó `allocate()` từ
chối, và ta có một hàng **không bao giờ chia được**.

## Trả lời ngắn

**Không xảy ra được.** Nhưng ba chi tiết dưới quan trọng hơn chữ "không".

## 1. Cả 24 ô tiền trong schema đã migrate đều là `bigint` — đo trên DB, không đọc model

```
money columns   : 24
distinct types  : ['bigint']
jsonb columns   : 2 -> ['audit_events.event_data', 'messages.card']
```

Không ô nào là `numeric`, `double precision`, hay nằm trong JSONB. Đó là lý do
cấu trúc khiến kịch bản hàng-kẹt không xảy ra: PostgreSQL ép kiểu ngay tại cột,
nên một float **không thể tồn tại** trong ô tiền để về sau bị `allocate()` từ chối.

Cái làm nên phòng thủ này là `bigint` — một tính chất **không ai chọn làm rào tiền**.

## 2. Nhưng đó là ÉP KIỂU, không phải TỪ CHỐI

Ghi thẳng qua ORM (đúng cửa mà seed / fixture / data migration dùng), rồi đọc lại:

```
float .5     sent 300.5    -> stored 300 (int)  <-- STORED NUMBER != SENT NUMBER
float .4     sent 300.4    -> stored 300 (int)  <-- STORED NUMBER != SENT NUMBER
float .0     sent 300.0    -> stored 300 (int)
bool True    sent True     -> REFUSED  CannotCoerce: cannot cast type boolean to bigint
int (base)   sent 300      -> stored 300 (int)          <- nền, PHẢI xanh
```

`300.5` thành **300**, không phải 301: `float8 -> bigint` làm tròn nửa-về-chẵn.
Nên số đã lưu khác số đã gửi, và không có một dòng log nào. `bool` thì bị DB từ
chối thật — lớp thứ hai cho đúng cái bug True-thành-1-đồng của #450, nhưng chỉ ở
đường GHI, không ở đường CHIA (nơi #450 tìm ra nó, trước khi chạm DB).

Hàng `int (base)` có mặt vì lượt đo đầu tiên của tôi cho ra "REFUSED" cho **cả
năm** ứng viên — vì thiếu `verification_scope`, không liên quan gì tới tiền. Một
bảng toàn đỏ không phân biệt được cái gì đang được gác.

Hậu quả sau khi đọc lại (PART 4): cả bốn giá trị đã lưu đều `SPLIT OK -> [150, 150]`.
**Không có hàng kẹt.**

## 3. Máy đếm nào chứng nhận điều 1? Có một — và nó mù 3 ô

`tests/db/test_migration_matches_models.py::test_no_money_column_uses_a_lossy_type`
duyệt `Base.metadata.tables`, tức là **các model ORM**, không phải database:

```
money columns the existing gate can iterate (Base.metadata): 21
money columns actually in the migrated schema             : 24
in the DB but INVISIBLE to the gate                       : 3
    collection_obligation_progress.amount_vnd
    collection_obligation_progress.confirmed_amount_vnd
    collection_obligation_progress.remaining_amount_vnd
```

Ba ô đó thuộc một **VIEW** do SQL thô trong `20260827_0001` tạo ra; `models.py`
không khai nó, nên vòng lặp của cổng không với tới. Hôm nay chúng là `bigint` nhờ
hai chỗ ép `::bigint` viết tay trong migration:

```sql
COALESCE(SUM(confirmation.amount_vnd), 0)::bigint AS confirmed_amount_vnd,
(obligation.amount_vnd - COALESCE(SUM(...), 0))::bigint AS remaining_amount_vnd,
```

Bỏ `::bigint` đi thì `SUM(bigint)` của PostgreSQL trả `numeric`, psycopg đưa về
`Decimal` — đúng thứ Luật 1 cấm — và **cổng vẫn xanh**, vì nó không nhìn thấy cột đó.

Cùng lỗ hổng đó áp cho JSONB: một số tiền đặt vào `event_data` hay `card` không có
kiểu cột nào cả. Đối chứng dương của phép đo này chính là chỗ ấy — ghi
`{"amount_vnd": 300.5}` vào `audit_events.event_data`, đọc lại vẫn là `300.5`
(`float`). Nên phép đo có thể *nhìn thấy* một float trong DB; "toàn int" ở PART 3
là kết quả, không phải máy quét hỏng.

Hôm nay chưa có tiền trong JSONB, và tôi đo chứ không tin docstring:

| chỗ | số đo |
|---|---|
| `AuditEvent(...)` trong `repository.py` | 7 chỗ, **0** khoá tên tiền vào `event_data` |
| chỗ đọc `event_data` ra | 4, chỉ lấy `obligation_id` và `reason` |
| tiền trong catalogue địa điểm (nguồn của `messages.card`) | 25 giá trị, **0** không phải int |

## 4. Điểm danh 39 cửa ghi tiền, theo từng loại Lead nêu tên

Máy đếm suy từ `models.py` (14 lớp mang tiền), quét 563 file Python cả cây:

```
TOTAL write sites found : 39
  test/fixture   15    app:api-layer  14    script/seed   5    other  4    migration  1
```

| cửa Lead nêu | số đo | kết luận |
|---|---|---|
| **seed** | `seed_demo_data.py` có 9 lệnh `.execute()`, **cả 9 là SELECT** (đếm bằng AST, không đọc docstring) | tiền vào qua HTTP → qua pydantic + `allocate()`. **Đóng.** |
| **migration** | 1 hit, và là **dương tính giả**: `c5f141903a2b` nhắc tên bảng `outings` nhưng ghi `memberships.origin` | **0 migration nào ghi tiền.** |
| **route ghi trực tiếp** | mọi trường tiền của bill/expense là `MoneyVnd = Annotated[int, Field(strict=True)]` | **Đóng** (và #460 đã đo strict bằng hành vi). |
| **bản vá dữ liệu** | xem mục 5 | **một phần MỞ.** |
| **fixture trên DB thật** | 15 chỗ trong `tests/postgres` + `tests/qa` dựng ORM có tiền, không qua pydantic hay `allocate()` | ghi được, nhưng `bigint` ép về int (mục 2). |

## 5. Bản vá dữ liệu: 9/14 bảng tiền có trigger append-only, 5 bảng thì không

```
  TRIGGER  collection_obligation_sources, collection_obligations,
           confirmed_allocations, expense_discounts, expense_items,
           expense_surcharges, expense_versions, payment_reports,
           receipt_confirmations
    none   bills, bill_items, bill_surcharges, bill_discounts, outings
```

Bắn thật, cả hai chiều, để "bị từ chối" không phải là phỏng đoán từ catalog:

```
UPDATE expense_versions.total_amount_vnd = 999.5  -> REJECTED  expense_versions is append-only
UPDATE expense_items.amount_vnd          = 999.5  -> REJECTED  expense_items is append-only
UPDATE bills.items_total_vnd             = 999.5  -> ACCEPTED, row now holds 1000 (int)   <- đối chứng ÂM
```

Không có dòng thứ ba thì hai dòng đầu không nói được là **trigger** từ chối hay
kết nối / schema / chính phép đo từ chối.

Năm bảng không trigger giữ tiền **bill đã quét** — đúng đoạn hero của PoC
(CHỤP BILL → AI đọc từng món). Một lệnh SQL chạy tay sửa được chúng, và làm tròn
im lặng (999.5 → 1000). Sổ cái thì không sửa được; bill thì được.

## Cái này KHÔNG chứng minh

- Không chứng minh không có ai từng chạy một `UPDATE` như vậy trên máy demo. Nó
  chỉ nói lệnh ấy sẽ đi lọt ở 5 bảng nào.
- Không chứng minh một float không thể tới `allocate()` **trong một request** —
  #450/#461 trả lời phần đó, phép đo này chỉ hỏi về cái **đã nằm trong DB**.
- Máy đếm 39 cửa suy từ `models.py`, nên nó mù đúng chỗ mục 3 nói: bảng/view do
  SQL thô trong migration tạo ra. `information_schema` ở PART 1 mới bắt được.

## Đề nghị (số liệu ở trên, quyết định là của Lead)

1. Cho `test_no_money_column_uses_a_lossy_type` đọc `information_schema` của một
   schema đã migrate thay vì `Base.metadata` — 3 ô nó đang không nhìn thấy sẽ vào
   tầm, và cả `numeric`/`double precision` do migration tạo về sau cũng vậy.
2. Thêm một câu khẳng định rằng **không ô tiền nào sống trong JSONB**. Hôm nay
   đúng (0/7 chỗ ghi audit, 25/25 giá trị catalogue là int), nhưng không gì giữ nó.
3. Bốn bảng bill không có trigger append-only là chủ ý hay bỏ sót — tôi không tự
   trả lời hộ. Nếu là chủ ý thì nên viết ra, vì "sổ cái bất biến" hiện dừng lại ở
   ranh giới bill/expense mà không chỗ nào nói.

## Tái lập

```bash
cd services/api
python3 tests/qa/qa2-101428-ghi-thang-so-cai/quet_cho_ghi_tien.py          # 39 cửa
MOBILE_TEST_DATABASE_URL='postgresql+psycopg://mobile:mobile-dev-only@localhost:5432/mobile' \
  python3 tests/qa/qa2-101428-ghi-thang-so-cai/probe_ghi_thang_so_cai.py   # exit 0
```

Probe tự tạo schema riêng, tự migrate, kiểm `current_schema()` khớp trước khi đo,
và drop schema ở `finally`. `occurred_at` cố định, không `datetime.now()`.
