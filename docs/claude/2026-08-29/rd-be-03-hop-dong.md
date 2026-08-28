# Hợp đồng rd-be-03 — món ăn, gán người, nối vào allocator đã có

Nhánh: `backend/rd-be-03-mon-an-gan-nguoi` (đã tạo, dựng từ `origin/main`).
Thư mục gốc repo: `/home/lakiet/agent-harness/wt/backend`
Thư mục API: `/home/lakiet/agent-harness/wt/backend/services/api`

## Mục tiêu

Nối kết quả đọc bill (`POST /receipts/scan`, đã có, trả về `app/domain/receipt.py::read_receipt`)
vào phép chia tiền đã đúng (`app/domain/allocator.py`, ADR-0004, đóng băng).

**TUYỆT ĐỐI KHÔNG viết phép chia thứ hai.** Không tính share, không chia, không làm tròn
ở bất kỳ chỗ nào mới. Mọi phép chia đi qua `allocate()`.

## Luật không được vi phạm

1. Số nguyên đồng. Không `float`, không `Decimal`, không `Fraction` ở code mới.
2. `Σ` phân bổ `=` đúng tổng khoản chi. Do allocator giữ, không do code mới giữ.
3. Số dư tính lại được từ sổ.
4. `app/domain/` thuần: không import `app.db`, `app.api`, `app.payments`,
   `sqlalchemy`, `fastapi`, `alembic`, `pydantic`.
5. Gán do AI gợi ý là **GỢI Ý**, không phải sự thật. Chỉ khi người dùng xác nhận
   mới được phép đi vào sổ.

## PHẦN 1 — `app/domain/bill.py` (module thuần, TẠO MỚI)

Hợp đồng đã ĐÓNG BĂNG bởi file test đã có sẵn trên nhánh:
`services/api/tests/domain/test_bill_projection.py`

ĐỌC FILE ĐÓ TRƯỚC. Nó là hợp đồng. Hiện thực phải làm nó xanh **không được sửa nó**.

Tóm tắt API bắt buộc:

```python
SHARE_SUGGESTED = "ai_suggested"
SHARE_CONFIRMED = "confirmed"

class BillError(Exception):
    def __init__(self, code: str): ...   # có thuộc tính .code

def allocator_input_from_bill(bill: dict) -> dict: ...
```

Input `bill`:

```python
{
  "participants": ["an", "binh"],           # id người, chuỗi
  "printed_total_vnd": 135000 | None,       # tổng IN TRÊN GIẤY; None = chưa đọc được
  "items": [
    {"item_key": "i1", "amount_vnd": 65000,
     "shares": [{"participant_id": "an", "source": "confirmed"}]},
  ],
  "surcharges": [ ... đúng shape ADR-0004 ... ],   # truyền thẳng, không đụng
  "discounts":  [ ... đúng shape ADR-0004 ... ],   # truyền thẳng, không đụng
  "advancer_id": "an" | None,
}
```

Output:

```python
{
  "expense": { ... input allocator đúng ADR-0004 ... },
  "assignment_state": "confirmed" | "ai_suggested",
  "suggested_item_keys": ["i2", ...],   # THỨ TỰ BYTE UTF-8, không phải thứ tự input
}
```

Quy tắc:

- `items[*].shares` → `shared_by` (danh sách `participant_id`, giữ nguyên thứ tự trong `shares`).
- `item_key` → `item_id`. `amount_vnd` giữ nguyên.
- `total_vnd` = `printed_total_vnd` nếu khác `None`; ngược lại
  `Σ items.amount_vnd + Σ surcharges.amount_vnd − Σ discounts.amount_vnd`.
  Đây là phép **cộng các số đã liệt kê**, không phải phép chia — được phép.
- `assignment_state` = `"confirmed"` KHI VÀ CHỈ KHI mọi share của mọi item là `confirmed`;
  ngược lại `"ai_suggested"`.
- `suggested_item_keys` = các `item_key` có ít nhất một share `ai_suggested`, sắp theo byte UTF-8.
- Lỗi `BillError`, thứ tự kiểm: `BILL_HAS_NO_ITEMS` → `ITEM_HAS_NO_ASSIGNEE` → `INVALID_SHARE_SOURCE`.
  - `items` rỗng → `BILL_HAS_NO_ITEMS`. (KHÔNG lui về EVEN_SPLIT — bill không đọc được món
    nghĩa là đọc hỏng, chia đều là nguỵ trang cái hỏng thành câu trả lời.)
  - item có `shares` rỗng → `ITEM_HAS_NO_ASSIGNEE`. (KHÔNG mặc định "chia cho tất cả" —
    đó là tự bịa nghĩa vụ tiền, ADR-0004 quyết định 4.)
  - `source` ngoài hai giá trị → `INVALID_SHARE_SOURCE`. Fail closed.
- **KHÔNG validate lại tham chiếu.** Người lạ trong `shares` để `allocate()` ném
  `UNKNOWN_PARTICIPANT`. Hai tầng validate là hai chỗ để bất đồng mã lỗi (ADR-0004 V2-02).
- **KHÔNG import allocator** trong module này. Service gọi allocator.
- **KHÔNG có `/`, `//`, `Fraction`, `Decimal`, `float`, `round`** trong file. Có test AST kiểm.

Comment/docstring trong code viết TIẾNG ANH.

## PHẦN 2 — bảng dữ liệu (`app/db/models.py` + migration Alembic mới)

Ba bảng mới. Đặt cạnh các model hiện có, dùng đúng phong cách file đó
(`_enum_type`, `UUID(as_uuid=True)`, `BigInteger` cho tiền, `CheckConstraint`, `UniqueConstraint`).

### `bills`
Bản nháp một tờ bill đã chụp. **Chưa phải tiền trong sổ.**

- `id` UUID PK
- `context_id` UUID NOT NULL, index — nhóm nào
- `created_by_id` UUID NOT NULL — ai chụp
- `printed_total_vnd` BigInteger NULL — tổng in trên giấy, `None` nếu không đọc được
- `items_total_vnd` BigInteger NOT NULL — tổng các dòng, do reader trả về
- `confidence` Integer NOT NULL — 0..100, từ `read_receipt`
- `needs_review` Boolean NOT NULL
- `created_at` timestamptz NOT NULL server_default now()
- CheckConstraint `confidence BETWEEN 0 AND 100`
- CheckConstraint `printed_total_vnd IS NULL OR printed_total_vnd >= 0`
- CheckConstraint `items_total_vnd >= 0`

### `bill_items`
- `id` UUID PK
- `bill_id` UUID FK → `bills.id` NOT NULL, index
- `item_key` String(64) NOT NULL — khoá ổn định trong phạm vi một bill
- `name` Text NOT NULL
- `quantity` Integer NOT NULL
- `unit_price_vnd` BigInteger NULL
- `line_total_vnd` BigInteger NOT NULL
- `position` Integer NOT NULL — giữ thứ tự đọc được trên giấy
- UniqueConstraint (`bill_id`, `item_key`)
- CheckConstraint `line_total_vnd > 0` (ADR-0004 từ chối dòng bằng 0)
- CheckConstraint `quantity > 0`

### `bill_item_shares`
- `id` UUID PK
- `bill_item_id` UUID FK → `bill_items.id` NOT NULL, index
- `participant_id` UUID NOT NULL
- `source` enum NOT NULL — `ai_suggested` | `confirmed`
  (dùng `StrEnum` + `_enum_type` như `MembershipRole` trên cùng file)
- `decided_by_id` UUID NULL — ai bấm xác nhận; NULL khi còn là gợi ý
- `decided_at` timestamptz NULL
- UniqueConstraint (`bill_item_id`, `participant_id`)
- CheckConstraint: `(source = 'confirmed' AND decided_by_id IS NOT NULL AND decided_at IS NOT NULL)
   OR (source = 'ai_suggested' AND decided_by_id IS NULL AND decided_at IS NULL)`
  — DB tự chứng minh "đã xác nhận" luôn có người chịu trách nhiệm. Đây là điều kiện
  nghiệm thu "gán do AI có cờ suggested, khác với đã xác nhận", cưỡng chế ở tầng DB
  chứ không chỉ ở tầng Python.

CẢNH BÁO đã từng làm hỏng việc trước trên repo này:
- `sa.Enum(native_enum=False, create_constraint=True)` **TỰ sinh** check constraint khi
  add_column. Đừng tạo thêm bằng tay → trùng tên → chết cả migration.
- Tên FK/constraint phải **≤ 63 ký tự**, Postgres cắt ngầm.
- Migration phải nối đúng `down_revision` vào head hiện tại. Kiểm tra bằng
  `alembic heads` trước khi viết.

## PHẦN 3 — repository

Thêm vào `ApiRepository` (Protocol) trong `app/api/repository.py`, hiện thực trong
`SqlAlchemyApiRepository` cùng file, và thêm vào fake repository ở `tests/api/conftest.py`.

```python
def create_bill(self, *, context_id, created_by_id, printed_total_vnd, items_total_vnd,
                confidence, needs_review, items, now) -> BillRecord: ...
    # items: list[{"item_key","name","quantity","unit_price_vnd","line_total_vnd",
    #              "position","suggested_participant_ids": [UUID,...]}]
    # mọi share tạo ra ở đây có source = ai_suggested, decided_by_id = None

def get_bill(self, bill_id) -> BillRecord | None: ...

def confirm_bill_assignments(self, *, bill_id, assignments, decided_by_id, now) -> BillRecord: ...
    # assignments: list[{"item_key": str, "participant_ids": [UUID,...]}]
    # THAY THẾ toàn bộ share của những item được nêu, source = confirmed,
    # decided_by_id/decided_at điền. Item không được nêu giữ nguyên.
    # item_key không tồn tại trong bill -> RepositoryConflict("UNKNOWN_BILL_ITEM")
```

`BillRecord` là dataclass (đặt cạnh các record dataclass khác trong file đó), mang đủ
để dựng input cho `allocator_input_from_bill`: `id, context_id, printed_total_vnd,
items_total_vnd, confidence, needs_review, created_by_id, created_at, items` với
`items` là list dataclass `BillItemRecord(item_key, name, quantity, unit_price_vnd,
line_total_vnd, position, shares)` và `shares` là list `BillShareRecord(participant_id,
source, decided_by_id, decided_at)`.

## PHẦN 4 — service + routes

`app/api/service.py`, thêm 3 method vào `ApiService`. `app/api/routes/bills.py` mới,
đăng ký router trong `app/api/main.py`. Schemas ở `app/api/schemas.py`.

### `POST /bills` → 201
Lưu một kết quả quét thành bản nháp, kèm gán do AI gợi ý.
Body: `context_id`, `printed_total_vnd` (nullable), `items_total_vnd`, `confidence`,
`needs_review`, `items[]` (mỗi item: `item_key`, `name`, `quantity`, `unit_price_vnd`
nullable, `line_total_vnd`, `suggested_participant_ids[]`).
Quyền: người gọi phải là thành viên `context_id` (dùng `_require_permission` với
capability đã có nếu hợp, nếu không có thì kiểm `identity.context_id in actor.context_ids`
theo đúng cách `confirm_expense` đang làm). Trả về `BillResponse` có cờ `source` từng share.

### `PUT /bills/{bill_id}/assignments` → 200
Người dùng xác nhận/sửa ai ăn món nào. Body: `assignments[]` như trên.
Mọi share bị thay thế có `source = confirmed`. Trả về `BillResponse` mới.

### `POST /bills/{bill_id}/split` → 200
Chiếu bill sang input allocator rồi **gọi `allocate()`**. Trả về:
`allocation` (đúng shape `AllocationProposal` đang dùng), `assignment_state`,
`suggested_item_keys`, và `total_amount_vnd`.
- `BillError` → 422 với `exc.code`.
- `AllocationError` → 422 với `exc.code` (giống `propose_expense` đang làm).
- `RECONCILIATION_MISMATCH` phải đi ra nguyên vẹn, KHÔNG được tự ép khớp.

`advancer_id` cho split: lấy từ body tuỳ chọn `paid_by_id`; nếu không có thì `None`.
`participants`: lấy từ `repository.list_members(context_id)` — những người đang là
thành viên active. Chuyển UUID → `str` như `_allocator_input` đang làm.

### Cổng vào sổ
`POST /bills/{bill_id}/split` chỉ là XEM TRƯỚC, không ghi sổ — đúng rồi, giữ vậy.
Điều kiện nghiệm thu "chỉ khi người dùng xác nhận mới ghi vào sổ" cần một cổng thật:
thêm vào `POST /bills/{bill_id}/split` một trường body `for_ledger: bool = False`.
Khi `for_ledger=True` mà `assignment_state != "confirmed"` → **422
`bill_assignments_not_confirmed`**. Đây là chỗ ranh giới gợi ý/đã-xác-nhận có hậu quả
thật, phải có test.

## PHẦN 5 — test (VIẾT TRƯỚC KHI HIỆN THỰC)

1. `tests/domain/test_bill_projection.py` — ĐÃ CÓ, đừng sửa, làm nó xanh.
2. `tests/api/test_bills.py` — tầng fake repo, tối thiểu:
   - `POST /bills` trả share có `source = ai_suggested`
   - `PUT .../assignments` đổi sang `confirmed` và điền `decided_by_id`
   - `POST .../split` khi còn gợi ý: trả allocation + `assignment_state = ai_suggested`
   - `POST .../split` với `for_ledger=True` khi còn gợi ý → 422 `bill_assignments_not_confirmed`
   - `POST .../split` với `for_ledger=True` sau khi đã xác nhận → 200
   - người ngoài nhóm gọi bất kỳ route nào → 403/404, không đọc được món của nhóm khác
   - bill lệch tổng (`printed_total_vnd` ≠ Σ dòng) → 422 `RECONCILIATION_MISMATCH`
3. `tests/postgres/test_bills_postgres.py` — ca LIVE trên PostgreSQL thật, tối thiểu:
   - tạo bill + item + share gợi ý, đọc lại bằng **connection/session khác**, cờ đúng
   - xác nhận gán rồi đọc lại: `source = confirmed`, `decided_by_id`/`decided_at` khác NULL
   - CheckConstraint chặn hàng bịa: INSERT thẳng `source='confirmed'` mà `decided_by_id IS NULL`
     phải bị DB từ chối (`IntegrityError`). Đây là ca chứng minh cờ được cưỡng chế ở DB.
   - UniqueConstraint chặn gán trùng người vào cùng một món
   - `confirm_bill_assignments` với `item_key` lạ → `RepositoryConflict`
   - đường đầy đủ: tạo bill → xác nhận → chiếu → `allocate()` → `Σ` đúng `printed_total_vnd`

   LƯU Ý: `tests/postgres` dùng CHUNG một schema cho cả phiên. Ca nào commit hàng mới
   có thể làm đỏ test đếm số hàng ở file khác. Đừng viết assert kiểu "bảng có đúng N hàng".

## Cổng phải xanh trước khi báo xong

```bash
cd /home/lakiet/agent-harness/wt/backend
python3 -m pytest services/api/tests tests -q

cd services/api
MOBILE_TEST_DATABASE_URL='postgresql+psycopg://mobile:mobile-dev-only@localhost:5432/mobile' \
  MOBILE_REQUIRE_POSTGRES_TESTS=1 python -m pytest tests/postgres -q

# migration biên dịch offline, không cần DB
cd services/api && python -c "
from alembic import command; from alembic.config import Config
c = Config('alembic.ini'); c.set_main_option('sqlalchemy.url','postgresql+psycopg://offline/offline')
command.upgrade(c,'head',sql=True)" >/dev/null && echo ok

ruff check <chỉ những file bạn sửa>
```

41 golden vector cũ (`tests/domain/test_allocator_golden.py`) phải vẫn xanh —
nếu chúng đỏ nghĩa là bạn đã đụng vào allocator, và đó là sai.

KHÔNG sửa `app/domain/allocator.py`, `app/domain/contract.py`,
`tests/domain/golden/*`, `phase0/`, `docs/protocol/v1/`.
