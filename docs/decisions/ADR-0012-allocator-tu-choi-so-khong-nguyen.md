# ADR-0012 — Allocator từ chối số không nguyên: thêm `AMOUNT_NOT_INTEGER`

- **Trạng thái:** 🟡 **BẢN THẢO** 2026-08-31 — chờ Lead duyệt tên mã và vị trí ưu tiên
- **Ngày:** 2026-08-31
- **DRI:** backend · **Reviewer:** Lead
- **Nguồn:** luật tiền số 1 (`CLAUDE.md`), ADR-0004 mục 6 và mục 7.2, phán quyết QA ở PR #445
- **Chặn:** không chặn ai; sửa một lỗ tiền đang sống trên `main`

## Bối cảnh — đo được, không phải suy đoán

Đo tại `origin/main@bf7cc78`, cây sạch, gọi thẳng `app.domain.allocator.allocate`:

| input | `main` trước bản vá |
|---|---|
| `total=300`, `item=300` | ✅ `{a: 150, b: 150}` (nền) |
| `total=300.5`, `item=300.5` | 💥 `TypeError: slice indices must be integers` |
| `total=301`, `item=300.5` | `AllocationError(RECONCILIATION_MISMATCH)` — đúng mã, **sai lý do** |
| `total=True`, `item=True` | ✅ `{a: 1, b: 0}` — **`True` thành 1 đồng, im lặng** |
| `total=300.0`, `item=300.0` | 💥 `TypeError` |

Hai kiểu hỏng khác nhau, cùng một gốc:

- **`TypeError` thoát ra ngoài** vi phạm ADR-0004 mục 7.2 property 10: `allocate`
  ném `AllocationError` với `code` thuộc danh sách đóng ở mục 6, không bao giờ ném
  lỗi Python trần. Gốc ở `allocator._apportion`, `ranked[:deficit]` khi `deficit`
  thành `float`.
- **`bool` thành tiền** vi phạm luật tiền số 1. Trong Python `isinstance(True, int)`
  là `True`, nên `True` trả lời `False` cho cả `< 0`, `== 0` **và**
  `> MAX_AMOUNT_VND` — đúng ba phép kiểm duy nhất mà `_validate_structure` chạy
  trên số tiền. Nó đi lọt cả ba rồi thành một đồng.

Gốc chung: **`allocator.py` chưa bao giờ kiểm *hình dạng* của con số.** Nó không gọi
`require_vnd`, không gọi `money.vnd_violation`, không có `isinstance` nào trên số
tiền. Module docstring của chính nó viết *"money is integer dong — no float
anywhere, not even in intermediates"*; câu đó không được cưỡng chế ở đâu cả.

### Vì sao hai cổng đã có trên `main` không thấy

Đây là phần đáng ghi lại, vì nó giải thích cách lỗ này sống sót qua hai lượt gác
tiền liên tiếp trong cùng một ngày:

- **#437 `test_one_money_check.py`** đếm **bản sao** của phép kiểm theo *hình dạng*
  (`isinstance(v, bool)` + `isinstance(v, int)` trên cùng `v`). Chỗ **không có phép
  kiểm nào** thì không có hình dạng để đếm. Cổng đếm 0 bản sao trong `allocator.py`
  và đó là con số đúng — chỉ là nó không trả lời câu đang cần hỏi.
- **#416** gác các slot tiền của `ledger.py`, đi bộ đối số của chính ledger. Nó
  không với tới `app/domain/allocator.py`.

QA đã ghi thẳng ở #445 rằng `allocator`, `bill`, `budget` là **ô CHƯA quét**. Đây
đúng là ô đó.

Câu hỏi hai cổng kia trả lời là *"phép kiểm có bị chép không?"*. Câu chưa ai hỏi là
*"có phép kiểm nào không?"*.

---

## Quyết định 1 — Thêm `AMOUNT_NOT_INTEGER` vào `ERROR_PRECEDENCE`

ADR-0004 mục 6 là **danh sách đóng**, và không có mã nào mang nghĩa "không phải số
nguyên". Không có mã sẵn nào dùng lại được cho trung thực:

- `NEGATIVE_AMOUNT` sai nghĩa — `0.5` không âm;
- `AMOUNT_TOO_LARGE` sai nghĩa;
- `RECONCILIATION_MISMATCH` là **đúng mã sai lý do**: nó gửi người đọc đi soi số học
  cộng trừ, trong khi vấn đề là kiểu dữ liệu. Đây là mã mà `main` đang trả cho ca
  `total=301, item=300.5`, và nó đã che lỗi thật.

Nên thêm một mã. Đây là **cộng thêm**, không sửa mã nào đang có.

## Quyết định 2 — Vị trí: nhóm 1, ngay TRƯỚC `NEGATIVE_AMOUNT`

```
INVALID_ENTITY_ID
DUPLICATE_ENTITY_ID
AMOUNT_NOT_INTEGER      ← thêm ở đây
NEGATIVE_AMOUNT
ZERO_AMOUNT
AMOUNT_TOO_LARGE
```

Lý do là ngữ nghĩa, không phải thẩm mỹ: **dấu và trần chỉ là câu hỏi có nghĩa trên
một giá trị đã là số nguyên đồng.** Hỏi "có âm không" về `True` cho ra câu trả lời
`False` đúng theo Python và vô nghĩa theo tiền. Đặt sau `NEGATIVE_AMOUNT` sẽ để
`True` tiếp tục đi lọt qua đúng ba phép so sánh đã cho nó đi lọt.

Đặt ở nhóm 1 cũng làm nó **thắng `RECONCILIATION_MISMATCH`** (nhóm 4). Điều đó cần
thiết: poison một `item.amount_vnd` làm sai **cả hai** thứ cùng lúc, và báo mismatch
là chỉ người đọc đi sai hướng.

## Quyết định 3 — Dùng lại `money.vnd_violation`, không viết phép kiểm mới

```python
for _, amount in amounts:
    if vnd_violation(amount) == NOT_INTEGER:
        raise AllocationError("AMOUNT_NOT_INTEGER")
```

Chỉ lấy **nửa hình dạng** của `vnd_violation`, không lấy phần dấu: allocator có luật
dấu riêng và khác ledger (`total_vnd = 0` **hợp lệ**, `item.amount_vnd = 0` là lỗi —
ADR-0004 ca 9). Viết lại `isinstance(...) or not isinstance(...)` tại chỗ là đúng
cách bản sao thứ 14 ra đời; #437 vừa gộp 13 bản sao xong.

## Quyết định 4 — 41 golden vector KHÔNG đổi

Cả 41 vector đều mang số tiền nguyên, nên **không vector nào tới được mã mới**. Đo
được: `test_allocator_golden.py` + `test_allocator_properties.py` +
`test_golden_selfcheck.py` + `test_selfcheck_catches_mutants.py` →
`33 passed, 4061 subtests passed`, bằng đúng nền trước bản vá.

Không thêm golden vector cho mã mới, có chủ ý: corpus 41 vector là oracle được tính
tay **trước** khi có allocator và không được để implementation ảnh hưởng. Ca lỗi mới
sống trong test riêng, sinh **từ** corpus chứ không thêm **vào** corpus.

---

## Cổng đi kèm — và đơn vị nó đếm

`tests/domain/test_allocator_rejects_non_integer_amounts.py`.

Danh sách slot tiền **không viết tay**. Nó suy ra từ chính 41 golden vector: mọi lá
trong `input` có khoá kết thúc bằng `_vnd`. Một trường tiền thứ năm không thể vào
hợp đồng allocator mà không có golden vector mang nó (ADR-0004 lấy corpus làm
oracle), nên danh sách tự lớn lên và cổng phủ trường mới ngay ngày nó được khai.

Đây là đơn vị mà hai lượt đếm trước trong repo này chỉ hội tụ về sau khi một danh
sách viết tay và một phép đếm theo tên export mỗi cái bỏ sót một thứ.

Số slot còn được suy ra **cách thứ hai, độc lập** cho từng vector —
`1 + len(items) + len(surcharges) + len(discounts)` — và hai phép suy ra phải khớp.
Máy đi bộ trả về rỗng trong im lặng là kiểu hỏng biến cổng thành đồ trang trí; hai
con số lệch nhau là thứ bắt được nó.

**Cổng này KHÔNG chứng minh:**

- Slot tiền không xuất hiện trong bất kỳ golden vector nào. Một trường khai mặc định
  `None` và vắng khỏi corpus thì máy đi bộ theo **giá trị** không thấy — đúng khoảng
  mù QA đo được ở cổng ledger (#445, đột biến D-B2). Phép đếm hai chiều ở trên giữ
  cho khoảng trống đó **nhìn thấy được**, chứ không đóng nó.
- Bất cứ điều gì về `app/api/` hay `app/db/`. Pydantic ở biên HTTP là biên khác, có
  test riêng. File này nói về việc tầng domain tự đứng được — tiền đề mà cả kiến
  trúc phân tầng dựa lên.

## Hệ quả

- `AllocationError.__init__` kiểm `code in ERROR_PRECEDENCE`, nên mã mới phải ở đó
  trước khi ném được. Đã đo: `ERROR_PRECEDENCE` chỉ bị đọc ở hai chỗ —
  `contract.py` (kiểm thành viên) và `test_allocator_properties.py:255`
  (`assertIn`). Thêm mã là cộng thêm, không phá cái nào.
- Caller nào đang bắt `TypeError` từ `allocate` sẽ không thấy nó nữa. Đo được: không
  có caller nào như thế.

## Cái ADR này KHÔNG quyết

`bill.py` và `budget.py` — hai ô còn lại QA ghi là chưa quét — **chưa đo lượt này**.
Không được đọc ADR này thành "tầng domain đã kín".
